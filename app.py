# from fastapi import FastAPI, UploadFile, File, HTTPException
# import shutil
# import os
# import tempfile
# from typing import List

# from src.transformation.weekly_data import process_data
# from src.storage import upload_file

# app = FastAPI()

# @app.post("/pipeline")
# def run_pipeline():
#     pass

# from src.etl.extraction.audiomack_boomplay import get_files

# get_files('2026-01-23', '2026-01-29')

from src.etl.transformation.audiomack_transform import transform_audiomack_data
from src.etl.transformation.boomplay_transform import transform_boomplay_data
from src.etl.extraction.audiomack_boomplay import get_files

get_files('2026-03-13', '2026-03-19')

transform_audiomack_data()

transform_boomplay_data()