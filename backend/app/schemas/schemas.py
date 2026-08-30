"""CivicSight Pydantic Schemas (Week 2)

Request and response validation models for User and Report CRUD operations.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from app.models.models import ReportStatus


# ============================================================================
# User Schemas
# ============================================================================

class UserBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, description="Full name or identifier")
    email: Optional[str] = Field(None, max_length=255, description="Contact email address")
    phone: Optional[str] = Field(None, max_length=30, description="Contact phone number")


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=30)


class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Report Schemas
# ============================================================================

class ReportBase(BaseModel):
    description: Optional[str] = Field(None, description="Detailed problem description")
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0, description="GPS Latitude coordinate")
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0, description="GPS Longitude coordinate")
    address_text: Optional[str] = Field(None, max_length=255, description="Human-readable address or landmark")
    image_url: Optional[str] = Field(None, max_length=500, description="Path or URL to damage photo")
    damage_type: Optional[str] = Field(None, max_length=50, description="Initial damage type (e.g. D00, D10, D20, D40)")


class ReportCreate(ReportBase):
    reporter_id: Optional[int] = Field(None, description="Optional foreign key to User")
    status: Optional[ReportStatus] = Field(default=ReportStatus.SUBMITTED, description="Initial status")


class ReportUpdate(BaseModel):
    description: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    address_text: Optional[str] = None
    image_url: Optional[str] = None
    status: Optional[ReportStatus] = None
    damage_type: Optional[str] = None
    severity_score: Optional[float] = None


class ReportStatusUpdate(BaseModel):
    status: ReportStatus = Field(..., description="Updated report lifecycle status")


class ReportResponse(ReportBase):
    id: int
    reporter_id: Optional[int] = None
    status: ReportStatus
    severity_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    reporter: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)
