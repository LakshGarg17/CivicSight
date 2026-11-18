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
    SECRET_KEY: str = "dev-only-change-in-env-civicsight-secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # CORS Allowed Origins (comma-separated; never wildcard '*' when allow_credentials=True)
    CORS_ORIGINS: str = (
        "http://127.0.0.1:8000,http://localhost:8000,"
        "http://127.0.0.1:3000,http://localhost:3000,"
        "http://127.0.0.1:5500,http://localhost:5500"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip() and o.strip() != "*"]

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

    # ML Inference & YOLO Model Configuration
    MODEL_PATH: str = "ml/runs/detect/clean_rdd2022_yolov8s/weights/best.pt"
    DETECTION_CONFIDENCE_THRESHOLD: float = 0.25
    DETECTION_IOU_THRESHOLD: float = 0.45
    DETECTION_IMGSZ: int = 640

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
