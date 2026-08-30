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


class ReportStatus(str, enum.Enum):
    """Lifecycle stages of a road damage report."""
    SUBMITTED = "submitted"
    DETECTED = "detected"
    PRIORITIZED = "prioritized"
    VERIFIED = "verified"
    ASSIGNED = "assigned"
    REPAIRED = "repaired"
    CLOSED = "closed"


class User(Base):
    """User entity representing a reporting citizen or municipal contact."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, index=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    phone = Column(String(30), nullable=True)
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
    )

    def __repr__(self):
        return f"<User id={self.id} name='{self.name}' email='{self.email}'>"


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

    # Future extensibility fields reserved for upcoming weeks
    # e.g., damage_type (D00-D40), severity_score, assigned_crew_id, repair_cost
    severity_score = Column(Float, nullable=True)
    damage_type = Column(String(50), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    reporter = relationship("User", back_populates="reports")

    def __repr__(self):
        return f"<Report id={self.id} status='{self.status}' reporter_id={self.reporter_id}>"
