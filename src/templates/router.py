import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from src.database import get_db
from src import models
from src.auth.utils import get_current_user, require_admin
from src.config import settings

router = APIRouter()

def get_templates_for_user(user: models.User) -> list[dict]:
    """Return templates visible to this user based on their role."""
    templates_dir = settings.TEMPLATES_DIR
    if not os.path.exists(templates_dir):
        return []

    files = [f for f in os.listdir(templates_dir) if f.endswith(".xlsx")]

    if user.role == "admin":
        # Admins see all templates
        visible = files
    elif user.role == "user":
        # Default users can use the currently supported cleaning templates.
        visible = files
    else:
        # Regular users only see templates prefixed with their role name
        role_prefix = user.role.lower().replace(" ", "_")
        visible = [f for f in files if f.lower().startswith(role_prefix)]

    return [
        {
            "filename": f,
            "display_name": f.replace("_", " ").replace(".xlsx", "").title(),
            "role": f.split("_")[0].title(),
            "download_url": f"/templates/download/{f}"
        }
        for f in sorted(visible)
    ]


@router.get("/")
def list_templates(current_user: models.User = Depends(get_current_user)):
    """List all templates available to the current user."""
    templates = get_templates_for_user(current_user)
    return {
        "user": current_user.email,
        "role": current_user.role,
        "templates": templates
    }


@router.get("/download/{filename}")
def download_template(
    filename: str,
    current_user: models.User = Depends(get_current_user)
):
    """Download a specific template — validates user is allowed to access it."""
    # Sanitize filename — prevent path traversal
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    if not filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx templates are supported.")

    # Check the user is allowed to access this template
    allowed = get_templates_for_user(current_user)
    allowed_filenames = [t["filename"] for t in allowed]

    if filename not in allowed_filenames:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this template."
        )

    file_path = os.path.join(settings.TEMPLATES_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Template file not found.")

    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename
    )


@router.post("/upload")
def upload_template(
    filename: str,
    _: models.User = Depends(require_admin)
):
    """
    Admin endpoint — placeholder for uploading new template versions.
    Full file upload handled in the admin panel (Phase 6).
    """
    return {"message": f"Template upload endpoint ready. Full UI in admin panel."}
