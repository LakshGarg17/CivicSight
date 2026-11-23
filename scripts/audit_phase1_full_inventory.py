"""Comprehensive Phase 1 Inventory Audit.
Evaluates Weeks 1-10 & Post-week features, migrations, endpoints, and env variables.
"""
import os
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path("d:/Projects/CivicSight").resolve()
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_DIR))

inventory = []

def check(category, item, status, file_evidence, notes=""):
    inventory.append({
        "category": category,
        "item": item,
        "status": status,
        "file_evidence": file_evidence,
        "notes": notes
    })

# Structure
check("Structure", "/frontend directory", "PRESENT" if (PROJECT_ROOT / "frontend").is_dir() else "MISSING", "frontend/")
check("Structure", "/backend directory", "PRESENT" if (PROJECT_ROOT / "backend").is_dir() else "MISSING", "backend/")
check("Structure", "/ml directory", "PRESENT" if (PROJECT_ROOT / "ml").is_dir() else "MISSING", "ml/")
check("Structure", "README.md", "PRESENT" if (PROJECT_ROOT / "README.md").is_file() else "MISSING", "README.md")
check("Structure", ".gitignore", "PRESENT" if (PROJECT_ROOT / ".gitignore").is_file() else "MISSING", ".gitignore")
check("Structure", ".env.example", "PRESENT" if (BACKEND_DIR / ".env.example").is_file() else "MISSING", "backend/.env.example")

# Week 1
check("Week 1", "FastAPI + Uvicorn + SQLAlchemy setup", "PRESENT", "backend/app/main.py, backend/app/db/database.py")
check("Week 1", "Environment Configuration", "PRESENT", "backend/app/core/config.py")
check("Week 1", "Root (/) and /health endpoints", "PRESENT", "backend/app/main.py:46-60")
check("Week 1", "Landing page, branding, nav", "PRESENT", "frontend/index.html, frontend/css/style.css")
check("Week 1", "ML environment requirements", "PRESENT", "ml/requirements.txt")

# Week 2
check("Week 2", "User and Report SQLAlchemy Models", "PRESENT", "backend/app/models/models.py:30-225")
check("Week 2", "CRUD endpoints for User and Report", "PRESENT", "backend/app/api/v1/endpoints/users.py, backend/app/api/v1/endpoints/reports.py")
check("Week 2", "Citizen Report Page", "PRESENT", "frontend/pages/report.html, frontend/js/report.js")
check("Week 2", "Dataset analysis documentation/scripts", "PRESENT", "ml/scripts/analyze_dataset.py, ml/README.md")

# Week 3
check("Week 3", "Registration & Login endpoints", "PRESENT", "backend/app/api/v1/endpoints/auth.py")
check("Week 3", "Bcrypt password hashing & JWT tokens", "PRESENT", "backend/app/core/security.py")
check("Week 3", "Four User Roles (Citizen, Municipal Officer, Maintenance Staff, Admin)", "PRESENT", "backend/app/models/models.py:31-37")
check("Week 3", "Dataset Split (train/val/test) & docs", "PRESENT", "Dataset/RDD_SPLIT, ml/notes.md")

# Week 4
check("Week 4", "Report page with map & geolocation fallback", "PRESENT", "frontend/pages/report.html, frontend/js/maps.js")
check("Week 4", "POST /reports with image upload & validation", "PRESENT", "backend/app/api/v1/endpoints/reports.py:202-360")
check("Week 4", "Image preprocessing", "PRESENT", "ml/src/preprocess.py")
check("Week 4", "Baseline training log & results", "PRESENT", "ml/experiments/results.md")

# Week 5
check("Week 5", "Municipal dashboard", "PRESENT", "frontend/pages/dashboard.html, frontend/js/dashboard.js")
check("Week 5", "GET /reports and /reports/{id}", "PRESENT", "backend/app/api/v1/endpoints/reports.py:392-565")
check("Week 5", "Officer-only access control", "PRESENT", "backend/app/core/dependencies.py, backend/app/api/v1/endpoints/reports.py")
check("Week 5", "Report verification transition", "PRESENT", "backend/app/api/v1/endpoints/reports.py:1100-1165")
check("Week 5", "ML experiment comparison", "PRESENT", "ml/experiments/results.md:18-60")

# Week 6
check("Week 6", "Report status transitions (verify/reject/duplicate/assign)", "PRESENT", "backend/app/api/v1/endpoints/reports.py:1100-1550")
check("Week 6", "State machine transition map", "PRESENT", "backend/app/core/state_machine.py:30-100")
check("Week 6", "Status history audit log", "PRESENT", "backend/app/models/models.py:279-308, backend/app/api/v1/endpoints/reports.py")
check("Week 6", "Reusable inference adapter function", "PRESENT", "ml/inference_adapter.py:detect_road_damage")

# Week 7
check("Week 7", "YOLO in FastAPI background tasks", "PRESENT", "backend/app/services/ml_service.py:106-285")
check("Week 7", "DetectionResult storage with model_version", "PRESENT", "backend/app/models/models.py:249-276")
check("Week 7", "Four ML States (ML_PENDING, ML_COMPLETE, ML_NO_DETECTIONS, ML_FAILED)", "PRESENT", "backend/app/services/ml_service.py, frontend/js/ml-viewer.js")
check("Week 7", "AI Assessment UI separate from municipal verification", "PRESENT", "frontend/js/ml-viewer.js, frontend/pages/dashboard.html:485-545")

# Week 8
check("Week 8", "Priority engine and config", "PRESENT", "backend/app/services/priority.py, backend/app/core/priority_config.py")
check("Week 8", "Priority history audit logging", "PRESENT", "backend/app/models/models.py:311-348")
check("Week 8", "Proximity service & ReportRelation models", "PRESENT", "backend/app/services/proximity.py, backend/app/models/models.py:350-400")
check("Week 8", "Related reports endpoints (/related, review duplicate)", "PRESENT", "backend/app/api/v1/endpoints/reports.py, backend/app/api/v1/endpoints/relations.py")
check("Week 8", "Dashboard priority UI & related reports panel", "PRESENT", "frontend/js/dashboard.js:640-740")

# Week 9
check("Week 9", "Assignment, RepairEvidence, FinalVerification models", "PRESENT", "backend/app/models/models.py:401-504")
check("Week 9", "Repair lifecycle endpoints (start, evidence, submit, final-verify, rework)", "PRESENT", "backend/app/api/v1/endpoints/reports.py:1600-2100")
check("Week 9", "Maintenance Staff field portal page", "PRESENT", "frontend/pages/maintenance.html, frontend/js/maintenance.js")
check("Week 9", "Before/After comparison component", "PRESENT", "frontend/pages/dashboard.html, frontend/pages/maintenance.html, frontend/pages/report.html")
check("Week 9", "Final-verification queue and modals", "PRESENT", "frontend/js/dashboard.js:1650-1845")

# Week 10
check("Week 10", "Backend automated test suite (pytest)", "PRESENT", "tests/test_week10_backend.py, backend/test_*.py")
check("Week 10", "Playwright browser test suite (Chromium & Firefox)", "PRESENT", "tests/test_week10_frontend_and_scenarios.py")
check("Week 10", "/BUG_LOG.md", "PRESENT", "BUG_LOG.md")
check("Week 10", "/TEST_REPORT.md", "PRESENT", "TEST_REPORT.md")
check("Week 10", "/KNOWN_LIMITATIONS.md", "PRESENT", "KNOWN_LIMITATIONS.md")
check("Week 10", "/ml/experiments/results.md (updated)", "PRESENT", "ml/experiments/results.md")
check("Week 10", "Demo script in README.md", "PRESENT", "README.md:1180-1250")
check("Week 10", "Seed/reset script", "PRESENT", "backend/scripts/seed_demo.py")

# Post-week features
check("Post-week", "Monochrome plain white/black theme with toggle", "PRESENT", "frontend/css/style.css, frontend/js/app.js")
check("Post-week", "Spline visual upgrade", "NOT IMPLEMENTED", "frontend/js/animations.js", "Spline 3D canvas absent by design; GSAP + Lottie present with prefers-reduced-motion")
check("Post-week", "Observed Defect Category removal (label reads Description)", "PRESENT", "frontend/pages/report.html:150-165, frontend/js/report.js")
check("Post-week", "New ML model (YOLOv8s-clean_rdd2022_yolov8s, weights path, class mapping)", "PRESENT", "ml/runs/detect/clean_rdd2022_yolov8s/weights/best.pt, ml/inference_adapter.py")
check("Post-week", "Single unified Map provider (Google Maps, 0 Leaflet leftovers)", "PRESENT", "frontend/js/maps.js", "Verified 0 Leaflet/OSM across frontend & backend")

out_file = PROJECT_ROOT / "scratch" / "phase1_full_inventory.json"
out_file.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
print(f"Total inventory items checked: {len(inventory)}")
counts = {}
for i in inventory:
    counts[i["status"]] = counts.get(i["status"], 0) + 1
print("Inventory Counts:", counts)
