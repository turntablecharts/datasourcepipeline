# Audiomack and Boomplay Automation — Implementation Plan

## 1. Goal

Automate the weekly Audiomack and Boomplay ingestion process so that:

- Every Saturday at 10:00 AM, the system attempts to fetch the seven daily source files for the immediately completed reporting week (Friday through Thursday).
- Audiomack `.csv.asc` files are decrypted and both platforms' files are validated and loaded into PostgreSQL.
- Source-level data is stored in `audiomack_streams` and `boomplay_streams`.
- Only source rows with at least 1,000 streams on that individual day are stored. The threshold is applied before multi-day aggregation.
- Authenticated users can select any inclusive start and end date and download totals aggregated by song.
  - Boomplay returns the top 500 positions after aggregation, including every song tied on streams at the 500th position.
  - Audiomack returns the top 800 positions independently for each selected country, including every song tied on streams at that country's 800th position.
- Audiomack users can select one or more countries. A multi-country download is an Excel workbook with one sheet per selected country.
- Re-running a week is safe and does not duplicate streams.

Example: a job running Saturday, 1 August 2026 at 10:00 AM processes Friday, 24 July 2026 through Thursday, 30 July 2026.

## 2. Confirmed source formats

### Audiomack daily source

The sample `audiomack_streams_20260717.csv` contains 813 rows with:

| Source column | Example | Stored as |
|---|---|---|
| `play_date` | `20260717` | `DATE` (`2026-07-17`) |
| `isrc` | `USUYG1804321` | text |
| `artist` | `Asake` | text |
| `title` | `Gratitude` | text |
| `geo` | `NG` | two-letter country code |
| `total` | `208714` | `BIGINT` |

The sample contains `NG` and `GH`, confirming that country must be retained rather than discarded during transformation.

### Boomplay data

The supplied `Boomplay_20260717_20260723.csv` is a weekly aggregated output with:

- `Artist`
- `Song`
- `Ad Supported Plays`

The FTP downloader currently expects daily files named `Boomplay_NG_YYYYMMDD.csv`, and the legacy transform expects the raw title column to be `Track Title`. The first implementation task must capture one current FTP source file and confirm whether the incoming daily schema is:

1. `Artist`, `Track Title`, `Ad Supported Plays`, or
2. `Artist`, `Song`, `Ad Supported Plays`.

The parser should accept both title headers, but reject other schema changes with an actionable ingestion error. Because the daily Boomplay file has no date column, derive and store `play_date` from the `YYYYMMDD` portion of its FTP filename.

## 3. Proposed architecture

Keep this feature within `src/streaming_data/audiomack_boomplay/` and separate each responsibility:

```text
src/streaming_data/audiomack_boomplay/
  __init__.py
  config.py            Environment-backed FTP, GPG, timezone, and path settings
  dates.py             Friday–Thursday reporting-window calculation
  ftp_client.py        FTP connection, listing, and atomic downloads
  decryptor.py         Audiomack GPG decryption
  parsers.py           Schema validation and typed row parsing
  repository.py        Transactional/idempotent database writes and export queries
  ingestion.py         End-to-end orchestration for one reporting week
  exports.py           Excel workbook generation and safe sheet naming
  router.py            Countries, ingestion-status, manual-run, and download endpoints
  cli.py               Scheduler-safe command-line entry point
  scheduler.py         APScheduler job managed by the FastAPI lifespan
  IMPLEMENTATION_PLAN.md

tests/
  streaming_data/audiomack_boomplay/
```

Run APScheduler inside the FastAPI process, matching the deployment pattern used by the existing scheduled service. Production must use exactly one API worker so only one scheduler is created; the PostgreSQL advisory lock remains a secondary overlap safeguard. The CLI remains available for manual and external execution.

## 4. Database design

Add the following SQLAlchemy models and a versioned SQL migration. `Base.metadata.create_all()` can remain a local convenience, but production deployment should explicitly apply the migration.

### `audiomack_streams`

| Column | Type | Notes |
|---|---|---|
| `id` | big integer PK | Surrogate key |
| `play_date` | date, not null | Source `play_date` |
| `isrc` | varchar, nullable | Preserve missing/invalid ISRCs for review |
| `artist` | text, not null | Display value from source |
| `song_title` | text, not null | Display value from source |
| `artist_normalized` | text, not null | Trimmed, whitespace-collapsed, case-folded |
| `song_title_normalized` | text, not null | Trimmed, whitespace-collapsed, case-folded |
| `country_code` | varchar(2), not null | Uppercase source `geo` |
| `streams` | bigint, not null | Source `total`; must be at least 1,000 for that day |
| `source_file` | text, not null | FTP filename |
| `source_row_number` | integer, not null | Traceability to source row |
| `ingestion_run_id` | UUID/FK, not null | Links row to its load |
| `created_at` | timestamptz | Server timestamp |

Indexes:

- `(play_date, country_code)` for export filtering.
- `(play_date, song_title_normalized, artist_normalized)` for aggregation.
- `(ingestion_run_id)` for audit and replacement.

### `boomplay_streams`

Use the same common columns except `isrc` and `country_code`. This implementation stores Nigeria-only Boomplay data and intentionally does not add a country column. Supporting other Boomplay countries later will require an explicit schema migration and corresponding API/UI changes.

- `play_date`
- `artist`, `song_title`
- normalized artist/title fields
- `streams` from `Ad Supported Plays`
- source filename, row number, run ID, and created timestamp

Indexes should cover `play_date` and the normalized aggregation fields.

### `streaming_ingestion_run_logs`

Track each scheduled or manual attempt:

- `id` (UUID)
- `platform`
- `week_start_date` and `week_end_date`
- `trigger` (`scheduled` or `manual`)
- `status` (`running`, `succeeded`, `partial`, `failed`)
- expected/downloaded/loaded file and row counts
- `started_at`, `completed_at`
- structured error summary (without credentials/passphrases)

Enforce at most one successful current load per platform/reporting week. A retry should stage and validate all seven files, then transactionally replace that platform/week's rows. This is safer than relying on a row-level natural key because source files may legitimately contain repeated track identifiers.

## 5. Weekly ingestion flow

1. Calculate the most recently completed Friday–Thursday window in the configured business timezone (`Africa/Lagos` by default).
2. Acquire a PostgreSQL advisory lock for the platform/week so overlapping scheduled or manual runs cannot race.
3. Create an ingestion-run record.
4. Generate the fourteen expected FTP names:
   - `audiomack_streams_YYYYMMDD.csv.asc`
   - `Boomplay_NG_YYYYMMDD.csv`
5. Download each file to a unique temporary staging directory using a `.part` suffix and rename it only after a complete transfer.
6. Decrypt Audiomack files using GPG in non-interactive/batch mode. Make `GPG_BINARY` configurable instead of hard-coding `/opt/homebrew/bin/gpg`.
7. Validate every file that is available before changing database rows:
   - record which of the seven expected dates are available and which are missing;
   - missing dates do not fail or stop the pipeline, but are recorded as warnings and included in the Slack alert;
   - the date in every row matches the expected file date;
   - required headers are present;
   - streams are integers greater than or equal to zero;
   - after validation, retain only rows with at least 1,000 streams for that individual source date; a valid file with no qualifying rows still loads successfully with zero stored rows;
   - artist/title are non-empty;
   - Audiomack country codes are non-empty uppercase ISO-style two-letter values;
   - files are non-empty and parse successfully with an explicit encoding fallback policy.
8. Load each available date in its own safe transaction. Replace rows only for the platform/date represented by that validated source file; do not delete or replace missing dates.
9. Mark the platform run `succeeded` when all seven dates load, or `partial` when one or more dates are missing. A `partial` run is a completed pipeline run, not a pipeline failure. If one platform has a processing error, retain data already committed for the other platform/dates and record the error on the affected run.
10. Remove the temporary plaintext and encrypted files in a `finally` block. Never retain decrypted Audiomack data on disk after a successful or failed attempt beyond the configured troubleshooting policy.

Missing files must not fail the pipeline and must not cause a non-zero process exit. The run should finish as `partial`, retain all successfully loaded dates, list the missing dates in ingestion history, and send a Slack warning. Configure bounded follow-up retries (for example, at 10:30 and 11:30) because upstream delivery can be late. A retry processes only dates that are still missing or explicitly selected for replacement, so previously loaded dates are not duplicated. Actual FTP connection, decryption, validation, or database errors should be recorded separately from a normal missing-file warning and determine the process exit code according to whether useful ingestion work could complete.

## 6. Scheduling and operations

Create a one-shot CLI such as:

```bash
python -m src.streaming_data.audiomack_boomplay.cli ingest-latest-week
```

Start APScheduler through the FastAPI lifespan handler and stop it during application shutdown. Schedule Saturday at 10:00 AM in `Africa/Lagos`, with follow-up attempts at 10:30 AM and 11:30 AM. Successful platform/week combinations are skipped during retries.

Required environment variables:

```text
FTP_HOST=
FTP_USER=
FTP_PASS=
GPG_PASSPHRASE=
GPG_BINARY=/usr/bin/gpg
STREAMING_TIMEZONE=Africa/Lagos
STREAMING_STAGING_DIR=/var/tmp/datasourcepipeline/streaming
```

Operational requirements:

- Use `FTP_TLS` if the provider supports it; otherwise document that plain FTP exposes credentials/data in transit and restrict network access accordingly.
- Set connection/data timeouts and always call `quit()`/close the session.
- Log run ID, platform, reporting dates, filenames, counts, duration, and failure type; never log secrets or decrypted row contents.
- Add a lightweight admin-only manual retry endpoint/command accepting a Friday start date. The end date is derived as Thursday to prevent malformed weeks.
- Add an ingestion-history endpoint and display the most recent run/status in the UI.

## 7. Download API

Add authenticated routes under the existing `/streaming` router.

### Reference-data endpoints

```text
GET /streaming/audiomack/countries?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
GET /streaming/audiomack/coverage
GET /streaming/boomplay/coverage
GET /streaming/audiomack-boomplay/ingestion-runs
```

`countries` returns distinct country codes present in the requested range. Coverage endpoints return the earliest/latest available dates and missing dates so the UI can warn users before export.

### Export endpoints

```text
GET /streaming/audiomack/export?start_date=...&end_date=...&countries=NG&countries=GH
GET /streaming/boomplay/export?start_date=...&end_date=...
```

Validation:

- Dates are required, inclusive, and `start_date <= end_date`.
- Apply a configurable maximum range (initially 366 days) to protect the API.
- Audiomack requires at least one available country and rejects unknown codes.
- Return `404`/`422` with a clear message when the range has no data or is invalid.

Aggregation:

- Filter rows by inclusive `play_date` and, for Audiomack, selected country.
- Perform filtering, grouping, summing, sorting, and tie-inclusive ranking in PostgreSQL when the export request is made. Python receives only the final aggregated rows for workbook generation.
- Group on `artist_normalized + song_title_normalized`, sum `streams`, and sort by streams descending then artist/title ascending.
- For Boomplay, determine the stream total at position 500 and include all rows with totals greater than or equal to that cutoff. The report can therefore contain more than 500 rows when songs are tied at the cutoff.
- For Audiomack, apply the same cutoff independently inside each country sheet at position 800. A country sheet can contain more than 800 rows when songs are tied at its cutoff. If a result contains fewer than 500 or 800 aggregated songs, return all available songs.
- Use stream total alone to determine cutoff ties. Artist/title ordering is deterministic presentation ordering and must not exclude tied songs.
- Return display artist/title deterministically (for example, the most recently ingested spelling) rather than applying `.title()`, which can damage stylized names.
- Include columns `Artist`, `Song`, and `Streams`.

Although the UI describes this as aggregation by song title, artist must remain part of the grouping key to avoid combining unrelated songs with identical titles. If title-only grouping is a strict business requirement, change this explicitly before implementation.

Export format:

- Boomplay: one `.xlsx` sheet named `Boomplay NG`.
- Audiomack: one `.xlsx` sheet per selected country, using names such as `NG` and `GH`.
- Every sheet repeats the same three columns and contains that country's independent aggregation.
- Sanitize/deduplicate sheet names and respect Excel's 31-character limit.
- Freeze the header, enable filters, format stream counts with thousands separators, set practical column widths, and include the selected period in the filename, for example `Audiomack_2026-07-17_2026-07-23.xlsx`.
- Generate workbooks in memory or in a request-scoped temporary file and delete temporary output after the response closes.

## 8. UI changes

Extend the existing Streaming Data dashboard with an `Audiomack / Boomplay` download panel:

1. Platform selector: Audiomack or Boomplay.
2. Inclusive start and end date inputs, constrained by the selected platform's available coverage.
3. Audiomack-only searchable multi-select populated from the countries endpoint.
4. Download button with loading, success, empty-range, and error states.
5. Coverage/missing-date warning so users know when an export is incomplete.
6. Admin-only ingestion status and retry controls, if the current user's role permits them.

Add an admin-only `Configurations` tab with an Audiomack/Boomplay backlog form. It accepts an inclusive start/end date, queues the work in the background, processes long ranges in seven-day chunks, and displays activity from `streaming_ingestion_run_logs`. Enforce admin authorization on the API, not only by hiding the tab.

The browser should download the authenticated binary response using its `Content-Disposition` filename. Preserve the current Apple Music upload workflow as a separate subsection.

## 9. Testing strategy

### Unit tests

- Reporting-window calculation around Fridays, Saturdays, month/year boundaries, and timezone-aware timestamps.
- Filename generation for exactly seven inclusive dates.
- Audiomack and both supported Boomplay title headers.
- Numeric/date/country validation and malformed/empty files.
- Name normalization without destroying display capitalization.
- Workbook sheet naming and multi-country separation.

### Database/integration tests

- Seven daily files produce the expected row counts and totals.
- Daily source rows below 1,000 are not stored, rows at exactly 1,000 are stored, and filtering happens before weekly or arbitrary-range aggregation.
- One or more missing daily files produce a successful `partial` run, load all available dates, preserve any existing rows for missing dates, and record the missing-date warning.
- A later retry fills previously missing dates without duplicating dates that already loaded.
- A second run of the same week replaces data without duplication.
- A failed validation leaves the previously successful week untouched.
- Concurrent runs are rejected/serialized by the advisory lock.
- Inclusive arbitrary-range queries aggregate correctly across week boundaries.
- Identical song titles by different artists remain separate.
- Audiomack selected countries never leak into one another's sheets.
- Boomplay returns the top 500 positions and includes all songs tied on streams at the 500th-position cutoff.
- Each Audiomack country independently returns the top 800 positions and includes all songs tied on streams at that country's 800th-position cutoff.

### API/UI tests

- Authentication and admin authorization.
- Invalid ranges, unavailable countries, empty results, and maximum-range enforcement.
- Correct response MIME type and filename.
- Excel workbook contents for one and multiple Audiomack countries and for Boomplay.
- Dashboard platform switching, country multi-select, download, and visible failures.

Use the supplied samples as fixtures after replacing artist/track values if production data must not be committed. Add a seven-day synthetic fixture because the supplied Audiomack file represents one day and the Boomplay file is already aggregated.

## 10. Delivery phases

### Phase 1 — Foundations

- Confirm the live Boomplay daily FTP schema and GPG binary location on the server.
- Add configuration, date logic, SQLAlchemy models, migration, and ingestion-run tracking.
- Add sanitized test fixtures derived from both samples.

### Phase 2 — Reliable ingestion

- Implement FTP download, GPG decryption, validation, transactions, advisory locking, cleanup, and CLI.
- Backfill a chosen historical period using the same CLI, one week at a time.
- Reconcile per-day/per-week database totals against the manual script outputs.

### Phase 3 — Scheduling and observability

- Start and stop APScheduler through the FastAPI lifespan and verify its `Africa/Lagos` trigger times.
- Confirm production runs exactly one API worker and run a manual CLI invocation.
- Add ingestion history/status and retry behavior.

### Phase 4 — Export API and UI

- Add coverage/country/export endpoints.
- Add the dashboard controls and `.xlsx` download behavior.
- Verify multi-country sheets and arbitrary date ranges.

### Phase 5 — Production acceptance

- Run one scheduled week in parallel with the manual process.
- Compare file counts, row counts, distinct countries, and total streams by platform/date/country.
- Accept only when totals match, retries are idempotent, missing-file behavior is safe, and downloaded workbooks match the selected range.
- Retire the manual `app.py` flow after successful reconciliation.

## 11. Decisions to confirm before implementation

1. Confirm `Africa/Lagos` as the production scheduling timezone. - yes
2. Confirm whether Boomplay's live daily source uses `Track Title` or `Song` (the parser can support both). support both
3. Confirm artist + song as the aggregation key; this plan recommends it over title-only grouping. yes
4. Confirm whether users may export incomplete date ranges when one or more daily files are missing. This plan allows the export but displays a coverage warning; strict rejection can be enabled instead. yes
5. Confirm the initial historical backfill start date and retention policy for ingestion-run/error records. yes

## 12. Definition of done

- A Saturday 10:00 AM run automatically selects the preceding Friday–Thursday dates.
- Every available expected file is downloaded, Audiomack files are decrypted, and valid rows are stored at daily granularity; missing files produce a `partial` run and warning without failing the pipeline.
- Failed or repeated runs do not corrupt or duplicate an existing week.
- The database exposes traceable ingestion status and date coverage.
- An authenticated user can download any valid inclusive period aggregated by artist/song.
- Boomplay and Audiomack exports enforce their respective 500/800 cutoffs while including all songs tied on streams at the cutoff position.
- Audiomack multi-country exports contain one correct, isolated worksheet per country.
- Automated tests pass, a scheduled production run matches the manual totals, and operational setup is documented.


## 13. Alerting

Use the optional `SLACK_WEBHOOK_URL` setting to send a notification after the Saturday run and its bounded retries:

- success when both platforms have complete coverage;
- warning when a platform is partial because expected dates are missing;
- failure for FTP connection, decryption, validation, or database errors.

Messages include the run ID, platform, reporting period, loaded file/row counts, and missing dates, but never credentials, passphrases, or source-row data. Slack delivery failure is recorded on the ingestion run and never rolls back successfully loaded data.
