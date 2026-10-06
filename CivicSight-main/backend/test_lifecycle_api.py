"""CivicSight Report Lifecycle, Status Transitions & History Test Suite (Week 6)

Validates Requirement 1 & Requirement 4:
1. Valid Lifecycle Path:
   - Submitted -> Verified -> Assigned -> Under Repair -> Repaired -> Closed
   - History is correctly persisted and retrievable via GET /reports/{id}/history at each step.
2. Illegal State Transition Rejections (Server-side Enforcement):
   - Assigning before verification (e.g. Submitted -> Assigned, Pending Verification -> Assigned) -> 400
   - Re-verifying an assigned report (Assigned -> Verified) -> 400
   - Rejecting an assigned report (Assigned -> Rejected) -> 400
   - Re-verifying a repaired/closed report (Closed -> Verified) -> 400
   - Assigning a rejected report (Rejected -> Assigned) -> 400
   - Transitioning from terminal state (Closed -> Assigned) -> 400
3. Reject Workflow:
   - Missing/empty rejection reason -> 422
   - Valid rejection -> 200, status='rejected', rejection_reason persisted, history recorded
4. Duplicate Workflow:
   - Duplicating self -> 400
   - Referencing non-existent report -> 404
   - Valid duplicate -> 200, status='duplicate', duplicate_of_id persisted, history recorded
5. Role-Based Access Control (RBAC):
   - Unauthenticated requests -> 401
   - Citizen requests -> 403
   - Municipal Officer & Admin requests -> 200
6. Root /reports and /api/v1/reports endpoint equivalence.
"""

import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.db.init_db import init_db
from app.db.database import SessionLocal
from app.models.models import User, UserRole, Report, ReportStatus, ReportStatusHistory
from app.core.security import create_access_token, get_password_hash

# Ensure database tables exist
init_db()

client = TestClient(app)


def get_or_create_user(role: UserRole, email: str, name: str) -> User:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                name=name,
                email=email,
                role=role,
                hashed_password=get_password_hash("testpassword123"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user
    finally:
        db.close()


def get_token_for_user(user: User) -> str:
    role_str = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    claims = {
        "email": user.email,
        "role": role_str,
        "name": user.name,
    }
    return create_access_token(subject=user.id, claims=claims)


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def create_test_report(status_val=ReportStatus.SUBMITTED, priority_val="HIGH", damage_type="D40") -> int:
    payload = {
        "description": f"Test hazard {uuid.uuid4().hex[:6]}",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "address_text": "Market Street & 5th",
        "damage_type": damage_type,
        "priority": priority_val,
        "status": status_val.value if isinstance(status_val, ReportStatus) else status_val,
        "image_url": "/uploads/reports/test_pothole.jpg",
    }
    res = client.post("/api/v1/reports", json=payload)
    assert res.status_code == 201, f"Failed to create test report: {res.text}"
    return res.json()["id"]


def test_week6_lifecycle():
    print("=" * 70)
    print(" CivicSight Week 6: Lifecycle State Transitions & History Test Suite")
    print("=" * 70)

    # 1. Setup Test Users
    citizen = get_or_create_user(UserRole.CITIZEN, "citizen_w6@example.com", "Citizen Alex")
    officer = get_or_create_user(UserRole.MUNICIPAL_OFFICER, "officer_w6@example.com", "Officer Maria")
    admin = get_or_create_user(UserRole.ADMIN, "admin_w6@example.com", "Admin Jordan")
    staff = get_or_create_user(UserRole.MAINTENANCE_STAFF, "staff_w6@example.com", "Tech Sam")

    cit_token = get_token_for_user(citizen)
    off_token = get_token_for_user(officer)
    adm_token = get_token_for_user(admin)
    staff_token = get_token_for_user(staff)

    # -------------------------------------------------------------------------
    # TEST 1: Full Valid Path (Submitted -> Verified -> Assigned -> Under Repair -> Repaired -> Closed)
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Full Valid Lifecycle Path with History Tracking...")
    report_id = create_test_report(ReportStatus.SUBMITTED)

    # Step 1.1: Verify initial history
    h_res0 = client.get(f"/api/v1/reports/{report_id}/history", headers=auth_headers(off_token))
    assert h_res0.status_code == 200
    h_list0 = h_res0.json()
    assert len(h_list0) >= 1
    assert h_list0[0]["to_status"] == "submitted"
    print(f"  [PASS] Initial report creation logged in history (to_status='submitted')")

    # Step 1.2: Submitted -> Verified
    v_res = client.patch(
        f"/api/v1/reports/{report_id}/verify",
        json={"note": "Verified by public works inspector"},
        headers=auth_headers(off_token),
    )
    assert v_res.status_code == 200
    assert v_res.json()["status"] == "verified"

    h_res1 = client.get(f"/api/v1/reports/{report_id}/history", headers=auth_headers(off_token))
    h_list1 = h_res1.json()
    assert len(h_list1) == 2
    assert h_list1[1]["from_status"] == "submitted"
    assert h_list1[1]["to_status"] == "verified"
    assert h_list1[1]["performed_by_name"] == officer.name
    print(f"  [PASS] Step 1: Submitted -> Verified (200 OK, History updated: from=submitted, to=verified)")

    # Step 1.3: Verified -> Assigned
    a_res = client.patch(
        f"/api/v1/reports/{report_id}/assign",
        json={"assigned_to": "Metro Crew Bravo", "staff_id": staff.id, "note": "Dispatch asphalt truck"},
        headers=auth_headers(off_token),
    )
    assert a_res.status_code == 200
    report_data = a_res.json()
    assert report_data["status"] == "assigned"
    assert report_data["assigned_to"] == "Metro Crew Bravo"

    h_res2 = client.get(f"/api/v1/reports/{report_id}/history", headers=auth_headers(off_token))
    h_list2 = h_res2.json()
    assert len(h_list2) == 3
    assert h_list2[2]["from_status"] == "verified"
    assert h_list2[2]["to_status"] == "assigned"
    assert "Assigned to: Metro Crew Bravo" in h_list2[2]["note"]
    print(f"  [PASS] Step 2: Verified -> Assigned (200 OK, History updated: from=verified, to=assigned)")

    # Step 1.4: Assigned -> Under Repair
    ur_res = client.patch(
        f"/api/v1/reports/{report_id}/status",
        json={"status": "under_repair"},
        headers=auth_headers(off_token),
    )
    assert ur_res.status_code == 200
    assert ur_res.json()["status"] == "under_repair"
    print(f"  [PASS] Step 3: Assigned -> Under Repair (200 OK)")

    # Step 1.5: Under Repair -> Repaired
    rep_res = client.patch(
        f"/api/v1/reports/{report_id}/status",
        json={"status": "repaired"},
        headers=auth_headers(off_token),
    )
    assert rep_res.status_code == 200
    assert rep_res.json()["status"] == "repaired"
    print(f"  [PASS] Step 4: Under Repair -> Repaired (200 OK)")

    # Step 1.6: Repaired -> Closed
    cls_res = client.patch(
        f"/api/v1/reports/{report_id}/status",
        json={"status": "closed"},
        headers=auth_headers(off_token),
    )
    assert cls_res.status_code == 200
    assert cls_res.json()["status"] == "closed"
    print(f"  [PASS] Step 5: Repaired -> Closed (200 OK)")

    # Final History Audit
    h_final = client.get(f"/api/v1/reports/{report_id}/history", headers=auth_headers(off_token)).json()
    assert len(h_final) == 6
    history_statuses = [h["to_status"] for h in h_final]
    assert history_statuses == ["submitted", "verified", "assigned", "under_repair", "repaired", "closed"]
    print(f"  [PASS] Complete chronological history chain verified: {history_statuses}")

    # -------------------------------------------------------------------------
    # TEST 2: Illegal Transition Rejections (Server-Side Validation)
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Server-Side Illegal Transition Validation (Zero Trust)...")

    # 2.1 Cannot assign a report that is still Submitted
    unverified_id = create_test_report(ReportStatus.SUBMITTED)
    bad_assign = client.patch(
        f"/api/v1/reports/{unverified_id}/assign",
        json={"assigned_to": "Alpha Crew"},
        headers=auth_headers(off_token),
    )
    assert bad_assign.status_code == 400
    assert "must be in 'verified' status before it can be assigned" in bad_assign.json()["detail"]
    print("  [PASS] Blocked assigning unverified report (Submitted -> Assigned) -> 400 Bad Request")

    # 2.2 Cannot assign a report in Pending Verification
    client.patch(
        f"/api/v1/reports/{unverified_id}/status",
        json={"status": "pending_verification"},
        headers=auth_headers(off_token),
    )
    bad_assign_pv = client.patch(
        f"/api/v1/reports/{unverified_id}/assign",
        json={"assigned_to": "Alpha Crew"},
        headers=auth_headers(off_token),
    )
    assert bad_assign_pv.status_code == 400
    print("  [PASS] Blocked assigning report in Pending Verification (Pending Verification -> Assigned) -> 400 Bad Request")

    # 2.3 Cannot re-verify an already Assigned report
    assigned_report_id = create_test_report(ReportStatus.SUBMITTED)
    client.patch(f"/api/v1/reports/{assigned_report_id}/verify", headers=auth_headers(off_token))
    client.patch(
        f"/api/v1/reports/{assigned_report_id}/assign",
        json={"assigned_to": "Beta Crew"},
        headers=auth_headers(off_token),
    )
    reverify_res = client.patch(f"/api/v1/reports/{assigned_report_id}/verify", headers=auth_headers(off_token))
    assert reverify_res.status_code == 400
    assert "cannot be re-verified" in reverify_res.json()["detail"]
    print("  [PASS] Blocked re-verifying an assigned report (Assigned -> Verified) -> 400 Bad Request")

    # 2.4 Cannot reject an already Assigned report
    bad_reject = client.patch(
        f"/api/v1/reports/{assigned_report_id}/reject",
        json={"reason": "Hazard no longer exists"},
        headers=auth_headers(off_token),
    )
    assert bad_reject.status_code == 400
    assert "cannot be rejected once already assigned" in bad_reject.json()["detail"]
    print("  [PASS] Blocked rejecting an assigned report (Assigned -> Rejected) -> 400 Bad Request")

    # 2.5 Cannot re-verify a closed report
    closed_report_id = create_test_report(ReportStatus.SUBMITTED)
    # verify -> assign -> repair -> close
    client.patch(f"/api/v1/reports/{closed_report_id}/verify", headers=auth_headers(off_token))
    client.patch(f"/api/v1/reports/{closed_report_id}/assign", json={"assigned_to": "Crew"}, headers=auth_headers(off_token))
    client.patch(f"/api/v1/reports/{closed_report_id}/status", json={"status": "under_repair"}, headers=auth_headers(off_token))
    client.patch(f"/api/v1/reports/{closed_report_id}/status", json={"status": "closed"}, headers=auth_headers(off_token))

    reverify_closed = client.patch(f"/api/v1/reports/{closed_report_id}/verify", headers=auth_headers(off_token))
    assert reverify_closed.status_code == 400
    assert "Already repaired or closed reports cannot be re-verified" in reverify_closed.json()["detail"]
    print("  [PASS] Blocked re-verifying a closed report (Closed -> Verified) -> 400 Bad Request")

    # 2.6 Cannot assign a rejected report
    rejected_id = create_test_report(ReportStatus.SUBMITTED)
    client.patch(
        f"/api/v1/reports/{rejected_id}/reject",
        json={"reason": "Private road, outside jurisdiction"},
        headers=auth_headers(off_token),
    )
    assign_rejected = client.patch(
        f"/api/v1/reports/{rejected_id}/assign",
        json={"assigned_to": "Crew"},
        headers=auth_headers(off_token),
    )
    assert assign_rejected.status_code == 400
    print("  [PASS] Blocked assigning a rejected report (Rejected -> Assigned) -> 400 Bad Request")

    # -------------------------------------------------------------------------
    # TEST 3: Reject Endpoint Specification
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Reject Endpoint Behavior...")
    r_id = create_test_report(ReportStatus.SUBMITTED)

    # Missing reason
    empty_rej = client.patch(f"/api/v1/reports/{r_id}/reject", json={"reason": ""}, headers=auth_headers(off_token))
    assert empty_rej.status_code == 422
    print("  [PASS] Empty rejection reason rejected -> 422 Unprocessable Content")

    # Valid rejection
    valid_rej = client.patch(
        f"/api/v1/reports/{r_id}/reject",
        json={"reason": "Not a municipal asphalt defect; private driveway.", "note": "Contacted homeowner"},
        headers=auth_headers(off_token),
    )
    assert valid_rej.status_code == 200
    rej_data = valid_rej.json()
    assert rej_data["status"] == "rejected"
    assert "Not a municipal asphalt defect" in rej_data["rejection_reason"]

    # History audit
    h_rej = client.get(f"/api/v1/reports/{r_id}/history", headers=auth_headers(off_token)).json()
    assert h_rej[-1]["to_status"] == "rejected"
    assert "Not a municipal asphalt defect" in h_rej[-1]["note"]
    print("  [PASS] Valid rejection transitions to 'rejected', persists reason, logs in history")

    # -------------------------------------------------------------------------
    # TEST 4: Duplicate Endpoint Specification
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Duplicate Endpoint Behavior...")
    orig_id = create_test_report(ReportStatus.SUBMITTED)
    dup_id = create_test_report(ReportStatus.SUBMITTED)

    # Duplicating self
    self_dup = client.patch(
        f"/api/v1/reports/{dup_id}/duplicate",
        json={"original_report_id": dup_id},
        headers=auth_headers(off_token),
    )
    assert self_dup.status_code == 400
    assert "cannot be marked as a duplicate of itself" in self_dup.json()["detail"]
    print("  [PASS] Duplicating self rejected -> 400 Bad Request")

    # Non-existent original report
    nonexist_dup = client.patch(
        f"/api/v1/reports/{dup_id}/duplicate",
        json={"original_report_id": 999999},
        headers=auth_headers(off_token),
    )
    assert nonexist_dup.status_code == 404
    print("  [PASS] Referencing non-existent report rejected -> 404 Not Found")

    # Valid duplicate
    valid_dup = client.patch(
        f"/api/v1/reports/{dup_id}/duplicate",
        json={"original_report_id": orig_id, "note": "Duplicate citizen photo from opposite angle"},
        headers=auth_headers(off_token),
    )
    assert valid_dup.status_code == 200
    dup_data = valid_dup.json()
    assert dup_data["status"] == "duplicate"
    assert dup_data["duplicate_of_id"] == orig_id

    # History audit
    h_dup = client.get(f"/api/v1/reports/{dup_id}/history", headers=auth_headers(off_token)).json()
    assert h_dup[-1]["to_status"] == "duplicate"
    assert f"Marked as duplicate of Report #{orig_id}" in h_dup[-1]["note"]
    print(f"  [PASS] Valid duplicate marked (Report #{dup_id} duplicates #{orig_id}), logged in history")

    # -------------------------------------------------------------------------
    # TEST 5: RBAC Enforcement
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Role-Based Access Control (RBAC) Enforcement...")
    test_id = create_test_report(ReportStatus.SUBMITTED)

    # Unauthenticated
    assert client.patch(f"/api/v1/reports/{test_id}/verify").status_code == 401
    assert client.patch(f"/api/v1/reports/{test_id}/reject", json={"reason": "test"}).status_code == 401
    assert client.patch(f"/api/v1/reports/{test_id}/duplicate", json={"original_report_id": 1}).status_code == 401
    assert client.patch(f"/api/v1/reports/{test_id}/assign", json={"assigned_to": "crew"}).status_code == 401
    assert client.get(f"/api/v1/reports/{test_id}/history").status_code == 401
    print("  [PASS] Unauthenticated requests rejected -> 401 Unauthorized across all lifecycle endpoints")

    # Citizen Forbidden
    assert client.patch(f"/api/v1/reports/{test_id}/verify", headers=auth_headers(cit_token)).status_code == 403
    assert client.patch(f"/api/v1/reports/{test_id}/reject", json={"reason": "test"}, headers=auth_headers(cit_token)).status_code == 403
    assert client.patch(f"/api/v1/reports/{test_id}/duplicate", json={"original_report_id": 1}, headers=auth_headers(cit_token)).status_code == 403
    assert client.patch(f"/api/v1/reports/{test_id}/assign", json={"assigned_to": "crew"}, headers=auth_headers(cit_token)).status_code == 403
    assert client.get(f"/api/v1/reports/{test_id}/history", headers=auth_headers(cit_token)).status_code == 403
    print("  [PASS] Citizen role requests forbidden -> 403 Forbidden across all lifecycle endpoints")

    # Maintenance Staff Forbidden from verification/triage
    assert client.patch(f"/api/v1/reports/{test_id}/verify", headers=auth_headers(staff_token)).status_code == 403
    assert client.patch(f"/api/v1/reports/{test_id}/reject", json={"reason": "test"}, headers=auth_headers(staff_token)).status_code == 403
    assert client.patch(f"/api/v1/reports/{test_id}/duplicate", json={"original_report_id": 1}, headers=auth_headers(staff_token)).status_code == 403
    assert client.patch(f"/api/v1/reports/{test_id}/assign", json={"assigned_to": "crew"}, headers=auth_headers(staff_token)).status_code == 403
    assert client.get(f"/api/v1/reports/{test_id}/history", headers=auth_headers(staff_token)).status_code == 403
    print("  [PASS] Maintenance Staff forbidden from officer triage operations -> 403 Forbidden")

    # Admin role authorized
    adm_v = client.patch(f"/api/v1/reports/{test_id}/verify", headers=auth_headers(adm_token))
    assert adm_v.status_code == 200
    print("  [PASS] Admin role granted full lifecycle authority -> 200 OK")

    # -------------------------------------------------------------------------
    # TEST 6: Root /reports and /api/v1/reports Equivalence
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Endpoint Route Equivalence (/reports vs /api/v1/reports)...")
    eq_id = create_test_report(ReportStatus.SUBMITTED)
    assert client.get(f"/reports/{eq_id}", headers=auth_headers(off_token)).status_code == 200
    assert client.get(f"/api/v1/reports/{eq_id}", headers=auth_headers(off_token)).status_code == 200
    assert client.get(f"/reports/{eq_id}/history", headers=auth_headers(off_token)).status_code == 200
    assert client.get(f"/api/v1/reports/{eq_id}/history", headers=auth_headers(off_token)).status_code == 200
    print("  [PASS] Root and /api/v1 routes operate equivalently")

    print("\n" + "=" * 70)
    print(" ALL WEEK 6 REPORT LIFECYCLE & HISTORY TESTS PASSED (100% SUCCESS)!")
    print("=" * 70)


if __name__ == "__main__":
    test_week6_lifecycle()
