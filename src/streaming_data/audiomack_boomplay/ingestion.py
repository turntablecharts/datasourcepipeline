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
from src.streaming_data.audiomack_boomplay.event_logs import safe_exception_details, write_ingestion_event
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

    run = StreamingIngestionRun(
        id=str(uuid4()), platform=platform, week_start_date=start, week_end_date=end,
        trigger=trigger, status="running", expected_file_count=expected_file_count,
    )
    db.add(run)
    db.commit()
    write_ingestion_event(
        db, run.id, "INFO", "run_started", "Ingestion run started.",
        details={"platform": platform, "start_date": start, "end_date": end,
                 "trigger": trigger, "expected_file_count": expected_file_count},
    )
    missing: list[date] = []
    errors: list[str] = []
    lock_acquired = False

    try:
        config.validate_ingestion()
        write_ingestion_event(db, run.id, "INFO", "configuration_validated", "Ingestion configuration validated.")
        if not _try_lock(db, platform, start):
            raise RuntimeError(f"An ingestion is already running for {platform} {start} to {end}")
        lock_acquired = True
        write_ingestion_event(db, run.id, "INFO", "run_lock_acquired", "Ingestion run lock acquired.")

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
            write_ingestion_event(
                db, run.id, "INFO", "ftp_connecting", "Connecting to the source FTP server.",
                details={"host": config.ftp_host},
            )
            with FTPSourceClient(config.ftp_host or "", config.ftp_user or "", config.ftp_password or "") as ftp:
                write_ingestion_event(db, run.id, "INFO", "ftp_connected", "Connected to the source FTP server.")
                for play_date in dates_inclusive(start, end):
                    filename = expected_filename(platform, play_date)
                    encrypted_or_csv = staging / filename
                    try:
                        ftp.download(filename, encrypted_or_csv)
                    except MissingRemoteFile:
                        missing.append(play_date)
                        logger.warning("Missing %s source file for %s", platform, play_date)
                        write_ingestion_event(
                            db, run.id, "WARNING", "file_missing", "Source file was not available; continuing.",
                            source_file=filename, play_date=play_date,
                        )
                        continue
                    run.downloaded_file_count += 1
                    downloaded.append((play_date, filename, encrypted_or_csv))
                    db.commit()
                    write_ingestion_event(
                        db, run.id, "INFO", "file_downloaded", "Source file downloaded.",
                        source_file=filename, play_date=play_date,
                    )

            for play_date, filename, encrypted_or_csv in downloaded:
                stage = "preparing_file"
                try:
                    if platform == "audiomack":
                        stage = "decrypting_file"
                        csv_path = staging / filename.removesuffix(".asc")
                        decrypt_audiomack(encrypted_or_csv, csv_path, config.gpg_passphrase or "", config.gpg_binary)
                        stage = "parsing_file"
                        rows = parse_audiomack(csv_path, play_date, run.id)
                        model = AudiomackStream
                    else:
                        stage = "parsing_file"
                        rows = parse_boomplay(encrypted_or_csv, play_date, run.id)
                        model = BoomplayStream
                    stage = "replacing_database_rows"
                    db.execute(delete(model).where(model.play_date == play_date))
                    db.bulk_insert_mappings(model, rows)
                    run.loaded_file_count += 1
                    run.loaded_row_count += len(rows)
                    db.commit()
                    write_ingestion_event(
                        db, run.id, "INFO", "file_loaded", "Source file processed and stored.",
                        details={"rows_stored": len(rows)}, source_file=filename, play_date=play_date,
                    )
                except Exception as exc:
                    db.rollback()
                    errors.append(f"{filename}: {exc}")
                    logger.exception("Could not process %s", filename)
                    write_ingestion_event(
                        db, run.id, "ERROR", "file_processing_failed", "Source file could not be processed.",
                        details={"stage": stage, **safe_exception_details(exc)},
                        source_file=filename, play_date=play_date,
                    )

        status = "failed" if errors else "partial" if missing else "succeeded"
        _finish_run(db, run, status, missing, errors)
        write_ingestion_event(
            db, run.id, "ERROR" if status == "failed" else "WARNING" if status == "partial" else "INFO",
            "run_completed", f"Ingestion run completed with status {status}.",
            details={"downloaded_files": run.downloaded_file_count, "loaded_files": run.loaded_file_count,
                     "rows_stored": run.loaded_row_count, "missing_files": len(missing), "errors": len(errors)},
        )
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
        write_ingestion_event(
            db, run.id, "INFO" if run.notification_status == "sent" else "WARNING",
            "slack_notification", "Slack ingestion alert processed.",
            details={"notification_status": run.notification_status},
        )
        return serialize_run(run)
    except Exception as exc:
        db.rollback()
        run = db.get(StreamingIngestionRun, run.id)
        if run:
            _finish_run(db, run, "failed", missing, errors + [str(exc)])
            write_ingestion_event(
                db, run.id, "ERROR", "run_failed", "Ingestion run failed.",
                details=safe_exception_details(exc),
            )
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
            write_ingestion_event(
                db, run.id, "INFO" if run.notification_status == "sent" else "WARNING",
                "slack_notification", "Slack ingestion alert processed.",
                details={"notification_status": run.notification_status},
            )
        raise
    finally:
        if lock_acquired:
            try:
                _unlock(db, platform, start)
            except Exception as exc:
                db.rollback()
                logger.exception("Could not release ingestion lock for %s", run.id)
                write_ingestion_event(
                    db, run.id, "ERROR", "run_unlock_failed", "Ingestion run lock could not be released.",
                    details=safe_exception_details(exc),
                )


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
