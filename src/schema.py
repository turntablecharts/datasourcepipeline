from pydantic import BaseModel, EmailStr, Field
from typing import Literal, Optional
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
    password: str = Field(min_length=8)
    username: str = Field(min_length=1, max_length=100)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    role: Literal["user", "admin"] = "user"

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
    file_hash: Optional[str] = None
    week_start_date: date
    week_end_date: date
    rows_input: int
    rows_output: int
    status: str
    error_detail: Optional[str] = None
    is_current: bool
    replaces_upload_log_id: Optional[int] = None
    replaced_by_upload_log_id: Optional[int] = None
    linked_data_cleared: bool
    duplicate_file_upload: bool
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
