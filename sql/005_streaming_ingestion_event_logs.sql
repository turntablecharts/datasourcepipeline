CREATE TABLE streaming_ingestion_run_log_events (
    id BIGSERIAL PRIMARY KEY,
    ingestion_run_id VARCHAR(36) NOT NULL
        REFERENCES streaming_ingestion_run_logs(id) ON DELETE CASCADE,
    level VARCHAR(10) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    message TEXT NOT NULL,
    details TEXT,
    source_file TEXT,
    play_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_streaming_run_events_run_created
    ON streaming_ingestion_run_log_events (ingestion_run_id, created_at);

CREATE INDEX idx_streaming_run_events_level_created
    ON streaming_ingestion_run_log_events (level, created_at);
