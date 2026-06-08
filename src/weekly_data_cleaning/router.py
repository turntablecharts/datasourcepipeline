import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
import pandas as pd
from sqlalchemy.orm import Session
from src.database import get_db
from src.models import CleanedAlbumData, RawAlbumData, User, UploadLog
from src.auth.utils import get_current_user
from src.weekly_data_cleaning.engine import get_script_module, run_pipeline
from src.templates.router import get_templates_for_user

router = APIRouter()


@router.post("/")
async def process_file(
    file: UploadFile = File(...),
    template_name: str = Form(...),
    week_start_date: str = Form(...),
    week_end_date: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check template exists and user has access
   
    allowed = [t["filename"] for t in get_templates_for_user(current_user)]
    if template_name not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Template '{template_name}' not found or you don't have access."
        )

    # Check a script is registered for this template ─────────────────
    try:
        get_script_module(template_name=template_name, file_bytes=b"", original_filename="")
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))

    # Check file extension ───────────────────────────────────────────
    if not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=400,
            detail="Only .xlsx files are supported."
        )

    # Read raw bytes, save raw rows, and hand off to the script ───────
    file_bytes = await file.read()
    start_date = parse_week_date(week_start_date, "week_start_date")
    end_date = parse_week_date(week_end_date, "week_end_date")

    upload_log = create_upload_log(
        db=db,
        user=current_user,
        template_name=template_name,
        original_filename=file.filename,
        week_start_date=start_date,
        week_end_date=end_date,
    )

    try:
        rows_input = save_raw_album_data(db=db, upload_log_id=upload_log.id, file_bytes=file_bytes)
        upload_log.rows_input = rows_input
        db.flush()
        output_bytes, output_filename, rows_input, rows_output, log = run_pipeline(
            file_bytes=file_bytes,
            original_filename=file.filename,
            template_name=template_name,
            week_start_date=week_start_date,
            week_end_date=week_end_date
        )
        save_cleaned_album_data(
            db=db,
            upload_log_id=upload_log.id,
            week_start_date=start_date,
            week_end_date=end_date,
            output_bytes=output_bytes,
        )
    except ValueError as e:
        update_upload_log(
            db=db,
            upload_log=upload_log,
            rows_input=upload_log.rows_input,
            rows_output=0,
            status="error",
            error_detail=str(e),
        )
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        db.rollback()
        update_upload_log(
            db=db,
            upload_log=upload_log,
            rows_input=upload_log.rows_input,
            rows_output=0,
            status="error",
            error_detail=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

    update_upload_log(
        db=db,
        upload_log=upload_log,
        rows_input=rows_input, rows_output=rows_output,
        status="success",
        error_detail=None
    )

    return Response(
        content=output_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={output_filename}"}
    )


@router.get("/available-templates")
def available_templates(current_user: User = Depends(get_current_user)):
   
    templates = get_templates_for_user(current_user)
    return {
        "templates": [
            {"filename": t["filename"], "display_name": t["display_name"]}
            for t in templates
        ]
    }


@router.get("/history")
def my_upload_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    logs = (
        db.query(UploadLog)
        .filter(UploadLog.user_id == current_user.id)
        .order_by(UploadLog.created_date.desc())
        .limit(20)
        .all()
    )
    return [serialize_upload_log(log) for log in logs]


@router.get("/raw-album-data")
def my_raw_album_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    upload_log_id: int | None = None,
    limit: int = 100,
):
    limit = max(1, min(limit, 500))
    query = (
        db.query(RawAlbumData)
        .join(UploadLog, RawAlbumData.upload_log_id == UploadLog.id)
        .filter(UploadLog.user_id == current_user.id)
    )
    if upload_log_id is not None:
        query = query.filter(RawAlbumData.upload_log_id == upload_log_id)

    rows = query.order_by(RawAlbumData.id.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "upload_log_id": row.upload_log_id,
            "source_sheet": row.source_sheet,
            "row_number": row.row_number,
            "original_album": row.original_album,
            "album_points": row.album_points,
            "spotify_equivalent_points": row.spotify_equivalent_points,
            "created_date": row.created_date,
        }
        for row in rows
    ]


def serialize_upload_log(log: UploadLog) -> dict:
    try:
        error_detail = log.error_detail
    except AttributeError:
        error_detail = None

    return {
        "id": log.id,
        "user_id": log.user_id,
        "original_filename": log.original_filename,
        "template_name": log.template_id,
        "week_start_date": log.week_start_date,
        "week_end_date": log.week_end_date,
        "rows_input": log.rows_input,
        "rows_output": log.rows_output,
        "issues_fixed": "",
        "status": log.status,
        "error_detail": error_detail,
        "uploaded_at": log.created_date,
    }


@router.get("/cleaned-album-data")
def my_cleaned_album_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    upload_log_id: int | None = None,
    limit: int = 100,
):
    limit = max(1, min(limit, 500))
    query = (
        db.query(CleanedAlbumData)
        .join(UploadLog, CleanedAlbumData.upload_log_id == UploadLog.id)
        .filter(UploadLog.user_id == current_user.id)
    )
    if upload_log_id is not None:
        query = query.filter(CleanedAlbumData.upload_log_id == upload_log_id)

    rows = query.order_by(CleanedAlbumData.id.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "upload_log_id": row.upload_log_id,
            "album": row.album,
            "total_points": row.total_points,
            "week_start_date": row.week_start_date,
            "week_end_date": row.week_end_date,
            "created_date": row.created_date,
        }
        for row in rows
    ]


@router.get("/album-data")
def my_album_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    upload_log_id: int | None = None,
    limit: int = 100,
):
    return my_cleaned_album_data(
        current_user=current_user,
        db=db,
        upload_log_id=upload_log_id,
        limit=limit,
    )


def parse_week_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{field_name} must be in YYYY-MM-DD format.") from exc


def create_upload_log(
    db: Session,
    user: User,
    template_name: str,
    original_filename: str,
    week_start_date: date,
    week_end_date: date,
) -> UploadLog:
    upload_log = UploadLog(
        user_id=user.id,
        username=user.username or user.email,
        template_id=template_name,
        original_filename=original_filename,
        week_start_date=week_start_date,
        week_end_date=week_end_date,
        rows_input=0,
        rows_output=0,
        status="processing",
        error_detail=None,
    )
    db.add(upload_log)
    db.commit()
    db.refresh(upload_log)
    return upload_log


def save_cleaned_album_data(
    db: Session,
    upload_log_id: int,
    week_start_date: date,
    week_end_date: date,
    output_bytes: bytes,
) -> int:
    dataframe = pd.read_excel(io.BytesIO(output_bytes), sheet_name="Joint Album Data")
    required_columns = {"Album", "Total Points"}
    missing_columns = required_columns - set(dataframe.columns)
    if missing_columns:
        raise ValueError(f"Cleaned output missing column(s): {', '.join(sorted(missing_columns))}")

    records = [
        CleanedAlbumData(
            upload_log_id=upload_log_id,
            week_start_date=week_start_date,
            week_end_date=week_end_date,
            album=str(row["Album"]),
            total_points=int(row["Total Points"]),
        )
        for _, row in dataframe.iterrows()
    ]

    db.add_all(records)
    db.flush()
    return len(records)


def save_raw_album_data(db: Session, upload_log_id: int, file_bytes: bytes) -> int:
    try:
        album_data = pd.read_excel(io.BytesIO(file_bytes), sheet_name="album")
        spotify_data = pd.read_excel(io.BytesIO(file_bytes), sheet_name="spotify_equivalent")
    except Exception as exc:
        raise ValueError("Could not read uploaded Excel workbook.") from exc

    required_album = {"Album", "Points"}
    required_spotify = {"Album", "Spotify Equivalent"}
    missing_album = required_album - set(album_data.columns)
    missing_spotify = required_spotify - set(spotify_data.columns)
    if missing_album:
        raise ValueError(f"Missing columns in album sheet: {', '.join(sorted(missing_album))}")
    if missing_spotify:
        raise ValueError(f"Missing columns in spotify_equivalent sheet: {', '.join(sorted(missing_spotify))}")

    records = []
    for row_number, row in enumerate(album_data.to_dict(orient="records"), start=2):
        records.append(
            RawAlbumData(
                upload_log_id=upload_log_id,
                source_sheet="album",
                row_number=row_number,
                original_album=to_nullable_string(row.get("Album")),
                album_points=to_nullable_bigint(row.get("Points"), "album", row_number, "Points"),
                spotify_equivalent_points=None,
            )
        )

    for row_number, row in enumerate(spotify_data.to_dict(orient="records"), start=2):
        records.append(
            RawAlbumData(
                upload_log_id=upload_log_id,
                source_sheet="spotify_equivalent",
                row_number=row_number,
                original_album=to_nullable_string(row.get("Album")),
                album_points=None,
                spotify_equivalent_points=to_nullable_bigint(
                    row.get("Spotify Equivalent"),
                    "spotify_equivalent",
                    row_number,
                    "Spotify Equivalent",
                ),
            )
        )

    db.add_all(records)
    db.flush()
    return len(records)


def to_nullable_string(value) -> str | None:
    if pd.isna(value):
        return None
    return str(value)


def to_nullable_bigint(value, sheet_name: str, row_number: int, column_name: str) -> int | None:
    if pd.isna(value):
        return None

    numeric_value = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric_value):
        raise ValueError(f"{sheet_name} row {row_number} has a non-numeric {column_name} value.")
    if numeric_value % 1 != 0:
        raise ValueError(f"{sheet_name} row {row_number} has a decimal {column_name} value.")

    return int(numeric_value)


def update_upload_log(
    db: Session,
    upload_log: UploadLog,
    rows_input: int,
    rows_output: int,
    status: str,
    error_detail: str | None,
) -> None:
    upload_log.rows_input = rows_input
    upload_log.rows_output = rows_output
    upload_log.status = status
    upload_log.error_detail = error_detail
    db.commit()
