import logging
from datetime import date
from pathlib import Path
import pandas as pd


class SourceValidationError(ValueError):
    # Distinguish invalid source data from other ingestion failures.
    pass


logger = logging.getLogger(__name__)  # Use this module's logger for skipped-row warnings.
MIN_WEEKLY_STREAMS = 5000  # Both platforms qualify songs after weekly aggregation.

class ProcessAudiomackBoomplay:
    def __init__(self, run_id: str,):
        self.run_id = run_id

    def normalize_name(self, value: str) -> str:
        # Collapse repeated whitespace and use Unicode-aware case folding for matching.
        return " ".join(value.split()).casefold()


    @staticmethod
    def _read_csv(path: Path) -> pd.DataFrame:
        """ Incase csv file is encoded. Preserve strings (including country code NA)
        and try UTF-8 before Latin-1.
        """
        for encoding in ("utf-8-sig", "latin-1"):
            try:
                return pd.read_csv(path, encoding=encoding, dtype=str, keep_default_na=False)
            except UnicodeDecodeError:
                continue
            except pd.errors.EmptyDataError as exc:
                raise SourceValidationError(f"{path.name}: could not read CSV headers") from exc
        raise SourceValidationError(f"{path.name}: could not decode CSV")


    def parse_audiomack(self, files: list[tuple[date, Path]]) -> list[dict]:
        """Read a reporting period and return qualifying daily records for insertion."""
        frames = []
        for expected_date, path in files:
            audiomack_df = self._read_csv(path)

            required = {"play_date", "isrc", "artist", "title", "geo", "total"}
            missing = required.difference(audiomack_df.columns)
            if missing:
                raise SourceValidationError(f"{path.name}: missing columns: {', '.join(sorted(missing))}")
            source_row_count = len(audiomack_df)
            # A header-only file is invalid; filtering all existing rows is allowed.
            if not source_row_count:
                raise SourceValidationError(f"{path.name}: file contains no data rows")
            # Save CSV row numbers before filtering so warnings keep their source locations.
            audiomack_df["source_row_number"] = range(2, source_row_count + 2)

            # Convert dates; invalid or missing values become NaT.
            dates = pd.to_datetime(
                audiomack_df["play_date"].str.strip(), format="%Y%m%d", errors="coerce"
            ).dt.date
            invalid_dates = dates.isna() | dates.ne(expected_date)
            if invalid_dates.any():
                row_number = audiomack_df.loc[invalid_dates, "source_row_number"].iloc[0]
                raise SourceValidationError(
                    f"Row {row_number}: play_date must match {expected_date.isoformat()}"
                )
            audiomack_df["play_date"] = dates

            #remove whitespaces
            for column in ["artist", "title", "total"]:
                audiomack_df[column] = audiomack_df[column].str.strip()
            #remove empty rows
            blank_values = audiomack_df[["artist", "title", "total"]].eq("").any(axis=1)
            skipped_rows = audiomack_df.loc[blank_values, "source_row_number"].tolist()
            audiomack_df = audiomack_df.loc[~blank_values].copy()

            # Report skipped rows, showing at most 20 source row numbers.
            if skipped_rows:
                logger.warning(
                    "Skipped %d Audiomack rows with a blank artist, title, or total in %s (rows: %s)",
                    len(skipped_rows),
                    path.name,
                    ", ".join(map(str, skipped_rows[:20]))
                    + (", ..." if len(skipped_rows) > 20 else ""),
                )
            # Require a country code containing exactly two letters.
            audiomack_df["geo"] = audiomack_df["geo"].fillna("").str.strip().str.upper()
            invalid_country = ~audiomack_df["geo"].str.fullmatch(r"[A-Z]{2}")
            if invalid_country.any():
                row_number = audiomack_df.loc[invalid_country, "source_row_number"].iloc[0]
                raise SourceValidationError(
                    f"Row {row_number}: geo must be a two-letter country code"
                )

            # convert total streams to integers
            audiomack_df["streams"] = audiomack_df["total"].str.strip().astype(int)
            negative_streams = audiomack_df["streams"].lt(0)
            if negative_streams.any():
                row_number = audiomack_df.loc[negative_streams, "source_row_number"].iloc[0]
                raise SourceValidationError(f"Row {row_number}: streams must not be negative")

            # Rename source fields to match the database columns.
            audiomack_df = audiomack_df.rename(
                columns={"title": "song_title", "geo": "country_code"}
            )
            # Blank ISRCs become null; original display names are kept alongside matching keys.
            audiomack_df["isrc"] = audiomack_df["isrc"].str.strip().replace("", None)
            audiomack_df["artist_normalized"] = audiomack_df["artist"].map(self.normalize_name)
            audiomack_df["song_title_normalized"] = audiomack_df["song_title"].map(self.normalize_name)
            audiomack_df["source_file"] = path.name.removesuffix(".asc")
            audiomack_df["ingestion_run_id"] = self.run_id

            # Select database fields only, then combine same-day entries across ISRCs.
            columns = [
                "play_date", "isrc", "artist", "song_title",
                "artist_normalized", "song_title_normalized",
                "country_code", "streams", "source_file",
                "source_row_number", "ingestion_run_id",
            ]
            frames.append(audiomack_df[columns])

        if not frames:
            return []
        full_audiomack_df = pd.concat(frames, ignore_index=True)
        if full_audiomack_df.empty:
            return []

        # Sum same-day entries for the same artist/title/country combination, keeping one representative row.
        keys = ["play_date", "artist", "song_title", "country_code"]
        aggregated = full_audiomack_df.groupby(keys, sort=False, dropna=False).agg(
            streams=("streams", "sum"),
            # A group with multiple ISRCs will have null isrc in db
            isrc=("isrc", lambda values: values.iloc[0] if values.nunique(dropna=False) == 1 else None),
            artist_normalized=("artist_normalized", "first"),
            song_title_normalized=("song_title_normalized", "first"),
            source_file=("source_file", "first"),
            source_row_number=("source_row_number", "first"),
            ingestion_run_id=("ingestion_run_id", "first"),
        ).reset_index()

        # Qualify songs over each Friday–Thursday week, keeping their daily counts.
        dates = pd.to_datetime(aggregated["play_date"])
        aggregated["week_start"] = dates - pd.to_timedelta((dates.dt.dayofweek - 4) % 7, unit="D")
        weekly_totals = aggregated.groupby(
            ["week_start", "artist", "song_title", "country_code"], sort=False
        )["streams"].transform("sum")
        retained = aggregated.loc[weekly_totals >= MIN_WEEKLY_STREAMS].drop(columns="week_start")
        # SQLAlchemy receives Python None instead of pandas missing values.
        retained = retained.astype(object).where(pd.notna(retained), None)
        return retained.to_dict(orient="records")


    def parse_boomplay(self, files: list[tuple[date, Path]]) -> list[dict]:
        """Read all daily files before applying the weekly song threshold."""
        rows = []
        for expected_date, path in files:
            boomplay_df = self._read_csv(path)
            headers = set(boomplay_df.columns)
            # Accept either title header used by Boomplay, preferring Track Title.
            title_column = "Track Title" if "Track Title" in headers else "Song" if "Song" in headers else None
            required = {"Artist", "Ad Supported Plays"}
            missing = required.difference(headers)
            # Reject files missing any columns needed to build stream records.
            if missing or not title_column:
                names = sorted(missing | ({"Track Title or Song"} if not title_column else set()))
                raise SourceValidationError(f"{path.name}: missing columns: {', '.join(names)}")
            # Validate counts for rows with an artist and title before building database records.
            valid_names = (
                boomplay_df["Artist"].str.strip().ne("")
                & boomplay_df[title_column].str.strip().ne("")
            )
            totals = boomplay_df.loc[valid_names, "Ad Supported Plays"].str.strip()
            invalid_streams = ~totals.str.fullmatch(r"[+-]?\d+(?:_\d+)*")
            if invalid_streams.any():
                row_number = totals.index[invalid_streams][0] + 2
                raise SourceValidationError(f"Row {row_number}: streams must be an integer")
            streams = totals.map(int)
            if streams.lt(0).any():
                row_number = streams.index[streams.lt(0)][0] + 2
                raise SourceValidationError(f"Row {row_number}: streams must not be negative")
            # Preserve integer precision when skipped rows leave gaps in the index.
            boomplay_df["streams"] = streams.astype(object)
            source_row_count = 0
            skipped_rows = []
            # Start at row 2 because the first CSV row contains the headers.
            for row_number, row in enumerate(boomplay_df.to_dict(orient="records"), start=2):
                source_row_count += 1
                # Trim surrounding whitespace and treat missing values as blank.
                artist = (row.get("Artist") or "").strip()
                title = (row.get(title_column) or "").strip()
                # Skip incomplete song identities and remember their rows for logging.
                if not artist or not title:
                    skipped_rows.append(row_number)
                    continue
                # Keep all nonnegative counts so small daily entries contribute to weekly totals.
                streams = int(row["streams"])
                # Map source fields to database fields; the caller supplies the file's date.
                rows.append({
                    "play_date": expected_date,
                    "artist": artist,
                    "song_title": title,
                    # Normalize case and whitespace for consistent song aggregation.
                    "artist_normalized": self.normalize_name(artist),
                    "song_title_normalized": self.normalize_name(title),
                    "streams": streams,
                    # Preserve the source location and ingestion run for traceability.
                    "source_file": path.name,
                    "source_row_number": row_number,
                    "ingestion_run_id": self.run_id,
                })
            # Summarize blank artist/title rows, limiting the logged row list to 20.
            if skipped_rows:
                logger.warning(
                    "Skipped %d Boomplay rows with a blank artist or title in %s (rows: %s)",
                    len(skipped_rows),
                    path.name,
                    ", ".join(map(str, skipped_rows[:20]))
                    + (", ..." if len(skipped_rows) > 20 else ""),
                )
            # A header-only file is invalid; a file whose data rows were all filtered is allowed.
            if not source_row_count:
                raise SourceValidationError(f"{path.name}: file contains no data rows")
        if not rows:
            return []
        # Combine duplicate entries into one row per day, artist, and title.
        daily = pd.DataFrame(rows).groupby(
            ["play_date", "artist", "song_title"], sort=False, dropna=False
        ).agg(
            streams=("streams", "sum"),
            artist_normalized=("artist_normalized", "first"),
            song_title_normalized=("song_title_normalized", "first"),
            source_file=("source_file", "first"),
            source_row_number=("source_row_number", "first"),
            ingestion_run_id=("ingestion_run_id", "first"),
        ).reset_index()
        # Calculate weekly qualification only after collecting every available day.
        dates = pd.to_datetime(daily["play_date"])
        daily["week_start"] = dates - pd.to_timedelta((dates.dt.dayofweek - 4) % 7, unit="D")
        weekly_totals = daily.groupby(
            ["week_start", "artist", "song_title"], sort=False
        )["streams"].transform("sum")
        retained = daily.loc[weekly_totals >= MIN_WEEKLY_STREAMS].drop(columns="week_start")
        return retained.to_dict(orient="records")
