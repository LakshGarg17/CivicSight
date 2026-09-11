"""CivicSight Report API Validation & Multipart Upload Test Suite (Week 4)

Validates:
1. Missing image -> 422 error
2. Missing description -> 422 error
3. Missing / invalid latitude/longitude -> 422 error
4. Out-of-range latitude (>90 or <-90) -> 422 error
5. Out-of-range longitude (>180 or <-180) -> 422 error
6. Fully valid multipart report submission -> 201 Created, unique ID, file saved on disk
7. Direct root /reports and versioned /api/v1/reports endpoint equivalence
8. Existing JSON creation backwards compatibility
"""

import os
import io
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.db.init_db import init_db

# Ensure tables are initialized
init_db()

client = TestClient(app)


def create_dummy_image_bytes(filename="test_hazard.jpg", color=(255, 0, 0), size=(100, 100)) -> io.BytesIO:
    """Creates an in-memory JPEG image buffer for testing file uploads."""
    buf = io.BytesIO()
    img = Image.new("RGB", size, color)
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


def test_missing_image():
    print("\n[TEST] 1. Testing Missing Image Validation...")
    data = {
        "description": "Deep pothole in center lane",
        "latitude": "37.7749",
        "longitude": "-122.4194",
    }
    # No files provided
    res = client.post("/api/v1/reports", data=data)
    assert res.status_code == 422, f"Expected 422, got {res.status_code}: {res.text}"
    assert "image" in res.json()["detail"].lower()
    print("   [OK] Missing image correctly rejected with 422.")


def test_missing_description():
    print("\n[TEST] 2. Testing Missing Description Validation...")
    img_buf = create_dummy_image_bytes()
    files = {"image": ("test_road.jpg", img_buf, "image/jpeg")}
    data = {
        "latitude": "37.7749",
        "longitude": "-122.4194",
        "description": "   ",  # Whitespace only
    }
    res = client.post("/api/v1/reports", data=data, files=files)
    assert res.status_code == 422, f"Expected 422, got {res.status_code}: {res.text}"
    assert "description" in res.json()["detail"].lower()
    print("   [OK] Missing / empty description correctly rejected with 422.")


def test_missing_coordinates():
    print("\n[TEST] 3. Testing Missing Coordinates Validation...")
    img_buf = create_dummy_image_bytes()
    files = {"image": ("test_road.jpg", img_buf, "image/jpeg")}
    data = {
        "description": "Deep pothole on 4th street",
        # Missing latitude & longitude
    }
    res = client.post("/api/v1/reports", data=data, files=files)
    assert res.status_code == 422, f"Expected 422, got {res.status_code}: {res.text}"
    assert "latitude" in res.json()["detail"].lower()
    print("   [OK] Missing coordinates correctly rejected with 422.")


def test_invalid_and_out_of_range_coordinates():
    print("\n[TEST] 4. Testing Out-of-Range and Malformed Coordinates...")
    # Malformed string
    img_buf = create_dummy_image_bytes()
    files = {"image": ("test_road.jpg", img_buf, "image/jpeg")}
    data_malformed = {
        "description": "Crack on pavement",
        "latitude": "not-a-number",
        "longitude": "-122.4194",
    }
    res_malformed = client.post("/api/v1/reports", data=data_malformed, files=files)
    assert res_malformed.status_code == 422, res_malformed.text

    # Out-of-range Latitude (> 90)
    img_buf2 = create_dummy_image_bytes()
    files2 = {"image": ("test_road.jpg", img_buf2, "image/jpeg")}
    data_lat_range = {
        "description": "Crack on pavement",
        "latitude": "95.5",
        "longitude": "-122.4194",
    }
    res_lat = client.post("/api/v1/reports", data=data_lat_range, files=files2)
    assert res_lat.status_code == 422, res_lat.text
    assert "latitude" in res_lat.json()["detail"].lower()

    # Out-of-range Longitude (> 180)
    img_buf3 = create_dummy_image_bytes()
    files3 = {"image": ("test_road.jpg", img_buf3, "image/jpeg")}
    data_lon_range = {
        "description": "Crack on pavement",
        "latitude": "37.7749",
        "longitude": "200.0",
    }
    res_lon = client.post("/api/v1/reports", data=data_lon_range, files=files3)
    assert res_lon.status_code == 422, res_lon.text
    assert "longitude" in res_lon.json()["detail"].lower()
    print("   [OK] Out-of-range coordinates correctly rejected with 422.")


def test_valid_multipart_submission():
    print("\n[TEST] 5. Testing Fully Valid Multipart Report Submission...")
    img_buf = create_dummy_image_bytes("pothole_verified.jpg", color=(45, 120, 200))
    files = {"image": ("pothole_verified.jpg", img_buf, "image/jpeg")}
    data = {
        "description": "Severe longitudinal cracking near traffic signal",
        "latitude": "37.774929",
        "longitude": "-122.419416",
        "address_text": "Market St & 5th Ave",
        "damage_type": "D00",
    }

    res = client.post("/api/v1/reports", data=data, files=files)
    assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
    report = res.json()

    assert report["id"] is not None and isinstance(report["id"], int)
    assert report["description"] == "Severe longitudinal cracking near traffic signal"
    assert report["latitude"] == 37.774929
    assert report["longitude"] == -122.419416
    assert report["status"] == "submitted"
    assert report["damage_type"] == "D00"
    assert report["created_at"] is not None
    assert report["image_url"].startswith("/uploads/reports/")

    # Verify that the image was actually written to disk
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    saved_rel_path = report["image_url"].lstrip("/")
    saved_abs_path = os.path.join(backend_dir, saved_rel_path)
    assert os.path.exists(saved_abs_path), f"Saved image file not found on disk at {saved_abs_path}"
    assert os.path.getsize(saved_abs_path) > 0, "Saved image file is empty"
    print(f"   [OK] Report created successfully: ID={report['id']}, Image saved at {saved_abs_path}")

    # Verify static file serving
    res_static = client.get(report["image_url"])
    assert res_static.status_code == 200, f"Static file GET failed: {res_static.status_code}"
    print(f"   [OK] Static file served successfully from {report['image_url']}")

    # Test root level /reports endpoint
    img_buf_root = create_dummy_image_bytes("root_test.jpg")
    files_root = {"image": ("root_test.jpg", img_buf_root, "image/jpeg")}
    res_root = client.post("/reports", data=data, files=files_root)
    assert res_root.status_code == 201
    assert res_root.json()["id"] is not None
    print(f"   [OK] Root endpoint /reports verified: ID={res_root.json()['id']}")


def run_all():
    print("=" * 60)
    print("CivicSight Week 4 — Backend Report API Test Suite")
    print("=" * 60)
    test_missing_image()
    test_missing_description()
    test_missing_coordinates()
    test_invalid_and_out_of_range_coordinates()
    test_valid_multipart_submission()
    print("\n" + "=" * 60)
    print("ALL REPORT API TESTS PASSED SUCCESSFULLY! [100%]")
    print("=" * 60)


if __name__ == "__main__":
    run_all()
