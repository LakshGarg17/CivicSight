import json
import os
import uuid
from datetime import datetime
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import Report, User, ReportStatus, UserRole, ReportStatusHistory
from app.core.dependencies import require_roles
from app.schemas.schemas import (
    ReportCreate,
    ReportUpdate,
    ReportStatusUpdate,
    ReportResponse,
    ReportVerifyRequest,
    ReportRejectRequest,
    ReportDuplicateRequest,
    ReportAssignRequest,
    ReportStatusHistoryResponse,
)

router = APIRouter(prefix="/reports", tags=["Reports"])


def infer_priority(damage_type: Optional[str]) -> str:
    """Derives default remediation priority from damage classification code."""
    dt = (damage_type or "").strip().upper()
    if dt in ["D40", "D20"]:
        return "HIGH"
    elif dt in ["D00", "D10"]:
        return "MEDIUM"
    return "LOW"


# Configure storage directory for uploaded damage photos
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
UPLOAD_DIR = os.path.join(BACKEND_DIR, "uploads", "reports")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".jfif"}


# ============================================================================
# Legal Lifecycle State Machine
# ============================================================================
# Submitted -> Pending Verification -> Verified -> Assigned -> Under Repair -> Repaired -> Closed
# Branches off Submitted / Pending Verification: Rejected, Duplicate

LEGAL_TRANSITIONS: dict[ReportStatus, set[ReportStatus]] = {
    ReportStatus.SUBMITTED: {
        ReportStatus.PENDING_VERIFICATION,
        ReportStatus.VERIFIED,
        ReportStatus.REJECTED,
        ReportStatus.DUPLICATE,
    },
    ReportStatus.PENDING_VERIFICATION: {
        ReportStatus.VERIFIED,
        ReportStatus.REJECTED,
        ReportStatus.DUPLICATE,
    },
    ReportStatus.DETECTED: {
        ReportStatus.PENDING_VERIFICATION,
        ReportStatus.VERIFIED,
        ReportStatus.REJECTED,
        ReportStatus.DUPLICATE,
    },
    ReportStatus.PRIORITIZED: {
        ReportStatus.PENDING_VERIFICATION,
        ReportStatus.VERIFIED,
        ReportStatus.REJECTED,
        ReportStatus.DUPLICATE,
    },
    ReportStatus.VERIFIED: {
        ReportStatus.ASSIGNED,
    },
    ReportStatus.ASSIGNED: {
        ReportStatus.UNDER_REPAIR,
    },
    ReportStatus.UNDER_REPAIR: {
        ReportStatus.REPAIRED,
        ReportStatus.CLOSED,
    },
    ReportStatus.REPAIRED: {
        ReportStatus.CLOSED,
    },
    ReportStatus.CLOSED: set(),
    ReportStatus.REJECTED: set(),
    ReportStatus.DUPLICATE: set(),
}


def validate_transition(current_status: ReportStatus, target_status: ReportStatus) -> None:
    """Validates that a status transition is permitted by the explicit legal transition map.
    
    Rejects illegal transitions with clear, descriptive HTTP 400 Bad Request errors.
    """
    allowed = LEGAL_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        # 1. Assignment rule: Must be verified first
        if target_status == ReportStatus.ASSIGNED and current_status != ReportStatus.VERIFIED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot assign report with status '{current_status.value}'. A report must be in 'verified' status before it can be assigned.",
            )

        # 2. Rejection rule: Cannot reject after assignment or completion
        if target_status == ReportStatus.REJECTED and current_status in [
            ReportStatus.ASSIGNED,
            ReportStatus.UNDER_REPAIR,
            ReportStatus.REPAIRED,
            ReportStatus.CLOSED,
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reject report with status '{current_status.value}'. Reports cannot be rejected once already assigned or in repair.",
            )

        # 3. Duplicate rule: Cannot mark duplicate after assignment or completion
        if target_status == ReportStatus.DUPLICATE and current_status in [
            ReportStatus.ASSIGNED,
            ReportStatus.UNDER_REPAIR,
            ReportStatus.REPAIRED,
            ReportStatus.CLOSED,
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot mark report with status '{current_status.value}' as duplicate. Reports cannot be marked as duplicate once assigned or repaired.",
            )

        # 4. Re-verification rule: Closed, repaired, or assigned reports cannot be re-verified
        if target_status == ReportStatus.VERIFIED:
            if current_status in [ReportStatus.REPAIRED, ReportStatus.CLOSED]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot verify report with status '{current_status.value}'. Already repaired or closed reports cannot be re-verified.",
                )
            if current_status == ReportStatus.ASSIGNED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot verify report with status 'assigned'. An assigned report cannot be re-verified.",
                )
            if current_status == ReportStatus.VERIFIED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Report is already verified.",
                )

        # 5. Terminal states rule
        if current_status in [ReportStatus.CLOSED, ReportStatus.REJECTED, ReportStatus.DUPLICATE]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot transition report from terminal state '{current_status.value}' to '{target_status.value}'.",
            )

        # Generic descriptive error
        allowed_list = sorted([s.value for s in allowed])
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Illegal state transition from '{current_status.value}' to '{target_status.value}'. Allowed transitions from '{current_status.value}': {allowed_list}.",
        )


def record_status_history(
    db: Session,
    report_id: int,
    from_status: Optional[str],
    to_status: str,
    user: Optional[User] = None,
    note: Optional[str] = None,
) -> ReportStatusHistory:
    """Appends an immutable transition record to the report status history log."""
    role_val = None
    if user and user.role:
        role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    name_val = user.name if user else ("System" if not from_status else None)

    history_entry = ReportStatusHistory(
        report_id=report_id,
        from_status=from_status,
        to_status=to_status,
        performed_by_id=user.id if user else None,
        performed_by_name=name_val,
        performed_by_role=role_val,
        note=note,
        created_at=datetime.utcnow(),
    )
    db.add(history_entry)
    return history_entry


# ============================================================================
# Report Creation
# ============================================================================

@router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a road damage report",
)
async def create_report(request: Request, db: Session = Depends(get_db)):
    """Creates a new road damage report.
    
    Accepts both multipart/form-data (with file upload) and application/json.
    Enforces strict server-side validation for description, image, and geographic coordinates.
    Stores the uploaded photo on disk and saves only the path reference in PostgreSQL.
    Records the initial status in report_status_history.
    """
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        
        # 1. Server-side validation: Image file
        image_file = form.get("image")
        if not image_file or not hasattr(image_file, "filename") or not image_file.filename:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Image file is required for citizen road damage reporting.",
            )
        
        ext = os.path.splitext(image_file.filename.lower())[1]
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid image format '{ext}'. Allowed formats: JPG, JPEG, PNG, WEBP.",
            )

        # 2. Server-side validation: Description
        description = form.get("description")
        if description is None or not str(description).strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Description is required and cannot be empty.",
            )
        description_clean = str(description).strip()

        # 3. Server-side validation: Latitude
        lat_raw = form.get("latitude")
        if lat_raw is None or str(lat_raw).strip() == "":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Latitude is required.",
            )
        try:
            lat_val = float(lat_raw)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Latitude must be a valid numeric coordinate.",
            )
        if not (-90.0 <= lat_val <= 90.0):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Latitude {lat_val} is out of range. Must be between -90.0 and 90.0.",
            )

        # 4. Server-side validation: Longitude
        lon_raw = form.get("longitude")
        if lon_raw is None or str(lon_raw).strip() == "":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Longitude is required.",
            )
        try:
            lon_val = float(lon_raw)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Longitude must be a valid numeric coordinate.",
            )
        if not (-180.0 <= lon_val <= 180.0):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Longitude {lon_val} is out of range. Must be between -180.0 and 180.0.",
            )

        # 5. Optional Reporter validation
        reporter_id_raw = form.get("reporter_id")
        reporter_id: Optional[int] = None
        reporter_user: Optional[User] = None
        if reporter_id_raw and str(reporter_id_raw).strip():
            try:
                reporter_id = int(reporter_id_raw)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Reporter ID must be a valid integer.",
                )
            reporter_user = db.query(User).filter(User.id == reporter_id).first()
            if not reporter_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Reporter user with ID {reporter_id} does not exist.",
                )

        # 6. Save image to disk safely
        safe_filename = f"{uuid.uuid4().hex}{ext}"
        saved_file_path = os.path.join(UPLOAD_DIR, safe_filename)
        
        try:
            contents = await image_file.read()
            with open(saved_file_path, "wb") as f:
                f.write(contents)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save image file on server: {str(e)}",
            )

        image_url = f"/uploads/reports/{safe_filename}"
        address_text = form.get("address_text")
        damage_type = form.get("damage_type")

        # Derive or extract priority
        raw_priority = form.get("priority")
        if raw_priority and str(raw_priority).strip():
            priority_val = str(raw_priority).strip().upper()
        else:
            priority_val = infer_priority(damage_type)

        raw_detections = form.get("ml_detections")
        ml_detections_str = str(raw_detections).strip() if raw_detections else None

        # 7. Commit Report record to database
        now = datetime.utcnow()
        report = Report(
            reporter_id=reporter_id,
            description=description_clean,
            latitude=lat_val,
            longitude=lon_val,
            address_text=str(address_text).strip() if address_text else None,
            image_url=image_url,
            damage_type=str(damage_type).strip() if damage_type else None,
            priority=priority_val,
            ml_detections=ml_detections_str,
            status=ReportStatus.SUBMITTED,
            created_at=now,
            updated_at=now,
        )
        db.add(report)
        db.flush()

        # 8. Record initial status in history
        record_status_history(
            db=db,
            report_id=report.id,
            from_status=None,
            to_status=ReportStatus.SUBMITTED.value,
            user=reporter_user,
            note="Initial citizen report submitted",
        )
        db.commit()
        db.refresh(report)
        return report

    else:
        # JSON Payload handler (maintains backwards compatibility for programmatic API tests)
        try:
            body = await request.json()
            report_in = ReportCreate(**body)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Malformed report payload: {str(e)}",
            )

        reporter_user = None
        if report_in.reporter_id:
            reporter_user = db.query(User).filter(User.id == report_in.reporter_id).first()
            if not reporter_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Reporter user with ID {report_in.reporter_id} does not exist.",
                )

        priority_val = report_in.priority
        if not priority_val or not str(priority_val).strip():
            priority_val = infer_priority(report_in.damage_type)
        else:
            priority_val = str(priority_val).strip().upper()

        ml_detections_str = None
        if report_in.ml_detections:
            if isinstance(report_in.ml_detections, str):
                ml_detections_str = report_in.ml_detections
            else:
                ml_detections_str = json.dumps(report_in.ml_detections)

        now = datetime.utcnow()
        initial_status = report_in.status or ReportStatus.SUBMITTED
        report = Report(
            reporter_id=report_in.reporter_id,
            description=report_in.description,
            latitude=report_in.latitude,
            longitude=report_in.longitude,
            address_text=report_in.address_text,
            image_url=report_in.image_url,
            damage_type=report_in.damage_type,
            priority=priority_val,
            ml_detections=ml_detections_str,
            status=initial_status,
            created_at=now,
            updated_at=now,
        )
        db.add(report)
        db.flush()

        record_status_history(
            db=db,
            report_id=report.id,
            from_status=None,
            to_status=initial_status.value if hasattr(initial_status, "value") else str(initial_status),
            user=reporter_user,
            note="Initial report created",
        )
        db.commit()
        db.refresh(report)
        return report


# ============================================================================
# Querying & Detail Endpoints (Municipal Officer & Admin Only)
# ============================================================================

@router.get(
    "",
    response_model=List[ReportResponse],
    summary="List road damage reports (Municipal/Admin only)",
)
def list_reports(
    status_filter: Optional[ReportStatus] = Query(None, alias="status", description="Filter by lifecycle status"),
    priority_filter: Optional[str] = Query(None, alias="priority", description="Filter by priority (HIGH, MEDIUM, LOW)"),
    reporter_id: Optional[int] = Query(None, description="Filter by reporter user ID"),
    skip: int = Query(0, ge=0, description="Pagination skip offset"),
    limit: int = Query(100, ge=1, le=200, description="Max results per page"),
    current_user: User = Depends(require_roles(UserRole.MUNICIPAL_OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Retrieves road damage reports with role-gated access (Municipal Officer / Admin ONLY).

    Supports independent or combined filtering by status and priority query parameters.
    """
    query = db.query(Report)
    if status_filter:
        query = query.filter(Report.status == status_filter)
    if priority_filter:
        query = query.filter(Report.priority == priority_filter.strip().upper())
    if reporter_id:
        query = query.filter(Report.reporter_id == reporter_id)

    reports = query.order_by(Report.created_at.desc()).offset(skip).limit(limit).all()
    return reports


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Get report by ID (Municipal/Admin only)",
)
def get_report(
    report_id: int,
    current_user: User = Depends(require_roles(UserRole.MUNICIPAL_OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Retrieves full detailed information for a single road damage report (Municipal Officer / Admin ONLY)."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {report_id} not found.",
        )
    return report


# ============================================================================
# Status Transition Endpoints (Municipal Officer & Admin Only)
# ============================================================================

@router.patch(
    "/{report_id}/verify",
    response_model=ReportResponse,
    summary="Verify road damage report (Municipal/Admin only)",
)
def verify_report(
    report_id: int,
    body: Optional[ReportVerifyRequest] = None,
    current_user: User = Depends(require_roles(UserRole.MUNICIPAL_OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Transitions a report to 'verified'.
    
    Enforces server-side lifecycle rules:
    - Only Municipal Officer and Admin roles can verify.
    - Valid from: submitted, pending_verification.
    - Rejects invalid transitions (e.g. from assigned, repaired, closed) with HTTP 400.
    - Appends transition to report status history.
    """
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {report_id} not found.",
        )

    validate_transition(report.status, ReportStatus.VERIFIED)

    prev_status = report.status.value
    report.status = ReportStatus.VERIFIED
    report.updated_at = datetime.utcnow()

    note_text = body.note if (body and body.note and body.note.strip()) else "Report verified by municipal officer"
    record_status_history(
        db=db,
        report_id=report.id,
        from_status=prev_status,
        to_status=ReportStatus.VERIFIED.value,
        user=current_user,
        note=note_text,
    )
    db.commit()
    db.refresh(report)
    return report


@router.patch(
    "/{report_id}/reject",
    response_model=ReportResponse,
    summary="Reject road damage report (Municipal/Admin only)",
)
def reject_report(
    report_id: int,
    body: ReportRejectRequest,
    current_user: User = Depends(require_roles(UserRole.MUNICIPAL_OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Transitions a report to 'rejected' with mandatory reason note.
    
    Enforces server-side lifecycle rules:
    - Only Municipal Officer and Admin roles can reject.
    - Requires a non-empty reason.
    - Valid from: submitted, pending_verification.
    - Rejects invalid transitions (e.g. already assigned, repaired, closed) with HTTP 400.
    - Appends transition to report status history with rejection reason.
    """
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {report_id} not found.",
        )

    if not body.reason or not body.reason.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Rejection reason is required.",
        )

    validate_transition(report.status, ReportStatus.REJECTED)

    prev_status = report.status.value
    report.status = ReportStatus.REJECTED
    report.rejection_reason = body.reason.strip()
    report.updated_at = datetime.utcnow()

    note_text = f"Rejection reason: {body.reason.strip()}"
    if body.note and body.note.strip():
        note_text += f" | Note: {body.note.strip()}"

    record_status_history(
        db=db,
        report_id=report.id,
        from_status=prev_status,
        to_status=ReportStatus.REJECTED.value,
        user=current_user,
        note=note_text,
    )
    db.commit()
    db.refresh(report)
    return report


@router.patch(
    "/{report_id}/duplicate",
    response_model=ReportResponse,
    summary="Mark report as duplicate of another report (Municipal/Admin only)",
)
def mark_report_duplicate(
    report_id: int,
    body: ReportDuplicateRequest,
    current_user: User = Depends(require_roles(UserRole.MUNICIPAL_OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Marks a report as 'duplicate' referencing an original report ID.
    
    Enforces server-side lifecycle rules:
    - Only Municipal Officer and Admin roles can mark duplicates.
    - Requires a valid reference to an existing original report.
    - A report cannot duplicate itself.
    - Valid from: submitted, pending_verification.
    - Rejects invalid transitions (e.g. already assigned, repaired, closed) with HTTP 400.
    - Appends transition to report status history with reference to original report ID.
    """
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {report_id} not found.",
        )

    if body.original_report_id == report_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A report cannot be marked as a duplicate of itself.",
        )

    original_report = db.query(Report).filter(Report.id == body.original_report_id).first()
    if not original_report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Original report with ID {body.original_report_id} does not exist.",
        )

    validate_transition(report.status, ReportStatus.DUPLICATE)

    prev_status = report.status.value
    report.status = ReportStatus.DUPLICATE
    report.duplicate_of_id = body.original_report_id
    report.updated_at = datetime.utcnow()

    note_text = f"Marked as duplicate of Report #{body.original_report_id}"
    if body.note and body.note.strip():
        note_text += f": {body.note.strip()}"

    record_status_history(
        db=db,
        report_id=report.id,
        from_status=prev_status,
        to_status=ReportStatus.DUPLICATE.value,
        user=current_user,
        note=note_text,
    )
    db.commit()
    db.refresh(report)
    return report


@router.patch(
    "/{report_id}/assign",
    response_model=ReportResponse,
    summary="Assign verified report to maintenance crew (Municipal/Admin only)",
)
def assign_report(
    report_id: int,
    body: ReportAssignRequest,
    current_user: User = Depends(require_roles(UserRole.MUNICIPAL_OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Transitions a report to 'assigned' and records the assigned maintenance staff.
    
    Enforces server-side lifecycle rules:
    - Only Municipal Officer and Admin roles can assign reports.
    - Requires a maintenance staff or crew identifier.
    - Valid ONLY from: verified.
    - Rejects unverified reports (e.g. submitted, pending_verification) with HTTP 400.
    - Appends transition to report status history with assigned staff information.
    """
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {report_id} not found.",
        )

    if not body.assigned_to or not body.assigned_to.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Maintenance staff identifier (assigned_to) is required.",
        )

    validate_transition(report.status, ReportStatus.ASSIGNED)

    prev_status = report.status.value
    report.status = ReportStatus.ASSIGNED
    report.assigned_to = body.assigned_to.strip()
    if body.staff_id:
        report.assigned_to_id = body.staff_id
    report.updated_at = datetime.utcnow()

    note_text = f"Assigned to: {body.assigned_to.strip()}"
    if body.note and body.note.strip():
        note_text += f" | {body.note.strip()}"

    record_status_history(
        db=db,
        report_id=report.id,
        from_status=prev_status,
        to_status=ReportStatus.ASSIGNED.value,
        user=current_user,
        note=note_text,
    )
    db.commit()
    db.refresh(report)
    return report


@router.get(
    "/{report_id}/history",
    response_model=List[ReportStatusHistoryResponse],
    summary="Get status transition history for a report (Municipal/Admin only)",
)
def get_report_history(
    report_id: int,
    current_user: User = Depends(require_roles(UserRole.MUNICIPAL_OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Retrieves the full chronological sequence of status transitions for a report."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {report_id} not found.",
        )

    history = (
        db.query(ReportStatusHistory)
        .filter(ReportStatusHistory.report_id == report_id)
        .order_by(ReportStatusHistory.created_at.asc())
        .all()
    )
    return history


@router.put(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Update report details",
)
def update_report(report_id: int, report_in: ReportUpdate, db: Session = Depends(get_db)):
    """Updates fields (description, location, status, severity, etc.) on an existing report."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {report_id} not found.",
        )

    update_data = report_in.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"] is not None:
        validate_transition(report.status, update_data["status"])
        record_status_history(
            db=db,
            report_id=report.id,
            from_status=report.status.value,
            to_status=update_data["status"].value,
            user=None,
            note="Status updated via PUT update",
        )

    for field, value in update_data.items():
        setattr(report, field, value)

    report.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(report)
    return report


@router.patch(
    "/{report_id}/status",
    response_model=ReportResponse,
    summary="Update report lifecycle status (Municipal/Admin only)",
)
def update_report_status(
    report_id: int,
    status_in: ReportStatusUpdate,
    current_user: User = Depends(require_roles(UserRole.MUNICIPAL_OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Transitions a report to a new stage in the workflow lifecycle with state validation."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {report_id} not found.",
        )

    validate_transition(report.status, status_in.status)

    prev_status = report.status.value
    report.status = status_in.status
    report.updated_at = datetime.utcnow()

    record_status_history(
        db=db,
        report_id=report.id,
        from_status=prev_status,
        to_status=status_in.status.value,
        user=current_user,
        note=f"Status transitioned to {status_in.status.value}",
    )
    db.commit()
    db.refresh(report)
    return report


@router.delete(
    "/{report_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a report",
)
def delete_report(report_id: int, db: Session = Depends(get_db)):
    """Deletes a road damage report record from the database."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {report_id} not found.",
        )

    db.delete(report)
    db.commit()
    return {"message": f"Report {report_id} successfully deleted", "id": report_id}
