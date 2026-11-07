"""CivicSight Pydantic Schemas (Week 3)

Request and response validation models for Authentication, User, and Report CRUD operations.
"""

from datetime import datetime
from typing import Optional, List, Union, Any
import json
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.models.models import ReportStatus, UserRole, EvidenceKind, VerificationDecision


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
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StaffUserResponse(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: UserRole
    is_active: bool = True
    open_workload_count: int = 0
    active_assignments_count: int = 0
    created_at: datetime

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


class ReportVerifyRequest(BaseModel):
    note: Optional[str] = Field(None, description="Optional note or inspection comments")


class ReportRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Reason for rejecting the report")
    note: Optional[str] = Field(None, description="Additional context or notes")

    @field_validator("reason")
    @classmethod
    def validate_reason_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Rejection reason cannot be empty")
        return v


class ReportDuplicateRequest(BaseModel):
    original_report_id: int = Field(..., ge=1, description="ID of the original report that this duplicates")
    note: Optional[str] = Field(None, description="Additional context or notes")


class ReportAssignRequest(BaseModel):
    assigned_to: Optional[str] = Field(None, description="Maintenance staff member or crew identifier")
    staff_id: Optional[int] = Field(None, description="Optional user ID of assigned maintenance staff")
    note: Optional[str] = Field(None, description="Optional assignment notes or instructions")

    @model_validator(mode="before")
    @classmethod
    def resolve_staff(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("staff_id") and data.get("assigned_to"):
                val = str(data["assigned_to"]).strip()
                if val.isdigit():
                    data["staff_id"] = int(val)
            elif not data.get("assigned_to") and data.get("staff_id"):
                data["assigned_to"] = str(data["staff_id"])
        return data


class AssignmentCreate(BaseModel):
    staff_id: Optional[int] = Field(None, description="ID of active maintenance staff user")
    assigned_to: Optional[Union[str, int]] = Field(None, description="Staff identifier or name")
    note: Optional[str] = Field(None, description="Optional assignment note or instructions")

    @model_validator(mode="before")
    @classmethod
    def resolve_staff(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("staff_id") and data.get("assigned_to"):
                val = str(data["assigned_to"]).strip()
                if val.isdigit():
                    data["staff_id"] = int(val)
            elif not data.get("assigned_to") and data.get("staff_id"):
                data["assigned_to"] = str(data["staff_id"])
        return data


class AssignmentReassign(BaseModel):
    staff_id: Optional[int] = Field(None, description="ID of new maintenance staff user")
    new_staff_id: Optional[int] = Field(None, description="Alias for staff_id")
    assigned_to: Optional[Union[str, int]] = Field(None, description="Staff identifier or name")
    reason: str = Field(..., min_length=1, description="Mandatory reason for reassigning")
    note: Optional[str] = Field(None, description="Optional reassignment note")

    @model_validator(mode="before")
    @classmethod
    def resolve_staff(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("staff_id") and data.get("new_staff_id"):
                data["staff_id"] = data["new_staff_id"]
            if not data.get("staff_id") and data.get("assigned_to"):
                val = str(data["assigned_to"]).strip()
                if val.isdigit():
                    data["staff_id"] = int(val)
            elif not data.get("assigned_to") and data.get("staff_id"):
                data["assigned_to"] = str(data["staff_id"])
        return data

    @field_validator("reason")
    @classmethod
    def validate_reason_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Reassignment reason cannot be empty")
        return v


class AssignmentUnassign(BaseModel):
    reason: str = Field(..., min_length=1, description="Mandatory reason for unassigning")
    note: Optional[str] = Field(None, description="Optional note")

    @field_validator("reason")
    @classmethod
    def validate_reason_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Unassign reason cannot be empty")
        return v


class AssignmentResponse(BaseModel):
    id: int
    report_id: int
    assigned_to: int
    assigned_to_name: Optional[str] = None
    assigned_to_email: Optional[str] = None
    assigned_by: Optional[int] = None
    assigned_by_name: Optional[str] = None
    assigned_at: datetime
    unassigned_at: Optional[datetime] = None
    is_active: bool
    note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def populate_orm_fields(cls, data: Any) -> Any:
        if hasattr(data, "assignee"):
            assignee = getattr(data, "assignee", None)
            assigner = getattr(data, "assigner", None)
            return {
                "id": getattr(data, "id", 0),
                "report_id": getattr(data, "report_id", 0),
                "assigned_to": getattr(data, "assigned_to", 0),
                "assigned_to_name": assignee.name if assignee else None,
                "assigned_to_email": assignee.email if assignee else None,
                "assigned_by": getattr(data, "assigned_by", None),
                "assigned_by_name": assigner.name if assigner else None,
                "assigned_at": getattr(data, "assigned_at", datetime.utcnow()),
                "unassigned_at": getattr(data, "unassigned_at", None),
                "is_active": getattr(data, "is_active", True),
                "note": getattr(data, "note", None),
            }
        return data


class RepairEvidenceResponse(BaseModel):
    id: int
    report_id: int
    uploaded_by: Optional[int] = None
    uploaded_by_name: Optional[str] = None
    kind: str
    file_path: str
    original_filename: str
    mime_type: str
    size_bytes: int
    checksum: str
    note: Optional[str] = None
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def populate_orm_fields(cls, data: Any) -> Any:
        if hasattr(data, "uploader") or hasattr(data, "kind"):
            uploader = getattr(data, "uploader", None)
            k = getattr(data, "kind", "AFTER")
            k_str = k.value if hasattr(k, "value") else str(k)
            return {
                "id": getattr(data, "id", 0),
                "report_id": getattr(data, "report_id", 0),
                "uploaded_by": getattr(data, "uploaded_by", None),
                "uploaded_by_name": uploader.name if uploader else None,
                "kind": k_str,
                "file_path": getattr(data, "file_path", ""),
                "original_filename": getattr(data, "original_filename", ""),
                "mime_type": getattr(data, "mime_type", ""),
                "size_bytes": getattr(data, "size_bytes", 0),
                "checksum": getattr(data, "checksum", ""),
                "note": getattr(data, "note", None),
                "uploaded_at": getattr(data, "uploaded_at", datetime.utcnow()),
            }
        return data


class FinalVerificationRequest(BaseModel):
    decision: VerificationDecision = Field(..., description="Decision: APPROVED or SENT_BACK")
    note: Optional[str] = Field(None, description="Inspection feedback (mandatory if SENT_BACK)")

    @model_validator(mode="after")
    def check_sent_back_note(self):
        if self.decision == VerificationDecision.SENT_BACK:
            if not self.note or not self.note.strip():
                raise ValueError("Note is required when sending report back for rework")
        return self


class FinalVerificationResponse(BaseModel):
    id: int
    report_id: int
    officer_id: Optional[int] = None
    officer_name: Optional[str] = None
    decision: str
    note: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def populate_orm_fields(cls, data: Any) -> Any:
        if hasattr(data, "officer") or hasattr(data, "decision"):
            officer = getattr(data, "officer", None)
            d = getattr(data, "decision", "")
            d_str = d.value if hasattr(d, "value") else str(d)
            return {
                "id": getattr(data, "id", 0),
                "report_id": getattr(data, "report_id", 0),
                "officer_id": getattr(data, "officer_id", None),
                "officer_name": officer.name if officer else None,
                "decision": d_str,
                "note": getattr(data, "note", None),
                "created_at": getattr(data, "created_at", datetime.utcnow()),
            }
        return data


class ReopenRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Mandatory reason for reopening report")

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Reopen reason cannot be empty")
        return v


class ReportStatusHistoryResponse(BaseModel):
    id: int
    report_id: int
    from_status: Optional[str] = None
    to_status: str
    performed_by_id: Optional[int] = None
    performed_by_name: Optional[str] = None
    performed_by_role: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DetectionResultResponse(BaseModel):
    """Structured detection response for a single bounding box finding (Week 7)."""
    id: int
    report_id: int
    detected_class: str
    class_name: Optional[str] = None
    confidence: float
    bbox_xmin: float
    bbox_ymin: float
    bbox_xmax: float
    bbox_ymax: float
    bbox: Optional[List[float]] = None
    bbox_normalized: Optional[List[float]] = None
    severity: Optional[str] = "MEDIUM"
    model_version: str
    inference_timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def compute_bbox_fields(cls, data: Any) -> Any:
        if hasattr(data, "bbox_xmin"):
            norm = getattr(data, "bbox_normalized", None)
            if isinstance(norm, str):
                try:
                    norm = json.loads(norm)
                except Exception:
                    norm = None
            return {
                "id": getattr(data, "id", 0),
                "report_id": getattr(data, "report_id", 0),
                "detected_class": getattr(data, "detected_class", ""),
                "class_name": getattr(data, "class_name", None),
                "confidence": getattr(data, "confidence", 0.0),
                "bbox_xmin": getattr(data, "bbox_xmin", 0.0),
                "bbox_ymin": getattr(data, "bbox_ymin", 0.0),
                "bbox_xmax": getattr(data, "bbox_xmax", 0.0),
                "bbox_ymax": getattr(data, "bbox_ymax", 0.0),
                "bbox": [
                    getattr(data, "bbox_xmin", 0.0),
                    getattr(data, "bbox_ymin", 0.0),
                    getattr(data, "bbox_xmax", 0.0),
                    getattr(data, "bbox_ymax", 0.0),
                ],
                "bbox_normalized": norm,
                "severity": getattr(data, "severity", "MEDIUM"),
                "model_version": getattr(data, "model_version", ""),
                "inference_timestamp": getattr(data, "inference_timestamp", datetime.utcnow()),
            }
        elif isinstance(data, dict):
            if "bbox" not in data and "bbox_xmin" in data:
                data["bbox"] = [
                    data.get("bbox_xmin", 0.0),
                    data.get("bbox_ymin", 0.0),
                    data.get("bbox_xmax", 0.0),
                    data.get("bbox_ymax", 0.0),
                ]
            if isinstance(data.get("bbox_normalized"), str):
                try:
                    data["bbox_normalized"] = json.loads(data["bbox_normalized"])
                except Exception:
                    data["bbox_normalized"] = None
            return data
        return data


# ============================================================================
# Week 8 Priority Engine & Proximity Schemas
# ============================================================================

class RelatedReportItemResponse(BaseModel):
    """Schema for a related report reference linked to a target report."""
    relation_id: int
    report_id: int
    related_report_id: int
    distance_meters: float
    relation_type: str  # POTENTIAL_DUPLICATE | NEARBY_RELATED
    review_status: str  # PENDING | CONFIRMED_DUPLICATE | DISMISSED
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    note: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    severity: Optional[str] = None
    damage_type: Optional[str] = None
    description: Optional[str] = None
    address_text: Optional[str] = None
    image_url: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PriorityHistoryResponse(BaseModel):
    """Audit log entry for priority/severity recalculation or manual override."""
    id: int
    report_id: int
    previous_priority: Optional[str] = None
    new_priority: Optional[str] = None
    previous_severity: Optional[str] = None
    new_severity: Optional[str] = None
    score: Optional[float] = None
    reasons: Optional[List[str]] = []
    trigger: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("reasons", mode="before")
    @classmethod
    def parse_reasons(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
                return [str(parsed)]
            except Exception:
                return [v]
        return v or []


class ReportRelationReviewRequest(BaseModel):
    """Payload for PATCH /report-relations/{relation_id}."""
    review_status: str = Field(..., description="Target review status: CONFIRMED_DUPLICATE or DISMISSED")
    note: Optional[str] = Field(None, description="Optional officer review note or justification")

    @field_validator("review_status")
    @classmethod
    def validate_review_status(cls, v: str) -> str:
        val = v.strip().upper()
        if val not in ("CONFIRMED_DUPLICATE", "DISMISSED"):
            raise ValueError("review_status must be either 'CONFIRMED_DUPLICATE' or 'DISMISSED'")
        return val


class PriorityOverrideRequest(BaseModel):
    """Payload for POST /reports/{id}/override-priority."""
    priority: str = Field(..., description="Target manual priority: HIGH, MEDIUM, or LOW")
    reason: str = Field(..., min_length=1, description="Required justification for manual priority override")

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        val = v.strip().upper()
        if val not in ("HIGH", "MEDIUM", "LOW"):
            raise ValueError("priority must be 'HIGH', 'MEDIUM', or 'LOW'")
        return val

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        val = v.strip()
        if not val:
            raise ValueError("Override reason cannot be empty")
        return val


class ReportResponse(ReportBase):
    id: int
    reporter_id: Optional[int] = None
    status: ReportStatus
    severity_score: Optional[float] = None
    assigned_to: Optional[str] = None
    assigned_to_id: Optional[int] = None
    duplicate_of_id: Optional[int] = None
    rejection_reason: Optional[str] = None

    # Week 8: Priority & Relations
    severity: Optional[str] = "UNKNOWN"
    priority_score: Optional[float] = None
    priority_reasons: Optional[List[str]] = []
    priority_updated_at: Optional[datetime] = None
    nearby_report_count: int = 0
    is_priority_overridden: bool = False
    priority_override_reason: Optional[str] = None
    has_pending_relations: bool = False
    related_reports: List[RelatedReportItemResponse] = []

    # ML Pipeline Enrichment (Week 7)
    ml_status: Optional[str] = "ML_PENDING"
    ml_model_version: Optional[str] = None
    ml_inference_time_ms: Optional[float] = None
    ml_processed_at: Optional[datetime] = None
    ml_error_message: Optional[str] = None
    detection_results: List[DetectionResultResponse] = []

    # Week 9 Lifecycle Additions
    current_assignee_id: Optional[int] = None
    current_assignee_name: Optional[str] = None
    repair_started_at: Optional[datetime] = None
    repair_submitted_at: Optional[datetime] = None
    final_verified_at: Optional[datetime] = None
    final_verified_by: Optional[int] = None
    final_verified_by_name: Optional[str] = None
    closed_at: Optional[datetime] = None
    version: int = 1
    assignments: List[AssignmentResponse] = []
    before_images: List[str] = []
    after_images: List[RepairEvidenceResponse] = []
    final_verifications: List[FinalVerificationResponse] = []

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

    @field_validator("priority_reasons", mode="before")
    @classmethod
    def parse_priority_reasons(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
                return [str(parsed)]
            except Exception:
                return [v]
        return v or []


class ReportMLStatusResponse(BaseModel):
    """Targeted response schema for ML inference status polling."""
    id: int
    status: ReportStatus
    ml_status: str
    ml_model_version: Optional[str] = None
    ml_inference_time_ms: Optional[float] = None
    ml_processed_at: Optional[datetime] = None
    ml_error_message: Optional[str] = None
    num_detections: int = 0
    detection_results: List[DetectionResultResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


