from urllib.parse import quote
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "Esports Tournament Management Platform"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"
    JWT_SECRET: str = "change-me-in-env"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 5432
    DB_NAME: str = "esports_tournament"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = ""

    @property
    def DATABASE_URL(self) -> str:
        # Percent-encode every reserved character (not only "@"): "#", "%", ":", "/"… in a password
        # would otherwise break the URL. make_url() decodes them back.
        user, password = quote(self.DB_USER, safe=""), quote(self.DB_PASSWORD, safe="")
        return f"postgresql+psycopg2://{user}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

@lru_cache()
def get_settings():
    return Settings()
