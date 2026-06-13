import io
import hashlib
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
import pandas as pd
from sqlalchemy.orm import Session
from src.database import get_db
from src.models import (
    CleanedAlbumData,
    RawAlbumData,
    RawArtisteGenreMetadata,
    User,
    UploadLog,
    WeeklyMetadataCleanedArtiste,
    WeeklyMetadataCleanedGenre,
    WeeklyMetadataCleanedProducer,
)
from src.auth.utils import get_current_user
from src.weekly_data_cleaning.engine import get_script_module, run_pipeline
from src.templates.router import get_templates_for_user

router = APIRouter()

ALBUM_DATA_TEMPLATES = {
    "editorial_top_album_data_template.xlsx",
    "top_album_data_template.xlsx",
}

ARTISTE_GENRE_METADATA_TEMPLATES = {
    "artiste_genre_metadata_templates.xlsx",
}


@router.post("/")
async def process_file(
    file: UploadFile = File(...),
    template_name: str = Form(...),
    week_start_date: str = Form(...),
    week_end_date: str = Form(...),
    confirm_replace: bool = Form(False),
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

    start_date = parse_week_date(week_start_date, "week_start_date")
    end_date = parse_week_date(week_end_date, "week_end_date")
    validate_week_range(start_date, end_date)

    previous_upload_log = get_current_upload_for_week(
        db=db,
        template_name=template_name,
        week_start_date=start_date,
    )
    if previous_upload_log and not confirm_replace:
        raise HTTPException(
            status_code=409,
            detail=(
                "This week's data has been processed in the past. "
                "Do you want to replace the DB data with this new version?"
            ),
        )

    if previous_upload_log:
        previous_upload_log = replace_current_upload_for_week(
            db=db,
            template_name=template_name,
            week_start_date=start_date,
        )

    # Read raw bytes, save raw rows, and hand off to the script ───────
    file_bytes = await file.read()
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    upload_log = create_upload_log(
        db=db,
        user=current_user,
        template_name=template_name,
        original_filename=file.filename,
        file_hash=file_hash,
        week_start_date=start_date,
        week_end_date=end_date,
        replaces_upload_log_id=previous_upload_log.id if previous_upload_log else None,
        duplicate_file_upload=previous_upload_log.file_hash == file_hash if previous_upload_log else False,
    )

    try:
        if template_name in ALBUM_DATA_TEMPLATES:
            rows_input = save_raw_album_data(db=db, upload_log_id=upload_log.id, file_bytes=file_bytes)
            upload_log.rows_input = rows_input
            db.flush()
        elif template_name in ARTISTE_GENRE_METADATA_TEMPLATES:
            rows_input = save_raw_artiste_genre_metadata(db=db, upload_log_id=upload_log.id, file_bytes=file_bytes)
            upload_log.rows_input = rows_input
            db.flush()

        output_bytes, output_filename, rows_input, rows_output, log = run_pipeline(
            file_bytes=file_bytes,
            original_filename=file.filename,
            template_name=template_name,
            week_start_date=week_start_date,
            week_end_date=week_end_date
        )
        if template_name in ALBUM_DATA_TEMPLATES:
            save_cleaned_album_data(
                db=db,
                upload_log_id=upload_log.id,
                week_start_date=start_date,
                week_end_date=end_date,
                output_bytes=output_bytes,
            )
        elif template_name in ARTISTE_GENRE_METADATA_TEMPLATES:
            save_cleaned_artiste_genre_metadata(
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
        headers={
            "Content-Disposition": f"attachment; filename={output_filename}",
            "X-Replaced-Previous-Upload": "true" if previous_upload_log else "false",
        }
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
        "file_hash": log.file_hash,
        "week_start_date": log.week_start_date,
        "week_end_date": log.week_end_date,
        "rows_input": log.rows_input,
        "rows_output": log.rows_output,
        "issues_fixed": "",
        "status": log.status,
        "error_detail": error_detail,
        "is_current": log.is_current,
        "replaces_upload_log_id": log.replaces_upload_log_id,
        "replaced_by_upload_log_id": log.replaced_by_upload_log_id,
        "linked_data_cleared": log.linked_data_cleared,
        "duplicate_file_upload": log.duplicate_file_upload,
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


def validate_week_range(week_start_date: date, week_end_date: date) -> None:
    if (week_end_date - week_start_date).days != 6:
        raise HTTPException(
            status_code=422,
            detail="week_end_date must be exactly 6 days after week_start_date.",
        )


def create_upload_log(
    db: Session,
    user: User,
    template_name: str,
    original_filename: str,
    file_hash: str,
    week_start_date: date,
    week_end_date: date,
    replaces_upload_log_id: int | None = None,
    duplicate_file_upload: bool = False,
) -> UploadLog:
    upload_log = UploadLog(
        user_id=user.id,
        username=user.username or user.email,
        template_id=template_name,
        original_filename=original_filename,
        file_hash=file_hash,
        week_start_date=week_start_date,
        week_end_date=week_end_date,
        rows_input=0,
        rows_output=0,
        status="processing",
        error_detail=None,
        is_current=True,
        replaces_upload_log_id=replaces_upload_log_id,
        linked_data_cleared=False,
        duplicate_file_upload=duplicate_file_upload,
    )
    db.add(upload_log)
    db.commit()
    if replaces_upload_log_id:
        previous_upload_log = db.query(UploadLog).filter(UploadLog.id == replaces_upload_log_id).first()
        if previous_upload_log:
            previous_upload_log.replaced_by_upload_log_id = upload_log.id
            db.commit()
    db.refresh(upload_log)
    return upload_log


def replace_current_upload_for_week(
    db: Session,
    template_name: str,
    week_start_date: date,
) -> UploadLog | None:
    upload_log = get_current_upload_for_week(
        db=db,
        template_name=template_name,
        week_start_date=week_start_date,
    )
    if upload_log is None:
        return None

    db.query(RawAlbumData).filter(RawAlbumData.upload_log_id == upload_log.id).delete()
    db.query(CleanedAlbumData).filter(CleanedAlbumData.upload_log_id == upload_log.id).delete()
    db.query(RawArtisteGenreMetadata).filter(RawArtisteGenreMetadata.upload_log_id == upload_log.id).delete()
    db.query(WeeklyMetadataCleanedArtiste).filter(WeeklyMetadataCleanedArtiste.upload_log_id == upload_log.id).delete()
    db.query(WeeklyMetadataCleanedGenre).filter(WeeklyMetadataCleanedGenre.upload_log_id == upload_log.id).delete()
    db.query(WeeklyMetadataCleanedProducer).filter(WeeklyMetadataCleanedProducer.upload_log_id == upload_log.id).delete()
    upload_log.is_current = False
    upload_log.status = "replaced"
    upload_log.linked_data_cleared = True
    db.commit()
    db.refresh(upload_log)
    return upload_log


def get_current_upload_for_week(
    db: Session,
    template_name: str,
    week_start_date: date,
) -> UploadLog | None:
    return (
        db.query(UploadLog)
        .filter(
            UploadLog.template_id == template_name,
            UploadLog.week_start_date == week_start_date,
            UploadLog.is_current.is_(True),
        )
        .first()
    )


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
            total_points=to_decimal_6(row["Total Points"], "cleaned", 0, "Total Points"),
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
                album_points=to_nullable_decimal_6(row.get("Points"), "album", row_number, "Points"),
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
                spotify_equivalent_points=to_nullable_decimal_6(
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


def save_raw_artiste_genre_metadata(db: Session, upload_log_id: int, file_bytes: bytes) -> int:
    try:
        workbook = pd.ExcelFile(io.BytesIO(file_bytes))
        dataframe = workbook.parse(sheet_name=workbook.sheet_names[0])
    except Exception as exc:
        raise ValueError("Could not read uploaded Excel workbook.") from exc

    dataframe.columns = [str(column).strip() for column in dataframe.columns]
    required_columns = {"Points", "Artiste", "Genre", "ProducedBy"}
    missing_columns = required_columns - set(dataframe.columns)
    if missing_columns:
        raise ValueError(f"Missing required column(s): {', '.join(sorted(missing_columns))}")

    featured_columns = [
        column
        for column in dataframe.columns
        if str(column).strip().startswith("Featured Artiste")
    ]

    records = []
    for row_number, row in enumerate(dataframe.to_dict(orient="records"), start=2):
        featured_artistes = [
            to_nullable_string(row.get(column))
            for column in featured_columns
            if to_nullable_string(row.get(column))
        ]
        records.append(
            RawArtisteGenreMetadata(
                upload_log_id=upload_log_id,
                source_sheet=workbook.sheet_names[0],
                row_number=row_number,
                title=to_nullable_string(row.get("Title")),
                points=to_nullable_decimal_6(row.get("Points"), "metadata", row_number, "Points"),
                artiste=to_nullable_string(row.get("Artiste")),
                featured_artistes=";".join(featured_artistes) if featured_artistes else None,
                genre=to_nullable_string(row.get("Genre")),
                produced_by=to_nullable_string(row.get("ProducedBy")),
            )
        )

    db.add_all(records)
    db.flush()
    return len(records)


def save_cleaned_artiste_genre_metadata(
    db: Session,
    upload_log_id: int,
    week_start_date: date,
    week_end_date: date,
    output_bytes: bytes,
) -> int:
    try:
        artistes = pd.read_excel(io.BytesIO(output_bytes), sheet_name="Artistes")
        genres = pd.read_excel(io.BytesIO(output_bytes), sheet_name="Genre")
        producers = pd.read_excel(io.BytesIO(output_bytes), sheet_name="Producers")
    except Exception as exc:
        raise ValueError("Could not read cleaned artiste genre metadata workbook.") from exc

    _validate_cleaned_metadata_columns(artistes, {"Artiste", "Points"}, "Artistes")
    _validate_cleaned_metadata_columns(genres, {"Genre", "Points"}, "Genre")
    _validate_cleaned_metadata_columns(producers, {"ProducedBy", "Points"}, "Producers")

    records = []
    records.extend(
        WeeklyMetadataCleanedArtiste(
            upload_log_id=upload_log_id,
            week_start_date=week_start_date,
            week_end_date=week_end_date,
            artiste=str(row["Artiste"]),
            points=to_decimal_6(row["Points"], "Artistes", 0, "Points"),
        )
        for _, row in artistes.iterrows()
    )
    records.extend(
        WeeklyMetadataCleanedGenre(
            upload_log_id=upload_log_id,
            week_start_date=week_start_date,
            week_end_date=week_end_date,
            genre=str(row["Genre"]),
            points=to_decimal_6(row["Points"], "Genre", 0, "Points"),
        )
        for _, row in genres.iterrows()
    )
    records.extend(
        WeeklyMetadataCleanedProducer(
            upload_log_id=upload_log_id,
            week_start_date=week_start_date,
            week_end_date=week_end_date,
            produced_by=str(row["ProducedBy"]),
            points=to_decimal_6(row["Points"], "Producers", 0, "Points"),
        )
        for _, row in producers.iterrows()
    )

    db.add_all(records)
    db.flush()
    return len(records)


def _validate_cleaned_metadata_columns(dataframe: pd.DataFrame, required_columns: set[str], sheet_name: str) -> None:
    missing_columns = required_columns - set(dataframe.columns)
    if missing_columns:
        raise ValueError(f"Cleaned {sheet_name} output missing column(s): {', '.join(sorted(missing_columns))}")


def to_nullable_string(value) -> str | None:
    if pd.isna(value):
        return None
    return str(value)


def to_nullable_decimal_6(value, sheet_name: str, row_number: int, column_name: str) -> Decimal | None:
    if pd.isna(value):
        return None

    return to_decimal_6(value, sheet_name, row_number, column_name)


def to_decimal_6(value, sheet_name: str, row_number: int, column_name: str) -> Decimal:
    if isinstance(value, str):
        value = value.replace(",", "").strip()

    numeric_value = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric_value):
        raise ValueError(f"{sheet_name} row {row_number} has a non-numeric {column_name} value.")

    try:
        decimal_value = Decimal(str(numeric_value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{sheet_name} row {row_number} has an invalid {column_name} value.") from exc

    if decimal_value < 0:
        raise ValueError(f"{sheet_name} row {row_number} has a negative {column_name} value.")

    return decimal_value


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
