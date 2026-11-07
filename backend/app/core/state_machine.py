"""CivicSight Canonical Lifecycle & State Machine (Week 9)

Defines the single source of truth for the complete report lifecycle:
  Verified -> Assigned -> Under Repair -> Repair Evidence Submitted -> Municipal Final Verification -> Closed

Canonical States:
- SUBMITTED: Fresh incident report submitted by citizen
- PENDING_VERIFICATION: Triage queue awaiting municipal review
- VERIFIED: Validated hazard awaiting work-order assignment
- ASSIGNED: Work order assigned to maintenance staff
- UNDER_REPAIR: Field crew active on site, repair in progress
- REPAIR_EVIDENCE_SUBMITTED: Staff completed repair and uploaded photographic evidence
- CLOSED: Municipal officer approved final verification (terminal)
- REJECTED: Report discarded with mandatory explanation (terminal)
- DUPLICATE: Incident identified as duplicate of another report (terminal)
"""

import enum
from typing import Set, Dict, Optional, List
from fastapi import HTTPException, status


class ReportStatus(str, enum.Enum):
    """Canonical Lifecycle Statuses for CivicSight Reports."""
    SUBMITTED = "submitted"
    PENDING_VERIFICATION = "pending_verification"
    VERIFIED = "verified"
    ASSIGNED = "assigned"
    UNDER_REPAIR = "under_repair"
    REPAIR_EVIDENCE_SUBMITTED = "repair_evidence_submitted"
    CLOSED = "closed"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"

    # Legacy aliases preserved for backward compatibility
    REPAIRED = "repaired"
    DETECTED = "detected"
    PRIORITIZED = "prioritized"


# Canonical set of valid current states
CANONICAL_STATUSES: Set[ReportStatus] = {
    ReportStatus.SUBMITTED,
    ReportStatus.PENDING_VERIFICATION,
    ReportStatus.VERIFIED,
    ReportStatus.ASSIGNED,
    ReportStatus.UNDER_REPAIR,
    ReportStatus.REPAIR_EVIDENCE_SUBMITTED,
    ReportStatus.CLOSED,
    ReportStatus.REJECTED,
    ReportStatus.DUPLICATE,
}

# Terminal states: No outgoing transitions permitted (except explicit logged Admin reopen)
TERMINAL_STATUSES: Set[ReportStatus] = {
    ReportStatus.CLOSED,
    ReportStatus.REJECTED,
    ReportStatus.DUPLICATE,
}

# Map for migrating legacy status values to canonical equivalents
LEGACY_STATUS_MAP: Dict[str, ReportStatus] = {
    "repaired": ReportStatus.REPAIR_EVIDENCE_SUBMITTED,
    "detected": ReportStatus.PENDING_VERIFICATION,
    "prioritized": ReportStatus.PENDING_VERIFICATION,
}


def normalize_status(val: str) -> ReportStatus:
    """Normalizes any string or legacy status into a canonical ReportStatus."""
    if not val:
        return ReportStatus.SUBMITTED
    cleaned = str(val).strip().lower()
    if cleaned in LEGACY_STATUS_MAP:
        return LEGACY_STATUS_MAP[cleaned]
    try:
        return ReportStatus(cleaned)
    except ValueError:
        raise ValueError(f"Unrecognized status '{val}'.")


# Canonical Legal Transition Map
LEGAL_TRANSITIONS: Dict[ReportStatus, Set[ReportStatus]] = {
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
    ReportStatus.VERIFIED: {
        ReportStatus.ASSIGNED,
    },
    ReportStatus.ASSIGNED: {
        ReportStatus.UNDER_REPAIR,
        ReportStatus.VERIFIED,  # Unassign / reassign with mandatory reason
    },
    ReportStatus.UNDER_REPAIR: {
        ReportStatus.REPAIR_EVIDENCE_SUBMITTED,
        ReportStatus.CLOSED,  # Officer / Admin direct closure or emergency resolution
    },
    ReportStatus.REPAIR_EVIDENCE_SUBMITTED: {
        ReportStatus.CLOSED,        # Officer approved
        ReportStatus.UNDER_REPAIR,  # Officer rejected / sent back for rework
    },
    # Terminal states
    ReportStatus.CLOSED: set(),
    ReportStatus.REJECTED: set(),
    ReportStatus.DUPLICATE: set(),
}

# Permitted transitions per user role
# Role strings match UserRole.value
ROLE_TRANSITIONS: Dict[str, Set[tuple[ReportStatus, ReportStatus]]] = {
    "Municipal Officer": {
        (ReportStatus.SUBMITTED, ReportStatus.PENDING_VERIFICATION),
        (ReportStatus.SUBMITTED, ReportStatus.VERIFIED),
        (ReportStatus.SUBMITTED, ReportStatus.REJECTED),
        (ReportStatus.SUBMITTED, ReportStatus.DUPLICATE),
        (ReportStatus.PENDING_VERIFICATION, ReportStatus.VERIFIED),
        (ReportStatus.PENDING_VERIFICATION, ReportStatus.REJECTED),
        (ReportStatus.PENDING_VERIFICATION, ReportStatus.DUPLICATE),
        (ReportStatus.VERIFIED, ReportStatus.ASSIGNED),
        (ReportStatus.ASSIGNED, ReportStatus.VERIFIED),  # Unassign
        (ReportStatus.ASSIGNED, ReportStatus.UNDER_REPAIR),
        (ReportStatus.UNDER_REPAIR, ReportStatus.REPAIR_EVIDENCE_SUBMITTED),
        (ReportStatus.UNDER_REPAIR, ReportStatus.CLOSED),
        (ReportStatus.REPAIR_EVIDENCE_SUBMITTED, ReportStatus.CLOSED),  # Approve
        (ReportStatus.REPAIR_EVIDENCE_SUBMITTED, ReportStatus.UNDER_REPAIR),  # Send back
    },
    "Admin": {
        (ReportStatus.SUBMITTED, ReportStatus.PENDING_VERIFICATION),
        (ReportStatus.SUBMITTED, ReportStatus.VERIFIED),
        (ReportStatus.SUBMITTED, ReportStatus.REJECTED),
        (ReportStatus.SUBMITTED, ReportStatus.DUPLICATE),
        (ReportStatus.PENDING_VERIFICATION, ReportStatus.VERIFIED),
        (ReportStatus.PENDING_VERIFICATION, ReportStatus.REJECTED),
        (ReportStatus.PENDING_VERIFICATION, ReportStatus.DUPLICATE),
        (ReportStatus.VERIFIED, ReportStatus.ASSIGNED),
        (ReportStatus.ASSIGNED, ReportStatus.VERIFIED),
        (ReportStatus.ASSIGNED, ReportStatus.UNDER_REPAIR),
        (ReportStatus.UNDER_REPAIR, ReportStatus.REPAIR_EVIDENCE_SUBMITTED),
        (ReportStatus.UNDER_REPAIR, ReportStatus.CLOSED),
        (ReportStatus.REPAIR_EVIDENCE_SUBMITTED, ReportStatus.CLOSED),
        (ReportStatus.REPAIR_EVIDENCE_SUBMITTED, ReportStatus.UNDER_REPAIR),
        # Admin reopen permissions
        (ReportStatus.CLOSED, ReportStatus.PENDING_VERIFICATION),
        (ReportStatus.REJECTED, ReportStatus.PENDING_VERIFICATION),
        (ReportStatus.DUPLICATE, ReportStatus.PENDING_VERIFICATION),
    },
    "Maintenance Staff": {
        (ReportStatus.ASSIGNED, ReportStatus.UNDER_REPAIR),
        (ReportStatus.UNDER_REPAIR, ReportStatus.REPAIR_EVIDENCE_SUBMITTED),
    },
    "Citizen": set(),  # Citizens cannot execute status transitions
}


def validate_transition(
    current_status: ReportStatus,
    target_status: ReportStatus,
    user_role: Optional[str] = None,
    is_assigned_staff: bool = True,
) -> None:
    """Validates that a status transition is permitted by both the lifecycle graph and actor RBAC.
    
    Rejects illegal transitions with clear, descriptive HTTP 400 Bad Request or 403 Forbidden errors.
    """
    # Normalize legacy statuses if any
    curr = normalize_status(current_status.value if hasattr(current_status, "value") else str(current_status))
    tgt = normalize_status(target_status.value if hasattr(target_status, "value") else str(target_status))

    # 1. Check lifecycle graph validity
    allowed = LEGAL_TRANSITIONS.get(curr, set())
    
    # Check Admin reopen exception
    if curr in TERMINAL_STATUSES and user_role == "Admin" and tgt == ReportStatus.PENDING_VERIFICATION:
        return

    if tgt not in allowed:
        allowed_list = sorted([s.value for s in allowed])
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Illegal status transition from '{curr.value}' to '{tgt.value}'. "
                f"Allowed transitions from '{curr.value}': {allowed_list if allowed_list else 'None (terminal state)'}."
            ),
        )

    # 2. Check Role Permissions
    if user_role is not None:
        role_key = str(user_role).strip()
        allowed_for_role = ROLE_TRANSITIONS.get(role_key, set())
        if (curr, tgt) not in allowed_for_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User role '{role_key}' is not authorized to transition report from '{curr.value}' to '{tgt.value}'.",
            )

    # 3. Check Maintenance Staff assignment ownership
    if user_role == "Maintenance Staff" and not is_assigned_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You can only update reports actively assigned to you.",
        )

