CREATE TABLE IF NOT EXISTS upload_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    username VARCHAR NOT NULL,
    template_id VARCHAR NOT NULL,
    original_filename VARCHAR,
    file_hash VARCHAR(64),
    week_start_date DATE NOT NULL,
    week_end_date DATE NOT NULL,
    rows_input INTEGER NOT NULL DEFAULT 0,
    rows_output INTEGER NOT NULL DEFAULT 0,
    status VARCHAR NOT NULL,
    error_detail TEXT,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    replaces_upload_log_id INTEGER,
    replaced_by_upload_log_id INTEGER,
    linked_data_cleared BOOLEAN NOT NULL DEFAULT FALSE,
    duplicate_file_upload BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE upload_logs
ADD COLUMN IF NOT EXISTS original_filename VARCHAR;

ALTER TABLE upload_logs
ADD COLUMN IF NOT EXISTS file_hash VARCHAR(64);

ALTER TABLE upload_logs
ADD COLUMN IF NOT EXISTS week_start_date DATE;

ALTER TABLE upload_logs
ADD COLUMN IF NOT EXISTS week_end_date DATE;

ALTER TABLE upload_logs
ADD COLUMN IF NOT EXISTS rows_input INTEGER NOT NULL DEFAULT 0;

ALTER TABLE upload_logs
ADD COLUMN IF NOT EXISTS rows_output INTEGER NOT NULL DEFAULT 0;

ALTER TABLE upload_logs
ADD COLUMN IF NOT EXISTS error_detail TEXT;

ALTER TABLE upload_logs
ADD COLUMN IF NOT EXISTS is_current BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE upload_logs
ADD COLUMN IF NOT EXISTS replaces_upload_log_id INTEGER;

ALTER TABLE upload_logs
ADD COLUMN IF NOT EXISTS replaced_by_upload_log_id INTEGER;

ALTER TABLE upload_logs
ADD COLUMN IF NOT EXISTS linked_data_cleared BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE upload_logs
ADD COLUMN IF NOT EXISTS duplicate_file_upload BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE upload_logs
ALTER COLUMN week_start_date DROP NOT NULL,
ALTER COLUMN week_end_date DROP NOT NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'upload_logs'
          AND column_name = 'number_of_rows'
    ) THEN
        ALTER TABLE upload_logs
        ALTER COLUMN number_of_rows DROP NOT NULL,
        ALTER COLUMN number_of_rows SET DEFAULT 0;

        UPDATE upload_logs
        SET rows_output = number_of_rows
        WHERE rows_output = 0
          AND number_of_rows IS NOT NULL;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'upload_logs'
          AND column_name = 'file_path'
    ) THEN
        UPDATE upload_logs
        SET original_filename = file_path
        WHERE original_filename IS NULL
          AND file_path IS NOT NULL;
    END IF;
END $$;

WITH ranked_uploads AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY template_id, week_start_date
            ORDER BY created_date DESC, id DESC
        ) AS row_rank
    FROM upload_logs
    WHERE week_start_date IS NOT NULL
      AND week_end_date IS NOT NULL
      AND status != 'replaced'
)
UPDATE upload_logs
SET is_current = ranked_uploads.row_rank = 1
FROM ranked_uploads
WHERE upload_logs.id = ranked_uploads.id;

UPDATE upload_logs
SET is_current = FALSE
WHERE status = 'replaced';

WITH replaced_uploads AS (
    SELECT id
    FROM upload_logs
    WHERE is_current = FALSE
)
DELETE FROM raw_album_data
USING replaced_uploads
WHERE raw_album_data.upload_log_id = replaced_uploads.id;

WITH replaced_uploads AS (
    SELECT id
    FROM upload_logs
    WHERE is_current = FALSE
)
DELETE FROM cleaned_album_data
USING replaced_uploads
WHERE cleaned_album_data.upload_log_id = replaced_uploads.id;

UPDATE upload_logs
SET status = 'replaced',
    linked_data_cleared = TRUE
WHERE is_current = FALSE
  AND status != 'replaced';

CREATE TABLE IF NOT EXISTS raw_album_data (
    id SERIAL PRIMARY KEY,
    upload_log_id INTEGER NOT NULL REFERENCES upload_logs(id) ON DELETE CASCADE,
    source_sheet VARCHAR NOT NULL,
    row_number INTEGER NOT NULL,
    original_album TEXT,
    album_points NUMERIC(20, 6),
    spotify_equivalent_points NUMERIC(20, 6),
    created_date TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cleaned_album_data (
    id SERIAL PRIMARY KEY,
    upload_log_id INTEGER NOT NULL REFERENCES upload_logs(id) ON DELETE CASCADE,
    album TEXT NOT NULL,
    total_points NUMERIC(20, 6) NOT NULL,
    week_start_date DATE NOT NULL,
    week_end_date DATE NOT NULL,
    created_date TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw_artiste_genre_metadata (
    id SERIAL PRIMARY KEY,
    upload_log_id INTEGER NOT NULL REFERENCES upload_logs(id) ON DELETE CASCADE,
    source_sheet VARCHAR NOT NULL,
    row_number INTEGER NOT NULL,
    title TEXT,
    points NUMERIC(20, 6),
    artiste TEXT,
    featured_artistes TEXT,
    genre TEXT,
    produced_by TEXT,
    created_date TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS weekly_metadata_cleaned_artiste (
    id SERIAL PRIMARY KEY,
    upload_log_id INTEGER NOT NULL REFERENCES upload_logs(id) ON DELETE CASCADE,
    artiste TEXT NOT NULL,
    points NUMERIC(20, 6) NOT NULL,
    week_start_date DATE NOT NULL,
    week_end_date DATE NOT NULL,
    created_date TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS weekly_metadata_cleaned_genre (
    id SERIAL PRIMARY KEY,
    upload_log_id INTEGER NOT NULL REFERENCES upload_logs(id) ON DELETE CASCADE,
    genre TEXT NOT NULL,
    points NUMERIC(20, 6) NOT NULL,
    week_start_date DATE NOT NULL,
    week_end_date DATE NOT NULL,
    created_date TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS weekly_metadata_cleaned_producers (
    id SERIAL PRIMARY KEY,
    upload_log_id INTEGER NOT NULL REFERENCES upload_logs(id) ON DELETE CASCADE,
    produced_by TEXT NOT NULL,
    points NUMERIC(20, 6) NOT NULL,
    week_start_date DATE NOT NULL,
    week_end_date DATE NOT NULL,
    created_date TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_album_upload_log_id
ON raw_album_data(upload_log_id);

ALTER TABLE raw_album_data
ALTER COLUMN album_points TYPE NUMERIC(20, 6) USING album_points::NUMERIC(20, 6),
ALTER COLUMN spotify_equivalent_points TYPE NUMERIC(20, 6) USING spotify_equivalent_points::NUMERIC(20, 6);

ALTER TABLE cleaned_album_data
ALTER COLUMN total_points TYPE NUMERIC(20, 6) USING total_points::NUMERIC(20, 6);

CREATE INDEX IF NOT EXISTS idx_raw_album_source_sheet
ON raw_album_data(source_sheet);

CREATE INDEX IF NOT EXISTS idx_cleaned_album_upload_log_id
ON cleaned_album_data(upload_log_id);

CREATE INDEX IF NOT EXISTS idx_cleaned_album_album
ON cleaned_album_data(album);

CREATE INDEX IF NOT EXISTS idx_cleaned_album_week
ON cleaned_album_data(week_start_date, week_end_date);

CREATE INDEX IF NOT EXISTS idx_raw_artiste_genre_upload_log_id
ON raw_artiste_genre_metadata(upload_log_id);

CREATE INDEX IF NOT EXISTS idx_raw_artiste_genre_source_sheet
ON raw_artiste_genre_metadata(source_sheet);

CREATE INDEX IF NOT EXISTS idx_weekly_metadata_artiste_upload_log_id
ON weekly_metadata_cleaned_artiste(upload_log_id);

CREATE INDEX IF NOT EXISTS idx_weekly_metadata_artiste_name
ON weekly_metadata_cleaned_artiste(artiste);

CREATE INDEX IF NOT EXISTS idx_weekly_metadata_artiste_week
ON weekly_metadata_cleaned_artiste(week_start_date, week_end_date);

CREATE INDEX IF NOT EXISTS idx_weekly_metadata_genre_upload_log_id
ON weekly_metadata_cleaned_genre(upload_log_id);

CREATE INDEX IF NOT EXISTS idx_weekly_metadata_genre_name
ON weekly_metadata_cleaned_genre(genre);

CREATE INDEX IF NOT EXISTS idx_weekly_metadata_genre_week
ON weekly_metadata_cleaned_genre(week_start_date, week_end_date);

CREATE INDEX IF NOT EXISTS idx_weekly_metadata_producers_upload_log_id
ON weekly_metadata_cleaned_producers(upload_log_id);

CREATE INDEX IF NOT EXISTS idx_weekly_metadata_producers_name
ON weekly_metadata_cleaned_producers(produced_by);

CREATE INDEX IF NOT EXISTS idx_weekly_metadata_producers_week
ON weekly_metadata_cleaned_producers(week_start_date, week_end_date);

ALTER TABLE raw_artiste_genre_metadata
ALTER COLUMN points TYPE NUMERIC(20, 6) USING points::NUMERIC(20, 6);

ALTER TABLE weekly_metadata_cleaned_artiste
ALTER COLUMN points TYPE NUMERIC(20, 6) USING points::NUMERIC(20, 6);

ALTER TABLE weekly_metadata_cleaned_genre
ALTER COLUMN points TYPE NUMERIC(20, 6) USING points::NUMERIC(20, 6);

ALTER TABLE weekly_metadata_cleaned_producers
ALTER COLUMN points TYPE NUMERIC(20, 6) USING points::NUMERIC(20, 6);

WITH replaced_uploads AS (
    SELECT id
    FROM upload_logs
    WHERE is_current = FALSE
)
DELETE FROM raw_artiste_genre_metadata
USING replaced_uploads
WHERE raw_artiste_genre_metadata.upload_log_id = replaced_uploads.id;

WITH replaced_uploads AS (
    SELECT id
    FROM upload_logs
    WHERE is_current = FALSE
)
DELETE FROM weekly_metadata_cleaned_artiste
USING replaced_uploads
WHERE weekly_metadata_cleaned_artiste.upload_log_id = replaced_uploads.id;

WITH replaced_uploads AS (
    SELECT id
    FROM upload_logs
    WHERE is_current = FALSE
)
DELETE FROM weekly_metadata_cleaned_genre
USING replaced_uploads
WHERE weekly_metadata_cleaned_genre.upload_log_id = replaced_uploads.id;

WITH replaced_uploads AS (
    SELECT id
    FROM upload_logs
    WHERE is_current = FALSE
)
DELETE FROM weekly_metadata_cleaned_producers
USING replaced_uploads
WHERE weekly_metadata_cleaned_producers.upload_log_id = replaced_uploads.id;

DROP INDEX IF EXISTS uq_upload_logs_current_template_week;

CREATE UNIQUE INDEX IF NOT EXISTS uq_upload_logs_current_template_week
ON upload_logs(template_id, week_start_date)
WHERE is_current;
