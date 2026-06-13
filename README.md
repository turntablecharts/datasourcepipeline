# TTC Data Service

A FastAPI application for authenticated data-cleaning workflows. 

1. **Weekly Cleaning Templates**: this lets users download an Excel template, upload a completed workbook (top album data, weekly song metadata) and persist both raw and cleaned album rows to PostgreSQL.

## Overview

The app has three main surfaces:

- **Static UI**: login and dashboard pages served from `src/static_ui`.
- **FastAPI API**: auth, template download, weekly cleaning upload, history, and album-data inspection endpoints.
- **PostgreSQL persistence**: users, upload logs, raw album rows, cleaned album rows, and template metadata.

Current weekly album cleaning behavior:

> Top Album Data

> - Accepts `.xlsx` files only.
> - Requires two sheets:
>  - `album`: `Album`, `Points`
>  - `spotify_equivalent`: `Album`, `Spotify Equivalent`
> - Cleans album names by collapsing whitespace, stripping, and title-casing.
> - Accepts decimal point values and stores them to 6 decimal places.
> - Groups duplicate albums, calculates `Total Points`, sorts output by `Total Points` descending, and writes `Joint Album Data`.
> - Saves raw rows from both sheets and cleaned output rows to the database.
> - Loads are idempotent by template and week range. Re-uploading the same template/week replaces the current linked raw/cleaned rows and records the replacement in `upload_logs`.

## Project Structure

```text
src/
  main.py                         FastAPI app entrypoint
  database.py                     SQLAlchemy engine/session setup
  models.py                       Database models
  schema.py                       Pydantic schemas
  auth/                           Login, JWT, password helpers
  templates/                      Template listing/download endpoints
  weekly_data_cleaning/           Cleaning API, engine, and cleaner clients
  static_ui/                      Login/dashboard HTML and JS

templates_store/                  Downloadable Excel templates
sql/001_album_cleaning_tables.sql Album-cleaning DDL/migration
tests/                            Focused cleaner tests
create_user.py                    Local helper for creating an admin user
requirements.txt                  Python dependencies
```

## Getting Started

### 1. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the repo root:

```bash
SECRET_KEY=dev-secret-change-me
DB_HOST=localhost
DB_PORT=5432
DB_USER=your_postgres_user
DB_PASSWORD=your_postgres_password
DB_NAME=datasourcepipeline
```

### 3. Create the PostgreSQL database

```bash
createdb datasourcepipeline
```

Or create it manually with your preferred PostgreSQL client.

### 4. Run the SQL migration

`Base.metadata.create_all(...)` creates the tables needed to successful runs.


### 5. Create the default admin user

```bash
python create_user.py
```

Default credentials from `create_user.py`:

```text
email: uuuuuu
password: xxxxx
```

Change these for any shared or deployed environment.

### 6. Start the app

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000/static/index.html
```

API docs (swagger):

```text
http://localhost:8000/docs
```

## Using the App

1. Log in from `/static/index.html`.
2. Go to the dashboard.
3. Download `Editorial Top Album Data Template`.
4. Fill the workbook sheets:
   - `album`
   - `spotify_equivalent`
5. Upload the workbook with week start/end dates.
6. The app downloads a cleaned Excel output and stores:
   - upload status in `upload_logs`
   - original workbook rows in `raw_album_data`
   - cleaned totals in `cleaned_album_data`

## Key API Endpoints

Authentication:

```text
POST /auth/login
GET  /auth/me
```

Templates:

```text
GET /templates/
GET /templates/download/{filename}
GET /clean/available-templates
```

Cleaning:

```text
POST /clean/
GET  /clean/history
GET  /clean/raw-album-data
GET  /clean/cleaned-album-data
GET  /clean/album-data
```

`GET /clean/album-data` is currently an alias for cleaned album data.

## Database Tables

Important tables:

- `users`: authenticated application users.
- `upload_logs`: one row per uploaded workbook.
- `raw_album_data`: original rows from both workbook sheets.
- `cleaned_album_data`: final cleaned album totals.
- `templates`: template metadata.

Upload idempotency uses the current dataset identity:

```text
template_id + week_start_date + week_end_date
```

`upload_logs` stores file and replacement metadata:

- `file_hash`
- `is_current`
- `replaces_upload_log_id`
- `replaced_by_upload_log_id`
- `linked_data_cleared`
- `duplicate_file_upload`

Album point columns use `NUMERIC(20, 6)`:

- `raw_album_data.album_points`
- `raw_album_data.spotify_equivalent_points`
- `cleaned_album_data.total_points`

## Running Tests

```bash
python -m pytest tests
```

The cleaner tests build Excel workbooks in memory and verify validation, grouping, album-name cleanup, and output behavior.

## GitHub Actions Deployment

This repo includes `.github/workflows/deploy.yml`.

On every push to `main`, GitHub Actions will:

1. Install Python dependencies.
2. Run `python -m pytest tests`.
3. SSH into the deployment server.
4. Pull the latest `main` branch in the app directory.
5. Install/update `requirements.txt`.
6. Run `sql/001_album_cleaning_tables.sql` if `psql` and DB env vars are available.
7. Restart the configured systemd service.

Add these GitHub repository secrets under **Settings → Secrets and variables → Actions**:

```text
DEPLOY_HOST       Server hostname or IP address
DEPLOY_USER       SSH user
DEPLOY_SSH_KEY    Private SSH key with access to the server
APP_DIR           Absolute path to the cloned repo on the server
DEPLOY_PORT       SSH port, optional, defaults to 22
SERVICE_NAME      systemd service, optional, defaults to datasourcepipeline.service
```

The server should already have:

- the repository cloned at `APP_DIR`
- a production `.env` file in `APP_DIR`
- Python 3 and `python3-venv`
- PostgreSQL client tools if you want Actions to run the SQL migration
- a systemd service that starts the app, for example `datasourcepipeline.service`

A sample systemd unit is available at `deploy/datasourcepipeline.service.example`.
Update its paths to match `APP_DIR`, then install it on the server:

```bash
sudo cp deploy/datasourcepipeline.service.example /etc/systemd/system/datasourcepipeline.service
sudo systemctl daemon-reload
sudo systemctl enable datasourcepipeline.service
sudo systemctl start datasourcepipeline.service
```

## Local HTTPS for Chrome Downloads

Chrome may mark downloads as insecure when the app is served over plain HTTP. For local HTTPS:

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout certs/local.key \
  -out certs/local.crt \
  -days 365 \
  -subj "/CN=localhost"
```

Run the app with TLS:

```bash
uvicorn src.main:app \
  --reload \
  --host 0.0.0.0 \
  --port 8443 \
  --ssl-keyfile certs/local.key \
  --ssl-certfile certs/local.crt
```

Then open:

```text
https://localhost:8443/static/index.html
```

## Notes

- `docker-compose.yml` is currently empty; run PostgreSQL locally or provide your own container setup.
- `templates_store/editorial_top_album_data_template.xlsx` is the currently registered weekly cleaning template.
- New cleaning templates need to be added to `templates_store` and registered in `src/weekly_data_cleaning/engine.py`.
- Keep `.env`, virtual environments, caches, and generated local files out of version control.
