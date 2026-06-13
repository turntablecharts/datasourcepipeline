import sys
from src.database import SessionLocal, engine
from src import models
from src.auth.utils import hash_password

models.Base.metadata.create_all(bind=engine)

def create_user(email, password, username, first_name, last_name, role="user"):
    db = SessionLocal()
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        print(f"User {email} already exists.")
        db.close()
        return
    user = models.User(
        email=email,
        hashed_password=hash_password(password),
        username=username,
        first_name=first_name,
        last_name=last_name,
        role=role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    print(f"Created {role}: {user.email}")
    db.close()

if __name__ == "__main__":
    # Create your admin account first
    create_user(
        email="babatolatemi@gmail.com",
        password="changeme123",
        username="temi",
        first_name="Temi",
        last_name="Babatola",
        role="admin"
    )
    # Add team members like this:
    # create_user("teammate@company.com", "pass123", "Jane", "Editorial", role="user")