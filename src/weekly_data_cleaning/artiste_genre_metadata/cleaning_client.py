import io
import logging
import re

import pandas as pd

logger = logging.getLogger("artiste_genre_metadata_cleaner")


class ArtisteGenreMetadata:
    """Clean the artiste/genre metadata template into ranked aggregate sheets."""

    EXCLUDED_OUTPUT_VALUES = {"-", "llc", "ltd", "0"}

    # These columns are the minimum needed to produce all output sheets.
    REQUIRED_COLUMNS = [
        "Points",
        "Artiste",
        "Genre",
        "ProducedBy",
    ]

    # Supports the template names and older exports like "Featured Artiste .1".
    FEATURED_ARTISTE_PATTERN = re.compile(r"^Featured Artiste\s*(?:\.\d+)?$")

    def __init__(self, file_bytes: bytes, original_filename: str, week_start_date: str, week_end_date: str):
        self.file_bytes = file_bytes
        self.original_filename = original_filename
        self.week_start_date = week_start_date
        self.week_end_date = week_end_date

    def get_dataset(self) -> pd.DataFrame:
        """Read the uploaded workbook and return the first sheet as a validated dataframe."""
        if self.original_filename and not self.original_filename.lower().endswith(".xlsx"):
            raise ValueError("Artiste genre metadata cleaning only supports .xlsx files.")

        try:
            workbook = pd.ExcelFile(io.BytesIO(self.file_bytes))
        except Exception as exc:
            raise ValueError("Could not read uploaded Excel workbook.") from exc

        # The template stores its metadata in the first sheet.
        dataframe = workbook.parse(sheet_name=workbook.sheet_names[0])

        # Strip header whitespace so exports with columns like "Artiste " still work.
        dataframe.columns = [str(column).strip() for column in dataframe.columns]
        self._validate_columns(dataframe, self.REQUIRED_COLUMNS)
        return dataframe

    @staticmethod
    def _validate_columns(dataframe: pd.DataFrame, required_columns: list[str]) -> None:
        missing = [column for column in required_columns if column not in dataframe.columns]
        if missing:
            raise ValueError(f"Missing required column(s): {', '.join(missing)}")

    @staticmethod
    def _normalize_points(dataframe: pd.DataFrame) -> pd.DataFrame:
        """Convert Points to numeric values after handling blanks and comma separators."""
        cleaned = dataframe.copy()
        point_values = (
            cleaned["Points"]
            .fillna(0)
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.strip()
            .replace({"": "0", "nan": "0", "None": "0"})
        )
        numeric_values = pd.to_numeric(point_values, errors="coerce")
        invalid_count = numeric_values.isna().sum()
        if invalid_count:
            raise ValueError(f"Uploaded sheet contains {invalid_count} non-numeric Points value(s).")

        negative_count = (numeric_values < 0).sum()
        if negative_count:
            raise ValueError(f"Uploaded sheet contains {negative_count} negative Points value(s).")

        cleaned["Points"] = numeric_values.round(6).astype(float)
        return cleaned

    @staticmethod
    def _clean_token(value) -> str:
        """Normalize one split item before grouping."""
        if pd.isna(value):
            return ""
        return re.sub(r"\s+", " ", str(value)).strip().lower()

    @staticmethod
    def _title_case(series: pd.Series) -> pd.Series:
        return series.str.replace(r"\s+", " ", regex=True).str.strip().str.title()

    @staticmethod
    def _split_and_sum(dataframe: pd.DataFrame, source_column: str, output_column: str, separators: str) -> pd.DataFrame:
        """Split a multi-value column, remove empty tokens, and sum Points per token."""
        values = dataframe[["Points", source_column]].copy()
        values[source_column] = values[source_column].fillna("").astype(str)

        # Convert the configured separators into one delimiter so explode can handle them uniformly.
        values[source_column] = values[source_column].str.replace(separators, ";", regex=True)

        # Turn rows like "A;B;C" into three rows that each carry the original Points value.
        split_values = (
            values.assign(**{source_column: values[source_column].str.split(";")})
            .explode(source_column, ignore_index=True)
        )
        split_values[source_column] = split_values[source_column].map(ArtisteGenreMetadata._clean_token)
        split_values = split_values[~split_values[source_column].isin(["", "none", "nan"])]

        # Aggregate after lower-casing, then title-case only the final display labels.
        grouped = (
            split_values.groupby(source_column, as_index=False)["Points"]
            .sum()
            .sort_values(by="Points", ascending=False, kind="mergesort")
        )
        grouped[source_column] = ArtisteGenreMetadata._title_case(grouped[source_column])
        return grouped.rename(columns={source_column: output_column}).reset_index(drop=True)

    @classmethod
    def _remove_excluded_output_rows(cls, dataframe: pd.DataFrame, label_column: str) -> pd.DataFrame:
        """Drop placeholder/business-suffix rows from a cleaned output sheet."""
        normalized_labels = dataframe[label_column].fillna("").astype(str).str.strip().str.lower()
        return dataframe[~normalized_labels.isin(cls.EXCLUDED_OUTPUT_VALUES)].reset_index(drop=True)

    def _build_artistes(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """Combine main and featured artiste columns before applying the shared split/group logic."""
        artiste_columns = ["Artiste"] + [
            column for column in dataframe.columns if self.FEATURED_ARTISTE_PATTERN.match(str(column).strip())
        ]
        artiste_values = dataframe[["Points"] + artiste_columns].copy()

        # Each track can list contributors across several columns, so merge them into one field first.
        artiste_values["Combined Artiste"] = (
            artiste_values[artiste_columns]
            .fillna("")
            .astype(str)
            .agg(";".join, axis=1)
        )
        return self._split_and_sum(
            dataframe=artiste_values,
            source_column="Combined Artiste",
            output_column="Artiste",
            separators=r"[,&]",
        )

    def manage(self):
        """Run the full cleaning pipeline and return downloadable workbook bytes plus metadata."""
        dataframe = self.get_dataset()
        rows_input = len(dataframe)
        dataframe = self._normalize_points(dataframe)

        # Producers and artistes split on commas and ampersands; genres split only on commas.
        producers = self._split_and_sum(
            dataframe=dataframe,
            source_column="ProducedBy",
            output_column="ProducedBy",
            separators=r"[,&]",
        )
        genres = self._split_and_sum(
            dataframe=dataframe,
            source_column="Genre",
            output_column="Genre",
            separators=r"[,]",
        )
        artistes = self._build_artistes(dataframe)

        # Remove known placeholder/noise rows before writing the final workbook.
        artistes = self._remove_excluded_output_rows(artistes, "Artiste")
        genres = self._remove_excluded_output_rows(genres, "Genre")
        producers = self._remove_excluded_output_rows(producers, "ProducedBy")

        rows_output = len(producers) + len(genres) + len(artistes)
        log = [
            "Validated artiste genre metadata workbook.",
            "Aggregated producer, genre, and artiste points.",
            "Removed placeholder rows from cleaned output.",
        ]

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            # The output is one workbook with separate ranked aggregate sheets.
            artistes.to_excel(writer, index=False, sheet_name="Artistes")
            genres.to_excel(writer, index=False, sheet_name="Genre")
            producers.to_excel(writer, index=False, sheet_name="Producers")
        output_bytes = output.getvalue()

        clean_start = self.week_start_date.replace("/", "-").replace("\\", "-")
        clean_end = self.week_end_date.replace("/", "-").replace("\\", "-")
        output_filename = f"artiste_genre_metadata_{clean_start}_to_{clean_end}.xlsx"

        return output_bytes, output_filename, rows_input, rows_output, log
