"""CivicSight Automated Authentication & Authorization Test Suite (Week 3)

Tests:
- POST /auth/register and POST /api/v1/auth/register (valid payload, duplicate email, format checks)
- POST /auth/login and POST /api/v1/auth/login (valid credentials, wrong password, nonexistent user)
- GET /api/v1/auth/me (JWT token verification)
- Role verification & RoleChecker gating on GET /api/v1/auth/protected-role-example
"""

import sys
import uuid
import time
from fastapi.testclient import TestClient
from app.main import app
from app.models.models import UserRole

client = TestClient(app)


def test_authentication_and_roles_workflow():
    print("\n" + "=" * 70)
    print(" [TEST] CivicSight Week 3: Authentication & Role-Based Access Tests")
    print("=" * 70)

    unique_suffix = uuid.uuid4().hex[:6]
    citizen_email = f"citizen_{unique_suffix}@example.com"
    officer_email = f"officer_{unique_suffix}@example.com"
    staff_email = f"staff_{unique_suffix}@example.com"
    admin_email = f"admin_{unique_suffix}@example.com"
    password_valid = "SecurePass123!"

    # -------------------------------------------------------------------------
    # 1. Registration - Validation & Edge Cases
    # -------------------------------------------------------------------------
    print("\n[1/7] Testing Registration Validation & Edge Cases...")

    # 1a. Short password (< 6 chars)
    short_pw_resp = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Short Pw User",
            "email": f"short_{unique_suffix}@example.com",
            "password": "123",
        },
    )
    assert short_pw_resp.status_code == 422, f"Expected 422 for short password, got {short_pw_resp.status_code}"
    print("  [PASS] Backend validation caught short password (< 6 chars) -> 422 Unprocessable Entity")

    # 1b. Invalid email format
    invalid_email_resp = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Invalid Email",
            "email": "not-an-email",
            "password": password_valid,
        },
    )
    assert invalid_email_resp.status_code == 422, f"Expected 422 for invalid email, got {invalid_email_resp.status_code}"
    print("  [PASS] Backend validation caught malformed email -> 422 Unprocessable Entity")

    # 1c. Valid Citizen Registration
    reg_citizen = client.post(
        "/auth/register",
        json={
            "name": f"Citizen User {unique_suffix}",
            "email": citizen_email,
            "password": password_valid,
            "phone": "+1-555-0100",
            "role": "Citizen",
        },
    )
    assert reg_citizen.status_code == 201, f"Expected 201, got {reg_citizen.status_code}: {reg_citizen.text}"
    citizen_data = reg_citizen.json()
    assert citizen_data["email"] == citizen_email
    assert citizen_data["role"] == "Citizen"
    assert "hashed_password" not in citizen_data, "Password hash leaked in response!"
    citizen_id = citizen_data["id"]
    print(f"  [PASS] Registered Citizen '{citizen_email}' (ID: {citizen_id}) via /auth/register -> 201 Created")

    # 1d. Duplicate Email Registration
    dup_resp = client.post(
        "/auth/register",
        json={
            "name": "Duplicate Person",
            "email": citizen_email,
            "password": password_valid,
        },
    )
    assert dup_resp.status_code == 400, f"Expected 400 for duplicate email, got {dup_resp.status_code}"
    assert "already exists" in dup_resp.json()["detail"].lower()
    print("  [PASS] Duplicate email rejected independently by backend -> 400 Bad Request")

    # -------------------------------------------------------------------------
    # 2. Register Additional Roles (Officer, Staff, Admin)
    # -------------------------------------------------------------------------
    print("\n[2/7] Registering Multi-Role User Accounts...")

    # Officer
    reg_officer = client.post(
        "/api/v1/auth/register",
        json={
            "name": f"Officer Dave {unique_suffix}",
            "email": officer_email,
            "password": password_valid,
            "role": "Municipal Officer",
        },
    )
    assert reg_officer.status_code == 201
    assert reg_officer.json()["role"] == "Municipal Officer"
    print(f"  [PASS] Registered Municipal Officer '{officer_email}' -> 201 Created")

    # Staff
    reg_staff = client.post(
        "/api/v1/auth/register",
        json={
            "name": f"Tech Alex {unique_suffix}",
            "email": staff_email,
            "password": password_valid,
            "role": "Maintenance Staff",
        },
    )
    assert reg_staff.status_code == 201
    assert reg_staff.json()["role"] == "Maintenance Staff"
    print(f"  [PASS] Registered Maintenance Staff '{staff_email}' -> 201 Created")

    # Admin
    reg_admin = client.post(
        "/api/v1/auth/register",
        json={
            "name": f"Admin Sarah {unique_suffix}",
            "email": admin_email,
            "password": password_valid,
            "role": "Admin",
        },
    )
    assert reg_admin.status_code == 201
    assert reg_admin.json()["role"] == "Admin"
    print(f"  [PASS] Registered Admin '{admin_email}' -> 201 Created")

    # -------------------------------------------------------------------------
    # 3. Login Endpoint & Credential Verification
    # -------------------------------------------------------------------------
    print("\n[3/7] Testing Login & Credential Verification...")

    # 3a. Invalid password
    bad_pw_resp = client.post(
        "/auth/login",
        json={"email": citizen_email, "password": "WrongPassword999!"},
    )
    assert bad_pw_resp.status_code == 401, f"Expected 401, got {bad_pw_resp.status_code}"
    assert "invalid email or password" in bad_pw_resp.json()["detail"].lower()
    print("  [PASS] Login with wrong password failed gracefully -> 401 Unauthorized")

    # 3b. Nonexistent user
    nonexistent_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@doesnotexist9999.com", "password": password_valid},
    )
    assert nonexistent_resp.status_code == 401, f"Expected 401, got {nonexistent_resp.status_code}"
    assert "invalid email or password" in nonexistent_resp.json()["detail"].lower()
    print("  [PASS] Login with nonexistent email failed gracefully without leak -> 401 Unauthorized")

    # 3c. Successful Citizen Login
    login_citizen = client.post(
        "/auth/login",
        json={"email": citizen_email, "password": password_valid},
    )
    assert login_citizen.status_code == 200
    token_citizen = login_citizen.json()["access_token"]
    assert token_citizen and len(token_citizen) > 20
    assert login_citizen.json()["token_type"] == "bearer"
    assert login_citizen.json()["user"]["role"] == "Citizen"
    print(f"  [PASS] Citizen login successful -> Received JWT token: {token_citizen[:18]}...")

    # Login Officer
    login_officer = client.post(
        "/api/v1/auth/login",
        json={"email": officer_email, "password": password_valid},
    )
    assert login_officer.status_code == 200
    token_officer = login_officer.json()["access_token"]

    # Login Staff
    login_staff = client.post(
        "/api/v1/auth/login",
        json={"email": staff_email, "password": password_valid},
    )
    assert login_staff.status_code == 200
    token_staff = login_staff.json()["access_token"]

    # Login Admin
    login_admin = client.post(
        "/api/v1/auth/login",
        json={"email": admin_email, "password": password_valid},
    )
    assert login_admin.status_code == 200
    token_admin = login_admin.json()["access_token"]
    print("  [PASS] All role accounts logged in successfully and received JWT tokens.")

    # -------------------------------------------------------------------------
    # 4. Authentication Proof: GET /api/v1/auth/me
    # -------------------------------------------------------------------------
    print("\n[4/7] Testing Authenticated Identity (GET /api/v1/auth/me)...")

    # Missing token
    unauth_me = client.get("/api/v1/auth/me")
    assert unauth_me.status_code == 401
    print("  [PASS] Access without token rejected -> 401 Unauthorized")

    # Invalid token
    invalid_tok_me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer bad.token.here"},
    )
    assert invalid_tok_me.status_code == 401
    print("  [PASS] Access with corrupted token rejected -> 401 Unauthorized")

    # Valid token
    auth_me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_citizen}"},
    )
    assert auth_me.status_code == 200
    me_data = auth_me.json()
    assert me_data["id"] == citizen_id
    assert me_data["email"] == citizen_email
    assert me_data["role"] == "Citizen"
    print(f"  [PASS] Verified authenticated profile for '{me_data['name']}' (Role: {me_data['role']})")

    # -------------------------------------------------------------------------
    # 5. Role-Based Access Control (RBAC) Gating Proof
    # Endpoint requires: 'Admin' or 'Municipal Officer'
    # -------------------------------------------------------------------------
    print("\n[5/7] Testing Role-Based Access Control (RBAC) on Protected Endpoint...")

    # 5a. Admin access (Authorized)
    admin_check = client.get(
        "/api/v1/auth/protected-role-example",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert admin_check.status_code == 200
    assert admin_check.json()["status"] == "authorized"
    print("  [PASS] Role 'Admin' granted access -> 200 OK")

    # 5b. Municipal Officer access (Authorized)
    officer_check = client.get(
        "/api/v1/auth/protected-role-example",
        headers={"Authorization": f"Bearer {token_officer}"},
    )
    assert officer_check.status_code == 200
    assert officer_check.json()["status"] == "authorized"
    print("  [PASS] Role 'Municipal Officer' granted access -> 200 OK")

    # 5c. Citizen access (Unauthorized Role -> Forbidden)
    citizen_check = client.get(
        "/api/v1/auth/protected-role-example",
        headers={"Authorization": f"Bearer {token_citizen}"},
    )
    assert citizen_check.status_code == 403, f"Expected 403, got {citizen_check.status_code}"
    assert "forbidden" in citizen_check.json()["detail"].lower()
    print("  [PASS] Role 'Citizen' forbidden on officer/admin endpoint -> 403 Forbidden")

    # 5d. Maintenance Staff access (Unauthorized Role -> Forbidden)
    staff_check = client.get(
        "/api/v1/auth/protected-role-example",
        headers={"Authorization": f"Bearer {token_staff}"},
    )
    assert staff_check.status_code == 403, f"Expected 403, got {staff_check.status_code}"
    assert "forbidden" in staff_check.json()["detail"].lower()
    print("  [PASS] Role 'Maintenance Staff' forbidden on officer/admin endpoint -> 403 Forbidden")

    # -------------------------------------------------------------------------
    # 6. Verify Existing CRUD Functionality Remains Intact
    # -------------------------------------------------------------------------
    print("\n[6/7] Verifying Existing User & Report CRUD Compatibility...")

    # Create report associated with newly registered citizen
    new_report = client.post(
        "/api/v1/reports",
        json={
            "reporter_id": citizen_id,
            "description": "Week 3 verified pothole submission with authenticated citizen link",
            "latitude": 37.7749,
            "longitude": -122.4194,
            "address_text": "Civic Center Blvd",
            "damage_type": "D40",
            "status": "submitted",
        },
    )
    assert new_report.status_code == 201
    report_id = new_report.json()["id"]
    assert new_report.json()["reporter_id"] == citizen_id
    print(f"  [PASS] Created damage report #{report_id} linked to citizen #{citizen_id}")

    # Read back report
    get_rep = client.get(f"/api/v1/reports/{report_id}")
    assert get_rep.status_code == 200
    assert get_rep.json()["reporter"]["email"] == citizen_email
    print(f"  [PASS] Report #{report_id} eager-loaded reporter profile with role '{get_rep.json()['reporter']['role']}'")

    # -------------------------------------------------------------------------
    # 7. Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print(" [SUMMARY] ALL AUTHENTICATION & ROLE ACCESS TESTS PASSED (100% SUCCESS)")
    print("=" * 70)


if __name__ == "__main__":
    test_authentication_and_roles_workflow()
