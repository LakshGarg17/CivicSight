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

                if "is_active" not in existing_cols:
                    logger.info("Adding 'is_active' column to users table...")
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1 NOT NULL;"))
                    conn.commit()

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

                # Week 8 additions: Priority Engine & Proximity
                if "severity" not in existing_report_cols:
                    logger.info("Adding 'severity' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN severity VARCHAR(20) DEFAULT 'UNKNOWN';"))
                    conn.commit()

                if "priority_score" not in existing_report_cols:
                    logger.info("Adding 'priority_score' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN priority_score FLOAT;"))
                    conn.commit()

                if "priority_reasons" not in existing_report_cols:
                    logger.info("Adding 'priority_reasons' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN priority_reasons TEXT;"))
                    conn.commit()

                if "priority_updated_at" not in existing_report_cols:
                    logger.info("Adding 'priority_updated_at' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN priority_updated_at TIMESTAMP;"))
                    conn.commit()

                if "nearby_report_count" not in existing_report_cols:
                    logger.info("Adding 'nearby_report_count' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN nearby_report_count INTEGER DEFAULT 0;"))
                    conn.commit()

                if "is_priority_overridden" not in existing_report_cols:
                    logger.info("Adding 'is_priority_overridden' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN is_priority_overridden BOOLEAN DEFAULT 0;"))
                    conn.commit()

                if "priority_override_reason" not in existing_report_cols:
                    logger.info("Adding 'priority_override_reason' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN priority_override_reason TEXT;"))
                    conn.commit()

                # Week 9 Lifecycle additions
                if "current_assignee_id" not in existing_report_cols:
                    logger.info("Adding 'current_assignee_id' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN current_assignee_id INTEGER;"))
                    conn.commit()

                if "repair_started_at" not in existing_report_cols:
                    logger.info("Adding 'repair_started_at' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN repair_started_at TIMESTAMP;"))
                    conn.commit()

                if "repair_submitted_at" not in existing_report_cols:
                    logger.info("Adding 'repair_submitted_at' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN repair_submitted_at TIMESTAMP;"))
                    conn.commit()

                if "final_verified_at" not in existing_report_cols:
                    logger.info("Adding 'final_verified_at' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN final_verified_at TIMESTAMP;"))
                    conn.commit()

                if "final_verified_by" not in existing_report_cols:
                    logger.info("Adding 'final_verified_by' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN final_verified_by INTEGER;"))
                    conn.commit()

                if "closed_at" not in existing_report_cols:
                    logger.info("Adding 'closed_at' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN closed_at TIMESTAMP;"))
                    conn.commit()

                if "version" not in existing_report_cols:
                    logger.info("Adding 'version' column to reports table...")
                    conn.execute(text("ALTER TABLE reports ADD COLUMN version INTEGER DEFAULT 1 NOT NULL;"))
                    conn.commit()

                # Week 9 Reversible Legacy Status Migration:
                # Map any legacy statuses (e.g. 'repaired' -> 'repair_evidence_submitted', 'detected' -> 'pending_verification')
                try:
                    conn.execute(text("UPDATE reports SET status = 'repair_evidence_submitted' WHERE status = 'repaired';"))
                    conn.execute(text("UPDATE reports SET status = 'pending_verification' WHERE status IN ('detected', 'prioritized');"))
                    conn.commit()
                except Exception as mig_err:
                    logger.warning(f"Legacy status migration note: {mig_err}")

            if "priority_history" in inspector.get_table_names():
                existing_ph_cols = [c["name"] for c in inspector.get_columns("priority_history")]
                if "reasons_snapshot" not in existing_ph_cols:
                    logger.info("Adding 'reasons_snapshot' column to priority_history table...")
                    conn.execute(text("ALTER TABLE priority_history ADD COLUMN reasons_snapshot TEXT;"))
                    conn.commit()
                if "reasons" not in existing_ph_cols:
                    logger.info("Adding 'reasons' column to priority_history table...")
                    conn.execute(text("ALTER TABLE priority_history ADD COLUMN reasons TEXT;"))
                    conn.commit()

            # Ensure Week 8 & 9 Indexes exist
            try:
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_reports_latitude ON reports (latitude);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_reports_longitude ON reports (longitude);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_reports_priority ON reports (priority);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_report_relations_review_status ON report_relations (review_status);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_assignments_report_id ON assignments (report_id);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_assignments_assigned_to ON assignments (assigned_to);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_repair_evidence_report_id ON repair_evidence (report_id);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_final_verifications_report_id ON final_verifications (report_id);"))

                # Partial unique index: Only one active assignment per report
                try:
                    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_assignments_active_report ON assignments (report_id) WHERE is_active = 1;"))
                except Exception:
                    try:
                        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_assignments_active_report ON assignments (report_id) WHERE is_active = true;"))
                    except Exception:
                        pass
                conn.commit()
            except Exception as idx_err:
                logger.debug(f"Index creation note: {idx_err}")

        # Ensure upload directories exist
        import os
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        os.makedirs(os.path.join(backend_dir, "uploads", "evidence"), exist_ok=True)
        os.makedirs(os.path.join(backend_dir, "uploads", "reports"), exist_ok=True)

        # Seed standard prototype and test users
        from app.db.database import SessionLocal
        from app.models.models import User, UserRole
        from app.core.security import get_password_hash

        db = SessionLocal()
        try:
            demo_users = [
                ("officer@civicsight.gov", "Sarah Chen", UserRole.MUNICIPAL_OFFICER, "Password123!"),
                ("officer1@civicsight.gov", "Officer Sarah", UserRole.MUNICIPAL_OFFICER, "Password123!"),
                ("officer_test_w5@example.com", "Officer Dave", UserRole.MUNICIPAL_OFFICER, "testpassword123"),
                ("staff1@civicsight.gov", "Alex Rivera", UserRole.MAINTENANCE_STAFF, "Password123!"),
                ("staff2@civicsight.gov", "Marcus Vance", UserRole.MAINTENANCE_STAFF, "Password123!") ,
                ("citizen@civicsight.org", "Jane Citizen", UserRole.CITIZEN, "Password123!"),
                ("citizen1@civicsight.org", "Citizen One", UserRole.CITIZEN, "Password123!"),
                ("citizen2@civicsight.org", "Citizen Two", UserRole.CITIZEN, "Password123!"),
                ("citizen_test_w5@example.com", "Citizen Jane", UserRole.CITIZEN, "testpassword123"),
                ("admin@civicsight.gov", "Admin Director", UserRole.ADMIN, "Password123!"),
                ("admin1@civicsight.gov", "Admin Director", UserRole.ADMIN, "Password123!"),
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
