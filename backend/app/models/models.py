"""CivicSight Database Models (Week 2)

Defines the core relational schema for CivicSight:
- User: Citizen or municipal contact entity (scaffolded without auth/roles for Week 2).
- Report: Road damage incident report tracking the full lifecycle workflow.
"""

from datetime import datetime
import enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship
from app.db.database import Base


class UserRole(str, enum.Enum):
    """Supported user roles for RBAC in CivicSight."""
    CITIZEN = "Citizen"
    MUNICIPAL_OFFICER = "Municipal Officer"
    MAINTENANCE_STAFF = "Maintenance Staff"
    ADMIN = "Admin"


class ReportStatus(str, enum.Enum):
    """Lifecycle stages of a road damage report."""
    SUBMITTED = "submitted"
    PENDING_VERIFICATION = "pending_verification"
    DETECTED = "detected"
    PRIORITIZED = "prioritized"
    VERIFIED = "verified"
    ASSIGNED = "assigned"
    UNDER_REPAIR = "under_repair"
    REPAIRED = "repaired"
    CLOSED = "closed"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


class User(Base):
    """User entity representing a citizen, municipal officer, maintenance staff, or admin."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, index=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    phone = Column(String(30), nullable=True)
    hashed_password = Column(String(255), nullable=True)
    role = Column(
        SQLEnum(UserRole, values_callable=lambda obj: [e.value for e in obj]),
        default=UserRole.CITIZEN,
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    reports = relationship(
        "Report",
        back_populates="reporter",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="Report.reporter_id",
    )

    def __repr__(self):
        return f"<User id={self.id} name='{self.name}' email='{self.email}' role='{self.role}'>"


class Report(Base):
    """Road damage report entity tracking hazards from citizen capture to repair closure."""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    description = Column(Text, nullable=True)
    
    # Location fields (flexible for manual text, GPS coords, or future GIS layers)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address_text = Column(String(255), nullable=True)
    
    # Image attachment reference
    image_url = Column(String(500), nullable=True)

    # Lifecycle Status
    status = Column(
        SQLEnum(ReportStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=ReportStatus.SUBMITTED,
        nullable=False,
        index=True,
    )

    severity_score = Column(Float, nullable=True)
    damage_type = Column(String(50), nullable=True)
    priority = Column(String(20), nullable=True, default="MEDIUM", index=True)
    ml_detections = Column(Text, nullable=True)

    # ML Pipeline Enrichment (Week 7)
    ml_status = Column(
        String(50),
        default="ML_PENDING",
        nullable=True,
        index=True,
    )
    ml_model_version = Column(String(100), nullable=True)
    ml_inference_time_ms = Column(Float, nullable=True)
    ml_processed_at = Column(DateTime, nullable=True)
    ml_error_message = Column(Text, nullable=True)

    # Assignment & Lifecycle Details
    assigned_to = Column(String(120), nullable=True)
    assigned_to_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    duplicate_of_id = Column(
        Integer,
        ForeignKey("reports.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rejection_reason = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    reporter = relationship("User", back_populates="reports", foreign_keys=[reporter_id])
    assigned_staff = relationship("User", foreign_keys=[assigned_to_id])
    duplicate_of = relationship("Report", remote_side=[id], foreign_keys=[duplicate_of_id])
    status_history = relationship(
        "ReportStatusHistory",
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="ReportStatusHistory.created_at.asc()",
    )
    detection_results = relationship(
        "DetectionResult",
        back_populates="report",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DetectionResult.confidence.desc()",
    )

    def __repr__(self):
        return f"<Report id={self.id} status='{self.status}' ml_status='{self.ml_status}' reporter_id={self.reporter_id}>"


class DetectionResult(Base):
    """Individual road defect detection result linked to a Report (Week 7)."""
    __tablename__ = "detection_results"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(
        Integer,
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    detected_class = Column(String(50), nullable=False, index=True)
    class_name = Column(String(100), nullable=True)
    confidence = Column(Float, nullable=False)
    bbox_xmin = Column(Float, nullable=False)
    bbox_ymin = Column(Float, nullable=False)
    bbox_xmax = Column(Float, nullable=False)
    bbox_ymax = Column(Float, nullable=False)
    bbox_normalized = Column(Text, nullable=True)
    severity = Column(String(20), nullable=True, default="MEDIUM")
    model_version = Column(String(100), nullable=False, default="YOLOv8n-experiment2_week5")
    inference_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    report = relationship("Report", back_populates="detection_results")

    def __repr__(self):
        return (
            f"<DetectionResult id={self.id} report_id={self.report_id} "
            f"class='{self.detected_class}' conf={self.confidence:.3f}>"
        )


class ReportStatusHistory(Base):
    """Audit log tracking every status transition across a report's lifecycle."""
    __tablename__ = "report_status_history"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(
        Integer,
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status = Column(String(50), nullable=True)
    to_status = Column(String(50), nullable=False, index=True)
    performed_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    performed_by_name = Column(String(120), nullable=True)
    performed_by_role = Column(String(50), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    report = relationship("Report", back_populates="status_history")
    performed_by = relationship("User", foreign_keys=[performed_by_id])

    def __repr__(self):
        return f"<ReportStatusHistory id={self.id} report_id={self.report_id} {self.from_status}->{self.to_status}>"
