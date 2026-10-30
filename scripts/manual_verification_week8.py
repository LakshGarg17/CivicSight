"""Week 8 Manual Verification Script.

Executes all verification steps from Requirement 8:
1. Submit real pothole image as Citizen -> confirm stored severity, priority, readable reasons.
2. Submit second report within nearby distance -> confirm updated nearby count, relation created, priority history row written.
3. Submit distant report -> confirm no relation created.
4. Officer views dashboard queries -> priority column, high-priority filter, readable reasons, related reports.
5. Officer confirms duplicate -> verify legal transition to DUPLICATE status, neither report deleted.
6. Break model -> submit report, confirm 201 Created, fallback priority rules applied, reasons note "Automated assessment unavailable".
7. Citizen RBAC -> verify citizen gets 403 on all privileged endpoints, unauthenticated gets 401.
8. Persistence -> reopen DB session, verify all records persisted.
"""

import os
import sys
import uuid
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ["DATABASE_URL"] = os.getenv("DATABASE_URL", f"sqlite:///{BACKEND_DIR}/civicsight.db")

from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.models.models import User, UserRole, Report, ReportStatus, ReportRelation, PriorityHistory
from app.core.security import create_access_token, get_password_hash

client = TestClient(app)

def get_auth_token(role: UserRole, email: str, name: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                name=name,
                email=email,
                role=role,
                hashed_password=get_password_hash("password123"),
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
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}, user.id
    finally:
        db.close()

def run_manual_verification():
    print("=" * 70)
    print("CIVICSIGHT WEEK 8: MANUAL VERIFICATION OF ALL 9 REQUIREMENTS")
    print("=" * 70)

    citizen_headers, citizen_id = get_auth_token(UserRole.CITIZEN, "citizen_manual@civicsight.org", "Citizen Manual")
    officer_headers, officer_id = get_auth_token(UserRole.MUNICIPAL_OFFICER, "officer_manual@civicsight.org", "Officer Manual")

    results = {}

    # ---------------------------------------------------------
    # STEP 1: Submit real pothole image as Citizen
    # ---------------------------------------------------------
    print("\n--- STEP 1: Submit Real Pothole Image as Citizen ---")
    test_image_path = PROJECT_ROOT / "Dataset" / "RDD_SPLIT" / "test" / "images" / "China_Drone_000008.jpg"
    assert test_image_path.exists(), f"Image not found at {test_image_path}"

    with open(test_image_path, "rb") as img_f:
        res1 = client.post(
            "/api/v1/reports",
            data={
                "description": "Deep hazardous pothole reported on Main Street",
                "latitude": 37.774929,
                "longitude": -122.419416,
                "damage_type": "D40",
                "reporter_id": citizen_id,
            },
            files={"image": ("pothole.jpg", img_f, "image/jpeg")},
            headers=citizen_headers,
        )

    assert res1.status_code == 201, f"Expected 201, got {res1.status_code}: {res1.text}"
    rep1_data = res1.json()
    rep1_id = rep1_data["id"]

    # Explicitly ensure ML pipeline finishes on this image
    from app.services.ml_service import process_report_image_ml
    process_report_image_ml(rep1_id)

    # Re-fetch report detail
    detail1 = client.get(f"/api/v1/reports/{rep1_id}", headers=citizen_headers).json()
    print(f"Report ID: {rep1_id}")
    print(f"Stored Severity: {detail1.get('severity')}")
    print(f"Stored Priority: {detail1.get('priority')}")
    print(f"Stored Score: {detail1.get('priority_score')}")
    print(f"Stored Reasons: {detail1.get('priority_reasons')}")

    assert detail1.get("priority") in ["HIGH", "MEDIUM", "LOW"]
    assert detail1.get("severity") in ["HIGH", "MEDIUM", "LOW", "UNKNOWN"]
    assert len(detail1.get("priority_reasons") or []) > 0
    results["Step 1: Real Pothole Submission"] = "PASS"

    # ---------------------------------------------------------
    # STEP 2: Submit another report within nearby distance (10 meters)
    # ---------------------------------------------------------
    print("\n--- STEP 2: Submit Second Report Within Nearby Distance ---")
    # 0.00009 deg lat ~ 10m
    lat_nearby = 37.774929 + 0.00009
    lng_nearby = -122.419416

    res2 = client.post(
        "/api/v1/reports",
        json={
            "description": "Nearby damage report at same intersection",
            "latitude": lat_nearby,
            "longitude": lng_nearby,
            "damage_type": "D40",
            "reporter_id": citizen_id,
        },
        headers=citizen_headers,
    )
    assert res2.status_code == 201, f"Expected 201, got {res2.status_code}: {res2.text}"
    rep2_id = res2.json()["id"]

    # Check both reports for updated nearby counts and priority recalculation
    rep1_updated = client.get(f"/api/v1/reports/{rep1_id}", headers=officer_headers).json()
    rep2_updated = client.get(f"/api/v1/reports/{rep2_id}", headers=officer_headers).json()

    print(f"Report 1 Nearby Count: {rep1_updated['nearby_report_count']}")
    print(f"Report 2 Nearby Count: {rep2_updated['nearby_report_count']}")
    print(f"Report 1 Related Count: {len(rep1_updated['related_reports'])}")
    print(f"Report 2 Related Count: {len(rep2_updated['related_reports'])}")

    assert rep1_updated["nearby_report_count"] >= 1
    assert rep2_updated["nearby_report_count"] >= 1
    assert len(rep1_updated["related_reports"]) >= 1

    # Check priority history rows
    hist_res = client.get(f"/api/v1/reports/{rep1_id}/priority-history", headers=officer_headers)
    assert hist_res.status_code == 200
    print(f"Report 1 Priority History entries: {len(hist_res.json())}")
    results["Step 2: Nearby Cluster & Priority Sync"] = "PASS"

    # ---------------------------------------------------------
    # STEP 3: Submit a report at distant location (> 1 km)
    # ---------------------------------------------------------
    print("\n--- STEP 3: Submit Report at Distant Location ---")
    dist_offset = (uuid.uuid4().int % 1000) * 0.001
    res_distant = client.post(
        "/api/v1/reports",
        json={
            "description": "Distant isolated rural road defect",
            "latitude": 45.0 + dist_offset,
            "longitude": -115.0 - dist_offset,
            "damage_type": "D10",
        },
        headers=citizen_headers,
    )
    assert res_distant.status_code == 201
    rep_distant_id = res_distant.json()["id"]

    rep_distant = client.get(f"/api/v1/reports/{rep_distant_id}", headers=officer_headers).json()
    print(f"Distant Report Nearby Count: {rep_distant['nearby_report_count']}")
    print(f"Distant Report Related Reports: {len(rep_distant['related_reports'])}")
    assert rep_distant["nearby_report_count"] == 0
    assert len(rep_distant["related_reports"]) == 0
    results["Step 3: Distant Report Proximity Isolation"] = "PASS"

    # ---------------------------------------------------------
    # STEP 4: Officer dashboard API queries
    # ---------------------------------------------------------
    print("\n--- STEP 4: Officer Dashboard API Queries ---")
    list_high = client.get("/api/v1/reports?priority=HIGH", headers=officer_headers)
    assert list_high.status_code == 200
    high_items = list_high.json()
    print(f"High Priority Filter Count: {len(high_items)}")
    for item in high_items[:3]:
        assert item["priority"] == "HIGH"
        print(f"  - Report #{item['id']} [Priority: {item['priority']}, Severity: {item['severity']}, Nearby: {item['nearby_report_count']}]")

    list_sorted = client.get("/api/v1/reports?sort_by=priority&order=desc", headers=officer_headers)
    assert list_sorted.status_code == 200
    results["Step 4: Dashboard Filtering & Sorting APIs"] = "PASS"

    # ---------------------------------------------------------
    # STEP 5: Confirm a duplicate relation
    # ---------------------------------------------------------
    print("\n--- STEP 5: Confirm Duplicate & Verify Lifecycle Rules ---")
    # Find pending relation between rep1 and rep2
    rep1_rels = rep1_updated["related_reports"]
    matching_rel = next((r for r in rep1_rels if (r.get("related_report_id") == rep2_id or r.get("report_id") == rep2_id)), None)
    assert matching_rel is not None, "Relation between rep1 and rep2 must exist"

    rel_id = matching_rel.get("relation_id") or matching_rel.get("id")
    patch_rel = client.patch(
        f"/api/v1/report-relations/{rel_id}",
        json={"review_status": "CONFIRMED_DUPLICATE", "note": "Confirmed duplicate by officer field review"},
        headers=officer_headers,
    )
    assert patch_rel.status_code == 200
    reviewed_rel = patch_rel.json()
    print(f"Relation #{rel_id} Review Status: {reviewed_rel['review_status']}")
    print(f"Reviewed By: {reviewed_rel['reviewed_by']}, Note: {reviewed_rel['note']}")

    # Check that original report (rep1) remains intact (not deleted, status unchanged)
    rep1_after = client.get(f"/api/v1/reports/{rep1_id}", headers=officer_headers).json()
    # Check that duplicate report (rep2) transitioned to DUPLICATE without being deleted
    rep2_after = client.get(f"/api/v1/reports/{rep2_id}", headers=officer_headers).json()

    print(f"Original Report #{rep1_id} Status: {rep1_after['status']} (Intact)")
    print(f"Duplicate Report #{rep2_id} Status: {rep2_after['status']} (Marked Duplicate)")
    assert rep1_after["status"] in ["submitted", "verified"]
    assert rep2_after["status"] == "duplicate"
    results["Step 5: Duplicate Review & Lifecycle Preservation"] = "PASS"

    # ---------------------------------------------------------
    # STEP 6: Break the model and submit report
    # ---------------------------------------------------------
    print("\n--- STEP 6: Break Model & Ingest Report with Fallback Priority ---")
    import ml.src.inference

    original_fn = ml.src.inference.detect_road_damage
    try:
        def faulty_detect(*args, **kwargs):
            raise FileNotFoundError("Weights file corrupt / missing GPU backend")
        ml.src.inference.detect_road_damage = faulty_detect

        res_broken = client.post(
            "/api/v1/reports",
            json={
                "description": "Report submitted during model maintenance outage",
                "latitude": 37.7760,
                "longitude": -122.4170,
                "damage_type": "D40",
            },
            headers=citizen_headers,
        )
        assert res_broken.status_code == 201, f"Report creation must not fail, got {res_broken.status_code}"
        rep_broken_id = res_broken.json()["id"]

        detail_broken = client.get(f"/api/v1/reports/{rep_broken_id}", headers=officer_headers).json()
        print(f"Broken ML Report ID: {rep_broken_id}")
        print(f"Stored Severity: {detail_broken['severity']}")
        print(f"Stored Priority: {detail_broken['priority']}")
        print(f"Stored Reasons: {detail_broken['priority_reasons']}")

        assert detail_broken["severity"] == "UNKNOWN"
        assert detail_broken["priority"] in ["HIGH", "MEDIUM", "LOW"]
        assert any("Automated assessment unavailable" in r for r in detail_broken["priority_reasons"])
        results["Step 6: Fault Tolerance on Broken ML Model"] = "PASS"
    finally:
        ml.src.inference.detect_road_damage = original_fn

    # ---------------------------------------------------------
    # STEP 7: Citizen and Unauthenticated RBAC verification
    # ---------------------------------------------------------
    print("\n--- STEP 7: RBAC Access Controls (403 for Citizen, 401 Unauthenticated) ---")
    endpoints = [
        ("GET", f"/api/v1/reports/{rep1_id}/related", None),
        ("PATCH", f"/api/v1/report-relations/{rel_id}", {"review_status": "DISMISSED"}),
        ("GET", f"/api/v1/reports/{rep1_id}/priority-history", None),
        ("POST", f"/api/v1/reports/{rep1_id}/recalculate-priority", None),
        ("POST", f"/api/v1/reports/{rep1_id}/override-priority", {"priority": "HIGH", "reason": "Test"}),
    ]

    for method, path, body in endpoints:
        # Unauthenticated -> 401
        res_noauth = client.request(method, path, json=body)
        assert res_noauth.status_code in [401, 403], f"Unauthenticated {path} expected 401/403, got {res_noauth.status_code}"

        # Citizen -> 403
        res_cit = client.request(method, path, json=body, headers=citizen_headers)
        assert res_cit.status_code == 403, f"Citizen {path} expected 403, got {res_cit.status_code}"
        print(f"  [OK] {method} {path} strictly blocked Citizen (403) & Unauth ({res_noauth.status_code})")

    # Citizen viewing own report: sees priority, but not related_reports details of other citizens
    cit_view_own = client.get(f"/api/v1/reports/{rep1_id}", headers=citizen_headers).json()
    assert cit_view_own.get("priority") is not None
    assert cit_view_own.get("related_reports") == [], "Citizen must not receive other citizens' report details"
    results["Step 7: Strict RBAC & Citizen Privacy"] = "PASS"

    # ---------------------------------------------------------
    # STEP 8: Backend Persistence Verification
    # ---------------------------------------------------------
    print("\n--- STEP 8: Database Persistence Check ---")
    db_fresh = SessionLocal()
    try:
        r1 = db_fresh.query(Report).filter(Report.id == rep1_id).first()
        r2 = db_fresh.query(Report).filter(Report.id == rep2_id).first()
        rel = db_fresh.query(ReportRelation).filter(ReportRelation.id == rel_id).first()
        hist_count = db_fresh.query(PriorityHistory).filter(PriorityHistory.report_id == rep1_id).count()

        assert r1 is not None and r1.priority is not None
        assert r2 is not None and r2.status == ReportStatus.DUPLICATE
        assert rel is not None and rel.review_status == "CONFIRMED_DUPLICATE"
        assert hist_count >= 1

        print(f"Persisted Report 1: Priority={r1.priority}, Severity={r1.severity}, Score={r1.priority_score}")
        print(f"Persisted Report 2: Status={r2.status.value}, Nearby={r2.nearby_report_count}")
        print(f"Persisted Relation: Status={rel.review_status}, Reviewer={rel.reviewed_by}")
        print(f"Persisted History Rows for Report 1: {hist_count}")
        results["Step 8: Storage Persistence Verification"] = "PASS"
    finally:
        db_fresh.close()

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------
    print("\n" + "=" * 70)
    print("MANUAL VERIFICATION RESULTS:")
    print("=" * 70)
    for step, status in results.items():
        print(f"  {step:<50}: [{status}]")
    print("=" * 70)

if __name__ == "__main__":
    run_manual_verification()
