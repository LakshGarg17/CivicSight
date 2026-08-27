import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from app.core.config import settings

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine
engine = create_engine(
    settings.sync_database_uri,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative Base for future models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency for yielding database sessions per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> dict:
    """Verifies active connectivity to PostgreSQL database."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            row = result.fetchone()
            if row and row[0] == 1:
                return {
                    "reachable": True,
                    "database": settings.POSTGRES_DB,
                    "message": "Database connection verified successfully"
                }
            return {
                "reachable": False,
                "database": settings.POSTGRES_DB,
                "message": "Database returned unexpected response"
            }
    except Exception as e:
        logger.warning(f"Database connection check failed: {str(e)}")
        return {
            "reachable": False,
            "database": settings.POSTGRES_DB,
            "message": f"Connection failed: {str(e)}"
        }
