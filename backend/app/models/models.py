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
    Boolean,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship
from app.db.database import Base


from app.core.state_machine import ReportStatus


class UserRole(str, enum.Enum):
    """Supported user roles for RBAC in CivicSight."""
    CITIZEN = "Citizen"
    MUNICIPAL_OFFICER = "Municipal Officer"
    MAINTENANCE_STAFF = "Maintenance Staff"
    ADMIN = "Admin"


class EvidenceKind(str, enum.Enum):
    """Categorization for repair evidence photos."""
    BEFORE = "BEFORE"
    AFTER = "AFTER"
    PROGRESS = "PROGRESS"


class VerificationDecision(str, enum.Enum):
    """Decision outcomes for municipal final verification."""
    APPROVED = "APPROVED"
    SENT_BACK = "SENT_BACK"


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
    is_active = Column(Boolean, default=True, nullable=False)
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
    latitude = Column(Float, nullable=True, index=True)
    longitude = Column(Float, nullable=True, index=True)
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

    # Week 8 Priority Engine Fields
    severity = Column(String(20), nullable=True, default="UNKNOWN")
    priority_score = Column(Float, nullable=True)
    priority_reasons = Column(Text, nullable=True)
    priority_updated_at = Column(DateTime, nullable=True)
    nearby_report_count = Column(Integer, default=0, nullable=False)
    is_priority_overridden = Column(Boolean, default=False, nullable=False)
    priority_override_reason = Column(Text, nullable=True)

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
    current_assignee_id = Column(
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

    # Week 9 Lifecycle Timestamps & Concurrency Version
    repair_started_at = Column(DateTime, nullable=True)
    repair_submitted_at = Column(DateTime, nullable=True)
    final_verified_at = Column(DateTime, nullable=True)
    final_verified_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    closed_at = Column(DateTime, nullable=True)
    version = Column(Integer, default=1, nullable=False)

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
    priority_history = relationship(
        "PriorityHistory",
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="PriorityHistory.created_at.desc()",
    )
    outgoing_relations = relationship(
        "ReportRelation",
        foreign_keys="ReportRelation.report_id",
        back_populates="report",
        cascade="all, delete-orphan",
    )
    incoming_relations = relationship(
        "ReportRelation",
        foreign_keys="ReportRelation.related_report_id",
        back_populates="related_report",
        cascade="all, delete-orphan",
    )
    current_assignee = relationship("User", foreign_keys=[current_assignee_id])
    final_verifier = relationship("User", foreign_keys=[final_verified_by])
    assignments = relationship(
        "Assignment",
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="Assignment.assigned_at.desc()",
    )
    repair_evidence = relationship(
        "RepairEvidence",
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="RepairEvidence.uploaded_at.asc()",
    )
    final_verifications = relationship(
        "FinalVerification",
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="FinalVerification.created_at.desc()",
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


class PriorityHistory(Base):
    """Audit log recording every recalculation, change, or manual override of priority/severity (Week 8)."""
    __tablename__ = "priority_history"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(
        Integer,
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_priority = Column(String(20), nullable=True)
    new_priority = Column(String(20), nullable=True)
    previous_severity = Column(String(20), nullable=True)
    new_severity = Column(String(20), nullable=True)
    score = Column(Float, nullable=True)
    reasons_snapshot = Column(Text, nullable=True)
    reasons = Column(Text, nullable=True)
    trigger = Column(String(50), nullable=False)  # "created", "nearby_report_added", "recalculated", "manual_override"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    report = relationship("Report", back_populates="priority_history")

    def __init__(self, **kwargs):
        # Support both reasons and reasons_snapshot transparently
        if "reasons_snapshot" in kwargs and "reasons" not in kwargs:
            kwargs["reasons"] = kwargs["reasons_snapshot"]
        elif "reasons" in kwargs and "reasons_snapshot" not in kwargs:
            kwargs["reasons_snapshot"] = kwargs["reasons"]
        super().__init__(**kwargs)

    def __repr__(self):
        return (
            f"<PriorityHistory id={self.id} report_id={self.report_id} "
            f"trigger='{self.trigger}' {self.previous_priority}->{self.new_priority}>"
        )


class ReportRelation(Base):
    """Spatial and duplicate relationship between two reports (Week 8)."""
    __tablename__ = "report_relations"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(
        Integer,
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    related_report_id = Column(
        Integer,
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    distance_meters = Column(Float, nullable=False)
    relation_type = Column(String(50), nullable=False)  # POTENTIAL_DUPLICATE / NEARBY_RELATED
    review_status = Column(
        String(50),
        default="PENDING",
        nullable=False,
        index=True,
    )  # PENDING / CONFIRMED_DUPLICATE / DISMISSED
    reviewed_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("report_id", "related_report_id", name="uq_report_relations_pair"),
        CheckConstraint("report_id != related_report_id", name="ck_report_relations_no_self"),
    )

    # Relationships
    report = relationship("Report", foreign_keys=[report_id], back_populates="outgoing_relations")
    related_report = relationship("Report", foreign_keys=[related_report_id], back_populates="incoming_relations")
    reviewer = relationship("User", foreign_keys=[reviewed_by])

    def __repr__(self):
        return (
            f"<ReportRelation id={self.id} {self.report_id}<->{self.related_report_id} "
            f"type='{self.relation_type}' status='{self.review_status}'>"
        )


class Assignment(Base):
    """Historical and active assignment records linking reports to maintenance staff."""
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(
        Integer,
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_to = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    unassigned_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    note = Column(Text, nullable=True)

    # Relationships
    report = relationship("Report", back_populates="assignments", foreign_keys=[report_id])
    assignee = relationship("User", foreign_keys=[assigned_to])
    assigner = relationship("User", foreign_keys=[assigned_by])

    def __repr__(self):
        return f"<Assignment id={self.id} report_id={self.report_id} staff_id={self.assigned_to} active={self.is_active}>"


class RepairEvidence(Base):
    """Photographic evidence uploaded for road hazard remediation."""
    __tablename__ = "repair_evidence"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(
        Integer,
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    kind = Column(
        SQLEnum(EvidenceKind, values_callable=lambda obj: [e.value for e in obj]),
        default=EvidenceKind.AFTER,
        nullable=False,
    )
    file_path = Column(String(500), nullable=False)
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    checksum = Column(String(64), nullable=False)  # SHA-256
    note = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    report = relationship("Report", back_populates="repair_evidence", foreign_keys=[report_id])
    uploader = relationship("User", foreign_keys=[uploaded_by])

    def __repr__(self):
        return f"<RepairEvidence id={self.id} report_id={self.report_id} kind='{self.kind}' file='{self.file_path}'>"


class FinalVerification(Base):
    """Municipal officer final inspection and closure decision record."""
    __tablename__ = "final_verifications"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(
        Integer,
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    officer_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    decision = Column(
        SQLEnum(VerificationDecision, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    report = relationship("Report", back_populates="final_verifications", foreign_keys=[report_id])
    officer = relationship("User", foreign_keys=[officer_id])

    def __repr__(self):
        return f"<FinalVerification id={self.id} report_id={self.report_id} decision='{self.decision}'>"


