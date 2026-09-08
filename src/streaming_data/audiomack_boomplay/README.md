# Audiomack and Boomplay automation

The scheduled job attempts to ingest the preceding Friday–Thursday reporting week every Monday at 7:45 AM. Missing remote files result in a completed `partial` run and an optional Slack warning; available files still load. Rerunning ingestion for the same week retries a partial week, while a platform/week that already succeeded is skipped. Actual connection, decryption, validation, and database errors are failures.

Only source rows with at least **1,000 streams on that individual day** are persisted for either platform. The threshold is applied before database insertion and before any multi-day export aggregation. A valid source file whose rows are all below 1,000 still counts as a successfully processed file and inserts zero rows.

Export requests perform date/country filtering, song aggregation, stream summing, sorting, and tie-inclusive top-500/top-800 ranking in PostgreSQL. Python receives only the final aggregated result rows and formats them into Excel.

## Commands

```bash
python -m src.streaming_data.audiomack_boomplay.cli ingest-latest-week
python -m src.streaming_data.audiomack_boomplay.cli ingest-week --start-date 2026-07-24
```

The explicit start date must be a Friday.

## Admin backfills

Admins see a `Configurations` tab in the Data Service UI. Its Audiomack/Boomplay Backfill form accepts any inclusive start and end date up to 366 days. The API returns `202 Accepted`, then processes the range in seven-day chunks in the background so the browser request does not remain open for a long import.

```text
POST /streaming/audiomack-boomplay/backfill?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

Each platform/chunk creates an entry in `streaming_ingestion_run_logs` with trigger `backfill`. Available source files replace that platform/date's stored rows, while missing files remain non-fatal warnings. The endpoint enforces the admin role server-side; hiding the tab is only a UI convenience.

## Database

Apply `sql/002_audiomack_boomplay_streams.sql` for a new production database. The app's `Base.metadata.create_all()` also creates the models in local environments.

For a database that already contains streaming rows, review and separately apply `sql/004_raise_daily_stream_threshold.sql`. It deletes previously stored rows below 1,000 and adds database constraints preventing them from being inserted again. Back up the database and review the affected row counts before running this destructive cleanup migration.

## Scheduler

APScheduler starts and stops with the FastAPI application. It runs the latest completed Friday–Thursday period every Monday at 7:45 AM in `STREAMING_TIMEZONE` (default `Africa/Lagos`). Restart the application after changing the schedule. The application must be running at the scheduled time; runs missed while it is stopped are not replayed on startup.

There are no additional scheduled retries. Use the CLI to rerun a partial week. Successfully completed platform/week combinations are skipped on reruns, and the existing PostgreSQL advisory lock prevents overlapping ingestion for the same platform/week.

Run the FastAPI application with exactly one Uvicorn/Gunicorn worker. Each worker is a separate process and would otherwise start its own scheduler. The current `deploy/datasourcepipeline.service.example` starts one Uvicorn process and is compatible with this setup.

## Alerts

Set `SLACK_WEBHOOK_URL` to enable Block Kit notifications for success, partial/missing-file, and failure outcomes. Alerts show the platform, date range, processed file count, qualifying rows stored, missing dates, and run ID. Failure messages include a safe error type/count and direct operators to the service logs without exposing credentials or raw source data. Alert delivery failures are recorded on the ingestion run and never roll back loaded data.
