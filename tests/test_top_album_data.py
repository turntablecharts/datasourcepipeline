import io

import pandas as pd
import pytest

from src.weekly_data_cleaning.top_album_data.cleaning_client import TopAlbumData


def make_workbook(album_data: pd.DataFrame | None = None, spotify_data: pd.DataFrame | None = None) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        if album_data is not None:
            album_data.to_excel(writer, index=False, sheet_name="album")
        if spotify_data is not None:
            spotify_data.to_excel(writer, index=False, sheet_name="spotify_equivalent")
    return output.getvalue()


def run_cleaner(file_bytes: bytes):
    cleaner = TopAlbumData(
        file_bytes=file_bytes,
        original_filename="top_album.xlsx",
        week_start_date="2026/05/01",
        week_end_date="2026/05/07",
    )
    return cleaner.manage()


def read_output(output_bytes: bytes) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(output_bytes), sheet_name="Joint Album Data")


def test_valid_workbook_outputs_expected_totals():
    file_bytes = make_workbook(
        album_data=pd.DataFrame({"Album": ["Alpha", "Beta"], "Points": [10, 4]}),
        spotify_data=pd.DataFrame({"Album": ["Alpha", "Gamma"], "Spotify Equivalent": [3, 8]}),
    )

    output_bytes, output_filename, rows_input, rows_output, log = run_cleaner(file_bytes)

    result = read_output(output_bytes).sort_values("Album").reset_index(drop=True)
    expected = pd.DataFrame(
        {"Album": ["Alpha", "Beta", "Gamma"], "Total Points": [13, 4, 8]}
    )
    pd.testing.assert_frame_equal(result, expected, check_dtype=False)
    assert output_filename == "joint_album_data_2026-05-01_to_2026-05-07.xlsx"
    assert rows_input == 4
    assert rows_output == 3
    assert "Cleaned album names." in log


def test_album_names_are_stripped_title_cased_and_grouped():
    file_bytes = make_workbook(
        album_data=pd.DataFrame({"Album": [" alpha ", "ALPHA", "beta"], "Points": [10, 2, 4]}),
        spotify_data=pd.DataFrame({"Album": ["alpha", " BETA "], "Spotify Equivalent": [3, 1]}),
    )

    output_bytes, _, _, rows_output, _ = run_cleaner(file_bytes)

    result = read_output(output_bytes).sort_values("Album").reset_index(drop=True)
    expected = pd.DataFrame({"Album": ["Alpha", "Beta"], "Total Points": [15, 5]})
    pd.testing.assert_frame_equal(result, expected, check_dtype=False)
    assert rows_output == 2


def test_missing_sheet_fails():
    file_bytes = make_workbook(
        album_data=pd.DataFrame({"Album": ["Alpha"], "Points": [10]}),
        spotify_data=None,
    )

    with pytest.raises(ValueError, match="Missing required sheet"):
        run_cleaner(file_bytes)


def test_missing_required_column_fails():
    file_bytes = make_workbook(
        album_data=pd.DataFrame({"Album": ["Alpha"], "Streams": [10]}),
        spotify_data=pd.DataFrame({"Album": ["Alpha"], "Spotify Equivalent": [3]}),
    )

    with pytest.raises(ValueError, match="Missing columns in album sheet: Points"):
        run_cleaner(file_bytes)


def test_blank_album_name_fails():
    file_bytes = make_workbook(
        album_data=pd.DataFrame({"Album": ["Alpha", " "], "Points": [10, 2]}),
        spotify_data=pd.DataFrame({"Album": ["Alpha"], "Spotify Equivalent": [3]}),
    )

    with pytest.raises(ValueError, match="blank album name"):
        run_cleaner(file_bytes)


def test_non_numeric_album_points_fail():
    file_bytes = make_workbook(
        album_data=pd.DataFrame({"Album": ["Alpha"], "Points": ["bad"]}),
        spotify_data=pd.DataFrame({"Album": ["Alpha"], "Spotify Equivalent": [3]}),
    )

    with pytest.raises(ValueError, match="non-numeric Points"):
        run_cleaner(file_bytes)


def test_non_numeric_spotify_points_fail():
    file_bytes = make_workbook(
        album_data=pd.DataFrame({"Album": ["Alpha"], "Points": [10]}),
        spotify_data=pd.DataFrame({"Album": ["Alpha"], "Spotify Equivalent": ["bad"]}),
    )

    with pytest.raises(ValueError, match="non-numeric Spotify Equivalent"):
        run_cleaner(file_bytes)


def test_negative_album_points_fail():
    file_bytes = make_workbook(
        album_data=pd.DataFrame({"Album": ["Alpha"], "Points": [-1]}),
        spotify_data=pd.DataFrame({"Album": ["Alpha"], "Spotify Equivalent": [3]}),
    )

    with pytest.raises(ValueError, match="negative Points"):
        run_cleaner(file_bytes)


def test_negative_spotify_points_fail():
    file_bytes = make_workbook(
        album_data=pd.DataFrame({"Album": ["Alpha"], "Points": [10]}),
        spotify_data=pd.DataFrame({"Album": ["Alpha"], "Spotify Equivalent": [-3]}),
    )

    with pytest.raises(ValueError, match="negative Spotify Equivalent"):
        run_cleaner(file_bytes)
