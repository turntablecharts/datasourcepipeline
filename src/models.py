from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
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
    __table_args__ = (
        Index(
            "uq_upload_logs_current_template_week",
            "template_id",
            "week_start_date",
            unique=True,
            postgresql_where=text("is_current"),
            sqlite_where=text("is_current"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    username = Column(String, nullable=False)
    template_id = Column(String, nullable=False)
    original_filename = Column(String)
    file_hash = Column(String(64))
    week_start_date = Column(Date, nullable=False)
    week_end_date = Column(Date, nullable=False)
    rows_input = Column(Integer, nullable=False, default=0)
    rows_output = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False)
    error_detail = Column(Text, nullable=True)
    is_current = Column(Boolean, nullable=False, default=True)
    replaces_upload_log_id = Column(Integer, nullable=True)
    replaced_by_upload_log_id = Column(Integer, nullable=True)
    linked_data_cleared = Column(Boolean, nullable=False, default=False)
    duplicate_file_upload = Column(Boolean, nullable=False, default=False)
    created_date = Column(DateTime(timezone=True), server_default=func.now())


class RawAlbumData(Base):
    __tablename__ = "raw_album_data"
    __table_args__ = (
        Index("idx_raw_album_upload_log_id", "upload_log_id"),
        Index("idx_raw_album_source_sheet", "source_sheet"),
    )

    id = Column(Integer, primary_key=True)
    upload_log_id = Column(Integer, ForeignKey("upload_logs.id", ondelete="CASCADE"), nullable=False)
    source_sheet = Column(String, nullable=False)
    row_number = Column(Integer, nullable=False)
    original_album = Column(Text)
    album_points = Column(Numeric(20, 6))
    spotify_equivalent_points = Column(Numeric(20, 6))
    created_date = Column(DateTime(timezone=True), server_default=func.now())


class CleanedAlbumData(Base):
    __tablename__ = "cleaned_album_data"
    __table_args__ = (
        Index("idx_cleaned_album_upload_log_id", "upload_log_id"),
        Index("idx_cleaned_album_album", "album"),
        Index("idx_cleaned_album_week", "week_start_date", "week_end_date"),
    )

    id = Column(Integer, primary_key=True)
    upload_log_id = Column(Integer, ForeignKey("upload_logs.id", ondelete="CASCADE"), nullable=False)
    album = Column(Text, nullable=False)
    total_points = Column(Numeric(20, 6), nullable=False)
    week_start_date = Column(Date, nullable=False)
    week_end_date = Column(Date, nullable=False)
    created_date = Column(DateTime(timezone=True), server_default=func.now())


class RawArtisteGenreMetadata(Base):
    __tablename__ = "raw_artiste_genre_metadata"
    __table_args__ = (
        Index("idx_raw_artiste_genre_upload_log_id", "upload_log_id"),
        Index("idx_raw_artiste_genre_source_sheet", "source_sheet"),
    )

    id = Column(Integer, primary_key=True)
    upload_log_id = Column(Integer, ForeignKey("upload_logs.id", ondelete="CASCADE"), nullable=False)
    source_sheet = Column(String, nullable=False)
    row_number = Column(Integer, nullable=False)
    title = Column(Text)
    points = Column(Numeric(20, 6))
    artiste = Column(Text)
    featured_artistes = Column(Text)
    genre = Column(Text)
    produced_by = Column(Text)
    created_date = Column(DateTime(timezone=True), server_default=func.now())


class WeeklyMetadataCleanedArtiste(Base):
    __tablename__ = "weekly_metadata_cleaned_artiste"
    __table_args__ = (
        Index("idx_weekly_metadata_artiste_upload_log_id", "upload_log_id"),
        Index("idx_weekly_metadata_artiste_name", "artiste"),
        Index("idx_weekly_metadata_artiste_week", "week_start_date", "week_end_date"),
    )

    id = Column(Integer, primary_key=True)
    upload_log_id = Column(Integer, ForeignKey("upload_logs.id", ondelete="CASCADE"), nullable=False)
    artiste = Column(Text, nullable=False)
    points = Column(Numeric(20, 6), nullable=False)
    week_start_date = Column(Date, nullable=False)
    week_end_date = Column(Date, nullable=False)
    created_date = Column(DateTime(timezone=True), server_default=func.now())


class WeeklyMetadataCleanedGenre(Base):
    __tablename__ = "weekly_metadata_cleaned_genre"
    __table_args__ = (
        Index("idx_weekly_metadata_genre_upload_log_id", "upload_log_id"),
        Index("idx_weekly_metadata_genre_name", "genre"),
        Index("idx_weekly_metadata_genre_week", "week_start_date", "week_end_date"),
    )

    id = Column(Integer, primary_key=True)
    upload_log_id = Column(Integer, ForeignKey("upload_logs.id", ondelete="CASCADE"), nullable=False)
    genre = Column(Text, nullable=False)
    points = Column(Numeric(20, 6), nullable=False)
    week_start_date = Column(Date, nullable=False)
    week_end_date = Column(Date, nullable=False)
    created_date = Column(DateTime(timezone=True), server_default=func.now())


class WeeklyMetadataCleanedProducer(Base):
    __tablename__ = "weekly_metadata_cleaned_producers"
    __table_args__ = (
        Index("idx_weekly_metadata_producers_upload_log_id", "upload_log_id"),
        Index("idx_weekly_metadata_producers_name", "produced_by"),
        Index("idx_weekly_metadata_producers_week", "week_start_date", "week_end_date"),
    )

    id = Column(Integer, primary_key=True)
    upload_log_id = Column(Integer, ForeignKey("upload_logs.id", ondelete="CASCADE"), nullable=False)
    produced_by = Column(Text, nullable=False)
    points = Column(Numeric(20, 6), nullable=False)
    week_start_date = Column(Date, nullable=False)
    week_end_date = Column(Date, nullable=False)
    created_date = Column(DateTime(timezone=True), server_default=func.now())


class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    template_name = Column(String, nullable=False)
    template_file_path = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_modified_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
