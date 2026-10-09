-- Weekly qualification permits daily aggregates below 1,000 streams.
-- Reingest affected reporting weeks to recover previously excluded source rows.
BEGIN;
ALTER TABLE boomplay_streams
    DROP CONSTRAINT IF EXISTS ck_boomplay_streams_minimum_daily_streams,
    DROP CONSTRAINT IF EXISTS ck_boomplay_streams_nonnegative,
    ADD CONSTRAINT ck_boomplay_streams_nonnegative CHECK (streams >= 0);
COMMIT;
