from datetime import date, timedelta
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from src.auth.utils import get_current_user, require_admin
from src.database import get_db
from src.models import AudiomackStream, BoomplayStream, StreamingIngestionRun, User
from src.streaming_data.audiomack_boomplay.dates import dates_inclusive, validate_reporting_week
from src.streaming_data.audiomack_boomplay.exports import build_workbook, query_audiomack, query_boomplay
from src.streaming_data.audiomack_boomplay.ingestion import ingest_week, run_backfill, serialize_run


router = APIRouter()
MAX_EXPORT_DAYS = 366
MAX_BACKFILL_DAYS = 366


def _range(start_date: date, end_date: date) -> tuple[date, date]:
    if end_date < start_date:
        raise HTTPException(422, "end_date must be on or after start_date")
    if (end_date - start_date).days + 1 > MAX_EXPORT_DAYS:
        raise HTTPException(422, f"Date range must not exceed {MAX_EXPORT_DAYS} days")
    return start_date, end_date


def _download(buffer, filename: str):
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/audiomack/countries")
def audiomack_countries(
    start_date: date, end_date: date, _: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _range(start_date, end_date)
    countries = db.query(distinct(AudiomackStream.country_code)).filter(
        AudiomackStream.play_date.between(start_date, end_date)
    ).order_by(AudiomackStream.country_code).all()
    return [row[0] for row in countries]


def _coverage(db: Session, model):
    earliest, latest = db.query(func.min(model.play_date), func.max(model.play_date)).one()
    if not earliest:
        return {"earliest_date": None, "latest_date": None, "missing_dates": []}
    present = {row[0] for row in db.query(distinct(model.play_date)).filter(model.play_date.between(earliest, latest)).all()}
    missing = [day.isoformat() for day in dates_inclusive(earliest, latest) if day not in present]
    return {"earliest_date": earliest.isoformat(), "latest_date": latest.isoformat(), "missing_dates": missing}


@router.get("/audiomack/coverage")
def audiomack_coverage(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _coverage(db, AudiomackStream)


@router.get("/boomplay/coverage")
def boomplay_coverage(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _coverage(db, BoomplayStream)


@router.get("/audiomack/export")
def export_audiomack(
    start_date: date,
    end_date: date,
    countries: list[str] = Query(...),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _range(start_date, end_date)
    requested = sorted({country.strip().upper() for country in countries if country.strip()})
    if not requested:
        raise HTTPException(422, "Select at least one Audiomack country")
    available = set(audiomack_countries(start_date, end_date, _, db))
    unknown = set(requested).difference(available)
    if unknown:
        raise HTTPException(422, f"No Audiomack data for: {', '.join(sorted(unknown))}")
    sheets = query_audiomack(db, start_date, end_date, requested)
    return _download(build_workbook(sheets), f"Audiomack_{start_date}_{end_date}.xlsx")


@router.get("/boomplay/export")
def export_boomplay(
    start_date: date, end_date: date, _: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _range(start_date, end_date)
    rows = query_boomplay(db, start_date, end_date)
    if not rows:
        raise HTTPException(404, "No Boomplay data is available for the selected period")
    return _download(build_workbook({"Boomplay NG": rows}), f"Boomplay_{start_date}_{end_date}.xlsx")


@router.get("/audiomack-boomplay/ingestion-runs")
def ingestion_runs(limit: int = 20, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    runs = db.query(StreamingIngestionRun).order_by(StreamingIngestionRun.started_at.desc()).limit(max(1, min(limit, 100))).all()
    return [serialize_run(run) for run in runs]


@router.post("/audiomack-boomplay/ingest")
def manual_ingestion(
    week_start_date: date,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        start, end = validate_reporting_week(week_start_date)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return ingest_week(db, start, end, trigger="manual")


@router.post("/audiomack-boomplay/backfill", status_code=status.HTTP_202_ACCEPTED)
def start_backfill(
    start_date: date,
    end_date: date,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
):
    if end_date < start_date:
        raise HTTPException(422, "end_date must be on or after start_date")
    day_count = (end_date - start_date).days + 1
    if day_count > MAX_BACKFILL_DAYS:
        raise HTTPException(422, f"Backfill range must not exceed {MAX_BACKFILL_DAYS} days")

    background_tasks.add_task(run_backfill, start_date, end_date)
    return {
        "status": "accepted",
        "message": "Audiomack and Boomplay backfill has been queued.",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "days": day_count,
        "requested_by": current_user.email,
    }
