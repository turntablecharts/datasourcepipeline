CREATE TABLE IF NOT EXISTS upload_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    username VARCHAR NOT NULL,
    template_id VARCHAR NOT NULL,
    original_filename VARCHAR,
    week_start_date DATE NOT NULL,
    week_end_date DATE NOT NULL,
    rows_input INTEGER NOT NULL DEFAULT 0,
    rows_output INTEGER NOT NULL DEFAULT 0,
    status VARCHAR NOT NULL,
    error_detail TEXT,
    created_date TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE upload_logs
ADD COLUMN IF NOT EXISTS original_filename VARCHAR;

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

CREATE TABLE IF NOT EXISTS raw_album_data (
    id SERIAL PRIMARY KEY,
    upload_log_id INTEGER NOT NULL REFERENCES upload_logs(id) ON DELETE CASCADE,
    source_sheet VARCHAR NOT NULL,
    row_number INTEGER NOT NULL,
    original_album TEXT,
    album_points BIGINT,
    spotify_equivalent_points BIGINT,
    created_date TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cleaned_album_data (
    id SERIAL PRIMARY KEY,
    upload_log_id INTEGER NOT NULL REFERENCES upload_logs(id) ON DELETE CASCADE,
    album TEXT NOT NULL,
    total_points BIGINT NOT NULL,
    week_start_date DATE NOT NULL,
    week_end_date DATE NOT NULL,
    created_date TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_album_upload_log_id
ON raw_album_data(upload_log_id);

CREATE INDEX IF NOT EXISTS idx_raw_album_source_sheet
ON raw_album_data(source_sheet);

CREATE INDEX IF NOT EXISTS idx_cleaned_album_upload_log_id
ON cleaned_album_data(upload_log_id);

CREATE INDEX IF NOT EXISTS idx_cleaned_album_album
ON cleaned_album_data(album);

CREATE INDEX IF NOT EXISTS idx_cleaned_album_week
ON cleaned_album_data(week_start_date, week_end_date);
