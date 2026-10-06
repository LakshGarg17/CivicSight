"""CivicSight Municipal Report APIs & RBAC Test Suite (Week 5)

Validates Requirement 1:
1. Unauthenticated requests to listing, detail, and verify endpoints -> 401 Unauthorized
2. Citizen-role authenticated requests -> 403 Forbidden
3. Municipal Officer / Admin authenticated requests -> 200 OK
4. Non-existent report lookup and verification -> 404 Not Found
5. Independent and combined status + priority filtering (?status=...&priority=...) -> exact subset
6. Verification endpoint state validation:
   - Valid state (submitted/detected) -> transitions to verified (200 OK)
   - Invalid state (repaired/closed) -> rejected with 400 Bad Request
7. Root /reports and /api/v1/reports equivalence
"""

import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.db.init_db import init_db
from app.db.database import SessionLocal
from app.models.models import User, UserRole, ReportStatus
from app.core.security import create_access_token, get_password_hash

# Initialize database schema
init_db()

client = TestClient(app)


def get_or_create_user(role: UserRole, email: str, name: str) -> User:
    """Ensures a user with the specified role exists in the test database."""
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
    """Generates a test JWT access token encoding the database user ID."""
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
    """Creates a report record via the API for testing."""
    payload = {
        "description": f"Test road defect {uuid.uuid4().hex[:6]}",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "address_text": "Market Street & 4th",
        "damage_type": damage_type,
        "priority": priority_val,
        "status": status_val.value if isinstance(status_val, ReportStatus) else status_val,
        "image_url": "/uploads/reports/sample_pothole.jpg",
        "ml_detections": [
            {"type": damage_type, "confidence": 0.94, "bbox": [0.3, 0.2, 0.7, 0.8]}
        ],
    }
    res = client.post("/api/v1/reports", json=payload)
    assert res.status_code == 201, f"Failed to create test report: {res.text}"
    return res.json()["id"]


def run_all_tests():
    print("=" * 70)
    print(" CivicSight Week 5: Municipal Report APIs & RBAC Test Suite")
    print("=" * 70)

    # Ensure real database accounts for role checks
    citizen_user = get_or_create_user(UserRole.CITIZEN, "citizen_test_w5@example.com", "Citizen Jane")
    officer_user = get_or_create_user(UserRole.MUNICIPAL_OFFICER, "officer_test_w5@example.com", "Officer Dave")
    admin_user = get_or_create_user(UserRole.ADMIN, "admin_test_w5@example.com", "Admin Sarah")

    citizen_token = get_token_for_user(citizen_user)
    officer_token = get_token_for_user(officer_user)
    admin_token = get_token_for_user(admin_user)

    # Create test reports for filtering tests
    rep_high_sub = create_test_report(ReportStatus.SUBMITTED, "HIGH", "D40")
    rep_med_sub = create_test_report(ReportStatus.SUBMITTED, "MEDIUM", "D00")
    rep_high_ver = create_test_report(ReportStatus.VERIFIED, "HIGH", "D20")
    rep_closed = create_test_report(ReportStatus.CLOSED, "LOW", "D10")

    print(f"\n[SETUP] Seeded test reports: ID={rep_high_sub} (HIGH/submitted), ID={rep_med_sub} (MEDIUM/submitted), ID={rep_high_ver} (HIGH/verified), ID={rep_closed} (LOW/closed)")

    # -------------------------------------------------------------
    # 1. Unauthenticated Requests (Must fail with 401)
    # -------------------------------------------------------------
    print("\n[TEST 1] Unauthenticated Requests (Expect 401 Unauthorized)...")
    res1 = client.get("/api/v1/reports")
    assert res1.status_code == 401, f"Expected 401 on GET /reports, got {res1.status_code}"
    print("  [PASS] GET /reports rejected without token -> 401")

    res2 = client.get(f"/api/v1/reports/{rep_high_sub}")
    assert res2.status_code == 401, f"Expected 401 on GET /reports/id, got {res2.status_code}"
    print("  [PASS] GET /reports/{id} rejected without token -> 401")

    res3 = client.patch(f"/api/v1/reports/{rep_high_sub}/verify")
    assert res3.status_code == 401, f"Expected 401 on PATCH /reports/id/verify, got {res3.status_code}"
    print("  [PASS] PATCH /reports/{id}/verify rejected without token -> 401")

    # -------------------------------------------------------------
    # 2. Citizen-Role Requests (Must fail with 403 Forbidden)
    # -------------------------------------------------------------
    print("\n[TEST 2] Citizen Role Enforcement (Expect 403 Forbidden)...")
    res4 = client.get("/api/v1/reports", headers=auth_headers(citizen_token))
    assert res4.status_code == 403, f"Expected 403 on GET /reports with citizen token, got {res4.status_code}"
    assert "not authorized" in res4.json()["detail"].lower()
    print("  [PASS] Citizen cannot access GET /reports -> 403 Forbidden")

    res5 = client.get(f"/api/v1/reports/{rep_high_sub}", headers=auth_headers(citizen_token))
    assert res5.status_code == 403, f"Expected 403 on GET /reports/id with citizen token, got {res5.status_code}"
    assert "not authorized" in res5.json()["detail"].lower()
    print("  [PASS] Citizen cannot access GET /reports/{id} -> 403 Forbidden")

    res6 = client.patch(f"/api/v1/reports/{rep_high_sub}/verify", headers=auth_headers(citizen_token))
    assert res6.status_code == 403, f"Expected 403 on PATCH /reports/id/verify with citizen token, got {res6.status_code}"
    assert "not authorized" in res6.json()["detail"].lower()
    print("  [PASS] Citizen cannot access PATCH /reports/{id}/verify -> 403 Forbidden")

    # -------------------------------------------------------------
    # 3. Municipal Officer & Admin Access (Must succeed with 200)
    # -------------------------------------------------------------
    print("\n[TEST 3] Municipal Officer & Admin Access (Expect 200 OK)...")
    res7 = client.get("/api/v1/reports", headers=auth_headers(officer_token))
    assert res7.status_code == 200, f"Officer failed to access GET /reports: {res7.status_code}"
    reports_list = res7.json()
    assert isinstance(reports_list, list) and len(reports_list) >= 4
    first_rep = reports_list[0]
    assert "id" in first_rep and "status" in first_rep and "priority" in first_rep
    assert "latitude" in first_rep and "longitude" in first_rep and "created_at" in first_rep
    print(f"  [PASS] Municipal Officer accessed GET /reports -> 200 ({len(reports_list)} reports returned)")

    res8 = client.get(f"/api/v1/reports/{rep_high_sub}", headers=auth_headers(officer_token))
    assert res8.status_code == 200, f"Officer failed to access GET /reports/{rep_high_sub}: {res8.status_code}"
    det_report = res8.json()
    assert det_report["id"] == rep_high_sub
    assert det_report["priority"] == "HIGH"
    assert "ml_detections" in det_report
    print("  [PASS] Municipal Officer accessed GET /reports/{id} -> 200 with full detail & ML results")

    # Admin verification
    res_admin = client.get("/api/v1/reports", headers=auth_headers(admin_token))
    assert res_admin.status_code == 200
    print("  [PASS] Admin role granted full access to GET /reports -> 200")

    # -------------------------------------------------------------
    # 4. Non-Existent Report (Expect 404 Not Found)
    # -------------------------------------------------------------
    print("\n[TEST 4] Non-Existent Report Handling (Expect 404 Not Found)...")
    res9 = client.get("/api/v1/reports/999999", headers=auth_headers(officer_token))
    assert res9.status_code == 404, f"Expected 404 for missing report, got {res9.status_code}"
    print("  [PASS] GET /reports/999999 -> 404 Not Found")

    res10 = client.patch("/api/v1/reports/999999/verify", headers=auth_headers(officer_token))
    assert res10.status_code == 404, f"Expected 404 on verify missing report, got {res10.status_code}"
    print("  [PASS] PATCH /reports/999999/verify -> 404 Not Found")

    # -------------------------------------------------------------
    # 5. Independent & Combined Filtering (?status=...&priority=...)
    # -------------------------------------------------------------
    print("\n[TEST 5] Independent & Combined Filtering...")
    # Status only
    res_status = client.get("/api/v1/reports?status=submitted", headers=auth_headers(officer_token))
    assert res_status.status_code == 200
    for r in res_status.json():
        assert r["status"] == "submitted"
    print(f"  [PASS] Filter ?status=submitted correctly filtered ({len(res_status.json())} matches)")

    # Priority only
    res_prio = client.get("/api/v1/reports?priority=HIGH", headers=auth_headers(officer_token))
    assert res_prio.status_code == 200
    for r in res_prio.json():
        assert r["priority"] == "HIGH"
    print(f"  [PASS] Filter ?priority=HIGH correctly filtered ({len(res_prio.json())} matches)")

    # Combined status + priority
    res_comb = client.get("/api/v1/reports?status=submitted&priority=HIGH", headers=auth_headers(officer_token))
    assert res_comb.status_code == 200
    comb_results = res_comb.json()
    assert len(comb_results) >= 1
    for r in comb_results:
        assert r["status"] == "submitted"
        assert r["priority"] == "HIGH"
    print(f"  [PASS] Combined filter ?status=submitted&priority=HIGH -> exact subset ({len(comb_results)} matches)")

    # -------------------------------------------------------------
    # 6. Report Verification Workflow & State Validation
    # -------------------------------------------------------------
    print("\n[TEST 6] Verification Endpoint Workflow & State Validation...")
    # Valid state transition: submitted -> verified
    res_v1 = client.patch(f"/api/v1/reports/{rep_high_sub}/verify", headers=auth_headers(officer_token))
    assert res_v1.status_code == 200, f"Expected 200 on verify, got {res_v1.status_code}: {res_v1.text}"
    v1_data = res_v1.json()
    assert v1_data["status"] == "verified"
    print(f"  [PASS] PATCH /reports/{rep_high_sub}/verify succeeded -> status='verified'")

    # Invalid state transition: verifying already closed/repaired report must fail with 400
    res_v_closed = client.patch(f"/api/v1/reports/{rep_closed}/verify", headers=auth_headers(officer_token))
    assert res_v_closed.status_code == 400, f"Expected 400 on verifying closed report, got {res_v_closed.status_code}"
    assert "already repaired or closed" in res_v_closed.json()["detail"].lower()
    print(f"  [PASS] Verifying closed report rejected with 400 Bad Request: '{res_v_closed.json()['detail']}'")

    # -------------------------------------------------------------
    # 7. Endpoint Equivalence: Root /reports and Versioned /api/v1/reports
    # -------------------------------------------------------------
    print("\n[TEST 7] Endpoint Equivalence (/reports vs /api/v1/reports)...")
    res_root = client.get(f"/reports/{rep_high_sub}", headers=auth_headers(officer_token))
    assert res_root.status_code == 200
    assert res_root.json()["id"] == rep_high_sub
    print("  [PASS] Root endpoint /reports/{id} is equivalent to /api/v1/reports/{id}")

    print("\n" + "=" * 70)
    print(" ALL MUNICIPAL REPORT API & RBAC TESTS PASSED SUCCESSFULLY! (100%)")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
