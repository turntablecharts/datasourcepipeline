import pandas as pd
import openpyxl
import io
import os
from datetime import datetime
from src.config import settings
from src.weekly_data_cleaning.top_album_data.cleaning_client import TopAlbumData


def get_script_module(template_name: str, file_bytes: bytes, original_filename: str, week_start_date: str = "", week_end_date: str = ""):
    module = None
    if template_name == "editorial_top_album_data_template.xlsx":
        module = TopAlbumData(
            file_bytes=file_bytes, 
            original_filename=original_filename, 
            week_start_date=week_start_date, 
            week_end_date=week_end_date
        )
    
    if module is None:
        raise NotImplementedError(
            f"No script registered for template '{template_name}'. "
        )

    return module


def validate_template_exists(template_name: str) -> bool:
    path = os.path.join(settings.TEMPLATES_DIR, template_name)
    return os.path.exists(path)


def run_pipeline(
    file_bytes: bytes, 
    original_filename: str,
    template_name: str,
    week_start_date: str,
    week_end_date: str
) -> tuple[bytes, str, int, int, list[str]]:
    """
    Route file bytes to the correct script and run the full pipeline.

    Each script handles its own reading, cleaning, and output.

    Returns:
        output_bytes    - cleaned file ready for download
        output_filename - custom filename determined by the script
        rows_input      - row count before cleaning
        rows_output     - row count after cleaning
        log             - list of step descriptions
    """
    module = get_script_module(
        template_name=template_name, 
        file_bytes=file_bytes, 
        original_filename=original_filename,
        week_start_date=week_start_date,
        week_end_date=week_end_date
    )
    return module.manage()
