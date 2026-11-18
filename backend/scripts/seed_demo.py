"""CivicSight Demo Seed & Reset Script (Week 10 Quality Gate).

Creates a clean, realistic, privacy-safe demonstration dataset with:
- 7 throwaway role accounts (password: Password123!)
- 7 sample road hazard reports spanning every canonical lifecycle state:
  submitted, verified, assigned, under_repair, repair_evidence_submitted,
  closed (with Before/After evidence), and rejected (with audit reason)
- A nearby duplicate pair (POTENTIAL_DUPLICATE) for spatial deduplication demo
- Matching DetectionResult, ReportStatusHistory, PriorityHistory, and RepairEvidence rows

Usage:
    # Seed if empty (idempotent for accounts):
    python backend/scripts/seed_demo.py

    # Full reset + clean demo seed (recommended right before a live demo):
    python backend/scripts/seed_demo.py --reset
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
SAMPLES_DIR = PROJECT_ROOT / "ml" / "samples"
REPORTS_UPLOAD_DIR = BACKEND_DIR / "uploads" / "reports"
EVIDENCE_UPLOAD_DIR = BACKEND_DIR / "uploads" / "evidence"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.security import get_password_hash
from app.db.database import SessionLocal, engine
from app.db.init_db import init_db
from app.models.models import (
    Assignment,
    DetectionResult,
    EvidenceKind,
    FinalVerification,
    PriorityHistory,
    RepairEvidence,
    Report,
    ReportRelation,
    ReportStatusHistory,
    User,
    UserRole,
)

DEMO_PASSWORD = "Password123!"
MODEL_VERSION = "YOLOv8s-clean_rdd2022_yolov8s"

DEMO_USERS = [
    ("Demo Citizen One", "citizen1@civicsight.org", UserRole.CITIZEN),
    ("Demo Citizen Two", "citizen2@civicsight.org", UserRole.CITIZEN),
    ("Demo Officer One", "officer1@civicsight.gov", UserRole.MUNICIPAL_OFFICER),
    ("Demo Officer Two", "officer2@civicsight.gov", UserRole.MUNICIPAL_OFFICER),
    ("Demo Maintenance Crew One", "staff1@civicsight.gov", UserRole.MAINTENANCE_STAFF),
    ("Demo Maintenance Crew Two", "staff2@civicsight.gov", UserRole.MAINTENANCE_STAFF),
    ("Demo System Admin", "admin1@civicsight.gov", UserRole.ADMIN),
]


def _pick_demo_image(preferred_fixture: str, dest_name: str, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / dest_name
    candidates = [
        FIXTURES_DIR / preferred_fixture,
        SAMPLES_DIR / "pothole_demo.jpg",
    ]
    for src in candidates:
        if src.is_file():
            shutil.copy2(src, dest)
            return dest
    raise FileNotFoundError(f"Could not locate demo fixture {preferred_fixture} in {FIXTURES_DIR}")


def seed_demo(reset: bool = False) -> dict:
    init_db(target_engine=engine, seed_users=False)
    db = SessionLocal()
    try:
        if reset:
            db.query(FinalVerification).delete()
            db.query(Assignment).delete()
            db.query(RepairEvidence).delete()
            db.query(ReportRelation).delete()
            db.query(PriorityHistory).delete()
            db.query(ReportStatusHistory).delete()
            db.query(DetectionResult).delete()
            db.query(Report).delete()
            db.commit()

        # Upsert all 7 demo users
        users_by_email: dict[str, User] = {}
        pw_hash = get_password_hash(DEMO_PASSWORD)
        for name, email, role in DEMO_USERS:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                user = User(name=name, email=email, role=role, hashed_password=pw_hash, is_active=True)
                db.add(user)
                db.flush()
            else:
                user.name = name
                user.role = role
                user.is_active = True
                if reset:
                    user.hashed_password = pw_hash
            users_by_email[email] = user
        db.commit()

        existing_reports = db.query(Report).count()
        if existing_reports > 0 and not reset:
            return {
                "action": "skipped_reports_already_exist",
                "users_ready": len(users_by_email),
                "reports_count": existing_reports,
            }

        now = datetime.now(timezone.utc)
        cit1 = users_by_email["citizen1@civicsight.org"]
        cit2 = users_by_email["citizen2@civicsight.org"]
        off1 = users_by_email["officer1@civicsight.gov"]
        off2 = users_by_email["officer2@civicsight.gov"]
        st1 = users_by_email["staff1@civicsight.gov"]
        st2 = users_by_email["staff2@civicsight.gov"]

        # Copy demo images into upload directories
        img_d40 = _pick_demo_image("sample_pothole_d40.jpg", "demo_d40_pothole.jpg", REPORTS_UPLOAD_DIR)
        img_d20 = _pick_demo_image("damage_d20.jpg", "demo_d20_alligator.jpg", REPORTS_UPLOAD_DIR)
        img_d00 = _pick_demo_image("damage_d00.jpg", "demo_d00_longitudinal.jpg", REPORTS_UPLOAD_DIR)
        img_d10 = _pick_demo_image("damage_d10.jpg", "demo_d10_transverse.jpg", REPORTS_UPLOAD_DIR)
        img_non = _pick_demo_image("non_road.jpg", "demo_non_road.jpg", REPORTS_UPLOAD_DIR)

        reports_spec = [
            {
                "description": "Deep pothole near bus stop crosswalk causing vehicles to swerve.",
                "latitude": 37.77490,
                "longitude": -122.41940,
                "address_text": "Market St & 5th St",
                "damage_type": "D40",
                "status": "submitted",
                "priority": "HIGH",
                "severity": "HIGH",
                "priority_score": 0.91,
                "priority_reasons": json.dumps(["Detected D40 (Pothole) with high confidence", "Corroborated by 1 nearby active report"]),
                "nearby_report_count": 1,
                "image_url": f"/uploads/reports/{img_d40.name}",
                "reporter_id": cit1.id,
                "confidence": 0.87,
            },
            {
                "description": "Second report of the same pothole on Market St (within 6m).",
                "latitude": 37.77494,
                "longitude": -122.41942,
                "address_text": "Market St near 5th St",
                "damage_type": "D40",
                "status": "submitted",
                "priority": "HIGH",
                "severity": "HIGH",
                "priority_score": 0.86,
                "priority_reasons": json.dumps(["Detected D40 (Pothole)", "Potential duplicate within 15m"]),
                "nearby_report_count": 1,
                "image_url": f"/uploads/reports/{img_d40.name}",
                "reporter_id": cit2.id,
                "confidence": 0.82,
            },
            {
                "description": "Severe alligator cracking mesh across northbound bike lane.",
                "latitude": 37.78120,
                "longitude": -122.41180,
                "address_text": "Mission St & 3rd St",
                "damage_type": "D20",
                "status": "verified",
                "priority": "HIGH",
                "severity": "HIGH",
                "priority_score": 0.78,
                "priority_reasons": json.dumps(["Detected D20 (Alligator Crack) mesh fatigue"]),
                "nearby_report_count": 0,
                "image_url": f"/uploads/reports/{img_d20.name}",
                "reporter_id": cit1.id,
                "confidence": 0.79,
            },
            {
                "description": "Longitudinal pavement seam crack expanding along outer lane.",
                "latitude": 37.76950,
                "longitude": -122.42610,
                "address_text": "Valencia St & 16th St",
                "damage_type": "D00",
                "status": "assigned",
                "priority": "MEDIUM",
                "severity": "MEDIUM",
                "priority_score": 0.56,
                "priority_reasons": json.dumps(["Detected D00 (Longitudinal Crack)"]),
                "nearby_report_count": 0,
                "image_url": f"/uploads/reports/{img_d00.name}",
                "reporter_id": cit2.id,
                "assigned_to_id": st1.id,
                "assigned_to": st1.name,
                "confidence": 0.74,
            },
            {
                "description": "Transverse asphalt fracture across intersection approach.",
                "latitude": 37.76420,
                "longitude": -122.43280,
                "address_text": "Castro St & 18th St",
                "damage_type": "D10",
                "status": "under_repair",
                "priority": "MEDIUM",
                "severity": "MEDIUM",
                "priority_score": 0.52,
                "priority_reasons": json.dumps(["Detected D10 (Transverse Crack)"]),
                "nearby_report_count": 0,
                "image_url": f"/uploads/reports/{img_d10.name}",
                "reporter_id": cit1.id,
                "assigned_to_id": st1.id,
                "assigned_to": st1.name,
                "confidence": 0.68,
            },
            {
                "description": "Pothole repaired with hot-mix asphalt; awaiting officer sign-off.",
                "latitude": 37.75810,
                "longitude": -122.41890,
                "address_text": "24th St & Mission St",
                "damage_type": "D40",
                "status": "repair_evidence_submitted",
                "priority": "HIGH",
                "severity": "HIGH",
                "priority_score": 0.84,
                "priority_reasons": json.dumps(["Detected D40 (Pothole)"]),
                "nearby_report_count": 0,
                "image_url": f"/uploads/reports/{img_d40.name}",
                "reporter_id": cit1.id,
                "assigned_to_id": st1.id,
                "assigned_to": st1.name,
                "confidence": 0.85,
                "needs_after_evidence": True,
            },
            {
                "description": "Completed and verified pothole restoration along Howard St.",
                "latitude": 37.78640,
                "longitude": -122.39920,
                "address_text": "Howard St & 2nd St",
                "damage_type": "D40",
                "status": "closed",
                "priority": "LOW",
                "severity": "HIGH",
                "priority_score": 0.88,
                "priority_reasons": json.dumps(["Detected D40 (Pothole)", "Repair verified and closed by officer"]),
                "nearby_report_count": 0,
                "image_url": f"/uploads/reports/{img_d40.name}",
                "reporter_id": cit1.id,
                "assigned_to_id": st2.id,
                "assigned_to": st2.name,
                "confidence": 0.89,
                "needs_after_evidence": True,
            },
            {
                "description": "Non-road photo submitted by mistake (park walkway).",
                "latitude": 37.76990,
                "longitude": -122.46620,
                "address_text": "Golden Gate Park",
                "damage_type": None,
                "status": "rejected",
                "priority": "LOW",
                "severity": "UNKNOWN",
                "priority_score": 0.10,
                "priority_reasons": json.dumps(["No road damage detected by ML"]),
                "nearby_report_count": 0,
                "image_url": f"/uploads/reports/{img_non.name}",
                "reporter_id": cit2.id,
                "rejection_reason": "Photo does not show a municipal roadway surface.",
                "ml_status": "ML_NO_DETECTIONS",
                "confidence": None,
            },
        ]

        created_reports: list[Report] = []
        for idx, spec in enumerate(reports_spec, start=1):
            rep = Report(
                description=spec["description"],
                latitude=spec["latitude"],
                longitude=spec["longitude"],
                address_text=spec["address_text"],
                damage_type=spec["damage_type"],
                status=spec["status"],
                priority=spec["priority"],
                severity=spec["severity"],
                priority_score=spec["priority_score"],
                priority_reasons=spec["priority_reasons"],
                priority_updated_at=now,
                nearby_report_count=spec["nearby_report_count"],
                image_url=spec["image_url"],
                reporter_id=spec["reporter_id"],
                assigned_to_id=spec.get("assigned_to_id"),
                assigned_to=spec.get("assigned_to"),
                rejection_reason=spec.get("rejection_reason"),
                ml_status=spec.get("ml_status", "ML_COMPLETE"),
                ml_model_version=MODEL_VERSION,
                ml_inference_time_ms=138.4,
                ml_processed_at=now,
            )
            db.add(rep)
            db.flush()
            created_reports.append(rep)

            if spec.get("confidence") is not None and spec["damage_type"]:
                db.add(
                    DetectionResult(
                        report_id=rep.id,
                        detected_class=spec["damage_type"],
                        class_name=spec["damage_type"],
                        confidence=spec["confidence"],
                        bbox_xmin=140.0,
                        bbox_ymin=210.0,
                        bbox_xmax=430.0,
                        bbox_ymax=480.0,
                        bbox_normalized=json.dumps([0.22, 0.35, 0.68, 0.78]),
                        severity=spec["severity"],
                        model_version=MODEL_VERSION,
                    )
                )

            if spec.get("assigned_to_id"):
                db.add(
                    Assignment(
                        report_id=rep.id,
                        assigned_to=spec["assigned_to_id"],
                        assigned_by=off1.id,
                        is_active=(spec["status"] != "closed"),
                        note="Assigned for field remediation",
                    )
                )

            db.add(
                ReportStatusHistory(
                    report_id=rep.id,
                    from_status=None,
                    to_status="submitted",
                    performed_by_id=spec["reporter_id"],
                    performed_by_role=UserRole.CITIZEN.value,
                    note="Demo report submitted",
                )
            )
            if spec["status"] != "submitted":
                actor = off1 if spec["status"] != "closed" else off2
                db.add(
                    ReportStatusHistory(
                        report_id=rep.id,
                        from_status="submitted",
                        to_status=spec["status"],
                        performed_by_id=actor.id,
                        performed_by_role=actor.role.value,
                        note=spec.get("rejection_reason") or f"Demo transitioned to {spec['status']}",
                    )
                )

            db.add(
                PriorityHistory(
                    report_id=rep.id,
                    previous_priority=None,
                    new_priority=spec["priority"],
                    previous_severity=None,
                    new_severity=spec["severity"],
                    score=spec["priority_score"],
                    reasons=spec["priority_reasons"],
                    trigger="created",
                )
            )

            if spec.get("needs_after_evidence"):
                ev_dir = EVIDENCE_UPLOAD_DIR / str(rep.id)
                ev_file = _pick_demo_image("after_repair.jpg", f"demo_after_{rep.id}.jpg", ev_dir)
                raw_ev = ev_file.read_bytes()
                uploader = st1 if spec.get("assigned_to_id") == st1.id else st2
                db.add(
                    RepairEvidence(
                        report_id=rep.id,
                        uploaded_by=uploader.id,
                        kind=EvidenceKind.AFTER,
                        file_path=f"uploads/evidence/{rep.id}/{ev_file.name}",
                        original_filename=ev_file.name,
                        mime_type="image/jpeg",
                        size_bytes=len(raw_ev),
                        checksum=hashlib.sha256(raw_ev).hexdigest(),
                        note="Hot-mix asphalt patch compacted and sealed.",
                    )
                )

        # Link the nearby pothole pair as POTENTIAL_DUPLICATE
        r1, r2 = created_reports[0], created_reports[1]
        db.add(
            ReportRelation(
                report_id=min(r1.id, r2.id),
                related_report_id=max(r1.id, r2.id),
                relation_type="POTENTIAL_DUPLICATE",
                distance_meters=4.8,
                review_status="PENDING",
            )
        )
        db.commit()
        return {
            "action": "seeded_clean_demo",
            "users_ready": len(users_by_email),
            "reports_created": len(created_reports),
        }
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Seed or reset CivicSight demo database.")
    parser.add_argument("--reset", action="store_true", help="Wipe existing reports/evidence and re-seed clean demo state.")
    args = parser.parse_args()
    summary = seed_demo(reset=args.reset)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
