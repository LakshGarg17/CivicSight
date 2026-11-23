# CivicSight 🏛️🛣️

> **Smart Road Damage Detection & Municipal Repair Management Platform**  
> *Production-Ready Software Engineering Submission (Week 11 Final Release)*

[![Backend Test Suite](https://img.shields.io/badge/pytest-17%2F17%20passed-brightgreen.svg)](docs/testing/TEST_RESULTS.md)
[![Test Coverage](https://img.shields.io/badge/coverage-74%25-brightgreen.svg)](docs/testing/TEST_RESULTS.md)
[![Model mAP@0.5](https://img.shields.io/badge/YOLOv8s%20mAP%400.5-52.70%25-blue.svg)](docs/ml/ML_REPORT.md)
[![State Machine](https://img.shields.io/badge/lifecycle-13%20transitions-purple.svg)](docs/architecture/ARCHITECTURE.md)
[![Status](https://img.shields.io/badge/status-submission--ready-success.svg)](#)

---

## 📖 Executive Summary

CivicSight is an enterprise-grade civic technology platform that solves the municipal road maintenance crisis:
1. **Public Hazard Reporting without Technical Jargon:** Citizens upload photos and capture GPS coordinates on an interactive Google Maps interface. The system deliberately eliminates confusing defect categories (like choosing between D00, D10, or D20) — the AI diagnoses the defect automatically.
2. **Automated AI Damage Classification:** An edge-grade YOLOv8s neural network fine-tuned on 14,046 RDD2022 road images classifies damage into four primary classes (**D00** Longitudinal Cracking, **D10** Transverse Cracking, **D20** Alligator Cracking, and **D40** Potholes) with an inference latency of ~344 ms on standard CPU.
3. **Multi-Factor Priority Scoring:** Algorithmic prioritization combines defect severity, road classification (arterial multiplier), repeat-report velocity, and model confidence into an objective 0–100 score.
4. **Geospatial Deduplication:** Automatic 50-meter spatial clustering links duplicate citizen reports to a primary master incident, preventing redundant work order dispatches.
5. **Cryptographically Audited Repair Lifecycle:** A strict finite state machine governs the repair workflow across four user roles (**Citizen**, **Municipal Officer**, **Maintenance Staff**, and **Admin**). Photographic completion evidence (SHA-256 hashed) is mandatory before work orders can be approved and closed.

---

## 🔄 End-to-End Workflow & Lifecycle Architecture

```text
[ Citizen ] ──> Submit Hazard (Photo + Google Maps Pin + Description)
                     │
                     ▼
[ ML Engine ] ─> Detect (YOLOv8s: D00, D10, D20, D40 + Bounding Boxes)
                     │
                     ▼
[ Backend ] ───> Multi-Factor Priority Engine (0–100 Score + 50m Deduplication)
                     │
                     ▼
[ Municipal ] ─> Verify (Officer Inspects AI Detection, Deduplicates, Approves)
                     │
                     ▼
[ Ops Hub ] ───> Assign Work Order (Dispatched to Dedicated Field Technician)
                     │
                     ▼
[ Field Crew ] ─> Repair Execution (Anti-IDOR Staff Queue -> Start Work -> Upload After-Photo)
                     │
                     ▼
[ Municipal ] ─> Final Inspection (Side-by-Side Before/After Photo Review -> Approve)
                     │
                     ▼
[ Citizen ] ────> Closed & Resolved (Real-Time Status Tracking + Complete Resolution History)
```

### Complete Finite State Machine (7 States, 13 Legal Transitions)

| Current State | Target State | Permitted Roles | Trigger Action / Business Rule |
| :--- | :--- | :--- | :--- |
| `SUBMITTED` | `VERIFIED` | Officer, Admin | Officer approves hazard and confirms valid defect |
| `SUBMITTED` | `REJECTED` | Officer, Admin | Officer rejects report (spam, out of jurisdiction) |
| `VERIFIED` | `ASSIGNED` | Officer, Admin | Officer assigns work order to active maintenance staff |
| `ASSIGNED` | `UNDER_REPAIR` | Assigned Staff, Admin | Technician arrives on site and begins work |
| `ASSIGNED` | `VERIFIED` | Officer, Admin | Officer reassigns or unassigns work order |
| `UNDER_REPAIR` | `REPAIR_EVIDENCE_SUBMITTED` | Assigned Staff, Admin | Staff uploads mandatory `AFTER` photo with SHA-256 proof |
| `REPAIR_EVIDENCE_SUBMITTED`| `CLOSED` | Officer, Admin | Officer reviews before/after evidence and approves |
| `REPAIR_EVIDENCE_SUBMITTED`| `UNDER_REPAIR` | Officer, Admin | Officer rejects evidence, sending back for rework |
| `CLOSED` | `REOPENED` | Officer, Admin | Citizen appeals or repair fails warranty inspection |
| `REOPENED` | `VERIFIED` | Officer, Admin | Re-verified for dispatch |
| `REOPENED` | `REJECTED` | Officer, Admin | Appeal rejected |
| `REJECTED` | `VERIFIED` | Officer, Admin | Reversal of accidental rejection |
| `ASSIGNED` | `REJECTED` | Officer, Admin | Work order cancelled before commencement |

---

## 🛠️ Ground-Truth Platform & Runtime Versions

Every component of CivicSight has been verified in production and test environments:

| Technology / Library | Verified Runtime Version | Purpose & Architecture Role |
| :--- | :--- | :--- |
| **Python** | `3.14.8` (AMD64) | Core backend runtime and ML execution |
| **FastAPI** | `0.142.2` | High-performance asynchronous REST API framework |
| **SQLAlchemy** | `2.1.3` | ORM with strict session scoping and foreign key enforcement |
| **Pydantic** | `2.13.5` | Data validation, schema serialization, and type safety |
| **Ultralytics YOLO** | `8.4.173` | YOLOv8s object detection architecture for road damage |
| **PyTorch** | `2.14.1+cpu` | Deep learning tensor engine optimized for CPU inference |
| **SQLite** | `3.50.4` | WAL mode enabled, `PRAGMA foreign_keys = ON`, composite indexes |
| **Node.js** | `v26.10.0` | Frontend verification and automated Playwright browser testing |
| **Google Maps JS API**| Dynamic Loader (`v=weekly`) | Vector maps, AdvancedMarkerElement, and Geocoding |

---

## 📁 Repository Directory Structure

```text
CivicSight/
├── backend/                      # FastAPI Asynchronous Application Subsystem
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── auth.py       # JWT authentication, login equalization, citizen register
│   │   │   │   ├── users.py      # User management, role provisioning
│   │   │   │   ├── reports.py    # Report submission, lifecycle transitions, evidence upload
│   │   │   │   └── staff.py      # Staff workload balancing, anti-IDOR assignment queues
│   │   │   └── router.py         # Consolidated API v1 router mounting (68 routes)
│   │   ├── core/
│   │   │   ├── config.py         # App configuration, env loader, token secrets
│   │   │   ├── dependencies.py   # RBAC dependencies (get_current_user, require_roles)
│   │   │   ├── security.py       # Bcrypt password hashing, PyJWT issuance & validation
│   │   │   ├── state_machine.py  # Centralized finite state machine & RBAC transition rules
│   │   │   └── priority.py       # Multi-factor priority engine & spatial deduplication
│   │   ├── db/
│   │   │   └── database.py       # SQLAlchemy engine, WAL PRAGMA hooks, session lifecycle
│   │   ├── models/
│   │   │   └── models.py         # 9 relational ORM models (Report, User, Assignment, Evidence...)
│   │   ├── schemas/
│   │   │   └── schemas.py        # Pydantic schemas for request validation & API responses
│   │   └── main.py               # FastAPI entrypoint, lifespan event, CORS, static routes
│   └── requirements.txt          # Production backend dependencies
│
├── frontend/                     # Modern High-Contrast Web Interface (HTML5/CSS3/ES6)
│   ├── css/
│   │   └── style.css             # Unified Black/White high-contrast theme & design tokens
│   ├── js/
│   │   ├── app.js                # Core UI interactivity, theme toggle, notifications
│   │   ├── auth.js               # JWT session storage, role badges, protected routes
│   │   ├── maps.js               # Centralized Google Maps API loader & marker manager
│   │   ├── report.js             # Photo dropzone, GPS pinpointing, API submission
│   │   ├── citizen_reports.js    # Citizen personal report tracking & status timelines
│   │   ├── municipal_dashboard.js# Officer GIS triage, priority filtering, crew dispatch
│   │   └── maintenance_staff.js  # Field crew work order execution & evidence upload
│   ├── pages/
│   │   ├── login.html            # Universal sign-in portal
│   │   ├── register.html         # Citizen self-registration
│   │   ├── report.html           # Hazard reporting with Google Maps & photo upload
│   │   ├── citizen_reports.html  # Citizen personal hazard tracking portal
│   │   ├── municipal_dashboard.html # Municipal officer GIS command center
│   │   ├── maintenance_staff.html   # Field technician work order execution
│   │   └── admin_dashboard.html     # System administration & user management
│   └── index.html                # Public landing page with architectural overview
│
├── ml/                           # Computer Vision Subsystem
│   ├── weights/
│   │   └── best.pt               # Trained YOLOv8s model weights (52.70% mAP@0.5)
│   ├── data.yaml                 # 4-class RDD2022 dataset specification
│   ├── dataset_benchmark_report.json # Automated benchmark evaluation metrics
│   └── scripts/
│       ├── train.py              # YOLOv8s training script (SGD, lr0=0.01, imgsz=640)
│       └── evaluate_benchmark.py # Batch benchmark latency & mAP evaluation suite
│
├── docs/                         # Comprehensive Engineering Documentation
│   ├── SRS.md                    # IEEE Std 830-1998 Software Requirements Specification
│   ├── AUDIT_WEEK11.md           # Baseline audit, snapshot manifest, zero-secrets scan
│   ├── architecture/
│   │   └── ARCHITECTURE.md       # C4 Component Architecture, state machine, threat model
│   ├── database/
│   │   └── DATABASE.md           # Complete data dictionary (107 columns, 9 tables, 0 drift)
│   ├── api/
│   │   └── API.md                # REST API reference covering all 68 OpenAPI routes
│   ├── ml/
│   │   ├── ML_REPORT.md          # Model architecture, training curves, confusion matrix
│   │   └── ml_evaluation_summary.json # Quantitative performance metrics
│   ├── testing/
│   │   ├── TEST_CASES.md         # Comprehensive test case specification (9 categories)
│   │   ├── TEST_RESULTS.md       # Pytest run log, 74% coverage report, 13/13 E2E results
│   │   ├── TRACEABILITY.md       # Requirements-to-test traceability matrix
│   │   └── traceability.csv      # Machine-readable traceability table
│   ├── user-guide/
│   │   ├── USER_GUIDE.md         # Step-by-step role guides with verified screenshots
│   │   └── screenshots/          # 24 real Playwright captures (Desktop, Mobile, Light/Dark)
│   ├── demo/
│   │   ├── DEMO_SCRIPT.md        # Timed 8-10 minute presentation script + 5 fallbacks
│   │   ├── REHEARSAL_LOG.md      # Dual end-to-end rehearsal run logs (100% pass)
│   │   └── seed_demo_data.py     # Deterministic demo data seeding script
│   ├── presentation/
│   │   └── CivicSight_Final.pptx # 20-slide executive deck with complete speaker notes
│   ├── diagrams/
│   │   ├── src/                  # 15 Mermaid diagram source specifications (.mmd)
│   │   └── rendered/             # High-resolution rendered diagrams (.svg and .png)
│   └── tools/
│       └── check_consistency.py  # Zero-placeholder consistency & secret audit tool
│
├── scripts/                      # Automated Verification & Build Tooling
│   ├── verify_phase2_3_all_checks.py # 13-point end-to-end integration verification suite
│   ├── capture_all_screenshots.py    # Playwright automated browser screenshot generator
│   └── render_all_diagrams.py        # Mermaid diagram compiler to SVG/PNG
│
├── tests/                        # Automated Pytest Suite
│   ├── test_week10_backend.py    # Backend unit, integration, RBAC, state machine tests
│   └── test_week10_ml.py         # Computer vision inference, corruption, threshold tests
│
└── README.md                     # Root project specification (this document)
```

---

## 🚀 Clean-Room Installation & Setup Guide

### Option A: Windows PowerShell Setup

```powershell
# 1. Clone repository and navigate to root
cd d:\Projects\CivicSight

# 2. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Upgrade pip and install production dependencies
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
pip install ultralytics torch torchvision

# 4. Configure environment variables
Copy-Item backend/.env.example backend/.env
# Note: Ensure GOOGLE_MAPS_API_KEY is configured in frontend/.env if live map rendering is required.

# 5. Initialize Database & Seed Demo Data
python docs/demo/seed_demo_data.py

# 6. Start FastAPI Backend Daemon
cd backend
..\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

In a separate terminal, serve the frontend:
```powershell
cd d:\Projects\CivicSight\frontend
python -m http.server 5500
```
Open your browser at `http://127.0.0.1:5500/index.html`.

---

### Option B: Linux / macOS Bash Setup

```bash
# 1. Clone repository and navigate to root
cd CivicSight

# 2. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r backend/requirements.txt
pip install ultralytics torch torchvision

# 4. Configure environment
cp backend/.env.example backend/.env

# 5. Initialize Database & Seed Demo Data
python3 docs/demo/seed_demo_data.py

# 6. Start FastAPI Backend Server
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

In a separate terminal, serve the frontend:
```bash
cd frontend
python3 -m http.server 5500
```

---

## 👥 Demo Accounts & Pre-Configured Roles

All demo accounts use the standard demo password: **`DemoPass123!`**

| Role | User Name | Email (Username) | Default Starting Portal |
| :--- | :--- | :--- | :--- |
| **Citizen (Reporter)** | Jane Citizen | `citizen1@civicsight.org` | `/pages/login.html` |
| **Citizen 2 (Commuter)**| Mark Resident | `citizen2@civicsight.org` | `/pages/login.html` |
| **Municipal Officer** | Supervisor Davis | `officer1@civicsight.org` | `/pages/municipal_dashboard.html` |
| **Municipal Officer 2** | Inspector Taylor | `officer2@civicsight.org` | `/pages/municipal_dashboard.html` |
| **Maintenance Staff** | Alex Rivera (Crew Lead) | `staff1@civicsight.org` | `/pages/maintenance_staff.html` |
| **Maintenance Staff 2** | Sam Chen (Field Crew) | `staff2@civicsight.org` | `/pages/maintenance_staff.html` |
| **System Admin** | System Admin | `admin1@civicsight.org` | `/pages/admin_dashboard.html` |

---

## 🧪 Automated Testing & Verification Suite

CivicSight adheres to rigorous automated quality gates:

### 1. Pytest Backend & ML Test Suites
```powershell
.venv\Scripts\pytest tests/test_week10_backend.py tests/test_week10_ml.py -v --cov=backend/app --cov-report=term-missing
```
*Result:* **17 passed in 38.07s | 74% Global Application Coverage** (0 Failures, 0 Warnings).

### 2. End-to-End 13-Point Integration Verification
```powershell
.venv\Scripts\python.exe scripts/verify_phase2_3_all_checks.py
```
*Result:* **13/13 Checks Passed (100%)** covering:
- **(a)** Citizen submission with real image and YOLOv8s inference
- **(b)** Multi-factor priority score calculation (0–100)
- **(c)** Spatial deduplication within 50-meter threshold
- **(d)** Municipal Officer inspection & verification transition
- **(e)** Work order dispatch & assignment isolation
- **(f)** Maintenance staff queue isolation (Anti-IDOR)
- **(g)** On-site repair commencement (`UNDER_REPAIR`)
- **(h)** Photographic evidence upload with SHA-256 integrity check
- **(i)** Municipal final inspection & closure approval (`CLOSED`)
- **(j)** Citizen personal tracking reflecting final closure
- **(k)** State machine rejection of illegal transitions (HTTP 400/409)
- **(l)** RBAC enforcement rejecting unprivileged role access (HTTP 403)
- **(m)** Zero secret leakage scan across all files, git tree, and responses

### 3. Consistency Gate & Secrets Scan
```powershell
.venv\Scripts\python.exe docs/tools/check_consistency.py
```
*Result:* **Zero incomplete placeholder markers and 0 leaked secrets across all documents.**

---

## 🧠 Machine Learning Model & Performance Summary

| Metric | Measured Value | Methodology / Dataset Details |
| :--- | :--- | :--- |
| **Architecture** | **YOLOv8s** (Small) | 11.2 Million Parameters, 28.7 GFLOPs |
| **Dataset** | **RDD2022** (Road Damage) | 14,046 labeled images across train, validation, and test |
| **Classes Evaluated** | 4 Classes | `D00` (Longitudinal), `D10` (Transverse), `D20` (Alligator), `D40` (Pothole) |
| **Precision** | **59.59%** | Evaluated on held-out test split |
| **Recall** | **50.05%** | Evaluated on held-out test split |
| **mAP@0.5** | **52.70%** | Mean Average Precision at IoU = 0.50 |
| **mAP@0.5:0.95** | **29.74%** | Mean Average Precision across IoU thresholds 0.50:0.95 |
| **CPU Inference Latency** | **344.52 ms** (Mean) | Benchmark across 50 real road test images on standard CPU |
| **CPU Latency p95** | **1,432.30 ms** | 95th percentile under continuous batch inference |
| **Data Leakage Audit** | **0 Duplicate Hashes** | Strict MD5 hash deduplication verified zero train/test contamination |

---

## 📚 Complete Documentation Sitemap

All formal engineering artifacts are version-controlled in the `/docs` tree:

1. **[Software Requirements Specification (IEEE 830 / ISO 29148)](docs/SRS.md)**
2. **[System Architecture & Security Specification](docs/architecture/ARCHITECTURE.md)**
3. **[Database Schema & Complete Data Dictionary (107 Columns)](docs/database/DATABASE.md)**
4. **[REST API Reference (68 OpenAPI Endpoints)](docs/api/API.md)**
5. **[Machine Learning Subsystem & Benchmark Report](docs/ml/ML_REPORT.md)**
6. **[Test Cases Specification (9 Complete Categories)](docs/testing/TEST_CASES.md)**
7. **[Test Execution Results & Coverage Analysis](docs/testing/TEST_RESULTS.md)**
8. **[Requirements-to-Test Traceability Matrix](docs/testing/TRACEABILITY.md)**
9. **[Citizen, Officer & Staff User Guide (with Screenshots)](docs/user-guide/USER_GUIDE.md)**
10. **[Official Live Demonstration Script & Fallbacks](docs/demo/DEMO_SCRIPT.md)**
11. **[Demonstration Rehearsal Logs (Dual Clean Runs)](docs/demo/REHEARSAL_LOG.md)**
12. **[Executive Presentation Deck (CivicSight_Final.pptx)](docs/presentation/CivicSight_Final.pptx)**
13. **[System Diagrams Source (.mmd) & High-Resolution Renders (.svg/.png)](docs/diagrams/)**

---

## 🔒 Security & Quality Commitments

- **Zero Hardcoded Secrets:** All credentials, tokens, and API keys are injected via environment variables (`.env`). Google Maps API keys are loaded strictly via client-side dynamic loaders and never logged or serialized.
- **Anti-IDOR Protection:** Evidence photographs and staff work order queues enforce cryptographic user-to-resource ownership checks. Unassigned personnel cannot view or download repair evidence.
- **Timing Equalization:** Authentication verifies passwords with constant-time dummy bcrypt comparisons to eliminate user enumeration side-channels.
- **Feature Freeze:** As of Week 11, the codebase is in official **Feature Freeze** for final submission and evaluation.
