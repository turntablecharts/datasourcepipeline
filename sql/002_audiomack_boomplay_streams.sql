CREATE TABLE IF NOT EXISTS streaming_ingestion_run_logs (
    id VARCHAR(36) PRIMARY KEY,
    platform VARCHAR(32) NOT NULL,
    week_start_date DATE NOT NULL,
    week_end_date DATE NOT NULL,
    trigger VARCHAR(20) NOT NULL DEFAULT 'scheduled',
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    expected_file_count INTEGER NOT NULL DEFAULT 7,
    downloaded_file_count INTEGER NOT NULL DEFAULT 0,
    loaded_file_count INTEGER NOT NULL DEFAULT 0,
    loaded_row_count INTEGER NOT NULL DEFAULT 0,
    missing_dates TEXT,
    warning_count INTEGER NOT NULL DEFAULT 0,
    error_detail TEXT,
    notification_status VARCHAR(32),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_streaming_runs_platform_week
    ON streaming_ingestion_run_logs (platform, week_start_date, week_end_date);
CREATE INDEX IF NOT EXISTS idx_streaming_runs_started_at
    ON streaming_ingestion_run_logs (started_at);

CREATE TABLE IF NOT EXISTS audiomack_streams (
    id BIGSERIAL PRIMARY KEY,
    play_date DATE NOT NULL,
    isrc VARCHAR(32),
    artist TEXT NOT NULL,
    song_title TEXT NOT NULL,
    artist_normalized TEXT NOT NULL,
    song_title_normalized TEXT NOT NULL,
    country_code VARCHAR(2) NOT NULL,
    streams BIGINT NOT NULL CONSTRAINT ck_audiomack_streams_minimum_daily_streams CHECK (streams >= 1000),
    source_file TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    ingestion_run_id VARCHAR(36) NOT NULL REFERENCES streaming_ingestion_run_logs(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audiomack_streams_date_country
    ON audiomack_streams (play_date, country_code);
CREATE INDEX IF NOT EXISTS idx_audiomack_streams_aggregation
    ON audiomack_streams (play_date, song_title_normalized, artist_normalized);
CREATE INDEX IF NOT EXISTS idx_audiomack_streams_run
    ON audiomack_streams (ingestion_run_id);

CREATE TABLE IF NOT EXISTS boomplay_streams (
    id BIGSERIAL PRIMARY KEY,
    play_date DATE NOT NULL,
    artist TEXT NOT NULL,
    song_title TEXT NOT NULL,
    artist_normalized TEXT NOT NULL,
    song_title_normalized TEXT NOT NULL,
    streams BIGINT NOT NULL CONSTRAINT ck_boomplay_streams_minimum_daily_streams CHECK (streams >= 1000),
    source_file TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    ingestion_run_id VARCHAR(36) NOT NULL REFERENCES streaming_ingestion_run_logs(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_boomplay_streams_date
    ON boomplay_streams (play_date);
CREATE INDEX IF NOT EXISTS idx_boomplay_streams_aggregation
    ON boomplay_streams (play_date, song_title_normalized, artist_normalized);
CREATE INDEX IF NOT EXISTS idx_boomplay_streams_run
    ON boomplay_streams (ingestion_run_id);
