# Apple Music streaming data

This module currently provides authenticated Apple Music report uploads,
filesystem staging, upload history, and database models for raw and enriched
data.

## User interface

The **Streaming Data** section of the dashboard contains the Apple Music upload
form. A user can:

- select the reporting week start and end dates;
- upload a `.csv` or `.xlsx` report;
- see whether the file was accepted; and
- view recent Apple Music uploads.

The week end date must be exactly six days after the week start date. Files are
limited to 20 MB.

## API endpoints

Both endpoints require an authenticated user.

### Upload a report

```http
POST /streaming/apple-music/upload
```

Multipart form fields:

- `file`: an Apple Music `.csv` or `.xlsx` report;
- `week_start_date`: an ISO date in `YYYY-MM-DD` format;
- `week_end_date`: an ISO date in `YYYY-MM-DD` format.

The endpoint stores the original file without opening or modifying it. It does
not currently validate spreadsheet columns or insert report rows into the
database.

### List recent uploads

```http
GET /streaming/apple-music/recent
```

The endpoint returns staged uploads in newest-first order. The optional `limit`
query parameter defaults to 20 and is restricted to a maximum of 100.

## Upload storage

Every upload receives a UUID and is stored in its own directory:

```text
uploads/streaming_data/apple_music/<upload_id>/
```

Each directory contains the unchanged report and an `upload.json` manifest:

```text
uploads/streaming_data/apple_music/
└── 19a86e0e-ff19-4e0c-9e30-2cf784d68da0/
    ├── apple_music_week_20.xlsx
    └── upload.json
```

Example manifest:

```json
{
  "upload_id": "19a86e0e-ff19-4e0c-9e30-2cf784d68da0",
  "original_filename": "apple_music_week_20.xlsx",
  "stored_file": "apple_music_week_20.xlsx",
  "week_start_date": "2026-05-11",
  "week_end_date": "2026-05-17",
  "uploaded_by_user_id": 1,
  "uploaded_by": "user@example.com",
  "status": "uploaded"
}
```

The manifest provides the reporting dates and uploader information that are not
necessarily part of the uploaded report.

## Available database models

The following SQLAlchemy models are defined in `src/models.py`:

- `AppleMusicRaw`, mapped to `apple_music_raw`, for validated report rows;
- `AppleMusicMetadata`, mapped to `apple_music_metadata`, for enriched song
  metadata.

The upload endpoint does not currently write to either table.

## Pipeline files

The module contains three empty pipeline files ready for implementation:

- `ingestion.py`: file discovery, report parsing, validation, and raw inserts;
- `processor.py`: processing and enrichment coordination;
- `spotify_client.py`: Spotify authentication, search, matching, and metadata
  retrieval.

The staged report path can be obtained by reading `upload.json` and joining its
`stored_file` value to the directory containing the manifest.

## Current metadata note

The enriched model contains `apple_music_song_id`, while Spotify returns a
Spotify track ID. The intended identifier should be confirmed before enriched
records are written. Producer and distributor information may also require a
source other than Spotify.
