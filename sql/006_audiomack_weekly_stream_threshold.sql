-- Allow daily aggregates below 1,000; Audiomack qualification is now weekly.
-- Reingest affected weeks to restore source rows removed by the old daily filter.
BEGIN;
ALTER TABLE audiomack_streams
    DROP CONSTRAINT IF EXISTS ck_audiomack_streams_minimum_daily_streams,
    DROP CONSTRAINT IF EXISTS ck_audiomack_streams_nonnegative,
    ADD CONSTRAINT ck_audiomack_streams_nonnegative CHECK (streams >= 0);
COMMIT;
