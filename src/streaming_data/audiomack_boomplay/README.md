# Audiomack and Boomplay automation

The scheduled job attempts to ingest the preceding Friday–Thursday reporting week every Monday at 7:45 AM. Missing remote files result in a completed `partial` run and an optional Slack warning; available files still load. Rerunning ingestion for the same week retries a partial week, while a platform/week that already succeeded is skipped. Actual connection, decryption, validation, and database errors are failures.

Audiomack combines source rows by `play_date + artist + title + geo`, summing streams across ISRCs. It then sums each `artist + title + geo` combination over its Friday–Thursday reporting week and retains daily aggregates only for songs with at least **2,000 weekly streams**. Artist and title grouping uses trimmed source values. Daily counts below 2,000 are retained for qualifying songs. A merged row keeps the first source row number; its ISRC is null when contributing ISRCs differ. All available files are parsed before any stream records are replaced; a parsing/decryption failure prevents that Audiomack period from being written. Missing files still produce a partial run, with qualification based on available days; rerun the full week when they arrive. Boomplay also uses pandas to combine daily entries by artist and title, then retains their daily aggregates only when the Friday–Thursday song total reaches 2,000 streams. Both platforms parse all available files before writing stream records.

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

Both platforms expand each requested chunk to full Friday–Thursday weeks so weekly totals are not split by chunk boundaries. This can also replace dates outside the original request, and overlapping chunks may reprocess a week.

Each platform/chunk creates an entry in `streaming_ingestion_run_logs` with trigger `backfill`. Available source files replace that platform/date's stored rows, while missing files remain non-fatal warnings. The endpoint enforces the admin role server-side; hiding the tab is only a UI convenience.

## Database

Apply `sql/002_audiomack_boomplay_streams.sql` for a new production database. The app's `Base.metadata.create_all()` also creates the models in local environments.

For an existing database, apply `sql/006_audiomack_weekly_stream_threshold.sql` after prior migrations to replace the Audiomack daily minimum constraint with a nonnegative-stream constraint. Reingest affected weeks to recover source rows excluded by the previous daily filter; use a manual ingestion or backfill because successful scheduled runs are skipped. Apply `sql/007_boomplay_weekly_stream_threshold.sql` as well to remove Boomplay's old daily minimum constraint. Neither migration rewrites existing data; reingest both platforms to recover previously filtered streams.

## Scheduler

APScheduler starts and stops with the FastAPI application. It runs the latest completed Friday–Thursday period every Monday at 7:45 AM in `STREAMING_TIMEZONE` (default `Africa/Lagos`). Restart the application after changing the schedule. The application must be running at the scheduled time; runs missed while it is stopped are not replayed on startup.

There are no additional scheduled retries. Use the CLI to rerun a partial week. Successfully completed platform/week combinations are skipped on reruns, and the existing PostgreSQL advisory lock prevents overlapping ingestion for the same platform/week.

Run the FastAPI application with exactly one Uvicorn/Gunicorn worker. Each worker is a separate process and would otherwise start its own scheduler. The current `deploy/datasourcepipeline.service.example` starts one Uvicorn process and is compatible with this setup.

## Alerts

Set `SLACK_WEBHOOK_URL` to enable Block Kit notifications for success, partial/missing-file, and failure outcomes. Alerts show the platform, date range, processed file count, qualifying rows stored, missing dates, and run ID. Failure messages include a safe error type/count and direct operators to the service logs without exposing credentials or raw source data. Alert delivery failures are recorded on the ingestion run and never roll back loaded data.
