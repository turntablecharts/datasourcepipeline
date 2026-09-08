import json
from datetime import date
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from src.auth.utils import get_current_user
from src.models import User
from src.streaming_data.audiomack_boomplay.router import router as audiomack_boomplay_router


router = APIRouter()
router.include_router(audiomack_boomplay_router)
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
APPLE_MUSIC_INBOX = Path("uploads/streaming_data/apple_music")


@router.post("/apple-music/upload")
async def upload_apple_music_data(
    file: UploadFile = File(...),
    week_start_date: str = Form(...),
    week_end_date: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    start_date = parse_date(week_start_date, "week_start_date")
    end_date = parse_date(week_end_date, "week_end_date")
    if (end_date - start_date).days != 6:
        raise HTTPException(422, "week_end_date must be exactly 6 days after week_start_date.")

    filename = file.filename or ""
    if not filename.lower().endswith((".csv", ".xlsx")):
        raise HTTPException(400, "Only .csv and .xlsx files are supported.")
    file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "The upload must be 20 MB or smaller.")

    upload_id = str(uuid4())
    upload_directory = APPLE_MUSIC_INBOX / upload_id
    stored_filename = Path(filename).name
    manifest = {
        "upload_id": upload_id,
        "original_filename": stored_filename,
        "stored_file": stored_filename,
        "week_start_date": start_date.isoformat(),
        "week_end_date": end_date.isoformat(),
        "uploaded_by_user_id": current_user.id,
        "uploaded_by": current_user.email,
        "status": "uploaded",
    }

    try:
        upload_directory.mkdir(parents=True, exist_ok=False)
        (upload_directory / stored_filename).write_bytes(file_bytes)
        (upload_directory / "upload.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        raise HTTPException(500, "The Apple Music file could not be stored.") from exc

    return manifest


@router.get("/apple-music/recent")
def recent_apple_music_uploads(
    limit: int = 20,
    _: User = Depends(get_current_user),
):
    """List staged files. This does not inspect or process their contents."""
    if not APPLE_MUSIC_INBOX.exists():
        return []

    manifests = []
    for manifest_path in APPLE_MUSIC_INBOX.glob("*/upload.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["uploaded_at"] = manifest_path.stat().st_mtime
            manifests.append(manifest)
        except (OSError, json.JSONDecodeError):
            continue

    manifests.sort(key=lambda item: item["uploaded_at"], reverse=True)
    return manifests[:max(1, min(limit, 100))]


def parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(422, f"{field_name} must use YYYY-MM-DD format.") from exc
