from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field
import os


class Settings(BaseSettings):
    PROJECT_NAME: str = "CivicSight API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # PostgreSQL Connection Parameters
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "civicsight_db"

    # Optional direct connection string
    DATABASE_URL: Optional[str] = None

    # Authentication & JWT Configuration
    SECRET_KEY: str = "civicsight-super-secret-jwt-key-for-development-2026-week3"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Week 8: Priority Engine & Proximity Settings
    NEARBY_DISTANCE_METERS: float = 50.0
    DUPLICATE_DISTANCE_METERS: float = 15.0
    DUPLICATE_TIME_WINDOW_DAYS: Optional[float] = None
    IMAGE_SIMILARITY_ENABLED: bool = False
    PRIORITY_MIN_CONFIDENCE: float = 0.25
    PRIORITY_HIGH_SEVERITY_THRESHOLD: float = 0.55
    PRIORITY_MEDIUM_SEVERITY_THRESHOLD: float = 0.28
    PRIORITY_HIGH_SCORE_THRESHOLD: float = 60.0
    PRIORITY_MEDIUM_SCORE_THRESHOLD: float = 30.0
    PRIORITY_HIGH_NEARBY_COUNT: int = 4
    PRIORITY_MEDIUM_NEARBY_COUNT: int = 2

    @computed_field
    @property
    def sync_database_uri(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        # Fallback to local SQLite database in backend directory for development
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        default_sqlite = os.path.join(backend_dir, "civicsight.db").replace("\\", "/")
        return f"sqlite:///{default_sqlite}"

    model_config = SettingsConfigDict(
        env_file=[
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
            ".env",
        ],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
