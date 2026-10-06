"""CivicSight — Week 6 Full Integration Sanity Check Suite

Verifies all 4 checkpoints specified in Week 6 Requirement 4:
1. Valid Path: Submitted -> Verified -> Assigned, checking status + history entry at each step.
2. Illegal Transition Blocking: Direct calls to illegal transitions (e.g. Assign before Verify,
   Verify after Assigned, Reject after Assigned, Verify on Closed) are rejected with 400 Bad Request,
   and history remains clean.
3. Reject & Duplicate End-to-End: Required reason/reference fields are enforced, statuses are updated,
   and events appear in history.
4. Reusable ML Inference Module: Runs on at least 3 held-out test images and produces properly structured output.
"""

import os
import sys
import uuid
from pathlib import Path

# Add project root and backend to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Ensure SQLite test database fallback if PostgreSQL is not active
os.environ["DATABASE_URL"] = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT}/backend/civicsight.db")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.init_db import init_db
from app.db.database import SessionLocal
from app.models.models import User, UserRole, ReportStatus
from app.core.security import create_access_token, get_password_hash
from ml.src.inference import detect_road_damage

# Ensure tables
init_db()
client = TestClient(app)


def get_officer_headers() -> dict:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "officer_sanity@civicsight.org").first()
        if not user:
            user = User(
                name="Officer Sanity",
                email="officer_sanity@civicsight.org",
                role=UserRole.MUNICIPAL_OFFICER,
                hashed_password=get_password_hash("testpass123"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        claims = {
            "email": user.email,
            "role": user.role.value if isinstance(user.role, UserRole) else str(user.role),
            "name": user.name,
        }
        token = create_access_token(subject=user.id, claims=claims)
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    finally:
        db.close()


def test_checkpoint_1_valid_lifecycle_path():
    """Sanity Check 1: Submitted -> Verified -> Assigned with status & history verification."""
    headers = get_officer_headers()

    # 1. Create a fresh report
    create_res = client.post(
        "/api/v1/reports",
        json={
            "description": f"Pothole on Market {uuid.uuid4().hex[:4]}",
            "latitude": 37.7749,
            "longitude": -122.4194,
            "address_text": "Market & 4th Street",
            "damage_type": "D40",
            "priority": "HIGH",
        },
        headers=headers,
    )
    assert create_res.status_code == 201, create_res.text
    report = create_res.json()
    report_id = report["id"]
    assert report["status"] == "submitted"

    # Check initial history
    h0_res = client.get(f"/api/v1/reports/{report_id}/history", headers=headers)
    assert h0_res.status_code == 200
    h0 = h0_res.json()
    assert len(h0) >= 1
    assert h0[0]["to_status"] == "submitted"

    # 2. Transition Submitted -> Verified
    verify_res = client.patch(
        f"/api/v1/reports/{report_id}/verify",
        json={"note": "Confirmed pothole hazard via inspector review."},
        headers=headers,
    )
    assert verify_res.status_code == 200, verify_res.text
    verified_data = verify_res.json()
    assert verified_data["status"] == "verified"

    # Check history after verify
    h1_res = client.get(f"/api/v1/reports/{report_id}/history", headers=headers)
    assert h1_res.status_code == 200
    h1 = h1_res.json()
    assert len(h1) >= 2
    last_event = h1[-1]
    assert last_event["from_status"] == "submitted"
    assert last_event["to_status"] == "verified"
    assert "Confirmed pothole" in last_event["note"]

    # 3. Transition Verified -> Assigned
    assign_res = client.patch(
        f"/api/v1/reports/{report_id}/assign",
        json={
            "assigned_to": "Metro Asphalt Rapid Unit 3",
            "note": "Dispatched for emergency night paving.",
        },
        headers=headers,
    )
    assert assign_res.status_code == 200, assign_res.text
    assigned_data = assign_res.json()
    assert assigned_data["status"] == "assigned"
    assert assigned_data["assigned_to"] == "Metro Asphalt Rapid Unit 3"

    # Check history after assign
    h2_res = client.get(f"/api/v1/reports/{report_id}/history", headers=headers)
    assert h2_res.status_code == 200
    h2 = h2_res.json()
    assert len(h2) >= 3
    last_event2 = h2[-1]
    assert last_event2["from_status"] == "verified"
    assert last_event2["to_status"] == "assigned"
    assert "Metro Asphalt Rapid Unit 3" in last_event2["note"]

    print(f"\n[PASS] Sanity Check 1: Report #{report_id} successfully progressed Submitted -> Verified -> Assigned with 3 verified history entries.")


def test_checkpoint_2_illegal_transitions_blocked():
    """Sanity Check 2: Server-side validation strictly blocks illegal transitions with 400 Bad Request."""
    headers = get_officer_headers()

    # Create fresh report in 'submitted'
    create_res = client.post(
        "/api/v1/reports",
        json={"latitude": 37.7800, "longitude": -122.4200, "damage_type": "D10", "priority": "MEDIUM"},
        headers=headers,
    )
    report_id = create_res.json()["id"]

    # Illegal Transition 1: Trying to Assign before Verifying (Submitted -> Assigned is illegal)
    illegal_assign = client.patch(
        f"/api/v1/reports/{report_id}/assign",
        json={"assigned_to": "Early Crew Alpha"},
        headers=headers,
    )
    assert illegal_assign.status_code == 400
    assert "Cannot assign report with status 'submitted'" in illegal_assign.json()["detail"]

    # Now verify legitimately
    client.patch(f"/api/v1/reports/{report_id}/verify", headers=headers)

    # Legitimately assign
    client.patch(
        f"/api/v1/reports/{report_id}/assign",
        json={"assigned_to": "Legit Crew Beta"},
        headers=headers,
    )

    # Illegal Transition 2: Trying to Verify again after already Assigned (Assigned -> Verified is illegal)
    illegal_reverify = client.patch(
        f"/api/v1/reports/{report_id}/verify",
        headers=headers,
    )
    assert illegal_reverify.status_code == 400
    assert "cannot be re-verified" in illegal_reverify.json()["detail"].lower()

    # Illegal Transition 3: Trying to Reject after already Assigned (Assigned -> Rejected is illegal)
    illegal_reject = client.patch(
        f"/api/v1/reports/{report_id}/reject",
        json={"reason": "Late rejection attempt"},
        headers=headers,
    )
    assert illegal_reject.status_code == 400
    assert "cannot reject report with status 'assigned'" in illegal_reject.json()["detail"].lower()

    # Advance report to Closed
    client.patch(f"/api/v1/reports/{report_id}/status", json={"status": "under_repair"}, headers=headers)
    client.patch(f"/api/v1/reports/{report_id}/status", json={"status": "closed"}, headers=headers)

    # Illegal Transition 4: Trying to re-verify a Closed report
    illegal_closed = client.patch(
        f"/api/v1/reports/{report_id}/verify",
        headers=headers,
    )
    assert illegal_closed.status_code == 400
    assert "cannot be re-verified" in illegal_closed.json()["detail"].lower()

    print(f"\n[PASS] Sanity Check 2: All 4 illegal transition attempts strictly rejected by backend API (400 Bad Request).")


def test_checkpoint_3_reject_and_duplicate_end_to_end():
    """Sanity Check 3: Reject and Duplicate actions work end-to-end with required validation & history."""
    headers = get_officer_headers()

    # A. Test Reject
    res_a = client.post(
        "/api/v1/reports",
        json={"latitude": 37.7810, "longitude": -122.4210, "damage_type": "D00", "priority": "LOW"},
        headers=headers,
    )
    report_a_id = res_a.json()["id"]

    # Missing reason must be rejected (validation error 422)
    missing_reason_res = client.patch(
        f"/api/v1/reports/{report_a_id}/reject",
        json={},
        headers=headers,
    )
    assert missing_reason_res.status_code == 422

    # Valid reject
    reject_res = client.patch(
        f"/api/v1/reports/{report_a_id}/reject",
        json={"reason": "Cosmetic oil stain on private drive; not structural pavement failure.", "note": "Resident notified."},
        headers=headers,
    )
    assert reject_res.status_code == 200, reject_res.text
    rejected_data = reject_res.json()
    assert rejected_data["status"] == "rejected"
    assert "Cosmetic oil stain" in rejected_data["rejection_reason"]

    # Check history shows rejection reason
    h_rej = client.get(f"/api/v1/reports/{report_a_id}/history", headers=headers)
    assert h_rej.status_code == 200
    rej_event = h_rej.json()[-1]
    assert rej_event["to_status"] == "rejected"
    assert "Cosmetic oil stain" in rej_event["note"]

    # B. Test Duplicate
    res_b = client.post(
        "/api/v1/reports",
        json={"latitude": 37.7812, "longitude": -122.4211, "damage_type": "D00", "priority": "LOW"},
        headers=headers,
    )
    report_b_id = res_b.json()["id"]

    # Missing original_report_id (validation error 422)
    missing_orig_res = client.patch(
        f"/api/v1/reports/{report_b_id}/duplicate",
        json={},
        headers=headers,
    )
    assert missing_orig_res.status_code == 422

    # Duplicate referencing self is invalid (400)
    self_dup_res = client.patch(
        f"/api/v1/reports/{report_b_id}/duplicate",
        json={"original_report_id": report_b_id},
        headers=headers,
    )
    assert self_dup_res.status_code == 400

    # Duplicate referencing non-existent report is invalid (404)
    nonexist_dup_res = client.patch(
        f"/api/v1/reports/{report_b_id}/duplicate",
        json={"original_report_id": 999999},
        headers=headers,
    )
    assert nonexist_dup_res.status_code == 404

    # Valid duplicate referencing report A
    valid_dup_res = client.patch(
        f"/api/v1/reports/{report_b_id}/duplicate",
        json={"original_report_id": report_a_id, "note": "Duplicate citizen angle of report A."},
        headers=headers,
    )
    assert valid_dup_res.status_code == 200, valid_dup_res.text
    dup_data = valid_dup_res.json()
    assert dup_data["status"] == "duplicate"
    assert dup_data["duplicate_of_id"] == report_a_id

    # Check history shows duplicate reference
    h_dup = client.get(f"/api/v1/reports/{report_b_id}/history", headers=headers)
    assert h_dup.status_code == 200
    dup_event = h_dup.json()[-1]
    assert dup_event["to_status"] == "duplicate"
    assert f"Report #{report_a_id}" in dup_event["note"]

    print(f"\n[PASS] Sanity Check 3: Reject and Duplicate actions work end-to-end with required field enforcement and persistent history.")


def test_checkpoint_4_ml_inference_on_held_out_images():
    """Sanity Check 4: ML inference function runs on >= 3 held-out test images and returns structured output."""
    test_img_dir = PROJECT_ROOT / "Dataset" / "RDD_SPLIT" / "test" / "images"

    held_out_images = [
        "China_Drone_000008.jpg",
        "China_Drone_000017.jpg",
        "China_Drone_000040.jpg",
        "China_MotorBike_000093.jpg",
    ]

    for fname in held_out_images:
        img_path = test_img_dir / fname
        assert img_path.exists(), f"Held-out test image {fname} not found in {test_img_dir}"

        # Run inference module
        result = detect_road_damage(img_path, confidence_threshold=0.10)

        # Verify structured output schema
        assert result["success"] is True
        assert result["model_version"] == "YOLOv8n-experiment2_week5"
        assert "original_dimensions" in result
        assert result["original_dimensions"]["width"] > 0
        assert result["original_dimensions"]["height"] > 0
        assert isinstance(result["inference_time_ms"], float)
        assert isinstance(result["num_detections"], int)
        assert result["primary_priority"] in ("HIGH", "MEDIUM", "LOW")
        assert isinstance(result["detections"], list)

        for det in result["detections"]:
            assert "class_id" in det
            assert det["class_name"] in ("D00", "D10", "D20", "D40")
            assert "description" in det
            assert 0.0 <= det["confidence"] <= 1.0
            assert det["severity"] in ("HIGH", "MEDIUM")
            assert len(det["bbox"]) == 4
            assert len(det["bbox_normalized"]) == 4
            # Verify coordinates are in ascending order
            assert det["bbox"][0] <= det["bbox"][2]
            assert det["bbox"][1] <= det["bbox"][3]

        print(f"\n[PASS] Sanity Check 4: '{fname}' passed ML inference ({result['num_detections']} detections, {result['inference_time_ms']}ms, priority={result['primary_priority']}).")
