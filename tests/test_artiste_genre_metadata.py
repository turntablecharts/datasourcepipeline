import io

import pandas as pd
import pytest

from src.weekly_data_cleaning.artiste_genre_metadata.cleaning_client import ArtisteGenreMetadata


def make_workbook(dataframe: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="Sheet1")
    return output.getvalue()


def run_cleaner(file_bytes: bytes):
    cleaner = ArtisteGenreMetadata(
        file_bytes=file_bytes,
        original_filename="artiste_genre.xlsx",
        week_start_date="2026/05/01",
        week_end_date="2026/05/07",
    )
    return cleaner.manage()


def read_output(output_bytes: bytes, sheet_name: str) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(output_bytes), sheet_name=sheet_name)


def test_valid_workbook_outputs_artiste_genre_and_producer_sheets():
    file_bytes = make_workbook(
        pd.DataFrame(
            {
                "Title": ["Song 1", "Song 2"],
                "Points": [10, "1,500"],
                "Artiste": ["Alpha", "Beta & Gamma"],
                "Featured Artiste": ["Delta, Epsilon", None],
                "Featured Artiste.1": [None, "Alpha"],
                "Genre": ["Afrobeats, Pop", "Pop"],
                "ProducedBy": ["Prod One & Prod Two", "Prod One"],
            }
        )
    )

    output_bytes, output_filename, rows_input, rows_output, log = run_cleaner(file_bytes)

    artistes = read_output(output_bytes, "Artistes")
    genres = read_output(output_bytes, "Genre")
    producers = read_output(output_bytes, "Producers")

    expected_artistes = pd.DataFrame(
        {
            "Artiste": ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"],
            "Points": [1510, 1500, 1500, 10, 10],
        }
    )
    expected_genres = pd.DataFrame(
        {
            "Genre": ["Pop", "Afrobeats"],
            "Points": [1510, 10],
        }
    )
    expected_producers = pd.DataFrame(
        {
            "ProducedBy": ["Prod One", "Prod Two"],
            "Points": [1510, 10],
        }
    )

    pd.testing.assert_frame_equal(artistes, expected_artistes, check_dtype=False)
    pd.testing.assert_frame_equal(genres, expected_genres, check_dtype=False)
    pd.testing.assert_frame_equal(producers, expected_producers, check_dtype=False)
    assert output_filename == "artiste_genre_metadata_2026-05-01_to_2026-05-07.xlsx"
    assert rows_input == 2
    assert rows_output == 9
    assert "Aggregated producer, genre, and artiste points." in log


def test_trailing_column_spaces_and_featured_artiste_space_before_number_are_supported():
    file_bytes = make_workbook(
        pd.DataFrame(
            {
                "Points": [5],
                "Artiste ": ["Alpha"],
                "Featured Artiste .1": ["Beta"],
                "Genre": ["Pop"],
                "ProducedBy": ["Prod One"],
            }
        )
    )

    output_bytes, _, _, _, _ = run_cleaner(file_bytes)

    artistes = read_output(output_bytes, "Artistes")
    expected = pd.DataFrame({"Artiste": ["Alpha", "Beta"], "Points": [5, 5]})
    pd.testing.assert_frame_equal(artistes, expected, check_dtype=False)


def test_missing_required_column_fails():
    file_bytes = make_workbook(
        pd.DataFrame(
            {
                "Points": [5],
                "Artiste": ["Alpha"],
                "Genre": ["Pop"],
            }
        )
    )

    with pytest.raises(ValueError, match="Missing required column"):
        run_cleaner(file_bytes)


def test_non_numeric_points_fail():
    file_bytes = make_workbook(
        pd.DataFrame(
            {
                "Points": ["bad"],
                "Artiste": ["Alpha"],
                "Genre": ["Pop"],
                "ProducedBy": ["Prod One"],
            }
        )
    )

    with pytest.raises(ValueError, match="non-numeric Points"):
        run_cleaner(file_bytes)
