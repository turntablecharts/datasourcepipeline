from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

# --- Auth ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# --- Users ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    username: str
    first_name: str
    last_name: str
    role: str = "user"

class UserOut(BaseModel):
    id: int
    email: str
    username: str
    first_name: str
    last_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_modified_at: datetime

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# --- Upload log ---
class UploadLogOut(BaseModel):
    id: int
    user_id: int
    username: str
    template_id: str
    original_filename: Optional[str] = None
    week_start_date: date
    week_end_date: date
    rows_input: int
    rows_output: int
    status: str
    error_detail: Optional[str] = None
    created_date: datetime

    class Config:
        from_attributes = True


class RawAlbumDataOut(BaseModel):
    id: int
    upload_log_id: int
    source_sheet: str
    row_number: int
    original_album: Optional[str] = None
    album_points: Optional[Decimal] = None
    spotify_equivalent_points: Optional[Decimal] = None
    created_date: datetime

    class Config:
        from_attributes = True


class CleanedAlbumDataOut(BaseModel):
    id: int
    upload_log_id: int
    album: str
    total_points: Decimal
    week_start_date: date
    week_end_date: date
    created_date: datetime

    class Config:
        from_attributes = True

# --- Templates ---
class TemplateCreate(BaseModel):
    template_name: str
    template_file_path: str

class TemplateOut(BaseModel):
    id: int
    template_name: str
    template_file_path: str
    created_at: datetime
    last_modified_at: datetime

    class Config:
        from_attributes = True
