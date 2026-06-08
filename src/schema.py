from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

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
    template_id: int
    file_path: str
    number_of_rows: int
    status: str
    remark: Optional[str] = None
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