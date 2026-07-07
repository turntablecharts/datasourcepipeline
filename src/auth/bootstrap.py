from sqlalchemy.orm import Session

from src import models
from src.auth.utils import hash_password
from src.database import SessionLocal


BOOTSTRAP_ADMIN_EMAIL = "babatolatemi@gmail.com"
BOOTSTRAP_ADMIN_PASSWORD = "password123"
BOOTSTRAP_ADMIN_USERNAME = "bimie"
BOOTSTRAP_ADMIN_FIRST_NAME = "Temitope"
BOOTSTRAP_ADMIN_LAST_NAME = "Babatola"


def bootstrap_admin_user() -> None:
    if not BOOTSTRAP_ADMIN_EMAIL or not BOOTSTRAP_ADMIN_PASSWORD:
        return

    db: Session = SessionLocal()
    try:
        existing = (
            db.query(models.User)
            .filter(models.User.email == BOOTSTRAP_ADMIN_EMAIL)
            .first()
        )
        if existing:
            existing.hashed_password = hash_password(BOOTSTRAP_ADMIN_PASSWORD)
            existing.username = BOOTSTRAP_ADMIN_USERNAME
            existing.first_name = BOOTSTRAP_ADMIN_FIRST_NAME
            existing.last_name = BOOTSTRAP_ADMIN_LAST_NAME
            existing.role = "admin"
            existing.is_active = True
            db.commit()
            return

        user = models.User(
            email=BOOTSTRAP_ADMIN_EMAIL,
            hashed_password=hash_password(BOOTSTRAP_ADMIN_PASSWORD),
            username=BOOTSTRAP_ADMIN_USERNAME,
            first_name=BOOTSTRAP_ADMIN_FIRST_NAME,
            last_name=BOOTSTRAP_ADMIN_LAST_NAME,
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()
