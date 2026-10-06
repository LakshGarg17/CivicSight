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

                # Week 6 additions
                if "assigned_to" not in existing_report_cols:
                    logger.info("Adding 'assigned_to' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN assigned_to VARCHAR(120);"))
                    conn.commit()

                if "assigned_to_id" not in existing_report_cols:
                    logger.info("Adding 'assigned_to_id' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN assigned_to_id INTEGER;"))
                    conn.commit()

                if "duplicate_of_id" not in existing_report_cols:
                    logger.info("Adding 'duplicate_of_id' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN duplicate_of_id INTEGER;"))
                    conn.commit()

                if "rejection_reason" not in existing_report_cols:
                    logger.info("Adding 'rejection_reason' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN rejection_reason TEXT;"))
                    conn.commit()

                # Week 7 additions: ML Pipeline fields
                if "ml_status" not in existing_report_cols:
                    logger.info("Adding 'ml_status' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN ml_status VARCHAR(50) DEFAULT 'ML_PENDING';"))
                    conn.commit()

                if "ml_model_version" not in existing_report_cols:
                    logger.info("Adding 'ml_model_version' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN ml_model_version VARCHAR(100);"))
                    conn.commit()

                if "ml_inference_time_ms" not in existing_report_cols:
                    logger.info("Adding 'ml_inference_time_ms' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN ml_inference_time_ms FLOAT;"))
                    conn.commit()

                if "ml_processed_at" not in existing_report_cols:
                    logger.info("Adding 'ml_processed_at' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN ml_processed_at TIMESTAMP;"))
                    conn.commit()

                if "ml_error_message" not in existing_report_cols:
                    logger.info("Adding 'ml_error_message' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN ml_error_message TEXT;"))
                    conn.commit()

        # Seed standard prototype and test users
        from app.db.database import SessionLocal
        from app.models.models import User, UserRole
        from app.core.security import get_password_hash

        db = SessionLocal()
        try:
            demo_users = [
                ("officer@civicsight.gov", "Sarah Chen", UserRole.MUNICIPAL_OFFICER, "Password123!"),
                ("officer_test_w5@example.com", "Officer Dave", UserRole.MUNICIPAL_OFFICER, "testpassword123"),
                ("citizen@civicsight.org", "Jane Citizen", UserRole.CITIZEN, "Password123!"),
                ("citizen_test_w5@example.com", "Citizen Jane", UserRole.CITIZEN, "testpassword123"),
                ("admin@civicsight.gov", "Admin Director", UserRole.ADMIN, "Password123!"),
            ]
            for email, name, role, pwd in demo_users:
                u = db.query(User).filter(User.email == email).first()
                if not u:
                    new_user = User(
                        email=email,
                        name=name,
                        role=role,
                        hashed_password=get_password_hash(pwd),
                    )
                    db.add(new_user)
            db.commit()
        finally:
            db.close()

        logger.info("Database tables verified/created successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("Database tables initialized successfully.")
