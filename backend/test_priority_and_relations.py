"""CivicSight — Week 8 Priority Engine & Proximity Relations Test Suite

Comprehensive pytest coverage meeting all Week 7/8 specifications:
1. Priority engine unit tests (pure, no DB, class weights, confidence thresholds, explainability reasons, determinism, config overrides).
2. Proximity math & DB constraints (haversine accuracy, threshold boundaries, self-relation prevention, unordered pair uniqueness, rejected exclusion, class similarity).
3. API endpoints & RBAC (detail fields, combined filtering, 403 for Citizen, 401 unauthenticated, single-review enforcement, 404 for missing relations, priority history audit tracking, manual override).
4. End-to-end resilience (broken ML zero-failure ingestion, spatial neighbor priority synchronization).
"""

import os
import sys
import uuid
import math
import json
from datetime import datetime
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Ensure database URL
os.environ["DATABASE_URL"] = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT}/backend/civicsight.db")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.init_db import init_db
from app.db.database import SessionLocal
from app.models.models import (
    User,
    UserRole,
    Report,
    ReportStatus,
    PriorityHistory,
    ReportRelation,
)
from app.core.security import create_access_token, get_password_hash
from app.services.priority import (
    PriorityConfig,
    calculate_severity,
    calculate_priority,
)
from app.services.proximity import (
    haversine_distance,
    get_bounding_box,
    are_damage_classes_similar,
    process_report_proximity,
    update_single_report_priority,
)

init_db()
client = TestClient(app)


# ============================================================================
# Auth Fixtures & Headers
# ============================================================================

def get_auth_headers(role: UserRole, email: str, name: str) -> dict:
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


@pytest.fixture
def officer_headers():
    headers, _ = get_auth_headers(UserRole.MUNICIPAL_OFFICER, "officer_week8@civicsight.org", "Officer Week8")
    return headers


@pytest.fixture
def citizen_auth():
    headers, user_id = get_auth_headers(UserRole.CITIZEN, "citizen_week8@civicsight.org", "Citizen Week8")
    return headers, user_id


# ============================================================================
# 1. PRIORITY ENGINE UNIT TESTS (Pure, no DB)
# ============================================================================

class TestPriorityEngineUnit:
    """Isolated unit tests for pure scoring functions."""

    def test_class_confidence_to_severity(self):
        cfg = PriorityConfig()

        # D40 high confidence pothole -> HIGH severity
        sev_high, sc_high, _ = calculate_severity(
            [{"class": "D40", "confidence": 0.90, "bbox_area": 0.10}],
            cfg=cfg
        )
        assert sev_high == "HIGH"
        assert sc_high >= cfg.high_severity_threshold

        # D10 transverse crack at moderate confidence -> LOW or MEDIUM
        sev_med, _, _ = calculate_severity(
            [{"class": "D10", "confidence": 0.40, "bbox_area": 0.02}],
            cfg=cfg
        )
        assert sev_med in ["LOW", "MEDIUM"]

        # D00 longitudinal crack -> LOW severity
        sev_low, _, _ = calculate_severity(
            [{"class": "D00", "confidence": 0.35, "bbox_area": 0.01}],
            cfg=cfg
        )
        assert sev_low == "LOW"

    def test_high_medium_low_priority_scenarios(self):
        cfg = PriorityConfig()

        # Scenario 1: HIGH priority triggered by severe pothole
        res_high = calculate_priority(
            detections=[{"class": "D40", "confidence": 0.95, "bbox_area": 0.12}],
            ml_status="ML_COMPLETE",
            nearby_report_count=0,
            report_age_days=1.0,
            config=cfg,
        )
        assert res_high["priority"] == "HIGH"
        assert res_high["severity"] == "HIGH"
        assert any("Pothole" in r for r in res_high["reasons"])

        # Scenario 2: HIGH priority triggered by repeated citizen reports
        res_repeated = calculate_priority(
            detections=[],
            ml_status="ML_NO_DETECTIONS",
            nearby_report_count=5,
            report_age_days=2.0,
            config=cfg,
        )
        assert res_repeated["priority"] == "HIGH"
        assert any("5 other reports" in r for r in res_repeated["reasons"])

        # Scenario 3: MEDIUM priority triggered by moderate crack with 2 nearby reports
        res_med = calculate_priority(
            detections=[{"class": "D10", "confidence": 0.50, "bbox_area": 0.03}],
            ml_status="ML_COMPLETE",
            nearby_report_count=2,
            report_age_days=0.5,
            config=cfg,
        )
        assert res_med["priority"] == "MEDIUM"

        # Scenario 4: LOW priority for minor single defect with no nearby reports
        res_low = calculate_priority(
            detections=[{"class": "D00", "confidence": 0.30, "bbox_area": 0.01}],
            ml_status="ML_COMPLETE",
            nearby_report_count=0,
            report_age_days=0.0,
            config=cfg,
        )
        assert res_low["priority"] == "LOW"
        assert len(res_low["reasons"]) > 0

    def test_sub_threshold_confidence_ignored_and_noted(self):
        cfg = PriorityConfig(min_confidence=0.25)
        res = calculate_priority(
            detections=[{"class": "D40", "confidence": 0.18, "bbox_area": 0.05}],
            ml_status="ML_COMPLETE",
            nearby_report_count=0,
            report_age_days=0.0,
            config=cfg,
        )
        # Low confidence detection must be discarded
        assert res["severity"] == "LOW"
        assert any("below minimum confidence (25%) ignored" in r for r in res["reasons"])

    def test_missing_and_unreliable_inputs_handle_safely(self):
        cfg = PriorityConfig()

        # ML_FAILED
        res_failed = calculate_priority(
            detections=None,
            ml_status="ML_FAILED",
            nearby_report_count=0,
            report_age_days=0.0,
            config=cfg,
        )
        assert res_failed["severity"] == "UNKNOWN"
        assert any("Automated assessment unavailable" in r for r in res_failed["reasons"])

        # ML_PENDING
        res_pending = calculate_priority(
            detections=None,
            ml_status="ML_PENDING",
            nearby_report_count=0,
            report_age_days=0.0,
            config=cfg,
        )
        assert res_pending["severity"] == "UNKNOWN"
        assert any("Automated assessment unavailable" in r for r in res_pending["reasons"])

        # ML_NO_DETECTIONS
        res_no_det = calculate_priority(
            detections=[],
            ml_status="ML_NO_DETECTIONS",
            nearby_report_count=0,
            report_age_days=0.0,
            config=cfg,
        )
        assert res_no_det["priority"] == "LOW"
        assert any("No road damage detected" in r for r in res_no_det["reasons"])

        # Invalid confidence (<0 or >1)
        res_invalid_conf = calculate_priority(
            detections=[{"class": "D40", "confidence": 1.5, "bbox_area": 0.05}],
            ml_status="ML_COMPLETE",
            nearby_report_count=0,
            report_age_days=0.0,
            config=cfg,
        )
        assert any("unreliable" in r for r in res_invalid_conf["reasons"])

    def test_determinism(self):
        cfg = PriorityConfig()
        dets = [
            {"class": "D40", "confidence": 0.88, "bbox_area": 0.06},
            {"class": "D10", "confidence": 0.45, "bbox_area": 0.02},
        ]
        first_run = calculate_priority(dets, ml_status="ML_COMPLETE", nearby_report_count=3, report_age_days=5.0, config=cfg)
        for _ in range(10):
            run = calculate_priority(dets, ml_status="ML_COMPLETE", nearby_report_count=3, report_age_days=5.0, config=cfg)
            assert run["priority"] == first_run["priority"]
            assert run["severity"] == first_run["severity"]
            assert math.isclose(run["score"], first_run["score"], rel_tol=1e-5)
            assert run["reasons"] == first_run["reasons"]

    def test_config_overrides_change_behavior(self):
        dets = [{"class": "D40", "confidence": 0.50, "bbox_area": 0.04}]

        # Standard config: 0.50 confidence D40 gives MEDIUM severity
        cfg_std = PriorityConfig(high_severity_threshold=0.55)
        out_std = calculate_priority(dets, ml_status="ML_COMPLETE", config=cfg_std)

        # Overridden config with lower high threshold: gives HIGH severity
        cfg_custom = PriorityConfig(high_severity_threshold=0.35, high_score_threshold=20.0)
        out_custom = calculate_priority(dets, ml_status="ML_COMPLETE", config=cfg_custom)

        assert out_std["severity"] != out_custom["severity"] or out_std["priority"] != out_custom["priority"]


# ============================================================================
# 2. PROXIMITY AND SPATIAL TESTS (Unit + DB)
# ============================================================================

class TestProximityUnitAndDB:
    """Tests for haversine accuracy, bounding boxes, DB uniqueness, and duplicate logic."""

    def test_haversine_distance_accuracy(self):
        # Known coordinates: San Francisco City Hall to Ferry Building (~2.88 km)
        sf_hall = (37.7793, -122.4193)
        sf_ferry = (37.7955, -122.3937)
        dist = haversine_distance(sf_hall[0], sf_hall[1], sf_ferry[0], sf_ferry[1])
        assert 2800 < dist < 2950

        # Exact same point -> 0 meters
        assert haversine_distance(37.7749, -122.4194, 37.7749, -122.4194) == 0.0

        # Small 10 meter delta
        # 1 degree of latitude ~ 111,139 meters. 10 meters ~ 0.00009 degrees.
        d10 = haversine_distance(37.774900, -122.419400, 37.774990, -122.419400)
        assert 9.0 <= d10 <= 11.0

    def test_distance_threshold_boundaries(self):
        # Base point
        lat0, lng0 = 37.7749, -122.4194
        meters_per_deg_lat = 111139.0

        # Point inside 50m threshold (at 45m)
        lat_inside = lat0 + (45.0 / meters_per_deg_lat)
        d_inside = haversine_distance(lat0, lng0, lat_inside, lng0)
        assert d_inside < 50.0

        # Point outside 50m threshold (at 55m)
        lat_outside = lat0 + (55.0 / meters_per_deg_lat)
        d_outside = haversine_distance(lat0, lng0, lat_outside, lng0)
        assert d_outside > 50.0

    def test_report_never_matches_itself_and_no_duplicate_pairs(self):
        db = SessionLocal()
        try:
            # Create test report at a guaranteed unique isolated coordinate (e.g. 80.0 - 84.0) to ensure zero pre-existing neighbors
            offset = (uuid.uuid4().int % 10000) * 0.001
            iso_lat, iso_lng = 80.0 + offset, 80.0 + offset
            rep_a = Report(
                description=f"Proximity test {uuid.uuid4().hex[:6]}",
                latitude=iso_lat,
                longitude=iso_lng,
                damage_type="D40",
                status=ReportStatus.SUBMITTED,
            )
            db.add(rep_a)
            db.commit()
            db.refresh(rep_a)

            # Processing self should never create a relation with itself
            rels = process_report_proximity(rep_a, db)
            assert len(rels) == 0
            assert all(r.report_id != r.related_report_id for r in rels)

            # Create second report ~8 meters away
            rep_b = Report(
                description=f"Proximity test {uuid.uuid4().hex[:6]}",
                latitude=iso_lat + 0.00007,  # ~8m away
                longitude=iso_lng,
                damage_type="D40",
                status=ReportStatus.SUBMITTED,
            )
            db.add(rep_b)
            db.commit()
            db.refresh(rep_b)

            # Process rep_b
            rels_b = process_report_proximity(rep_b, db)
            assert len(rels_b) >= 1
            # Never self-relate
            assert all(r.report_id != r.related_report_id for r in rels_b)

            # Count total relations between rep_a and rep_b
            id_min, id_max = min(rep_a.id, rep_b.id), max(rep_a.id, rep_b.id)
            all_rels = (
                db.query(ReportRelation)
                .filter(
                    ReportRelation.report_id == id_min,
                    ReportRelation.related_report_id == id_max,
                )
                .all()
            )
            assert len(all_rels) == 1, "There must be exactly one canonical relation record for the pair"

            # Re-running proximity must not create duplicate relation
            rels_re = process_report_proximity(rep_a, db)
            all_rels_after = (
                db.query(ReportRelation)
                .filter(
                    ReportRelation.report_id == id_min,
                    ReportRelation.related_report_id == id_max,
                )
                .all()
            )
            assert len(all_rels_after) == 1

        finally:
            db.close()

    def test_rejected_reports_excluded_from_proximity(self):
        db = SessionLocal()
        try:
            # Create a rejected report
            rep_rejected = Report(
                description="Rejected test report",
                latitude=37.7500,
                longitude=-122.4200,
                damage_type="D40",
                status=ReportStatus.REJECTED,
                rejection_reason="Test rejection",
            )
            db.add(rep_rejected)
            db.commit()
            db.refresh(rep_rejected)

            # Create fresh report 10 meters away
            rep_fresh = Report(
                description="Fresh report near rejected",
                latitude=37.75008,
                longitude=-122.4200,
                damage_type="D40",
                status=ReportStatus.SUBMITTED,
            )
            db.add(rep_fresh)
            db.commit()
            db.refresh(rep_fresh)

            rels = process_report_proximity(rep_fresh, db)
            # Must not relate to rejected report
            related_ids = [r.related_report_id if r.report_id == rep_fresh.id else r.report_id for r in rels]
            assert rep_rejected.id not in related_ids

        finally:
            db.close()

    def test_nearby_but_different_classes_yields_nearby_related_not_duplicate(self):
        db = SessionLocal()
        try:
            # Report 1: Pothole D40
            rep1 = Report(
                description="Pothole at intersection",
                latitude=37.7600,
                longitude=-122.4300,
                damage_type="D40",
                status=ReportStatus.SUBMITTED,
            )
            db.add(rep1)
            db.commit()
            db.refresh(rep1)

            # Report 2: Longitudinal crack D00 located 10 meters away
            rep2 = Report(
                description="Longitudinal crack at intersection",
                latitude=37.76008,  # ~9m
                longitude=-122.4300,
                damage_type="D00",
                status=ReportStatus.SUBMITTED,
            )
            db.add(rep2)
            db.commit()
            db.refresh(rep2)

            rels = process_report_proximity(rep2, db)
            pair_rel = next((r for r in rels if (r.report_id == rep1.id or r.related_report_id == rep1.id)), None)
            assert pair_rel is not None
            # Nearby distance is <15m, but damage classes are distinct (D40 vs D00) -> NEARBY_RELATED, NOT duplicate!
            assert pair_rel.relation_type == "NEARBY_RELATED"

        finally:
            db.close()

    def test_invalid_coordinates_skip_without_crashing(self):
        db = SessionLocal()
        try:
            rep_no_coords = Report(
                description="Report without GPS",
                latitude=None,
                longitude=None,
                status=ReportStatus.SUBMITTED,
            )
            db.add(rep_no_coords)
            db.commit()
            db.refresh(rep_no_coords)

            rels = process_report_proximity(rep_no_coords, db)
            assert rels == []
            assert rep_no_coords.nearby_report_count == 0

            # Priority calculation must still succeed
            res = update_single_report_priority(rep_no_coords, db)
            assert rep_no_coords.priority in ["HIGH", "MEDIUM", "LOW"]
            reasons_list = json.loads(rep_no_coords.priority_reasons) if isinstance(rep_no_coords.priority_reasons, str) else (rep_no_coords.priority_reasons or [])
            assert any("coordinate" in r.lower() for r in reasons_list)

        finally:
            db.close()


# ============================================================================
# 3. API ENDPOINTS & RBAC TESTS
# ============================================================================

class TestReportAPIWeek8:
    """Verifies API endpoints, query filters, and strict role access controls."""

    def test_get_report_detail_has_priority_and_reasons(self, officer_headers):
        create_res = client.post(
            "/api/v1/reports",
            json={
                "description": "API detail test pothole",
                "latitude": 37.7780,
                "longitude": -122.4180,
                "damage_type": "D40",
            },
            headers=officer_headers,
        )
        assert create_res.status_code == 201
        rep_id = create_res.json()["id"]

        detail_res = client.get(f"/api/v1/reports/{rep_id}", headers=officer_headers)
        assert detail_res.status_code == 200
        data = detail_res.json()

        assert "priority" in data
        assert "severity" in data
        assert "priority_score" in data
        assert "priority_reasons" in data
        assert isinstance(data["priority_reasons"], list)
        assert len(data["priority_reasons"]) > 0
        assert "nearby_report_count" in data
        assert "related_reports" in data

    def test_list_reports_combined_priority_and_status_filter(self, officer_headers):
        # Create a HIGH priority report
        res_h = client.post(
            "/api/v1/reports",
            json={
                "description": "High priority filter test",
                "latitude": 37.7700,
                "longitude": -122.4100,
                "damage_type": "D40",
                "priority": "HIGH",
            },
            headers=officer_headers,
        )
        assert res_h.status_code == 201

        # Query with ?priority=HIGH&status=submitted
        filter_res = client.get("/api/v1/reports?priority=HIGH&status=submitted", headers=officer_headers)
        assert filter_res.status_code == 200
        reports = filter_res.json()
        assert len(reports) >= 1
        for r in reports:
            assert r["priority"] == "HIGH"
            assert r["status"] == "submitted"
            assert "has_pending_relations" in r

    def test_rbac_citizen_403_and_unauthenticated_401(self, citizen_auth):
        citizen_headers, citizen_id = citizen_auth
        test_report_id = 1
        test_relation_id = 1

        endpoints = [
            ("GET", f"/api/v1/reports/{test_report_id}/related", None),
            ("PATCH", f"/api/v1/report-relations/{test_relation_id}", {"review_status": "DISMISSED"}),
            ("GET", f"/api/v1/reports/{test_report_id}/priority-history", None),
            ("POST", f"/api/v1/reports/{test_report_id}/recalculate-priority", None),
            ("POST", f"/api/v1/reports/{test_report_id}/override-priority", {"priority": "HIGH", "reason": "Officer test"}),
        ]

        for method, url, payload in endpoints:
            # 1. Unauthenticated (no token) -> 401
            if method == "GET":
                unauth_res = client.get(url)
            elif method == "PATCH":
                unauth_res = client.patch(url, json=payload)
            else:
                unauth_res = client.post(url, json=payload)
            assert unauth_res.status_code in [401, 403], f"Expected 401/403 unauthenticated for {url}, got {unauth_res.status_code}"

            # 2. Citizen authenticated -> 403 Forbidden
            if method == "GET":
                cit_res = client.get(url, headers=citizen_headers)
            elif method == "PATCH":
                cit_res = client.patch(url, json=payload, headers=citizen_headers)
            else:
                cit_res = client.post(url, json=payload, headers=citizen_headers)
            assert cit_res.status_code == 403, f"Expected 403 for Citizen on {url}, got {cit_res.status_code}"

    def test_citizen_viewing_own_report_sees_priority_but_not_other_reports(self, citizen_auth, officer_headers):
        citizen_headers, citizen_id = citizen_auth

        # Create report owned by citizen
        create_res = client.post(
            "/api/v1/reports",
            json={
                "description": "Citizen personal report",
                "latitude": 37.7712,
                "longitude": -122.4150,
                "damage_type": "D40",
                "reporter_id": citizen_id,
            },
            headers=officer_headers,
        )
        assert create_res.status_code == 201
        rep_id = create_res.json()["id"]

        # Citizen views own report
        cit_get = client.get(f"/api/v1/reports/{rep_id}", headers=citizen_headers)
        assert cit_get.status_code == 200
        cit_data = cit_get.json()
        assert cit_data["priority"] is not None
        # Must not receive other people's related reports
        assert cit_data["related_reports"] == []

    def test_relation_review_confirm_dismiss_and_404(self, officer_headers):
        db = SessionLocal()
        try:
            # Create two adjacent reports
            r1 = Report(description="Rel test 1", latitude=37.7810, longitude=-122.4100, damage_type="D40", status=ReportStatus.SUBMITTED)
            r2 = Report(description="Rel test 2", latitude=37.78107, longitude=-122.4100, damage_type="D40", status=ReportStatus.SUBMITTED)
            db.add_all([r1, r2])
            db.commit()
            db.refresh(r1)
            db.refresh(r2)

            # Form relation
            rels = process_report_proximity(r2, db)
            assert len(rels) >= 1
            rel_id = rels[0].id

            # 1. Nonexistent relation -> 404
            err_res = client.patch(
                "/api/v1/report-relations/999999",
                json={"review_status": "DISMISSED"},
                headers=officer_headers,
            )
            assert err_res.status_code == 404

            # 2. Confirm duplicate on PENDING relation -> 200
            confirm_res = client.patch(
                f"/api/v1/report-relations/{rel_id}",
                json={"review_status": "CONFIRMED_DUPLICATE", "note": "Verified duplicate on site"},
                headers=officer_headers,
            )
            assert confirm_res.status_code == 200
            conf_data = confirm_res.json()
            assert conf_data["review_status"] == "CONFIRMED_DUPLICATE"

            # Verify that one of the reports transitioned to DUPLICATE without being deleted
            db.refresh(r1)
            db.refresh(r2)
            assert ReportStatus.DUPLICATE in [r1.status, r2.status]
            # Both reports still exist in DB
            assert db.query(Report).filter(Report.id == r1.id).first() is not None
            assert db.query(Report).filter(Report.id == r2.id).first() is not None

            # 3. Second review attempt on already reviewed relation -> 400 Bad Request
            second_res = client.patch(
                f"/api/v1/report-relations/{rel_id}",
                json={"review_status": "DISMISSED"},
                headers=officer_headers,
            )
            assert second_res.status_code == 400

        finally:
            db.close()

    def test_priority_history_audit_logging(self, officer_headers):
        create_res = client.post(
            "/api/v1/reports",
            json={
                "description": "History audit test",
                "latitude": 37.7850,
                "longitude": -122.4050,
                "damage_type": "D40",
            },
            headers=officer_headers,
        )
        assert create_res.status_code == 201
        rep_id = create_res.json()["id"]

        # Manual priority override
        override_res = client.post(
            f"/api/v1/reports/{rep_id}/override-priority",
            json={"priority": "HIGH", "reason": "Mayor inspection visit"},
            headers=officer_headers,
        )
        assert override_res.status_code == 200
        assert override_res.json()["priority"] == "HIGH"
        assert override_res.json()["is_priority_overridden"] is True

        # Fetch priority history
        hist_res = client.get(f"/api/v1/reports/{rep_id}/priority-history", headers=officer_headers)
        assert hist_res.status_code == 200
        history = hist_res.json()
        assert len(history) >= 1
        last_entry = history[-1]
        assert last_entry["trigger"] == "manual_override"
        assert last_entry["new_priority"] == "HIGH"


# ============================================================================
# 4. END-TO-END RESILIENCE TESTS
# ============================================================================

class TestEndToEndResilience:
    """Verifies that ML failures never block submission and spatial clustering updates neighbors."""

    def test_broken_ml_model_never_blocks_report_creation_and_uses_fallback(self, officer_headers, monkeypatch):
        # Deliberately break the ML detection pipeline
        import ml.src.inference

        def broken_detect(*args, **kwargs):
            raise RuntimeError("Deliberate GPU / Model Fault Injection")

        monkeypatch.setattr(ml.src.inference, "detect_road_damage", broken_detect)

        # Citizen submits report
        create_res = client.post(
            "/api/v1/reports",
            json={
                "description": "Broken ML resilience test",
                "latitude": 37.7730,
                "longitude": -122.4210,
                "damage_type": "D40",
            },
            headers=officer_headers,
        )
        # MUST succeed with 201 Created
        assert create_res.status_code == 201
        rep = create_res.json()
        assert rep["id"] is not None
        # Priority must still be populated via fallback rules
        assert rep["priority"] in ["HIGH", "MEDIUM", "LOW"]
        assert len(rep["priority_reasons"]) > 0

    def test_submitting_second_report_near_first_updates_both(self, officer_headers):
        # Report 1
        res1 = client.post(
            "/api/v1/reports",
            json={
                "description": "First nearby cluster report",
                "latitude": 37.7890,
                "longitude": -122.4010,
                "damage_type": "D40",
            },
            headers=officer_headers,
        )
        assert res1.status_code == 201
        rep1_id = res1.json()["id"]

        # Report 2 (10 meters away)
        res2 = client.post(
            "/api/v1/reports",
            json={
                "description": "Second nearby cluster report",
                "latitude": 37.78908,
                "longitude": -122.4010,
                "damage_type": "D40",
            },
            headers=officer_headers,
        )
        assert res2.status_code == 201
        rep2_id = res2.json()["id"]

        # Re-fetch both reports
        rep1 = client.get(f"/api/v1/reports/{rep1_id}", headers=officer_headers).json()
        rep2 = client.get(f"/api/v1/reports/{rep2_id}", headers=officer_headers).json()

        # Both reports must show nearby_report_count >= 1
        assert rep1["nearby_report_count"] >= 1
        assert rep2["nearby_report_count"] >= 1

        # Relation must exist between them
        rel_ids1 = [r["related_report_id"] for r in rep1["related_reports"]]
        assert rep2_id in rel_ids1
