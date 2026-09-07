import csv
import io
import logging
import re
from datetime import date, datetime
from pathlib import Path


class SourceValidationError(ValueError):
    pass


logger = logging.getLogger(__name__)
MIN_DAILY_STREAMS = 1000


def normalize_name(value: str) -> str:
    return " ".join(value.split()).casefold()


def _required(row: dict[str, str], column: str, row_number: int) -> str:
    value = (row.get(column) or "").strip()
    if not value:
        raise SourceValidationError(f"Row {row_number}: {column} is required")
    return value


def _streams(value: str, row_number: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise SourceValidationError(f"Row {row_number}: streams must be an integer") from exc
    if result < 0:
        raise SourceValidationError(f"Row {row_number}: streams must not be negative")
    return result


def _open_dict_reader(path: Path):
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            content = path.read_text(encoding=encoding)
            handle = io.StringIO(content, newline="")
            reader = csv.DictReader(handle)
            if reader.fieldnames:
                return handle, reader
        except UnicodeDecodeError:
            continue
    raise SourceValidationError(f"{path.name}: could not read CSV headers")


def parse_audiomack(path: Path, expected_date: date, run_id: str) -> list[dict]:
    handle, reader = _open_dict_reader(path)
    try:
        required = {"play_date", "isrc", "artist", "title", "geo", "total"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise SourceValidationError(f"{path.name}: missing columns: {', '.join(sorted(missing))}")
        rows = []
        source_row_count = 0
        skipped_rows = []
        for row_number, row in enumerate(reader, start=2):
            source_row_count += 1
            raw_date = _required(row, "play_date", row_number)
            try:
                play_date = datetime.strptime(raw_date, "%Y%m%d").date()
            except ValueError as exc:
                raise SourceValidationError(f"Row {row_number}: invalid play_date {raw_date!r}") from exc
            if play_date != expected_date:
                raise SourceValidationError(f"Row {row_number}: play_date does not match {expected_date.isoformat()}")
            artist = (row.get("artist") or "").strip()
            title = (row.get("title") or "").strip()
            if not artist or not title:
                skipped_rows.append(row_number)
                continue
            country = _required(row, "geo", row_number).upper()
            if not re.fullmatch(r"[A-Z]{2}", country):
                raise SourceValidationError(f"Row {row_number}: geo must be a two-letter country code")
            streams = _streams(row.get("total"), row_number)
            if streams < MIN_DAILY_STREAMS:
                continue
            rows.append({
                "play_date": play_date,
                "isrc": (row.get("isrc") or "").strip() or None,
                "artist": artist,
                "song_title": title,
                "artist_normalized": normalize_name(artist),
                "song_title_normalized": normalize_name(title),
                "country_code": country,
                "streams": streams,
                "source_file": path.name.removesuffix(".asc"),
                "source_row_number": row_number,
                "ingestion_run_id": run_id,
            })
        if skipped_rows:
            logger.warning(
                "Skipped %d Audiomack rows with a blank artist or title in %s (rows: %s)",
                len(skipped_rows),
                path.name,
                ", ".join(map(str, skipped_rows[:20]))
                + (", ..." if len(skipped_rows) > 20 else ""),
            )
    finally:
        handle.close()
    if not source_row_count:
        raise SourceValidationError(f"{path.name}: file contains no data rows")
    return rows


def parse_boomplay(path: Path, expected_date: date, run_id: str) -> list[dict]:
    handle, reader = _open_dict_reader(path)
    try:
        headers = set(reader.fieldnames or [])
        title_column = "Track Title" if "Track Title" in headers else "Song" if "Song" in headers else None
        required = {"Artist", "Ad Supported Plays"}
        missing = required.difference(headers)
        if missing or not title_column:
            names = sorted(missing | ({"Track Title or Song"} if not title_column else set()))
            raise SourceValidationError(f"{path.name}: missing columns: {', '.join(names)}")
        rows = []
        source_row_count = 0
        skipped_rows = []
        for row_number, row in enumerate(reader, start=2):
            source_row_count += 1
            artist = (row.get("Artist") or "").strip()
            title = (row.get(title_column) or "").strip()
            if not artist or not title:
                skipped_rows.append(row_number)
                continue
            streams = _streams(row.get("Ad Supported Plays"), row_number)
            if streams < MIN_DAILY_STREAMS:
                continue
            rows.append({
                "play_date": expected_date,
                "artist": artist,
                "song_title": title,
                "artist_normalized": normalize_name(artist),
                "song_title_normalized": normalize_name(title),
                "streams": streams,
                "source_file": path.name,
                "source_row_number": row_number,
                "ingestion_run_id": run_id,
            })
        if skipped_rows:
            logger.warning(
                "Skipped %d Boomplay rows with a blank artist or title in %s (rows: %s)",
                len(skipped_rows),
                path.name,
                ", ".join(map(str, skipped_rows[:20]))
                + (", ..." if len(skipped_rows) > 20 else ""),
            )
    finally:
        handle.close()
    if not source_row_count:
        raise SourceValidationError(f"{path.name}: file contains no data rows")
    return rows
