"""CivicSight Database Initialization (Week 2)

Creates all relational schema tables in PostgreSQL if they do not already exist.
"""

import logging
from app.db.database import engine, Base
import app.models.models  # Ensure all model entities are registered with Base

logger = logging.getLogger(__name__)


def init_db() -> None:
    """Creates database tables defined across all registered SQLAlchemy models."""
    try:
        logger.info("Initializing CivicSight database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("Database tables initialized successfully.")
