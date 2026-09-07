import json
import logging
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.models import AudiomackStream, BoomplayStream, StreamingIngestionRun
from src.streaming_data.audiomack_boomplay.alerts import build_ingestion_alert, send_slack_alert
from src.streaming_data.audiomack_boomplay.config import StreamingConfig
from src.streaming_data.audiomack_boomplay.dates import dates_inclusive, expected_filename, latest_completed_week
from src.streaming_data.audiomack_boomplay.decryptor import decrypt_audiomack
from src.streaming_data.audiomack_boomplay.ftp_client import FTPSourceClient, MissingRemoteFile
from src.streaming_data.audiomack_boomplay.parsers import parse_audiomack, parse_boomplay


logger = logging.getLogger(__name__)
PLATFORMS = ("audiomack", "boomplay")


def _lock_key(platform: str, start: date) -> int:
    return int(start.strftime("%Y%m%d")) * 10 + PLATFORMS.index(platform)


def _try_lock(db: Session, platform: str, start: date) -> bool:
    if db.bind and db.bind.dialect.name == "postgresql":
        return bool(db.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": _lock_key(platform, start)}).scalar())
    return True


def _unlock(db: Session, platform: str, start: date) -> None:
    if db.bind and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _lock_key(platform, start)})


def _finish_run(db: Session, run: StreamingIngestionRun, status: str, missing: list[date], errors: list[str]) -> None:
    run.status = status
    run.missing_dates = json.dumps([item.isoformat() for item in missing])
    run.warning_count = len(missing)
    run.error_detail = json.dumps(errors) if errors else None
    run.completed_at = datetime.now(timezone.utc)
    db.commit()


def ingest_platform_period(
    db: Session,
    platform: str,
    start: date,
    end: date,
    trigger: str = "scheduled",
    config: StreamingConfig | None = None,
) -> dict:
    if platform not in PLATFORMS:
        raise ValueError(f"Unsupported platform: {platform}")
    if end < start:
        raise ValueError("end date must not be before start date")
    expected_file_count = (end - start).days + 1
    config = config or StreamingConfig()
    config.validate_ingestion()
    if not _try_lock(db, platform, start):
        raise RuntimeError(f"An ingestion is already running for {platform} {start} to {end}")

    run = StreamingIngestionRun(
        id=str(uuid4()), platform=platform, week_start_date=start, week_end_date=end,
        trigger=trigger, status="running", expected_file_count=expected_file_count,
    )
    db.add(run)
    db.commit()
    missing: list[date] = []
    errors: list[str] = []

    try:
        temp_args = {"prefix": f"{platform}-{start}-"}
        if config.staging_dir:
            config.staging_dir.mkdir(parents=True, exist_ok=True)
            temp_args["dir"] = str(config.staging_dir)
        with tempfile.TemporaryDirectory(**temp_args) as temporary:
            staging = Path(temporary)
            downloaded: list[tuple[date, str, Path]] = []

            # Keep the FTP session dedicated to network I/O. Parsing, decryption,
            # and database writes can take long enough for the server to close an
            # otherwise idle control connection.
            with FTPSourceClient(config.ftp_host or "", config.ftp_user or "", config.ftp_password or "") as ftp:
                for play_date in dates_inclusive(start, end):
                    filename = expected_filename(platform, play_date)
                    encrypted_or_csv = staging / filename
                    try:
                        ftp.download(filename, encrypted_or_csv)
                    except MissingRemoteFile:
                        missing.append(play_date)
                        logger.warning("Missing %s source file for %s", platform, play_date)
                        continue
                    run.downloaded_file_count += 1
                    downloaded.append((play_date, filename, encrypted_or_csv))
                    db.commit()

            for play_date, filename, encrypted_or_csv in downloaded:
                try:
                    if platform == "audiomack":
                        csv_path = staging / filename.removesuffix(".asc")
                        decrypt_audiomack(encrypted_or_csv, csv_path, config.gpg_passphrase or "", config.gpg_binary)
                        rows = parse_audiomack(csv_path, play_date, run.id)
                        model = AudiomackStream
                    else:
                        rows = parse_boomplay(encrypted_or_csv, play_date, run.id)
                        model = BoomplayStream
                    db.execute(delete(model).where(model.play_date == play_date))
                    db.bulk_insert_mappings(model, rows)
                    run.loaded_file_count += 1
                    run.loaded_row_count += len(rows)
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    errors.append(f"{filename}: {exc}")
                    logger.exception("Could not process %s", filename)

        status = "failed" if errors else "partial" if missing else "succeeded"
        _finish_run(db, run, status, missing, errors)
        alert = build_ingestion_alert(
            status=status,
            platform=platform,
            start=start,
            end=end,
            loaded_files=run.loaded_file_count,
            expected_files=expected_file_count,
            loaded_rows=run.loaded_row_count,
            run_id=run.id,
            missing_dates=missing,
            error_count=len(errors),
        )
        run.notification_status = send_slack_alert(config.slack_webhook_url, alert)
        db.commit()
        return serialize_run(run)
    except Exception as exc:
        db.rollback()
        run = db.get(StreamingIngestionRun, run.id)
        if run:
            _finish_run(db, run, "failed", missing, errors + [str(exc)])
            alert = build_ingestion_alert(
                status="failed",
                platform=platform,
                start=start,
                end=end,
                loaded_files=run.loaded_file_count,
                expected_files=(end - start).days + 1,
                loaded_rows=run.loaded_row_count,
                run_id=run.id,
                missing_dates=missing,
                error_count=len(errors) + 1,
                error_type=exc.__class__.__name__,
            )
            run.notification_status = send_slack_alert(config.slack_webhook_url, alert)
            db.commit()
        raise
    finally:
        _unlock(db, platform, start)


def ingest_platform_week(
    db: Session,
    platform: str,
    start: date,
    end: date,
    trigger: str = "scheduled",
    config: StreamingConfig | None = None,
) -> dict:
    """Backward-compatible entry point for weekly ingestion callers."""
    if (end - start).days != 6:
        raise ValueError("A reporting week must contain exactly seven days")
    return ingest_platform_period(db, platform, start, end, trigger=trigger, config=config)


def ingest_period(db: Session, start: date, end: date, trigger: str = "scheduled", config: StreamingConfig | None = None) -> list[dict]:
    results = []
    failures = []
    for platform in PLATFORMS:
        if trigger == "scheduled":
            completed = db.query(StreamingIngestionRun).filter(
                StreamingIngestionRun.platform == platform,
                StreamingIngestionRun.week_start_date == start,
                StreamingIngestionRun.week_end_date == end,
                StreamingIngestionRun.status == "succeeded",
            ).order_by(StreamingIngestionRun.completed_at.desc()).first()
            if completed:
                result = serialize_run(completed)
                result["skipped"] = True
                results.append(result)
                continue
        try:
            results.append(ingest_platform_period(db, platform, start, end, trigger=trigger, config=config))
        except Exception as exc:
            failures.append({"platform": platform, "status": "failed", "error": str(exc)})
    return results + failures


def ingest_week(db: Session, start: date, end: date, trigger: str = "scheduled", config: StreamingConfig | None = None) -> list[dict]:
    if (end - start).days != 6:
        raise ValueError("A reporting week must contain exactly seven days")
    return ingest_period(db, start, end, trigger=trigger, config=config)


def run_backfill(start: date, end: date, chunk_days: int = 7) -> list[dict]:
    """Process an inclusive backlog range in bounded chunks using independent DB sessions."""
    if end < start:
        raise ValueError("end date must not be before start date")
    if chunk_days < 1:
        raise ValueError("chunk_days must be at least one")

    results = []
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=chunk_days - 1), end)
        with SessionLocal() as db:
            results.extend(ingest_period(db, chunk_start, chunk_end, trigger="backfill"))
        chunk_start = chunk_end + timedelta(days=1)
    return results


def ingest_latest_week(db: Session, trigger: str = "scheduled", config: StreamingConfig | None = None) -> list[dict]:
    config = config or StreamingConfig()
    start, end = latest_completed_week(timezone=config.timezone)
    return ingest_week(db, start, end, trigger=trigger, config=config)


def serialize_run(run: StreamingIngestionRun) -> dict:
    return {
        "id": run.id,
        "platform": run.platform,
        "week_start_date": run.week_start_date.isoformat(),
        "week_end_date": run.week_end_date.isoformat(),
        "trigger": run.trigger,
        "status": run.status,
        "expected_file_count": run.expected_file_count,
        "downloaded_file_count": run.downloaded_file_count,
        "loaded_file_count": run.loaded_file_count,
        "loaded_row_count": run.loaded_row_count,
        "missing_dates": json.loads(run.missing_dates or "[]"),
        "warning_count": run.warning_count,
        "error_detail": json.loads(run.error_detail or "[]"),
        "notification_status": run.notification_status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }
