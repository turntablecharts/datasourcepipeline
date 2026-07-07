import os

from sqlalchemy.orm import Session

from src import models
from src.auth.utils import hash_password
from src.database import SessionLocal


def bootstrap_admin_user() -> None:
    email = "babatolatemi@gmail.com"
    password = "password123"

    if not email or not password:
        return

    db: Session = SessionLocal()
    try:
        existing = db.query(models.User).filter(models.User.email == email).first()
        if existing:
            return

        user = models.User(
            email=email,
            hashed_password=hash_password(password),
            username="bimie", 
            first_name="Temitope",
            last_name="Babatola",
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()
