"""CivicSight Backend CRUD Test Suite (Week 2)

Validates end-to-end database transactions and REST endpoint contracts
for User and Report entities against live PostgreSQL database.
"""

from fastapi.testclient import TestClient
from app.main import app
from app.db.init_db import init_db

# Ensure tables exist
init_db()

client = TestClient(app)


def test_system_endpoints():
    print("\n[TEST] 1. Testing System & Health Endpoints...")
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert res_root.json()["project"] == "CivicSight"
    print("   [OK] Root endpoint verified.")

    res_health = client.get("/health")
    assert res_health.status_code == 200
    data_health = res_health.json()
    assert data_health["system_health"] == "ok"
    assert data_health["database"]["reachable"] is True
    print("   [OK] Health & PostgreSQL connectivity verified.")


def test_user_crud():
    print("\n[TEST] 2. Testing User CRUD Operations...")
    import uuid
    random_suffix = str(uuid.uuid4())[:8]
    test_email = f"citizen_{random_suffix}@civicsight.org"

    # CREATE
    user_payload = {
        "name": "Jane Citizen",
        "email": test_email,
        "phone": "+1-555-0199"
    }
    res_create = client.post("/api/v1/users", json=user_payload)
    assert res_create.status_code == 201, res_create.text
    user = res_create.json()
    user_id = user["id"]
    assert user["name"] == "Jane Citizen"
    assert user["email"] == test_email
    print(f"   [OK] Created User: ID={user_id}, Name='{user['name']}'")

    # READ SINGLE
    res_get = client.get(f"/api/v1/users/{user_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == user_id
    print(f"   [OK] Retrieved User by ID={user_id}")

    # LIST
    res_list = client.get("/api/v1/users")
    assert res_list.status_code == 200
    users = res_list.json()
    assert any(u["id"] == user_id for u in users)
    print(f"   [OK] Listed Users (Found {len(users)} users)")

    # UPDATE
    update_payload = {"name": "Jane Citizen Updated", "phone": "+1-555-9999"}
    res_update = client.put(f"/api/v1/users/{user_id}", json=update_payload)
    assert res_update.status_code == 200
    assert res_update.json()["name"] == "Jane Citizen Updated"
    assert res_update.json()["phone"] == "+1-555-9999"
    print(f"   [OK] Updated User ID={user_id}")

    return user_id


def test_report_crud(user_id: int):
    print("\n[TEST] 3. Testing Report CRUD & Workflow Operations...")
    
    # CREATE REPORT
    report_payload = {
        "reporter_id": user_id,
        "description": "Deep pothole near municipal library entrance",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "address_text": "100 Main St, Civic Center",
        "image_url": "https://storage.civicsight.org/reports/sample_pothole_01.jpg",
        "damage_type": "D40",
        "status": "submitted"
    }
    res_create = client.post("/api/v1/reports", json=report_payload)
    assert res_create.status_code == 201, res_create.text
    report = res_create.json()
    report_id = report["id"]
    assert report["status"] == "submitted"
    assert report["reporter_id"] == user_id
    print(f"   [OK] Created Report: ID={report_id}, Status='{report['status']}'")

    # READ SINGLE
    res_get = client.get(f"/api/v1/reports/{report_id}")
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["id"] == report_id
    assert data["reporter"]["name"] == "Jane Citizen Updated"
    print(f"   [OK] Retrieved Report ID={report_id} with nested Reporter relation")

    # LIST & FILTER
    res_list_all = client.get("/api/v1/reports")
    assert res_list_all.status_code == 200
    assert len(res_list_all.json()) >= 1
    
    res_list_filtered = client.get("/api/v1/reports?status=submitted")
    assert res_list_filtered.status_code == 200
    assert any(r["id"] == report_id for r in res_list_filtered.json())
    print("   [OK] Filtered Reports by status='submitted'")

    # UPDATE REPORT
    update_payload = {
        "description": "Critical pothole with exposed aggregate layer",
        "severity_score": 0.88,
        "damage_type": "D40"
    }
    res_update = client.put(f"/api/v1/reports/{report_id}", json=update_payload)
    assert res_update.status_code == 200
    assert res_update.json()["severity_score"] == 0.88
    print(f"   [OK] Updated Report ID={report_id} severity score to 0.88")

    # STATUS WORKFLOW TRANSITIONS
    lifecycle = ["detected", "prioritized", "verified", "assigned", "repaired", "closed"]
    for next_status in lifecycle:
        res_patch = client.patch(f"/api/v1/reports/{report_id}/status", json={"status": next_status})
        assert res_patch.status_code == 200
        assert res_patch.json()["status"] == next_status
    print(f"   [OK] Successfully tested full workflow lifecycle transitions -> {lifecycle}")

    # DELETE REPORT
    res_del_rep = client.delete(f"/api/v1/reports/{report_id}")
    assert res_del_rep.status_code == 200
    res_check = client.get(f"/api/v1/reports/{report_id}")
    assert res_check.status_code == 404
    print(f"   [OK] Deleted Report ID={report_id} and verified 404")

    # DELETE USER
    res_del_user = client.delete(f"/api/v1/users/{user_id}")
    assert res_del_user.status_code == 200
    res_check_user = client.get(f"/api/v1/users/{user_id}")
    assert res_check_user.status_code == 404
    print(f"   [OK] Deleted User ID={user_id} and verified 404")


if __name__ == "__main__":
    print("=" * 65)
    print("CivicSight Week 2: Automated Backend CRUD Test Suite")
    print("=" * 65)
    test_system_endpoints()
    uid = test_user_crud()
    test_report_crud(uid)
    print("=" * 65)
    print("ALL TESTS PASSED SUCCESSFULLY! (100% CRUD Coverage Against PostgreSQL)")
    print("=" * 65)
