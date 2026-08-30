"""CivicSight Road Damage Report CRUD Endpoints (Week 2)"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import Report, User, ReportStatus
from app.schemas.schemas import (
    ReportCreate,
    ReportUpdate,
    ReportStatusUpdate,
    ReportResponse,
)

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a road damage report",
)
def create_report(report_in: ReportCreate, db: Session = Depends(get_db)):
    """Creates a new citizen or automated road damage incident report."""
    # If reporter_id is specified, ensure user exists
    if report_in.reporter_id:
        user = db.query(User).filter(User.id == report_in.reporter_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reporter user with ID {report_in.reporter_id} does not exist.",
            )

    report = Report(
        reporter_id=report_in.reporter_id,
        description=report_in.description,
        latitude=report_in.latitude,
        longitude=report_in.longitude,
        address_text=report_in.address_text,
        image_url=report_in.image_url,
        damage_type=report_in.damage_type,
        status=report_in.status or ReportStatus.SUBMITTED,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get(
    "",
    response_model=List[ReportResponse],
    summary="List road damage reports",
)
def list_reports(
    status_filter: Optional[ReportStatus] = Query(None, alias="status", description="Filter by lifecycle status"),
    reporter_id: Optional[int] = Query(None, description="Filter by reporter user ID"),
    skip: int = Query(0, ge=0, description="Pagination skip offset"),
    limit: int = Query(50, ge=1, le=100, description="Max results per page"),
    db: Session = Depends(get_db),
):
    """Retrieves road damage reports with optional status and reporter filtering."""
    query = db.query(Report)
    if status_filter:
        query = query.filter(Report.status == status_filter)
    if reporter_id:
        query = query.filter(Report.reporter_id == reporter_id)

    reports = query.order_by(Report.created_at.desc()).offset(skip).limit(limit).all()
    return reports


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Get report by ID",
)
def get_report(report_id: int, db: Session = Depends(get_db)):
    """Retrieves detailed information for a single road damage report."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {report_id} not found.",
        )
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
