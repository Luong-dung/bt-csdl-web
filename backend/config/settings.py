from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import os
from dotenv import load_dotenv

# Try to load .env from the backend directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

class Settings(BaseSettings):
    PROJECT_NAME: str = "Esports Tournament API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 5432
    DB_NAME: str = "esports_tournament"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "dung1010"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

@lru_cache()
def get_settings():
    return Settings()
