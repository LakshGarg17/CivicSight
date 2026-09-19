import json
import os
import uuid
from datetime import datetime
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import Report, User, ReportStatus, UserRole
from app.core.dependencies import require_roles
from app.schemas.schemas import (
    ReportCreate,
    ReportUpdate,
    ReportStatusUpdate,
    ReportResponse,
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
        if reporter_id_raw and str(reporter_id_raw).strip():
            try:
                reporter_id = int(reporter_id_raw)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Reporter ID must be a valid integer.",
                )
            user = db.query(User).filter(User.id == reporter_id).first()
            if not user:
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

        # 7. Commit Report record to PostgreSQL
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

        if report_in.reporter_id:
            user = db.query(User).filter(User.id == report_in.reporter_id).first()
            if not user:
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
            status=report_in.status or ReportStatus.SUBMITTED,
            created_at=now,
            updated_at=now,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report


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
    limit: int = Query(50, ge=1, le=100, description="Max results per page"),
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


@router.patch(
    "/{report_id}/verify",
    response_model=ReportResponse,
    summary="Verify road damage report (Municipal/Admin only)",
)
def verify_report(
    report_id: int,
    current_user: User = Depends(require_roles(UserRole.MUNICIPAL_OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Marks a report as verified by an authorized municipal officer.
    
    Enforces that:
    - Only Municipal Officer and Admin roles can verify.
    - The report exists (404).
    - The report is in a valid state (cannot verify already closed or repaired reports -> 400).
    """
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {report_id} not found.",
        )

    if report.status in [ReportStatus.REPAIRED, ReportStatus.CLOSED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot verify report with status '{report.status.value}'. Already repaired or closed reports cannot be verified.",
        )

    report.status = ReportStatus.VERIFIED
    report.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(report)
    return report


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
    for field, value in update_data.items():
        setattr(report, field, value)

    report.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(report)
    return report


@router.patch(
    "/{report_id}/status",
    response_model=ReportResponse,
    summary="Update report lifecycle status",
)
def update_report_status(report_id: int, status_in: ReportStatusUpdate, db: Session = Depends(get_db)):
    """Transitions a report to a new stage in the workflow lifecycle."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {report_id} not found.",
        )

    report.status = status_in.status
    report.updated_at = datetime.utcnow()
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
