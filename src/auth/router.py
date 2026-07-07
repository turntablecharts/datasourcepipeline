from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from src.database import get_db
from src import models, schema
from src.auth.utils import hash_password, verify_password, create_access_token, get_current_user, require_admin


router = APIRouter()

@router.post("/register", response_model=schema.UserOut)
def create_user(
    user_data: schema.UserCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin)  # only admins can hit this
):
    existing = db.query(models.User).filter(models.User.email == user_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists."
        )
    user = models.User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        username=user_data.username,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        role=user_data.role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user



@router.post("/login", response_model=schema.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),  # <-- form data, not JSON
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled. Contact your administrator."
        )
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=schema.UserOut)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user
