-- Raise the daily ingestion threshold from 500 to 1,000 streams.
-- Review affected row counts and back up the database before applying.
-- Existing ingestion run logs are preserved.

BEGIN;

LOCK TABLE audiomack_streams, boomplay_streams IN ACCESS EXCLUSIVE MODE;

DELETE FROM audiomack_streams WHERE streams < 1000;
DELETE FROM boomplay_streams WHERE streams < 1000;

ALTER TABLE audiomack_streams
    DROP CONSTRAINT IF EXISTS ck_audiomack_streams_minimum_daily_streams,
    ADD CONSTRAINT ck_audiomack_streams_minimum_daily_streams CHECK (streams >= 1000);

ALTER TABLE boomplay_streams
    DROP CONSTRAINT IF EXISTS ck_boomplay_streams_minimum_daily_streams,
    ADD CONSTRAINT ck_boomplay_streams_minimum_daily_streams CHECK (streams >= 1000);

COMMIT;
