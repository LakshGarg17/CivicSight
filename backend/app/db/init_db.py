"""CivicSight Database Initialization (Week 3)

Creates all relational schema tables in PostgreSQL and ensures columns for
Week 3 (hashed_password, role) are migrated smoothly.
"""

import logging
from sqlalchemy import text, inspect
from app.db.database import engine, Base
import app.models.models  # Ensure all model entities are registered with Base

logger = logging.getLogger(__name__)


def init_db() -> None:
    """Creates database tables defined across all registered SQLAlchemy models."""
    try:
        logger.info("Initializing CivicSight database tables...")
        Base.metadata.create_all(bind=engine)

        # Check and migrate columns for Week 3 schema additions
        with engine.connect() as conn:
            inspector = inspect(engine)
            if "users" in inspector.get_table_names():
                existing_cols = [c["name"] for c in inspector.get_columns("users")]

                # Ensure enum type exists in PostgreSQL if supported
                try:
                    conn.execute(
                        text(
                            "DO $$ BEGIN "
                            "CREATE TYPE userrole AS ENUM ('Citizen', 'Municipal Officer', 'Maintenance Staff', 'Admin'); "
                            "EXCEPTION WHEN duplicate_object THEN null; "
                            "END $$;"
                        )
                    )
                    conn.commit()
                except Exception:
                    pass

                if "hashed_password" not in existing_cols:
                    logger.info("Adding 'hashed_password' column to users table...")
                    conn.execute(text("ALTER TABLE users ADD COLUMN hashed_password VARCHAR(255);"))
                    conn.commit()

                if "role" not in existing_cols:
                    logger.info("Adding 'role' column to users table...")
                    try:
                        conn.execute(
                            text("ALTER TABLE users ADD COLUMN role userrole NOT NULL DEFAULT 'Citizen';")
                        )
                        conn.commit()
                    except Exception:
                        conn.execute(
                            text("ALTER TABLE users ADD COLUMN role VARCHAR(50) NOT NULL DEFAULT 'Citizen';")
                        )
                        conn.commit()

            # Check and migrate columns for Week 5 reports schema additions (priority, ml_detections)
            if "reports" in inspector.get_table_names():
                existing_report_cols = [c["name"] for c in inspector.get_columns("reports")]

                if "priority" not in existing_report_cols:
                    logger.info("Adding 'priority' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN priority VARCHAR(20) DEFAULT 'MEDIUM';"))
                    conn.commit()

                if "ml_detections" not in existing_report_cols:
                    logger.info("Adding 'ml_detections' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN ml_detections TEXT;"))
                    conn.commit()

        logger.info("Database tables verified/created successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("Database tables initialized successfully.")
