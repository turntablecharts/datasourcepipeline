import io
import logging

import pandas as pd

logger = logging.getLogger("top_album_data_cleaner")


class TopAlbumData:
    """Clean the top album workbook into one ranked joint album data sheet."""

    def __init__(self, file_bytes: bytes, original_filename: str, week_start_date: str, week_end_date: str):
        self.file_bytes = file_bytes
        self.original_filename = original_filename
        self.week_start_date = week_start_date
        self.week_end_date = week_end_date

    def get_dataset(self):
        """Read and validate the two required workbook sheets."""
        if self.original_filename and not self.original_filename.lower().endswith(".xlsx"):
            raise ValueError("Top album data cleaning only supports .xlsx files.")

        try:
            workbook = pd.ExcelFile(io.BytesIO(self.file_bytes))
        except Exception as exc:
            raise ValueError("Could not read uploaded Excel workbook.") from exc

        required_sheets = {"album", "spotify_equivalent"}
        missing_sheets = required_sheets - set(workbook.sheet_names)
        if missing_sheets:
            raise ValueError(f"Missing required sheet(s): {', '.join(sorted(missing_sheets))}")

        # The album sheet carries chart points; spotify_equivalent carries equivalent points.
        album_data = workbook.parse(sheet_name="album")
        spotify_data = workbook.parse(sheet_name="spotify_equivalent")

        required_album = ["Album", "Points"]
        required_spotify = ["Album", "Spotify Equivalent"]

        self._validate_columns(album_data, required_album, "album")
        self._validate_columns(spotify_data, required_spotify, "spotify_equivalent")

        return album_data, spotify_data

    @staticmethod
    def _validate_columns(dataframe: pd.DataFrame, required_columns: list[str], sheet_name: str) -> None:
        missing = [column for column in required_columns if column not in dataframe.columns]
        if missing:
            raise ValueError(f"Missing columns in {sheet_name} sheet: {', '.join(missing)}")

    @staticmethod
    def _clean_album_names(dataframe: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
        """Standardize album names before grouping matching rows together."""
        cleaned = dataframe.copy()
        cleaned["Album"] = (
            cleaned["Album"]
            .fillna("")
            .astype(str)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
            .str.title()
        )

        blank_count = (cleaned["Album"] == "").sum()
        if blank_count:
            raise ValueError(f"{sheet_name} sheet contains {blank_count} blank album name(s).")

        return cleaned

    @staticmethod
    def _validate_numeric_column(dataframe: pd.DataFrame, column_name: str, sheet_name: str) -> pd.DataFrame:
        """Ensure a points column is numeric, non-negative, and consistently rounded."""
        cleaned = dataframe.copy()
        numeric_values = pd.to_numeric(cleaned[column_name], errors="coerce")
        invalid_count = numeric_values.isna().sum()

        if invalid_count:
            raise ValueError(f"{sheet_name} sheet contains {invalid_count} non-numeric {column_name} value(s).")

        negative_count = (numeric_values < 0).sum()
        if negative_count:
            raise ValueError(f"{sheet_name} sheet contains {negative_count} negative {column_name} value(s).")

        cleaned[column_name] = numeric_values.round(6).astype(float)
        return cleaned
        
    def manage(self):
        """Run the full cleaning pipeline and return downloadable workbook bytes plus metadata."""
        album_data, spotify_data = self.get_dataset()
        
        rows_input = len(album_data) + len(spotify_data)
        
        # Normalize names first so spelling/casing differences group into the same album.
        album_data = self._clean_album_names(album_data, "album")
        spotify_data = self._clean_album_names(spotify_data, "spotify_equivalent")

        # Validate points after reading so upload errors are reported before any output is created.
        album_data = self._validate_numeric_column(album_data, "Points", "album")
        spotify_data = self._validate_numeric_column(spotify_data, "Spotify Equivalent", "spotify_equivalent")

        # Collapse duplicate albums inside each sheet before merging the two sources.
        album_grouped = album_data.groupby('Album', as_index=False)['Points'].sum()
        spotify_grouped = spotify_data.groupby('Album', as_index=False)['Spotify Equivalent'].sum()
        
        # Outer merge keeps albums that appear in only one of the two sheets.
        merged_df = pd.merge(album_grouped, spotify_grouped, on='Album', how='outer')
        
        # Missing source values mean the album earned 0 points from that source.
        merged_df['Points'] = merged_df['Points'].fillna(0)
        merged_df['Spotify Equivalent'] = merged_df['Spotify Equivalent'].fillna(0)
        
        # The final score is the chart points plus the Spotify equivalent points.
        merged_df['Total Points'] = merged_df['Points'] + merged_df['Spotify Equivalent']
        
        # Final consolidation prevents duplicate album rows from leaking into the output.
        final_df = merged_df[['Album', 'Total Points']].groupby(
            'Album',
            as_index=False,
        )['Total Points'].sum().sort_values(
            by="Total Points",
            ascending=False,
            kind="mergesort",
        )
        
        rows_output = len(final_df)
        log = [
            "Cleaned album names.",
            "Merged album and spotify datasets and calculated Total Points.",
        ]
        
        # Convert to Excel bytes so the API can return the file directly as a download.
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            final_df.to_excel(writer, index=False, sheet_name="Joint Album Data")
        output_bytes = output.getvalue()
        
        # Clean up date formats for a filesystem-friendly output filename.
        clean_start = self.week_start_date.replace("/", "-").replace("\\", "-")
        clean_end = self.week_end_date.replace("/", "-").replace("\\", "-")
        output_filename = f"joint_album_data_{clean_start}_to_{clean_end}.xlsx"
        
        return output_bytes, output_filename, rows_input, rows_output, log
