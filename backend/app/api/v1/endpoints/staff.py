"""CivicSight Staff Management & Workload Endpoints (Week 9)

Provides maintenance staff workload querying for municipal dispatchers
and role-gated assignment management for field maintenance personnel.
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.db.database import get_db
from app.models.models import (
    Assignment,
    Report,
    ReportRelation,
    ReportStatus,
    User,
    UserRole,
)
from app.schemas.schemas import ReportResponse, StaffUserResponse
from app.api.v1.endpoints.reports import populate_report_relations, populate_report_lifecycle_details

router = APIRouter(prefix="/staff", tags=["Staff"])


@router.get(
    "",
    response_model=List[StaffUserResponse],
    summary="List maintenance staff with active workload counts (Officer/Admin only)",
)
def list_maintenance_staff(
    current_user: User = Depends(require_roles(UserRole.MUNICIPAL_OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Returns active maintenance staff personnel with real-time workload counts.
    
    Workload count reflects reports currently in ASSIGNED or UNDER_REPAIR status,
    allowing municipal officers to balance crew assignments effectively.
    """
    staff_users = (
        db.query(User)
        .filter(User.role == UserRole.MAINTENANCE_STAFF, User.is_active == True)
        .order_by(User.name.asc())
        .all()
    )

    results: List[StaffUserResponse] = []
    for staff in staff_users:
        # Open workload count: reports assigned to staff in ASSIGNED or UNDER_REPAIR states
        open_workload = (
            db.query(Report)
            .filter(
                or_(Report.current_assignee_id == staff.id, Report.assigned_to_id == staff.id),
                Report.status.in_([ReportStatus.ASSIGNED, ReportStatus.UNDER_REPAIR]),
            )
            .count()
        )

        # Active assignments count from assignments table
        active_assignments = (
            db.query(Assignment)
            .filter(Assignment.assigned_to == staff.id, Assignment.is_active == True)
            .count()
        )

        results.append(
            StaffUserResponse(
                id=staff.id,
                name=staff.name,
                email=staff.email,
                phone=staff.phone,
                role=staff.role,
                is_active=staff.is_active,
                open_workload_count=open_workload,
                active_assignments_count=active_assignments,
                created_at=staff.created_at,
            )
        )

    return results


@router.get(
    "/me/assignments",
    response_model=List[ReportResponse],
    summary="Get caller's assigned repair work orders (Maintenance Staff only)",
)
def get_my_assignments(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: assigned, under_repair, etc."),
    view: Optional[str] = Query("active", description="View mode: active (default), completed, all"),
    current_user: User = Depends(require_roles(UserRole.MAINTENANCE_STAFF)),
    db: Session = Depends(get_db),
):
    """Retrieves work orders assigned to the authenticated maintenance staff member.
    
    Enforces strict access isolation: staff members NEVER see reports assigned to other staff.
    Results are sorted by priority (HIGH first), then creation timestamp.
    """
    query = db.query(Report)

    if view == "completed":
        # Completed/closed reports where this staff was assigned
        query = query.filter(
            or_(
                Report.current_assignee_id == current_user.id,
                Report.id.in_(
                    db.query(Assignment.report_id).filter(Assignment.assigned_to == current_user.id)
                ),
            ),
            Report.status == ReportStatus.CLOSED,
        )
    elif view == "active":
        # Active assignments currently under this staff's responsibility
        query = query.filter(
            or_(
                Report.current_assignee_id == current_user.id,
                Report.id.in_(
                    db.query(Assignment.report_id).filter(
                        Assignment.assigned_to == current_user.id,
                        Assignment.is_active == True,
                    )
                ),
            ),
            Report.status.in_([
                ReportStatus.ASSIGNED,
                ReportStatus.UNDER_REPAIR,
                ReportStatus.REPAIR_EVIDENCE_SUBMITTED,
            ]),
        )
    else:  # "all"
        query = query.filter(
            or_(
                Report.current_assignee_id == current_user.id,
                Report.id.in_(
                    db.query(Assignment.report_id).filter(Assignment.assigned_to == current_user.id)
                ),
            )
        )

    if status_filter:
        s_val = status_filter.strip().lower()
        query = query.filter(Report.status == s_val)

    # Sort by priority (HIGH=1, MEDIUM=2, LOW=3), then date desc
    p_order = case(
        (Report.priority == "HIGH", 1),
        (Report.priority == "MEDIUM", 2),
        (Report.priority == "LOW", 3),
        else_=4,
    )
    reports = query.order_by(p_order.asc(), Report.created_at.desc()).all()

    for rep in reports:
        populate_report_lifecycle_details(rep, db)
        populate_report_relations(rep, db, is_privileged=True)

    return reports

