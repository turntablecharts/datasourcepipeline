from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from src.utils.constant import EnvConstants

DATABASE_URL = f"postgresql://{EnvConstants.DB_USER}:{EnvConstants.DB_PASSWORD}@{EnvConstants.DB_HOST}:{EnvConstants.DB_PORT}/{EnvConstants.DB_NAME}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()