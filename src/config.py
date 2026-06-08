from pydantic_settings import BaseSettings
from src.utils.constant import EnvConstants

class Settings(BaseSettings):
    DATABASE_URL: str = f"postgresql://{EnvConstants.DB_USER}:{EnvConstants.DB_PASSWORD}@{EnvConstants.DB_HOST}:{EnvConstants.DB_PORT}/{EnvConstants.DB_NAME}"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    TEMPLATES_DIR: str = "templates_store"

    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }

settings = Settings()