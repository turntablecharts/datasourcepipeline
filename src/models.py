from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
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


class AppleMusicRaw(Base):
    """An Apple Music report row exactly as it was uploaded."""

    __tablename__ = "apple_music_raw"

    id = Column(Integer, primary_key=True)
    song_title = Column(String(500), nullable=False)
    artiste_name = Column(String(500), nullable=False)
    streams = Column(BigInteger, nullable=False)
    source = Column(String(255))
    week_start_date = Column(Date, nullable=False)
    week_end_date = Column(Date, nullable=False)
    created_date = Column(DateTime, nullable=False, server_default=func.now())


class AppleMusicMetadata(Base):
    """Spotify metadata matched to an uploaded Apple Music report row."""

    __tablename__ = "apple_music_metadata"

    id = Column(Integer, primary_key=True)
    apple_music_song_id = Column(String(255), nullable=False)
    song_title_raw = Column(String(500), nullable=False)
    song_title_fetched = Column(String(500), nullable=False)
    artist_name_raw = Column(String(500))
    artiste_name_fetched = Column(String(500), nullable=False)
    featured_artists = Column(Text)
    streams = Column(BigInteger, nullable=False)
    album_name = Column(String(500))
    genre = Column(String(255))
    producer = Column(String(500))
    record_label = Column(String(500))
    distributor = Column(String(500))
    release_date = Column(Date)
    reporting_week_start = Column(Date, nullable=False)
    reporting_week_end = Column(Date, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class StreamingIngestionRun(Base):
    __tablename__ = "streaming_ingestion_run_logs"
    __table_args__ = (
        Index("idx_streaming_runs_platform_week", "platform", "week_start_date", "week_end_date"),
        Index("idx_streaming_runs_started_at", "started_at"),
    )

    id = Column(String(36), primary_key=True)
    platform = Column(String(32), nullable=False)
    week_start_date = Column(Date, nullable=False)
    week_end_date = Column(Date, nullable=False)
    trigger = Column(String(20), nullable=False, default="scheduled")
    status = Column(String(20), nullable=False, default="running")
    expected_file_count = Column(Integer, nullable=False, default=7)
    downloaded_file_count = Column(Integer, nullable=False, default=0)
    loaded_file_count = Column(Integer, nullable=False, default=0)
    loaded_row_count = Column(Integer, nullable=False, default=0)
    missing_dates = Column(Text)
    warning_count = Column(Integer, nullable=False, default=0)
    error_detail = Column(Text)
    notification_status = Column(String(32))
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True))


class AudiomackStream(Base):
    __tablename__ = "audiomack_streams"
    __table_args__ = (
        CheckConstraint("streams >= 1000", name="ck_audiomack_streams_minimum_daily_streams"),
        Index("idx_audiomack_streams_date_country", "play_date", "country_code"),
        Index("idx_audiomack_streams_aggregation", "play_date", "song_title_normalized", "artist_normalized"),
        Index("idx_audiomack_streams_run", "ingestion_run_id"),
    )

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    play_date = Column(Date, nullable=False)
    isrc = Column(String(32))
    artist = Column(Text, nullable=False)
    song_title = Column(Text, nullable=False)
    artist_normalized = Column(Text, nullable=False)
    song_title_normalized = Column(Text, nullable=False)
    country_code = Column(String(2), nullable=False)
    streams = Column(BigInteger, nullable=False)
    source_file = Column(Text, nullable=False)
    source_row_number = Column(Integer, nullable=False)
    ingestion_run_id = Column(String(36), ForeignKey("streaming_ingestion_run_logs.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class BoomplayStream(Base):
    __tablename__ = "boomplay_streams"
    __table_args__ = (
        CheckConstraint("streams >= 1000", name="ck_boomplay_streams_minimum_daily_streams"),
        Index("idx_boomplay_streams_date", "play_date"),
        Index("idx_boomplay_streams_aggregation", "play_date", "song_title_normalized", "artist_normalized"),
        Index("idx_boomplay_streams_run", "ingestion_run_id"),
    )

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    play_date = Column(Date, nullable=False)
    artist = Column(Text, nullable=False)
    song_title = Column(Text, nullable=False)
    artist_normalized = Column(Text, nullable=False)
    song_title_normalized = Column(Text, nullable=False)
    streams = Column(BigInteger, nullable=False)
    source_file = Column(Text, nullable=False)
    source_row_number = Column(Integer, nullable=False)
    ingestion_run_id = Column(String(36), ForeignKey("streaming_ingestion_run_logs.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
