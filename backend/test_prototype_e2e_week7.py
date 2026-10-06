"""
CivicSight Week 7 — Full End-to-End Prototype Verification Script
Tests all 6 mandatory requirements against the live FastAPI server and SQLite DB.
"""

import sys
import os
import time
import requests
import sqlite3

BASE_URL = "http://127.0.0.1:8000"
API_URL = f"{BASE_URL}/api/v1"
DB_PATH = os.path.join(os.path.dirname(__file__), "civicsight.db")

SAMPLE_DEFECT_IMG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ml", "samples", "sample_pothole_d40.jpg"))
SAMPLE_CLEAN_IMG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ml", "samples", "sample_road.jpg"))
CORRUPT_IMG = os.path.abspath(os.path.join(os.path.dirname(__file__), "corrupt_test.jpg"))

def step(title):
    print("\n" + "=" * 70)
    print(f"CHECK {title}")
    print("=" * 70)

def get_officer_headers():
    res = requests.post(f"{API_URL}/auth/login", json={"email": "officer@civicsight.gov", "password": "Password123!"})
    assert res.status_code == 200, f"Officer login failed: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_check_1_and_2():
    step("1 & 2: Citizen uploads real damage photo -> 201 Created (ML_PENDING) -> Transitions to ML_COMPLETE with detections")
    
    # 1. Citizen submits report with real defect image
    assert os.path.exists(SAMPLE_DEFECT_IMG), f"Sample defect image missing: {SAMPLE_DEFECT_IMG}"
    with open(SAMPLE_DEFECT_IMG, "rb") as f:
        files = {"image": ("pothole.jpg", f, "image/jpeg")}
        data = {
            "description": "Severe pothole on 4th street near crosswalk",
            "latitude": "37.7749",
            "longitude": "-122.4194",
            "address_text": "4th & Market St, SF",
            "damage_type": "D40"
        }
        t0 = time.time()
        res = requests.post(f"{API_URL}/reports", files=files, data=data)
        submission_time_ms = (time.time() - t0) * 1000
    
    assert res.status_code == 201, f"Expected 201 Created, got {res.status_code}: {res.text}"
    report = res.json()
    report_id = report["id"]
    print(f"[PASSED] Report #{report_id} created in {submission_time_ms:.1f}ms (non-blocking).")
    print(f"         Initial lifecycle status: {report.get('status')}")
    print(f"         Initial ML status:        {report.get('ml_status')}")
    assert report.get("status") == "submitted"
    assert report.get("ml_status") == "ML_PENDING", f"Expected ML_PENDING, got {report.get('ml_status')}"

    # 2. Poll until ML completes
    print("\nPolling /ml-status until background YOLO inference finishes...")
    ml_status = "ML_PENDING"
    status_data = None
    for attempt in range(25):
        time.sleep(0.5)
        st_res = requests.get(f"{API_URL}/reports/{report_id}/ml-status")
        if st_res.status_code == 200:
            status_data = st_res.json()
            ml_status = status_data["ml_status"]
            if ml_status != "ML_PENDING":
                break
    
    print(f"[PASSED] ML Transitioned to: {ml_status} in attempt {attempt+1}")
    assert ml_status == "ML_COMPLETE", f"Expected ML_COMPLETE, got {ml_status}"
    
    # Fetch full report details
    headers = get_officer_headers()
    det_res = requests.get(f"{API_URL}/reports/{report_id}", headers=headers)
    assert det_res.status_code == 200
    full_report = det_res.json()
    detections = full_report.get("detection_results", [])
    
    print(f"         Detections count:      {len(detections)}")
    print(f"         Model version:         {full_report.get('ml_model_version')}")
    print(f"         Inference time:        {full_report.get('ml_inference_time_ms')} ms")
    assert len(detections) > 0, "Expected at least 1 detection for real pothole image"
    for d in detections:
        print(f"         -> Defect: {d['detected_class']} ({d['class_name']}) | Conf: {d['confidence']:.3f} | BBox: {d['bbox_normalized']}")
        assert d["detected_class"] in ["D40", "D00", "D10", "D20"]
        assert d["confidence"] > 0.0
        assert len(d["bbox_normalized"]) == 4

    return report_id

def test_check_3():
    step("3: Citizen uploads clean road (no damage) -> Transitions to ML_NO_DETECTIONS (not an error)")
    
    assert os.path.exists(SAMPLE_CLEAN_IMG), f"Sample clean image missing: {SAMPLE_CLEAN_IMG}"
    with open(SAMPLE_CLEAN_IMG, "rb") as f:
        files = {"image": ("clean_road.jpg", f, "image/jpeg")}
        data = {
            "description": "Clear asphalt road surface for baseline verification",
            "latitude": "37.7833",
            "longitude": "-122.4167",
            "address_text": "Geary Blvd, SF",
            "damage_type": "OTHER"
        }
        res = requests.post(f"{API_URL}/reports", files=files, data=data)
    
    assert res.status_code == 201
    report = res.json()
    report_id = report["id"]
    print(f"[PASSED] Clean road report #{report_id} created successfully.")

    # Poll until ML finishes
    ml_status = "ML_PENDING"
    for _ in range(25):
        time.sleep(0.5)
        st_res = requests.get(f"{API_URL}/reports/{report_id}/ml-status")
        if st_res.status_code == 200:
            st = st_res.json()
            ml_status = st["ml_status"]
            if ml_status != "ML_PENDING":
                break

    print(f"[PASSED] Clean road ML status: {ml_status}")
    assert ml_status == "ML_NO_DETECTIONS", f"Expected ML_NO_DETECTIONS, got {ml_status}"
    
    headers = get_officer_headers()
    det_res = requests.get(f"{API_URL}/reports/{report_id}", headers=headers)
    full_report = det_res.json()
    assert full_report.get("ml_status") == "ML_NO_DETECTIONS"
    assert len(full_report.get("detection_results", [])) == 0
    assert full_report.get("ml_error_message") is None
    print("[PASSED] Confirmed 0 detections stored, error message is None, report is valid.")

    return report_id

def test_check_4():
    step("4: Deliberately break inference -> ML_FAILED handled gracefully, report valid")
    
    # Write a corrupt file with jpg extension (corrupted header/payload)
    with open(CORRUPT_IMG, "wb") as f:
        f.write(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00CORRUPT_DATA_NOT_A_VALID_IMAGE" * 20)

    try:
        with open(CORRUPT_IMG, "rb") as f:
            files = {"image": ("corrupted.jpg", f, "image/jpeg")}
            data = {
                "description": "Corrupted image payload stress test",
                "latitude": "37.7600",
                "longitude": "-122.4200",
                "address_text": "Mission St, SF",
                "damage_type": "OTHER"
            }
            res = requests.post(f"{API_URL}/reports", files=files, data=data)
        
        # Non-blocking submission: report must STILL be created successfully!
        assert res.status_code == 201, f"Report creation should succeed even with bad image, got {res.status_code}"
        report = res.json()
        report_id = report["id"]
        print(f"[PASSED] Report #{report_id} created with HTTP 201 despite corrupted image.")

        # Poll until ML fails gracefully
        ml_status = "ML_PENDING"
        for _ in range(25):
            time.sleep(0.5)
            st_res = requests.get(f"{API_URL}/reports/{report_id}/ml-status")
            if st_res.status_code == 200:
                st = st_res.json()
                ml_status = st["ml_status"]
                if ml_status != "ML_PENDING":
                    break

        print(f"[PASSED] Resulting ML status: {ml_status}")
        assert ml_status == "ML_FAILED", f"Expected ML_FAILED, got {ml_status}"
        
        headers = get_officer_headers()
        det_res = requests.get(f"{API_URL}/reports/{report_id}", headers=headers)
        full_report = det_res.json()
        print(f"         Recorded error message: {full_report.get('ml_error_message')}")
        print(f"         Report status:          {full_report.get('status')} (remains valid)")
        assert full_report.get("ml_status") == "ML_FAILED"
        assert full_report.get("status") == "submitted"
        assert full_report.get("ml_error_message") is not None
        assert len(full_report.get("detection_results", [])) == 0
        return report_id
    finally:
        if os.path.exists(CORRUPT_IMG):
            os.remove(CORRUPT_IMG)

def test_check_5(defect_report_id):
    step("5: Municipal Officer login -> inspects report -> verifies independently of AI results")
    
    # Login as municipal officer
    login_payload = {
        "email": "officer@civicsight.gov",
        "password": "Password123!"
    }
    login_res = requests.post(f"{API_URL}/auth/login", json=login_payload)
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token_data = login_res.json()
    token = token_data["access_token"]
    user = token_data["user"]
    user_display = user.get("full_name") or user.get("name")
    print(f"[PASSED] Authenticated as {user_display} (Role: {user['role']})")
    
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch report for inspection
    rep_res = requests.get(f"{API_URL}/reports/{defect_report_id}", headers=headers)
    assert rep_res.status_code == 200
    rep = rep_res.json()
    print(f"[PASSED] Officer inspected Report #{defect_report_id}")
    print(f"         AI Status:          {rep['ml_status']} ({len(rep['detection_results'])} detections)")
    print(f"         Officer Verification Status: {rep['status']}")

    # Officer performs official verification
    verify_res = requests.patch(
        f"{API_URL}/reports/{defect_report_id}/verify",
        headers=headers,
        json={"note": "Pothole confirmed by Municipal Officer Sarah Chen after onsite field review."}
    )
    assert verify_res.status_code == 200, f"Verification failed: {verify_res.text}"
    verified_report = verify_res.json()
    print(f"[PASSED] Report #{defect_report_id} status updated to: {verified_report['status']}")
    assert verified_report["status"] == "verified"
    
    # Ensure AI assessment was NOT overwritten or confused with municipal status
    assert verified_report["ml_status"] == "ML_COMPLETE"
    assert len(verified_report["detection_results"]) > 0
    print("[PASSED] AI Assessment and Municipal Verification remain completely separate and intact.")

def test_check_6(defect_report_id):
    step("6: Confirm detection results persist in SQLite database and are retrievable via GET /reports/{id}")
    
    # Query database directly
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, report_id, detected_class, class_name, confidence, bbox_xmin, bbox_ymin, bbox_xmax, bbox_ymax, model_version FROM detection_results WHERE report_id = ?", (defect_report_id,))
    db_rows = cursor.fetchall()
    conn.close()

    print(f"[PASSED] Direct SQLite Query found {len(db_rows)} row(s) in 'detection_results' table for report #{defect_report_id}:")
    for r in db_rows:
        print(f"         DB Row -> id={r[0]}, report_id={r[1]}, class={r[2]} ({r[3]}), conf={r[4]:.3f}, bbox=[{r[5]}, {r[6]}, {r[7]}, {r[8]}], model={r[9]}")
    assert len(db_rows) > 0, "Database row was not persisted!"

    # Verify API retrieval
    headers = get_officer_headers()
    api_res = requests.get(f"{API_URL}/reports/{defect_report_id}", headers=headers)
    assert api_res.status_code == 200
    data = api_res.json()
    assert len(data["detection_results"]) == len(db_rows)
    print(f"[PASSED] GET /reports/{defect_report_id} perfectly retrieved {len(data['detection_results'])} persisted detections.")

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("CIVICSIGHT WEEK 7 — PROTOTYPE VERIFICATION SUITE")
    print("=" * 70)
    
    defect_id = test_check_1_and_2()
    clean_id = test_check_3()
    corrupt_id = test_check_4()
    test_check_5(defect_id)
    test_check_6(defect_id)
    
    print("\n" + "=" * 70)
    print("ALL 6 PROTOTYPE INTEGRATION CHECKS COMPLETED AND VERIFIED 100%!")
    print("=" * 70)
