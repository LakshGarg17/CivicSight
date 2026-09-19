"""CivicSight Pydantic Schemas (Week 3)

Request and response validation models for Authentication, User, and Report CRUD operations.
"""

from datetime import datetime
from typing import Optional, List, Union, Any
import json
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.models import ReportStatus, UserRole


# ============================================================================
# User & Authentication Schemas
# ============================================================================

class UserBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, description="Full name or identifier")
    email: Optional[str] = Field(None, max_length=255, description="Contact email address")
    phone: Optional[str] = Field(None, max_length=30, description="Contact phone number")
    role: Optional[UserRole] = Field(default=UserRole.CITIZEN, description="User system role")


class UserCreate(UserBase):
    password: Optional[str] = Field(None, min_length=6, max_length=128, description="Optional initial password")


class UserRegister(BaseModel):
    """Schema for POST /auth/register endpoint."""
    name: str = Field(..., min_length=1, max_length=120, description="Full Name")
    email: str = Field(..., min_length=3, max_length=255, description="Valid email address")
    password: str = Field(..., min_length=6, max_length=128, description="Secure password (min 6 characters)")
    phone: Optional[str] = Field(None, max_length=30, description="Optional phone number")
    role: Optional[UserRole] = Field(default=UserRole.CITIZEN, description="Assigned role")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        v = v.strip().lower()
        email_regex = r"^[^@]+@[^@]+\.[^@]+$"
        if not re.match(email_regex, v):
            raise ValueError("Invalid email format")
        return v

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty or whitespace only")
        return v


class UserLogin(BaseModel):
    """Schema for POST /auth/login endpoint."""
    email: str = Field(..., description="Registered user email")
    password: str = Field(..., description="User password")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=30)
    role: Optional[UserRole] = None


class UserResponse(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: UserRole
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """JWT response payload returned upon successful login."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenPayload(BaseModel):
    """Decoded JWT claim payload."""
    sub: Optional[str] = None
    role: Optional[str] = None
    exp: Optional[int] = None


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
    priority: Optional[str] = Field("MEDIUM", description="Assigned priority: HIGH, MEDIUM, LOW")
    ml_detections: Optional[Union[dict, list, str]] = Field(None, description="Attached ML defect detection data")


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
    priority: Optional[str] = None
    ml_detections: Optional[Union[dict, list, str]] = None


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

    @field_validator("ml_detections", mode="before")
    @classmethod
    def parse_ml_detections(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return v
        return v

