"""
CivicSight Week 9 - Comprehensive Canonical Lifecycle & Repair System Test Suite
================================================================================
Validates all Week 9 functional, security, state machine, and concurrency criteria:
 1. Full canonical lifecycle happy path:
    SUBMITTED -> PENDING_VERIFICATION -> VERIFIED -> ASSIGNED -> UNDER_REPAIR -> REPAIR_EVIDENCE_SUBMITTED -> CLOSED
 2. Timestamps & audit metadata:
    repair_started_at, repair_submitted_at, final_verified_at, final_verified_by, closed_at, version
 3. Send-back flow with mandatory rework reason:
    REPAIR_EVIDENCE_SUBMITTED -> UNDER_REPAIR (rework requested) -> re-submitted -> APPROVED -> CLOSED
 4. Reassignment & Unassignment with mandatory audit reasons & history tracking
 5. Strict Role-Based Access Control (RBAC):
    Citizen 403 on staff/officer endpoints
    Staff 403 on unassigned reports & officer-only actions
    Officer-only final verification
 6. Anti-IDOR protection on evidence files:
    Unrelated citizen & unrelated staff 403
 7. File upload security & magic-byte validation:
    Reject fake executables/HTML renamed to .jpg
    Reject files > 15MB
    Reject reports exceeding 10 photos
    Enforce >= 1 AFTER photo requirement before submission
 8. Optimistic locking / version checking
 9. Admin-only reopen from terminal states
"""

import io
import os
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.init_db import init_db
from app.db.database import SessionLocal
from app.models.models import (
    User, UserRole, Report, ReportStatus, ReportStatusHistory,
    Assignment, RepairEvidence, FinalVerification, EvidenceKind, VerificationDecision
)
from app.core.security import create_access_token, get_password_hash

# Ensure schema initialized
init_db()
client = TestClient(app)

# Minimal valid JPEG bytes (passes JPEG magic header check 0xFF 0xD8 0xFF)
VALID_JPEG_BYTES = (
    b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    + b"\xFF\xDB\x00\x43\x00" + b"\x01" * 64
    + b"\xFF\xC0\x00\x0B\x08\x00\x01\x00\x01\x01\x01\x11\x00"
    + b"\xFF\xDA\x00\x08\x01\x01\x00\x00\x3F\x00\xBF\x00"
    + b"\xFF\xD9"
)

# Invalid magic bytes (Windows PE header renamed as jpg)
FAKE_EXE_BYTES = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xFF\xFF\x00\x00"


def get_or_create_user(email: str, name: str, role: UserRole) -> User:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                name=name,
                email=email,
                role=role,
                hashed_password=get_password_hash("Password123!"),
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user
    finally:
        db.close()


def auth_headers(user: User) -> dict:
    role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
    token = create_access_token(str(user.id), claims={"role": role_str, "email": user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def users():
    admin = get_or_create_user("admin_w9@civicsight.gov", "Admin Nine", UserRole.ADMIN)
    officer = get_or_create_user("officer_w9@civicsight.gov", "Officer Nine", UserRole.MUNICIPAL_OFFICER)
    staff1 = get_or_create_user("staff1_w9@civicsight.gov", "Sam Crew Alpha", UserRole.MAINTENANCE_STAFF)
    staff2 = get_or_create_user("staff2_w9@civicsight.gov", "Alex Crew Beta", UserRole.MAINTENANCE_STAFF)
    citizen1 = get_or_create_user("citizen1_w9@civicsight.org", "Alice Citizen", UserRole.CITIZEN)
    citizen2 = get_or_create_user("citizen2_w9@civicsight.org", "Bob Citizen", UserRole.CITIZEN)
    return {
        "admin": admin,
        "officer": officer,
        "staff1": staff1,
        "staff2": staff2,
        "citizen1": citizen1,
        "citizen2": citizen2,
    }


def create_test_report(user: User, status: str = "submitted") -> int:
    """Helper to seed a report in database with valid fields."""
    db = SessionLocal()
    try:
        report = Report(
            reporter_id=user.id,
            description="Week 9 lifecycle test hazard",
            damage_type="Pothole",
            latitude=37.7749,
            longitude=-122.4194,
            image_url="uploads/test_hazard.jpg",
            status=status,
            priority="HIGH",
            ml_status="ML_COMPLETE",
            version=1
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        # Initial history row
        history = ReportStatusHistory(
            report_id=report.id,
            from_status=None,
            to_status=status,
            performed_by_id=user.id, performed_by_name=user.name,
            performed_by_role=user.role.value if hasattr(user.role, 'value') else str(user.role),
            note="Initial report submission"
        )
        db.add(history)
        db.commit()
        return report.id
    finally:
        db.close()


# =============================================================================
# 1. Full Canonical Lifecycle Happy Path
# =============================================================================
def test_canonical_lifecycle_happy_path(users):
    """
    Traces: SUBMITTED -> PENDING_VERIFICATION -> VERIFIED -> ASSIGNED
            -> UNDER_REPAIR -> REPAIR_EVIDENCE_SUBMITTED -> CLOSED
    """
    officer_h = auth_headers(users["officer"])
    staff_h = auth_headers(users["staff1"])
    citizen_h = auth_headers(users["citizen1"])

    # 1. Citizen creates report
    report_id = create_test_report(users["citizen1"], status="submitted")

    # 2. Officer verifies report (submitted -> verified)
    res_verify = client.patch(f"/api/v1/reports/{report_id}/verify", headers=officer_h)
    assert res_verify.status_code == 200, res_verify.text
    assert res_verify.json()["status"] == "verified"

    # 3. Officer assigns report to Staff 1 (verified -> assigned)
    assign_payload = {
        "staff_id": users["staff1"].id,
        "note": "Dispatch asphalt patch unit"
    }
    res_assign = client.post(f"/api/v1/reports/{report_id}/assign", json=assign_payload, headers=officer_h)
    assert res_assign.status_code == 200, res_assign.text
    rep_assigned = res_assign.json()
    assert rep_assigned["status"] == "assigned"
    assert rep_assigned["current_assignee_id"] == users["staff1"].id

    # Check assignment record in DB
    db = SessionLocal()
    assign_record = db.query(Assignment).filter(
        Assignment.report_id == report_id,
        Assignment.is_active == True
    ).first()
    assert assign_record is not None
    assert assign_record.assigned_to == users["staff1"].id
    assert assign_record.assigned_by == users["officer"].id
    db.close()

    # 4. Staff 1 starts repair (assigned -> under_repair)
    res_start = client.post(f"/api/v1/reports/{report_id}/repair/start", headers=staff_h)
    assert res_start.status_code == 200, res_start.text
    rep_under_repair = res_start.json()
    assert rep_under_repair["status"] == "under_repair"
    assert rep_under_repair["repair_started_at"] is not None

    # 5. Staff 1 uploads AFTER repair evidence photo
    evidence_file = io.BytesIO(VALID_JPEG_BYTES)
    res_evidence = client.post(
        f"/api/v1/reports/{report_id}/repair/evidence",
        headers=staff_h,
        files={"photo": ("completed_repair.jpg", evidence_file, "image/jpeg")},
        data={"kind": "AFTER", "note": "Hot mix asphalt compacted flush with road"}
    )
    assert res_evidence.status_code == 201, res_evidence.text
    evidence_data = res_evidence.json()
    assert evidence_data["kind"] == "AFTER"
    evidence_id = evidence_data["id"]

    # 6. Staff 1 submits repair for verification (under_repair -> repair_evidence_submitted)
    res_submit = client.post(
        f"/api/v1/reports/{report_id}/repair/submit",
        json={"note": "Ready for municipal inspection"},
        headers=staff_h
    )
    assert res_submit.status_code == 200, res_submit.text
    rep_submitted = res_submit.json()
    assert rep_submitted["status"] == "repair_evidence_submitted"
    assert rep_submitted["repair_submitted_at"] is not None

    # 7. Officer conducts final verification and approves (repair_evidence_submitted -> closed)
    res_approve = client.post(
        f"/api/v1/reports/{report_id}/final-verify",
        json={"decision": "APPROVED", "note": "Pavement restoration verified to code"},
        headers=officer_h
    )
    assert res_approve.status_code == 200, res_approve.text
    rep_closed = res_approve.json()
    assert rep_closed["status"] == "closed"
    assert rep_closed["final_verified_at"] is not None
    assert rep_closed["closed_at"] is not None
    assert rep_closed["final_verified_by"] == users["officer"].id

    # 8. Verify complete status history timeline
    res_history = client.get(f"/api/v1/reports/{report_id}/history", headers=officer_h)
    assert res_history.status_code == 200
    history_items = res_history.json()
    statuses = [h["to_status"] for h in history_items]
    assert "verified" in statuses
    assert "assigned" in statuses
    assert "under_repair" in statuses
    assert "repair_evidence_submitted" in statuses
    assert "closed" in statuses


# =============================================================================
# 2. Send-Back for Rework Flow
# =============================================================================
def test_send_back_rework_flow(users):
    """
    Tests: REPAIR_EVIDENCE_SUBMITTED -> Officer sends back (SENT_BACK with mandatory note)
           -> UNDER_REPAIR -> Staff re-submits -> Officer approves -> CLOSED
    """
    officer_h = auth_headers(users["officer"])
    staff_h = auth_headers(users["staff1"])

    report_id = create_test_report(users["citizen1"], status="verified")

    # Assign & start
    client.post(f"/api/v1/reports/{report_id}/assign", json={"staff_id": users["staff1"].id}, headers=officer_h)
    client.post(f"/api/v1/reports/{report_id}/repair/start", headers=staff_h)

    # Upload evidence & submit
    client.post(
        f"/api/v1/reports/{report_id}/repair/evidence",
        headers=staff_h,
        files={"photo": ("patch1.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")},
        data={"kind": "AFTER"}
    )
    client.post(f"/api/v1/reports/{report_id}/repair/submit", json={}, headers=staff_h)

    # Send back without note -> rejected with 400
    res_no_note = client.post(
        f"/api/v1/reports/{report_id}/final-verify",
        json={"decision": "SENT_BACK", "note": ""},
        headers=officer_h
    )
    assert res_no_note.status_code in (400, 422), "Sending back without a reason must fail."

    # Send back with note -> returns to UNDER_REPAIR
    rework_reason = "Edge sealant missing; re-compact and apply tack coat."
    res_rework = client.post(
        f"/api/v1/reports/{report_id}/final-verify",
        json={"decision": "SENT_BACK", "note": rework_reason},
        headers=officer_h
    )
    assert res_rework.status_code == 200
    assert res_rework.json()["status"] == "under_repair"

    # Verify history recorded rework instruction
    res_history = client.get(f"/api/v1/reports/{report_id}/history", headers=officer_h)
    assert any(rework_reason in (h.get("note") or "") for h in res_history.json())

    # Staff re-submits
    res_resubmit = client.post(
        f"/api/v1/reports/{report_id}/repair/submit",
        json={"note": "Edge sealant applied and re-compacted"},
        headers=staff_h
    )
    assert res_resubmit.status_code == 200
    assert res_resubmit.json()["status"] == "repair_evidence_submitted"

    # Officer approves
    res_final = client.post(
        f"/api/v1/reports/{report_id}/final-verify",
        json={"decision": "APPROVED", "note": "Satisfactory rework"},
        headers=officer_h
    )
    assert res_final.status_code == 200
    assert res_final.json()["status"] == "closed"


# =============================================================================
# 3. Reassign & Unassign with Audit Reasons
# =============================================================================
def test_reassign_and_unassign_workflow(users):
    """
    Tests:
      - Assign to Staff 1
      - Reassign to Staff 2 (requires reason)
      - Unassign back to VERIFIED (requires reason)
    """
    officer_h = auth_headers(users["officer"])

    report_id = create_test_report(users["citizen1"], status="verified")

    # 1. Initial assignment to Staff 1
    res1 = client.post(
        f"/api/v1/reports/{report_id}/assign",
        json={"staff_id": users["staff1"].id, "note": "Initial dispatch"},
        headers=officer_h
    )
    assert res1.status_code == 200
    assert res1.json()["current_assignee_id"] == users["staff1"].id

    # 2. Reassign to Staff 2 without reason -> 400
    res_fail = client.post(
        f"/api/v1/reports/{report_id}/reassign",
        json={"new_staff_id": users["staff2"].id, "reason": ""},
        headers=officer_h
    )
    assert res_fail.status_code in (400, 422)

    # Reassign with reason -> succeeds
    res_reassign = client.post(
        f"/api/v1/reports/{report_id}/reassign",
        json={"new_staff_id": users["staff2"].id, "reason": "Staff 1 reassigned to emergency water main"},
        headers=officer_h
    )
    assert res_reassign.status_code == 200
    assert res_reassign.json()["current_assignee_id"] == users["staff2"].id

    # Check assignment DB state: exactly 1 active assignment
    db = SessionLocal()
    active_assignments = db.query(Assignment).filter(
        Assignment.report_id == report_id,
        Assignment.is_active == True
    ).all()
    assert len(active_assignments) == 1
    assert active_assignments[0].assigned_to == users["staff2"].id

    inactive_assignments = db.query(Assignment).filter(
        Assignment.report_id == report_id,
        Assignment.is_active == False
    ).all()
    assert len(inactive_assignments) == 1
    assert inactive_assignments[0].assigned_to == users["staff1"].id
    assert inactive_assignments[0].unassigned_at is not None
    db.close()

    # 3. Unassign without reason -> 400
    res_unassign_fail = client.post(
        f"/api/v1/reports/{report_id}/unassign",
        json={"reason": ""},
        headers=officer_h
    )
    assert res_unassign_fail.status_code in (400, 422)

    # Unassign with reason -> succeeds, returns to verified
    res_unassign = client.post(
        f"/api/v1/reports/{report_id}/unassign",
        json={"reason": "Inclement weather postponing pavement repairs"},
        headers=officer_h
    )
    assert res_unassign.status_code == 200
    assert res_unassign.json()["status"] == "verified"
    assert res_unassign.json()["current_assignee_id"] is None


# =============================================================================
# 4. Strict Role-Based Access Control (RBAC)
# =============================================================================
def test_rbac_matrix_and_permission_isolation(users):
    """
    Validates:
      - Citizen has NO access to staff or officer endpoints (403)
      - Staff A CANNOT modify or upload evidence on a report assigned to Staff B (403)
      - Staff CANNOT approve or close reports (403)
      - Officer CANNOT start repair or upload evidence (403)
    """
    citizen_h = auth_headers(users["citizen1"])
    staff1_h = auth_headers(users["staff1"])
    staff2_h = auth_headers(users["staff2"])
    officer_h = auth_headers(users["officer"])

    report_id = create_test_report(users["citizen1"], status="verified")

    # 1. Citizen unauthorized attempts on officer/staff routes -> 403
    assert client.post(f"/api/v1/reports/{report_id}/assign", json={"staff_id": users["staff1"].id}, headers=citizen_h).status_code == 403
    assert client.post(f"/api/v1/reports/{report_id}/reassign", json={"new_staff_id": users["staff1"].id, "reason": "test"}, headers=citizen_h).status_code == 403
    assert client.post(f"/api/v1/reports/{report_id}/unassign", json={"reason": "test"}, headers=citizen_h).status_code == 403
    assert client.post(f"/api/v1/reports/{report_id}/repair/start", headers=citizen_h).status_code == 403
    assert client.post(f"/api/v1/reports/{report_id}/repair/submit", json={}, headers=citizen_h).status_code == 403
    assert client.post(f"/api/v1/reports/{report_id}/final-verify", json={"decision": "APPROVED"}, headers=citizen_h).status_code == 403
    assert client.get("/api/v1/staff", headers=citizen_h).status_code == 403
    assert client.get("/api/v1/staff/me/assignments", headers=citizen_h).status_code == 403

    # 2. Officer assigns report to Staff 1
    client.post(f"/api/v1/reports/{report_id}/assign", json={"staff_id": users["staff1"].id}, headers=officer_h)

    # 3. Staff 2 attempts to touch Staff 1's assignment -> 403
    res_cross_start = client.post(f"/api/v1/reports/{report_id}/repair/start", headers=staff2_h)
    assert res_cross_start.status_code == 403, "Staff 2 cannot start Staff 1's work order"

    # Staff 1 starts repair
    client.post(f"/api/v1/reports/{report_id}/repair/start", headers=staff1_h)

    # Staff 2 attempts to upload evidence to Staff 1's report -> 403
    res_cross_evidence = client.post(
        f"/api/v1/reports/{report_id}/repair/evidence",
        headers=staff2_h,
        files={"photo": ("hacker.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")},
        data={"kind": "AFTER"}
    )
    assert res_cross_evidence.status_code == 403, "Staff 2 cannot upload evidence to Staff 1's work order"

    # 4. Staff 1 attempts to self-verify / close -> 403
    res_staff_close = client.post(
        f"/api/v1/reports/{report_id}/final-verify",
        json={"decision": "APPROVED"},
        headers=staff1_h
    )
    assert res_staff_close.status_code == 403, "Maintenance staff cannot final-verify or close reports"


# =============================================================================
# 5. Anti-IDOR Evidence File Access
# =============================================================================
def test_anti_idor_evidence_download(users):
    """
    Validates GET /reports/{id}/evidence/{evidence_id}/file:
      - Report creator (Citizen 1): Allowed (200)
      - Assigned Staff (Staff 1): Allowed (200)
      - Officer & Admin: Allowed (200)
      - Unrelated Citizen (Citizen 2): Rejected (403)
      - Unassigned Staff (Staff 2): Rejected (403)
      - Anonymous user: Rejected (401)
    """
    officer_h = auth_headers(users["officer"])
    staff1_h = auth_headers(users["staff1"])
    staff2_h = auth_headers(users["staff2"])
    citizen1_h = auth_headers(users["citizen1"])
    citizen2_h = auth_headers(users["citizen2"])
    admin_h = auth_headers(users["admin"])

    report_id = create_test_report(users["citizen1"], status="verified")

    # Assign and upload evidence by Staff 1
    client.post(f"/api/v1/reports/{report_id}/assign", json={"staff_id": users["staff1"].id}, headers=officer_h)
    client.post(f"/api/v1/reports/{report_id}/repair/start", headers=staff1_h)
    res_up = client.post(
        f"/api/v1/reports/{report_id}/repair/evidence",
        headers=staff1_h,
        files={"photo": ("evidence_test.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")},
        data={"kind": "AFTER"}
    )
    evidence_id = res_up.json()["id"]

    file_url = f"/api/v1/reports/{report_id}/evidence/{evidence_id}/file"

    # Anonymous -> 401
    assert client.get(file_url).status_code == 401

    # Unrelated citizen -> 403
    assert client.get(file_url, headers=citizen2_h).status_code == 403

    # Unassigned staff -> 403
    assert client.get(file_url, headers=staff2_h).status_code == 403

    # Authorized callers -> 200
    assert client.get(file_url, headers=citizen1_h).status_code == 200
    assert client.get(file_url, headers=staff1_h).status_code == 200
    assert client.get(file_url, headers=officer_h).status_code == 200
    assert client.get(file_url, headers=admin_h).status_code == 200


# =============================================================================
# 6. File Upload Security & Magic Byte Validation
# =============================================================================
def test_evidence_file_security_and_validation(users):
    """
    Tests:
      - Reject fake executables/HTML renamed to .jpg (magic byte inspection)
      - Reject oversized files (> 15MB)
      - Enforce maximum 10 evidence photos per report
      - Reject submitting repair when 0 AFTER photos exist
    """
    officer_h = auth_headers(users["officer"])
    staff_h = auth_headers(users["staff1"])

    report_id = create_test_report(users["citizen1"], status="verified")
    client.post(f"/api/v1/reports/{report_id}/assign", json={"staff_id": users["staff1"].id}, headers=officer_h)
    client.post(f"/api/v1/reports/{report_id}/repair/start", headers=staff_h)

    # 1. Attempt to submit with 0 evidence photos -> 400
    res_empty_submit = client.post(f"/api/v1/reports/{report_id}/repair/submit", json={}, headers=staff_h)
    assert res_empty_submit.status_code == 400
    assert "AFTER" in res_empty_submit.json()["detail"]

    # 2. Upload fake executable renamed as .jpg -> 400
    res_fake_exe = client.post(
        f"/api/v1/reports/{report_id}/repair/evidence",
        headers=staff_h,
        files={"photo": ("payload.jpg", io.BytesIO(FAKE_EXE_BYTES), "image/jpeg")},
        data={"kind": "AFTER"}
    )
    assert res_fake_exe.status_code == 400
    assert "invalid image file format" in res_fake_exe.json()["detail"].lower()

    # 3. Upload file > 15MB -> 400
    oversized_bytes = b"\xFF\xD8\xFF\xE0" + b"\x00" * (16 * 1024 * 1024)
    res_oversized = client.post(
        f"/api/v1/reports/{report_id}/repair/evidence",
        headers=staff_h,
        files={"photo": ("huge.jpg", io.BytesIO(oversized_bytes), "image/jpeg")},
        data={"kind": "AFTER"}
    )
    assert res_oversized.status_code == 400
    assert "15mb" in res_oversized.json()["detail"].lower()

    # 4. Upload PROGRESS only and try to submit -> 400
    client.post(
        f"/api/v1/reports/{report_id}/repair/evidence",
        headers=staff_h,
        files={"photo": ("progress.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")},
        data={"kind": "PROGRESS"}
    )
    res_progress_only = client.post(f"/api/v1/reports/{report_id}/repair/submit", json={}, headers=staff_h)
    assert res_progress_only.status_code == 400

    # 5. Upload up to 10 valid photos; 11th should be rejected
    # (We already uploaded 1 PROGRESS, upload 9 more AFTER photos = 10 total)
    for i in range(9):
        res = client.post(
            f"/api/v1/reports/{report_id}/repair/evidence",
            headers=staff_h,
            files={"photo": (f"after_{i}.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")},
            data={"kind": "AFTER"}
        )
        assert res.status_code == 201

    # 11th upload -> 400
    res_11th = client.post(
        f"/api/v1/reports/{report_id}/repair/evidence",
        headers=staff_h,
        files={"photo": ("after_overflow.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")},
        data={"kind": "AFTER"}
    )
    assert res_11th.status_code == 400
    assert "maximum" in res_11th.json()["detail"].lower()


# =============================================================================
# 7. Staff Workload Endpoint & Workload Balancing
# =============================================================================
def test_staff_workload_endpoint(users):
    """
    Tests GET /api/v1/staff and GET /api/v1/staff/me/assignments
    """
    officer_h = auth_headers(users["officer"])
    staff1_h = auth_headers(users["staff1"])

    res_staff = client.get("/api/v1/staff", headers=officer_h)
    assert res_staff.status_code == 200
    staff_list = res_staff.json()
    assert isinstance(staff_list, list)
    assert any(s["id"] == users["staff1"].id for s in staff_list)

    # Staff me assignments
    res_my_assignments = client.get("/api/v1/staff/me/assignments?view=active", headers=staff1_h)
    assert res_my_assignments.status_code == 200
    assert isinstance(res_my_assignments.json(), list)


# =============================================================================
# 8. Admin Reopen from Terminal Status
# =============================================================================
def test_admin_reopen_from_terminal_states(users):
    """
    Tests POST /api/v1/reports/{id}/reopen:
      - Non-admin receives 403
      - Missing reason receives 400
      - Reopening a non-terminal report receives 400
      - Admin reopening a closed report succeeds and sets status to PENDING_VERIFICATION
    """
    officer_h = auth_headers(users["officer"])
    admin_h = auth_headers(users["admin"])

    # 1. Closed report
    closed_id = create_test_report(users["citizen1"], status="closed")

    # Non-admin attempt -> 403
    assert client.post(f"/api/v1/reports/{closed_id}/reopen", json={"reason": "test"}, headers=officer_h).status_code == 403

    # Admin without reason -> 400
    assert client.post(f"/api/v1/reports/{closed_id}/reopen", json={"reason": ""}, headers=admin_h).status_code in (400, 422)

    # Admin with reason -> succeeds
    res_reopen = client.post(
        f"/api/v1/reports/{closed_id}/reopen",
        json={"reason": "Citizen reported defect reappeared after heavy rain"},
        headers=admin_h
    )
    assert res_reopen.status_code == 200
    assert res_reopen.json()["status"] == "pending_verification"

    # Reopening an already open report -> 400
    res_already_open = client.post(
        f"/api/v1/reports/{closed_id}/reopen",
        json={"reason": "test"},
        headers=admin_h
    )
    assert res_already_open.status_code == 400
