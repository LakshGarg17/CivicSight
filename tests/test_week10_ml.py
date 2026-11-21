"""CivicSight Week 10 Quality Gate — Phase 3 ML Testing, Failure Handling & Closure Independence.

Covers Phase 3.1, 3.3, 3.5, 3.6, 3.7, and 3.8.
(Held-out dataset metric evaluation & confusion matrix for Phase 3.2/3.4 runs via scripts/eval_week10_ml.py.)
"""

import io
import json
import os
import statistics
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from app.core.config import settings
from app.models.models import DetectionResult, Report, ReportStatus
from app.services.ml_service import process_report_image_ml
from app.services.priority import PriorityConfig
from ml.inference_adapter import (
    CLASS_METADATA,
    detect_road_damage,
    get_model_path,
    get_model_version,
    get_road_damage_detector,
)
from ml.src.preprocess import preprocess_report_image

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
TESTS_DIR = Path(__file__).resolve().parent


# =============================================================================
# PHASE 3.1: WEIGHTS, MODEL_PATH, MODEL.NAMES & CLASS MAPPING ALIGNMENT
# =============================================================================

def test_phase3_1_model_weights_and_class_alignment():
    mpath = get_model_path()
    assert mpath.is_file(), f"Weights missing at {mpath}"
    assert "clean_rdd2022_yolov8s" in str(mpath)
    assert str(get_model_version(mpath)) == "YOLOv8s-clean_rdd2022_yolov8s"

    model = get_road_damage_detector(mpath)
    assert model.task == "detect"
    assert model.names == {0: "D00", 1: "D10", 2: "D20", 3: "D40"}
    assert {k: v["code"] for k, v in CLASS_METADATA.items()} == model.names
    assert set(PriorityConfig().class_weights.keys()) == set(model.names.values())


# =============================================================================
# PHASE 3.3 & 3.7: REALISTIC CONDITIONS + CPU TIMING (MEAN & P95)
# =============================================================================

def test_phase3_3_and_3_7_realistic_conditions_and_timing():
    condition_files = [
        ("D00_longitudinal", "damage_d00.jpg"),
        ("D10_transverse", "damage_d10.jpg"),
        ("D20_alligator", "damage_d20.jpg"),
        ("D40_pothole_rdd", "damage_d40.jpg"),
        ("D40_pothole_phone", "sample_pothole_d40.jpg"),
        ("no_damage_road", "no_damage_road.jpg"),
        ("non_road_scene", "non_road.jpg"),
        ("blurry_dark_night", "blurry_dark.jpg"),
        ("exif_rotated_phone", "exif_gps_rotated.jpg"),
        ("very_large_4096x3072", "very_large.jpg"),
        ("tiny_16x16", "tiny.jpg"),
    ]
    results = []
    timings_ms = []

    # Warm-up 1 call so singleton model load isn't skewed into inference latency
    detect_road_damage(FIXTURES_DIR / "damage_d40.jpg", confidence_threshold=0.25)

    for label, fname in condition_files:
        fpath = FIXTURES_DIR / fname
        assert fpath.is_file(), f"Missing fixture {fpath}"
        pre = preprocess_report_image(fpath)
        out = detect_road_damage(pre, confidence_threshold=0.25, iou_threshold=0.45)
        assert out["success"] is True
        timings_ms.append(out["inference_time_ms"])
        # Verify every detection has valid class, confidence in [0,1], and valid bbox
        for det in out["detections"]:
            assert det["class_name"] in {"D00", "D10", "D20", "D40"}
            assert 0.0 <= det["confidence"] <= 1.0
            bx = det["bbox_normalized"]
            assert len(bx) == 4 and all(0.0 <= v <= 1.0 for v in bx)
            assert bx[2] >= bx[0] and bx[3] >= bx[1]
        results.append({
            "condition": label,
            "filename": fname,
            "num_detections": out["num_detections"],
            "classes": [d["class_name"] for d in out["detections"]],
            "max_conf": round(max((d["confidence"] for d in out["detections"]), default=0.0), 4),
            "inference_time_ms": round(out["inference_time_ms"], 2),
        })

    # Additional timing samples on real road images for accurate p95
    for _ in range(5):
        out = detect_road_damage(FIXTURES_DIR / "sample_pothole_d40.jpg", confidence_threshold=0.25)
        timings_ms.append(out["inference_time_ms"])

    sorted_t = sorted(timings_ms)
    mean_ms = statistics.mean(sorted_t)
    p95_idx = min(len(sorted_t) - 1, int(round(0.95 * (len(sorted_t) - 1))))
    p95_ms = sorted_t[p95_idx]

    summary = {
        "conditions": results,
        "timing_samples": len(sorted_t),
        "cpu_mean_ms": round(mean_ms, 2),
        "cpu_p95_ms": round(p95_ms, 2),
        "cpu_min_ms": round(sorted_t[0], 2),
        "cpu_max_ms": round(sorted_t[-1], 2),
    }
    (TESTS_DIR / "ml_conditions_and_timing.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    assert mean_ms < 5000.0, f"Inference unreasonably slow: {mean_ms:.1f}ms"


# =============================================================================
# PHASE 3.5: INFERENCE FAILURE HANDLING & EDGE CASES (ALL COLOR MODES + ERRORS)
# =============================================================================

def test_phase3_5_color_modes_and_cuda_cpu_fallback():
    # Grayscale, RGBA, CMYK, Palette, EXIF rotation all succeed cleanly without crash
    for fname in ("mode_grayscale.png", "mode_rgba.png", "mode_cmyk.jpg", "mode_palette.png", "exif_gps_rotated.jpg"):
        pre = preprocess_report_image(FIXTURES_DIR / fname)
        assert pre["preprocessed_np"].shape == (640, 640, 3)
        out = detect_road_damage(pre, confidence_threshold=0.25)
        assert out["success"] is True

    # Zero-size numpy array rejected cleanly
    with pytest.raises(ValueError):
        preprocess_report_image(np.zeros((0, 0, 3), dtype=np.uint8))

    # CUDA requested when unavailable falls back safely to CPU
    out_cuda = detect_road_damage(FIXTURES_DIR / "damage_d40.jpg", device="cuda")
    assert out_cuda["success"] is True


def test_phase3_5_pipeline_failure_states_never_block_reports(TestSessionLocal):
    db = TestSessionLocal()
    try:
        def _make_rep(img_url):
            r = Report(description="ML failure isolation test", latitude=37.77, longitude=-122.41, image_url=img_url, status=ReportStatus.SUBMITTED, ml_status="ML_PENDING")
            db.add(r)
            db.commit()
            db.refresh(r)
            return r

        # 1. Missing image file on disk
        r1 = _make_rep("/uploads/reports/nonexistent_file_xyz.jpg")
        res1 = process_report_image_ml(r1.id, db=db)
        assert res1["ml_status"] == "ML_FAILED"
        db.refresh(r1)
        assert r1.ml_status == "ML_FAILED" and r1.status == ReportStatus.SUBMITTED

        # 2. Corrupted JPEG bytes on disk
        r2 = _make_rep(str(FIXTURES_DIR / "corrupted.jpg"))
        res2 = process_report_image_ml(r2.id, db=db)
        assert res2["ml_status"] == "ML_FAILED"

        # 3. Non-image text bytes on disk
        r3 = _make_rep(str(FIXTURES_DIR / "fake_text.jpg"))
        res3 = process_report_image_ml(r3.id, db=db)
        assert res3["ml_status"] == "ML_FAILED"

        # 4. Empty 0-byte file on disk
        r4 = _make_rep(str(FIXTURES_DIR / "empty.jpg"))
        res4 = process_report_image_ml(r4.id, db=db)
        assert res4["ml_status"] == "ML_FAILED"

        # 5. Missing weights / invalid MODEL_PATH
        r5 = _make_rep(str(FIXTURES_DIR / "damage_d40.jpg"))
        with patch.dict(os.environ, {"MODEL_PATH": "ml/nonexistent_weights_999.pt"}):
            res5 = process_report_image_ml(r5.id, db=db)
        assert res5["ml_status"] == "ML_FAILED"

        # 6. Model load / OOM exception
        r6 = _make_rep(str(FIXTURES_DIR / "damage_d40.jpg"))
        with patch("ml.inference_adapter.get_road_damage_detector", side_effect=MemoryError("Simulated CUDA/CPU OOM")):
            res6 = process_report_image_ml(r6.id, db=db)
        assert res6["ml_status"] == "ML_FAILED"

        # 7. Inference runtime exception
        r7 = _make_rep(str(FIXTURES_DIR / "damage_d40.jpg"))
        with patch("ml.inference_adapter.detect_road_damage", side_effect=RuntimeError("Simulated inference crash")):
            res7 = process_report_image_ml(r7.id, db=db)
        assert res7["ml_status"] == "ML_FAILED"

        # 8. Inference timeout
        r8 = _make_rep(str(FIXTURES_DIR / "damage_d40.jpg"))
        def _slow(*args, **kwargs):
            time.sleep(0.3)
            return {"success": True, "detections": []}
        with patch("ml.inference_adapter.detect_road_damage", side_effect=_slow):
            res8 = process_report_image_ml(r8.id, db=db, timeout_seconds=0.05)
        assert res8["ml_status"] == "ML_FAILED"
        assert "timed out" in res8["error"].lower()
    finally:
        db.close()


# =============================================================================
# PHASE 3.6: FASTAPI INTEGRATION PARITY WITH DIRECT INFERENCE
# =============================================================================

def test_phase3_6_fastapi_stored_detections_match_direct_inference(client, seeded_accounts, TestSessionLocal):
    c1 = seeded_accounts["citizen1"]
    img_path = FIXTURES_DIR / "sample_pothole_d40.jpg"
    direct_pre = preprocess_report_image(img_path)
    direct_out = detect_road_damage(direct_pre, confidence_threshold=settings.PRIORITY_MIN_CONFIDENCE, iou_threshold=0.45)

    # Submit via real FastAPI multipart endpoint (let real background ML run!)
    res = client.post(
        "/api/v1/reports",
        data={"description": "ML integration parity test", "latitude": "37.791", "longitude": "-122.401"},
        files={"image": ("sample_pothole_d40.jpg", io.BytesIO(img_path.read_bytes()), "image/jpeg")},
        headers=c1["headers"],
    )
    assert res.status_code == 201
    rid = res.json()["id"]

    # Fetch stored detail
    detail = client.get(f"/api/v1/reports/{rid}", headers=c1["headers"]).json()
    expected_status = "ML_COMPLETE" if direct_out["num_detections"] > 0 else "ML_NO_DETECTIONS"
    assert detail["ml_status"] == expected_status
    assert detail["ml_model_version"] == str(direct_out["model_version"])
    assert len(detail["detection_results"]) == direct_out["num_detections"]
    if direct_out["num_detections"] > 0:
        direct_classes = sorted(d["class_name"] for d in direct_out["detections"])
        stored_classes = sorted(d["detected_class"] for d in detail["detection_results"])
        assert stored_classes == direct_classes
        direct_confs = sorted(round(d["confidence"], 4) for d in direct_out["detections"])
        stored_confs = sorted(round(d["confidence"], 4) for d in detail["detection_results"])
        assert stored_confs == direct_confs


# =============================================================================
# PHASE 3.8: CLOSURE INDEPENDENCE WITH DELIBERATELY BROKEN ML MODEL
# =============================================================================

def test_phase3_8_full_lifecycle_and_closure_with_broken_ml(client, seeded_accounts):
    c1 = seeded_accounts["citizen1"]
    off1 = seeded_accounts["officer1"]
    st1 = seeded_accounts["staff1"]
    img_bytes = (FIXTURES_DIR / "damage_d40.jpg").read_bytes()
    after_bytes = (FIXTURES_DIR / "after_repair.jpg").read_bytes()

    # Deliberately break the ML detector throughout report creation & full lifecycle
    with patch("ml.inference_adapter.get_road_damage_detector", side_effect=RuntimeError("DELIBERATELY BROKEN MODEL")):
        r_create = client.post(
            "/api/v1/reports",
            data={"description": "Broken ML closure independence test", "latitude": "37.795", "longitude": "-122.405"},
            files={"image": ("damage_d40.jpg", io.BytesIO(img_bytes), "image/jpeg")},
            headers=c1["headers"],
        )
        assert r_create.status_code == 201
        rid = r_create.json()["id"]

        # Confirm ML marked as ML_FAILED while report is alive & intact
        detail = client.get(f"/api/v1/reports/{rid}", headers=off1["headers"]).json()
        assert detail["ml_status"] == "ML_FAILED"
        assert detail["status"] == "submitted"
        assert detail["severity"] == "UNKNOWN"
        assert len(detail["priority_reasons"]) >= 1

        # Complete full municipal lifecycle: verify -> assign -> start -> upload AFTER -> submit -> final-verify APPROVED -> CLOSED
        assert client.post(f"/api/v1/reports/{rid}/verify", json={"note": "Manual inspector visual check"}, headers=off1["headers"]).status_code == 200
        assert client.post(f"/api/v1/reports/{rid}/assign", json={"staff_id": st1["id"]}, headers=off1["headers"]).status_code == 200
        assert client.post(f"/api/v1/reports/{rid}/repair/start", headers=st1["headers"]).status_code == 200
        assert client.post(
            f"/api/v1/reports/{rid}/repair/evidence",
            data={"kind": "AFTER", "note": "Repaired independently of ML"},
            files={"file": ("after_repair.jpg", io.BytesIO(after_bytes), "image/jpeg")},
            headers=st1["headers"],
        ).status_code == 201
        assert client.post(f"/api/v1/reports/{rid}/repair/submit", json={"note": "Ready for officer sign-off"}, headers=st1["headers"]).status_code == 200
        r_close = client.post(
            f"/api/v1/reports/{rid}/final-verify",
            json={"decision": "APPROVED", "note": "Verified on-site; ML failure did not impede closure"},
            headers=off1["headers"],
        )
        assert r_close.status_code == 200
        closed = r_close.json()
        assert closed["status"] == "closed"
        assert closed["ml_status"] == "ML_FAILED"
        assert closed["closed_at"] is not None
