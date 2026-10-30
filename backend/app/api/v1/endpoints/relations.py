"""CivicSight Report Relations Endpoints (Week 8)

Handles municipal review of spatial proximity and duplicate report relations:
- PATCH /report-relations/{relation_id} (CONFIRMED_DUPLICATE or DISMISSED)
- Gated to Municipal Officer and Admin roles only (403 for Citizen, 401 unauthenticated)
- Reuses Week 6 duplicate workflow and legal transition rules
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import Report, ReportRelation, ReportStatus, User, UserRole, ReportStatusHistory
from app.core.dependencies import require_roles
from app.schemas.schemas import ReportRelationReviewRequest, RelatedReportItemResponse

router = APIRouter(prefix="/report-relations", tags=["Report Relations"])


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
    name_val = user.name if user else None

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


@router.patch(
    "/{relation_id}",
    response_model=RelatedReportItemResponse,
    summary="Review spatial report relation (Confirm Duplicate / Dismiss) — Officer/Admin only",
)
def review_report_relation(
    relation_id: int,
    body: ReportRelationReviewRequest,
    current_user: User = Depends(require_roles(UserRole.MUNICIPAL_OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Reviews a potential duplicate or nearby report relation.
    
    Rules:
    - Only Municipal Officers and Admins may review relations (403 for Citizen, 401 if unauthenticated).
    - Target relation must exist (404 otherwise).
    - Target relation must currently be PENDING; second review attempts are strictly rejected (400 Bad Request).
    - If CONFIRMED_DUPLICATE:
        * Reuses the Week 6 duplicate workflow and authoritative transition map.
        * Evaluates reports (newer report transitioned to duplicate of older report).
        * Both original reports remain intact in the database (never merged or deleted).
        * Audit history logged in report_status_history.
    """
    from app.api.v1.endpoints.reports import validate_transition

    relation = db.query(ReportRelation).filter(ReportRelation.id == relation_id).first()
    if not relation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report relation with ID {relation_id} not found.",
        )

    if relation.review_status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Relation #{relation_id} has already been reviewed ({relation.review_status}).",
        )

    # Load both related reports
    rep_a = db.query(Report).filter(Report.id == relation.report_id).first()
    rep_b = db.query(Report).filter(Report.id == relation.related_report_id).first()

    if not rep_a or not rep_b:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both reports associated with this relation no longer exist.",
        )

    if body.review_status == "CONFIRMED_DUPLICATE":
        # Identify original vs duplicate report:
        # The chronologically newer report is marked as a duplicate of the older report
        created_a = rep_a.created_at or datetime.utcnow()
        created_b = rep_b.created_at or datetime.utcnow()

        if created_b >= created_a:
            dup_report, orig_report = rep_b, rep_a
        else:
            dup_report, orig_report = rep_a, rep_b

        # Enforce Week 6 legal state machine transition rules
        validate_transition(dup_report.status, ReportStatus.DUPLICATE)

        prev_status = dup_report.status.value if hasattr(dup_report.status, "value") else str(dup_report.status)
        dup_report.status = ReportStatus.DUPLICATE
        dup_report.duplicate_of_id = orig_report.id
        dup_report.updated_at = datetime.utcnow()

        note_text = f"Confirmed duplicate of Report #{orig_report.id} via relation #{relation.id}"
        if body.note and body.note.strip():
            note_text += f": {body.note.strip()}"

        record_status_history(
            db=db,
            report_id=dup_report.id,
            from_status=prev_status,
            to_status=ReportStatus.DUPLICATE.value,
            user=current_user,
            note=note_text,
        )

    relation.review_status = body.review_status
    relation.reviewed_by = current_user.id
    relation.reviewed_at = datetime.utcnow()
    relation.note = body.note.strip() if body.note else None

    db.commit()
    db.refresh(relation)

    return RelatedReportItemResponse(
        relation_id=relation.id,
        report_id=relation.report_id,
        related_report_id=relation.related_report_id,
        distance_meters=relation.distance_meters,
        relation_type=relation.relation_type,
        review_status=relation.review_status,
        reviewed_by=relation.reviewed_by,
        reviewed_at=relation.reviewed_at,
        note=relation.note,
        status=rep_b.status.value if hasattr(rep_b.status, "value") else str(rep_b.status),
        priority=rep_b.priority,
        severity=rep_b.severity,
        damage_type=rep_b.damage_type,
        description=rep_b.description,
        address_text=rep_b.address_text,
        image_url=rep_b.image_url,
        created_at=rep_b.created_at,
    )
