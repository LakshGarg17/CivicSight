import json
import os
import uuid
from datetime import datetime
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, BackgroundTasks
from sqlalchemy import or_, case
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import (
    Report,
    User,
    ReportStatus,
    UserRole,
    ReportStatusHistory,
    PriorityHistory,
    ReportRelation,
)
from app.core.dependencies import require_roles, get_current_user
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
    ReportMLStatusResponse,
    DetectionResultResponse,
    RelatedReportItemResponse,
    PriorityHistoryResponse,
    PriorityOverrideRequest,
)
from app.services.ml_service import process_report_image_ml
from app.services.proximity import process_report_proximity, update_single_report_priority

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


def populate_report_relations(report: Report, db: Session, is_privileged: bool = False) -> None:
    """Populates related_reports list and has_pending_relations flag on a Report instance."""
    relations = (
        db.query(ReportRelation)
        .filter(
            or_(
                ReportRelation.report_id == report.id,
                ReportRelation.related_report_id == report.id,
            )
        )
        .all()
    )
    report.has_pending_relations = any(r.review_status == "PENDING" for r in relations)

    # Citizens must not receive other people's report data
    if not is_privileged:
        report.related_reports = []
        return

    related_items: List[RelatedReportItemResponse] = []
    for rel in relations:
        other_id = rel.related_report_id if rel.report_id == report.id else rel.report_id
        other = db.query(Report).filter(Report.id == other_id).first()
        if other:
            related_items.append(
                RelatedReportItemResponse(
                    relation_id=rel.id,
                    report_id=report.id,
                    related_report_id=other_id,
                    distance_meters=rel.distance_meters,
                    relation_type=rel.relation_type,
                    review_status=rel.review_status,
                    reviewed_by=rel.reviewed_by,
                    reviewed_at=rel.reviewed_at,
                    note=rel.note,
                    status=other.status.value if hasattr(other.status, "value") else str(other.status),
                    priority=other.priority,
                    severity=other.severity,
                    damage_type=other.damage_type,
                    description=other.description,
                    address_text=other.address_text,
                    image_url=other.image_url,
                    created_at=other.created_at,
                )
            )
    report.related_reports = related_items



# ============================================================================
# Report Creation
# ============================================================================

@router.post(
    "/detect",
    summary="Run pre-submission road damage detection on an uploaded photo",
)
async def detect_damage_on_image(
    request: Request,
):
    """Executes real-time YOLO damage detection on an uploaded image before report creation.
    
    Accepts multipart/form-data with 'image' or 'file'.
    Returns detected bounding boxes, class names (D00, D10, D20, D40), confidence, and priority.
    """
    form = await request.form()
    image_file = form.get("image") or form.get("file")
    if not image_file or not hasattr(image_file, "filename") or not image_file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Image file is required for defect detection.",
        )

    ext = os.path.splitext(image_file.filename.lower())[1]
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid image format '{ext}'. Allowed formats: JPG, JPEG, PNG, WEBP.",
        )

    try:
        contents = await image_file.read()
        if not contents or len(contents) == 0:
            raise ValueError("Empty image file provided.")

        import cv2
        import numpy as np
        from ml.src.inference import detect_road_damage

        nparr = np.frombuffer(contents, np.uint8)
        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            raise ValueError("Could not decode image file bytes.")

        conf_raw = form.get("confidence_threshold")
        try:
            conf_thresh = float(conf_raw) if conf_raw else 0.25
            conf_thresh = max(0.05, min(0.95, conf_thresh))
        except (ValueError, TypeError):
            conf_thresh = 0.25

        result = detect_road_damage(img_bgr, confidence_threshold=conf_thresh, iou_threshold=0.45)
        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process image with detection model: {str(e)}",
        )


@router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a road damage report",
)
async def create_report(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
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
        else:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                try:
                    token = auth_header.split(" ")[1]
                    from app.core.security import decode_access_token
                    payload = decode_access_token(token)
                    if payload and "sub" in payload:
                        reporter_id = int(payload["sub"])
                        reporter_user = db.query(User).filter(User.id == reporter_id).first()
                except Exception:
                    pass

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
            ml_status="ML_PENDING",
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

        # Initial proximity analysis and priority scoring (guarded so failure never blocks creation)
        try:
            process_report_proximity(report, db, recalculate_neighbors=True)
            db.refresh(report)
        except Exception as prox_err:
            logger.error(f"[Proximity] Initial proximity failure for report #{report.id}: {prox_err}", exc_info=True)

        # 9. Asynchronously process image with YOLO defect detection
        background_tasks.add_task(process_report_image_ml, report.id)

        populate_report_relations(report, db, is_privileged=True)
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
        effective_reporter_id = report_in.reporter_id
        if effective_reporter_id:
            reporter_user = db.query(User).filter(User.id == effective_reporter_id).first()
            if not reporter_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Reporter user with ID {effective_reporter_id} does not exist.",
                )
        else:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                try:
                    token = auth_header.split(" ")[1]
                    from app.core.security import decode_access_token
                    payload = decode_access_token(token)
                    if payload and "sub" in payload:
                        effective_reporter_id = int(payload["sub"])
                        reporter_user = db.query(User).filter(User.id == effective_reporter_id).first()
                except Exception:
                    pass

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
        ml_status_init = "ML_PENDING" if report_in.image_url else None
        report = Report(
            reporter_id=effective_reporter_id,
            description=report_in.description,
            latitude=report_in.latitude,
            longitude=report_in.longitude,
            address_text=report_in.address_text,
            image_url=report_in.image_url,
            damage_type=report_in.damage_type,
            priority=priority_val,
            ml_detections=ml_detections_str,
            ml_status=ml_status_init,
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

        # Initial proximity analysis and priority scoring (guarded so failure never blocks creation)
        try:
            process_report_proximity(report, db, recalculate_neighbors=True)
        except Exception as prox_err:
            logger.error(f"[Proximity] Initial proximity failure for report #{report.id}: {prox_err}", exc_info=True)

        if report_in.image_url:
            background_tasks.add_task(process_report_image_ml, report.id)

        populate_report_relations(report, db, is_privileged=True)
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
    severity_filter: Optional[str] = Query(None, alias="severity", description="Filter by severity (HIGH, MEDIUM, LOW, UNKNOWN)"),
    sort_by: Optional[str] = Query(None, description="Sort field: priority, score, priority_score, created_at"),
    sort_order: Optional[str] = Query("desc", description="Sort order: asc, desc"),
    reporter_id: Optional[int] = Query(None, description="Filter by reporter user ID"),
    skip: int = Query(0, ge=0, description="Pagination skip offset"),
    limit: int = Query(100, ge=1, le=200, description="Max results per page"),
    current_user: User = Depends(require_roles(UserRole.MUNICIPAL_OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Retrieves road damage reports with role-gated access (Municipal Officer / Admin ONLY).

    Supports independent or combined filtering by status, priority, and severity query parameters.
    Supports sorting by priority (HIGH first), score, or creation timestamp.
    """
    query = db.query(Report)
    if status_filter:
        query = query.filter(Report.status == status_filter)
    if priority_filter:
        query = query.filter(Report.priority == priority_filter.strip().upper())
    if severity_filter:
        query = query.filter(Report.severity == severity_filter.strip().upper())
    if reporter_id:
        query = query.filter(Report.reporter_id == reporter_id)

    if sort_by == "priority":
        p_order = case(
            (Report.priority == "HIGH", 1),
            (Report.priority == "MEDIUM", 2),
            (Report.priority == "LOW", 3),
            else_=4,
        )
        if sort_order and sort_order.lower() == "asc":
            query = query.order_by(p_order.desc(), Report.created_at.desc())
        else:
            query = query.order_by(p_order.asc(), Report.priority_score.desc().nullslast(), Report.created_at.desc())
    elif sort_by in ["score", "priority_score"]:
        if sort_order and sort_order.lower() == "asc":
            query = query.order_by(Report.priority_score.asc().nullsfirst(), Report.created_at.asc())
        else:
            query = query.order_by(Report.priority_score.desc().nullslast(), Report.created_at.desc())
    else:
        query = query.order_by(Report.created_at.desc())

    reports = query.offset(skip).limit(limit).all()

    # Pre-fetch pending relations to populate has_pending_relations flag efficiently
    pending_relations = (
        db.query(ReportRelation.report_id, ReportRelation.related_report_id)
        .filter(ReportRelation.review_status == "PENDING")
        .all()
    )
    pending_relation_report_ids = set()
    for r1, r2 in pending_relations:
        pending_relation_report_ids.add(r1)
        pending_relation_report_ids.add(r2)

    for rep in reports:
        rep.has_pending_relations = rep.id in pending_relation_report_ids
        rep.related_reports = []

    return reports


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Get report by ID (Municipal/Admin or owning Citizen)",
)
def get_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves full detailed information for a single road damage report.
    
    Accessible by Municipal Officers, Admins, or the Citizen who authored the report.
    Citizens see their report's priority and assessment, but never other citizens' reports.
    """
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {report_id} not found.",
        )

    user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    is_privileged = user_role in [UserRole.MUNICIPAL_OFFICER.value, UserRole.ADMIN.value]
    is_owner = report.reporter_id is not None and report.reporter_id == current_user.id

    if not (is_privileged or is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not authorized to access this report.",
        )

    populate_report_relations(report, db, is_privileged=is_privileged)
    return report


@router.get(
    "/{report_id}/ml-status",
    response_model=ReportMLStatusResponse,
    summary="Get ML assessment status and detections for a report (Public/Citizen polling)",
)
def get_report_ml_status(
    report_id: int,
    db: Session = Depends(get_db),
):
    """Returns the ML inference status (ML_PENDING, ML_COMPLETE, ML_NO_DETECTIONS, ML_FAILED)
    and associated bounding box detections for public and citizen status tracking.
    """
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {report_id} not found.",
        )

    return ReportMLStatusResponse(
        id=report.id,
        status=report.status,
        ml_status=report.ml_status or "ML_PENDING",
        ml_model_version=report.ml_model_version,
        ml_inference_time_ms=report.ml_inference_time_ms,
        ml_processed_at=report.ml_processed_at,
        ml_error_message=report.ml_error_message,
        num_detections=len(report.detection_results),
        detection_results=report.detection_results,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.post(
    "/{report_id}/process-ml",
    response_model=ReportResponse,
    summary="Trigger ML damage detection inference on a report",
)
def trigger_report_ml_inference(
    report_id: int,
    sync: bool = Query(True, description="Whether to execute synchronously before returning"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """Executes or enqueues YOLOv8 damage detection for a specific report."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {report_id} not found.",
        )

    if sync:
        process_report_image_ml(report_id=report.id, db=db)
        db.refresh(report)
        return report
    else:
        report.ml_status = "ML_PENDING"
        db.commit()
        if background_tasks:
            background_tasks.add_task(process_report_image_ml, report.id)
        return report


# ============================================================================
# Priority & Spatial Relations Endpoints (Municipal Officer & Admin Only)
# ============================================================================

@router.get(
    "/{report_id}/related",
    response_model=List[RelatedReportItemResponse],
    summary="Get spatial relations and potential duplicates for a report (Municipal/Admin only)",
)
def get_report_related_reports(
    report_id: int,
    current_user: User = Depends(require_roles(UserRole.MUNICIPAL_OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Retrieves spatial neighbors and potential duplicate relations for a report.
    
    Restricted to Municipal Officers and Admins (403 for Citizen, 401 unauthenticated).
    """
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {report_id} not found.",
        )

    populate_report_relations(report, db, is_privileged=True)
    return report.related_reports


@router.get(
    "/{report_id}/priority-history",
    response_model=List[PriorityHistoryResponse],
    summary="Get priority and severity audit history for a report (Municipal/Admin only)",
)
def get_report_priority_history(
    report_id: int,
    current_user: User = Depends(require_roles(UserRole.MUNICIPAL_OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Returns the immutable chronological log of priority/severity scoring updates."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {report_id} not found.",
        )

    history = (
        db.query(PriorityHistory)
        .filter(PriorityHistory.report_id == report_id)
        .order_by(PriorityHistory.created_at.asc())
        .all()
    )
    return history


@router.post(
    "/{report_id}/recalculate-priority",
    response_model=ReportResponse,
    summary="Recalculate report priority and update spatial neighbors (Municipal/Admin only)",
)
def recalculate_report_priority(
    report_id: int,
    current_user: User = Depends(require_roles(UserRole.MUNICIPAL_OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Manually triggers recalculation of spatial proximity and priority scoring."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {report_id} not found.",
        )

    process_report_proximity(report, db, recalculate_neighbors=True)
    update_single_report_priority(report, db, trigger="recalculated")

    db.refresh(report)
    populate_report_relations(report, db, is_privileged=True)
    return report


@router.post(
    "/{report_id}/override-priority",
    response_model=ReportResponse,
    summary="Manually override report priority with audit reason (Municipal/Admin only)",
)
def override_report_priority(
    report_id: int,
    body: PriorityOverrideRequest,
    current_user: User = Depends(require_roles(UserRole.MUNICIPAL_OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Manually sets report priority. Overridden priorities are flagged and protected from automatic recalculations."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {report_id} not found.",
        )

    if not body.reason or not body.reason.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A non-empty reason is required for manual priority override.",
        )

    target_priority = body.priority.strip().upper()
    if target_priority not in ["HIGH", "MEDIUM", "LOW"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid priority '{body.priority}'. Must be HIGH, MEDIUM, or LOW.",
        )

    prev_priority = report.priority
    prev_severity = report.severity

    report.priority = target_priority
    report.is_priority_overridden = True
    report.priority_override_reason = body.reason.strip()
    report.priority_updated_at = datetime.utcnow()

    raw_reasons = report.priority_reasons
    if isinstance(raw_reasons, str):
        try:
            reasons_list = json.loads(raw_reasons)
        except Exception:
            reasons_list = [raw_reasons] if raw_reasons else []
    elif isinstance(raw_reasons, list):
        reasons_list = raw_reasons
    else:
        reasons_list = []

    override_label = f"Manual override by {current_user.name or 'Officer'}: {body.reason.strip()}"
    new_reasons = [override_label] + [r for r in reasons_list if not str(r).startswith("Manual override")]
    report.priority_reasons = json.dumps(new_reasons)

    history_row = PriorityHistory(
        report_id=report.id,
        previous_priority=prev_priority,
        new_priority=report.priority,
        previous_severity=prev_severity,
        new_severity=report.severity,
        score=report.priority_score,
        reasons_snapshot=json.dumps(new_reasons),
        trigger="manual_override",
        created_at=datetime.utcnow(),
    )
    db.add(history_row)
    db.commit()
    db.refresh(report)

    populate_report_relations(report, db, is_privileged=True)
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
