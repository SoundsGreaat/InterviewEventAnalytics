from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Set

class Settings(BaseSettings):
    DATABASE_URL: str = "..."
    NATS_URL: str = "..."
    API_KEYS: Set[str] = set()

    class Config:
        env_file = Path(__file__).parent.parent / ".env"
        case_sensitive = True

settings = Settings()