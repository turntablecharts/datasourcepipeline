from sqlalchemy import BigInteger, Column, Date, ForeignKey, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from src.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    role = Column(String, default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_modified_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UploadLog(Base):
    __tablename__ = "upload_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    username = Column(String, nullable=False)
    template_id = Column(String, nullable=False)
    original_filename = Column(String)
    week_start_date = Column(Date, nullable=False)
    week_end_date = Column(Date, nullable=False)
    rows_input = Column(Integer, nullable=False, default=0)
    rows_output = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False)
    error_detail = Column(Text, nullable=True)
    created_date = Column(DateTime(timezone=True), server_default=func.now())


class RawAlbumData(Base):
    __tablename__ = "raw_album_data"

    id = Column(Integer, primary_key=True, index=True)
    upload_log_id = Column(Integer, ForeignKey("upload_logs.id", ondelete="CASCADE"), nullable=False, index=True)
    source_sheet = Column(String, nullable=False, index=True)
    row_number = Column(Integer, nullable=False)
    original_album = Column(Text)
    album_points = Column(BigInteger)
    spotify_equivalent_points = Column(BigInteger)
    created_date = Column(DateTime(timezone=True), server_default=func.now())


class CleanedAlbumData(Base):
    __tablename__ = "cleaned_album_data"

    id = Column(Integer, primary_key=True, index=True)
    upload_log_id = Column(Integer, ForeignKey("upload_logs.id", ondelete="CASCADE"), nullable=False, index=True)
    album = Column(Text, nullable=False, index=True)
    total_points = Column(BigInteger, nullable=False)
    week_start_date = Column(Date, nullable=False, index=True)
    week_end_date = Column(Date, nullable=False, index=True)
    created_date = Column(DateTime(timezone=True), server_default=func.now())


class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    template_name = Column(String, nullable=False)
    template_file_path = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_modified_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
