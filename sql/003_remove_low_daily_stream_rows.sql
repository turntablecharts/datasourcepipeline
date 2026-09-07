-- One-time cleanup for databases populated before the daily >= 500 threshold.
-- Review row counts and take a database backup before applying this migration.

BEGIN;

DELETE FROM audiomack_streams WHERE streams < 500;
DELETE FROM boomplay_streams WHERE streams < 500;

ALTER TABLE audiomack_streams
    ADD CONSTRAINT ck_audiomack_streams_minimum_daily_streams CHECK (streams >= 500);

ALTER TABLE boomplay_streams
    ADD CONSTRAINT ck_boomplay_streams_minimum_daily_streams CHECK (streams >= 500);

COMMIT;
