# CivicSight - Backend API Service

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-D71F00.svg?style=flat&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Computer%20Vision-00FFFF.svg?style=flat)](https://github.com/ultralytics/ultralytics)

The backend service for **CivicSight**, an intelligent road damage detection and municipal maintenance platform. The API orchestrates citizen incident reporting, automated computer vision defect detection, severity-based prioritization, and municipal officer verification workflows.

---

## Architecture Overview

CivicSight is built with **FastAPI**, **SQLAlchemy ORM**, and asynchronous background tasks for machine learning inference.

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── auth.py          # User authentication & token issuance
│   │       │   ├── reports.py       # Report ingestion, municipal lifecycle & verification
│   │       │   └── users.py         # User management & profile retrieval
│   │       └── router.py            # API v1 route aggregator
│   ├── core/
│   │   ├── config.py                # Pydantic Settings configuration & environment parser
│   │   └── security.py              # Password hashing (bcrypt) & JWT token helpers
│   ├── db/
│   │   ├── database.py              # SQLAlchemy engine, session maker & health checks
│   │   └── init_db.py               # Table schema creation, column migrations & seed data
│   ├── models/
│   │   └── models.py                # Declarative models: User, Report, DetectionResult, ReportStatusHistory
│   ├── schemas/
│   │   ├── auth.py                  # Token & login request/response schemas
│   │   ├── report.py                # Report creation, response, filter & status schemas
│   │   └── user.py                  # User registration & response schemas
│   ├── services/
│   │   └── ml_service.py            # Guarded YOLOv8 background inference & detection persistence
│   └── main.py                      # FastAPI application entrypoint, CORS & static file mounting
├── uploads/
│   └── reports/                     # Local filesystem storage for uploaded incident photos
├── requirements.txt                 # Backend Python package dependencies
├── .env.example                     # Sample configuration template
├── test_*.py                        # Comprehensive pytest test suites
└── test_prototype_e2e_week7.py      # End-to-end integration validation script
```

---

## Core Capabilities

1. **Authentication & Role-Based Access Control (RBAC):**
   - JWT Bearer Token authentication (`HS256`).
   - Four distinct roles:
     - `Citizen`: Report incidents, view public reports, track submitted reports.
     - `Municipal Officer`: Verify, prioritize, accept/reject, and assign repair work.
     - `Maintenance Staff`: Update repair status (`under_repair`, `repaired`).
     - `Admin`: System administration and user management.

2. **Full Report Lifecycle Workflow:**
   - 11 formal lifecycle stages:
     `submitted` → `pending_verification` → `detected` → `prioritized` → `verified` → `assigned` → `under_repair` → `repaired` → `closed` (plus terminal states `rejected` and `duplicate`).
   - Audit trail in `report_status_history` logging every transition, timestamp, actor ID, and optional note.

3. **Asynchronous Computer Vision Pipeline:**
   - Reports accept multi-part form submissions with image uploads (`.jpg`, `.jpeg`, `.png`, `.webp`).
   - Ingestion delegates detection to `FastAPI.BackgroundTasks` using `process_report_image_ml`.
   - **Zero-Failure Guarantee:** Image processing failures or timeouts never crash report submission.
   - **Letterbox Preprocessing:** Retains aspect ratios via 640x640 letterboxing.
   - **YOLOv8 Inference:** Identifies defect classes (`Pothole`, `Alligator Crack`, `Longitudinal Crack`, `Transverse Crack`) with bounding boxes (`bbox_xmin`, `bbox_ymin`, `bbox_xmax`, `bbox_ymax`) and confidence metrics.
   - **Explicit ML Lifecycle States:**
     - `ML_PENDING`: Image uploaded, inference queued.
     - `ML_COMPLETE`: One or more defect detections identified and recorded.
     - `ML_NO_DETECTIONS`: Inference executed successfully, but no defects detected above threshold.
     - `ML_FAILED`: Handled gracefully if image is corrupted or missing.
   - Individual detections stored in `detection_results` (1:N relationship with reports).

4. **Static File Serving:**
   - Uploaded report images are mounted at `/uploads/...`.
   - The frontend application is optionally served directly at `/frontend/...`.

---

## Getting Started

### 1. Prerequisites
- **Python:** 3.10 or higher
- **Virtual Environment:** Recommended (`venv` or `conda`)

### 2. Environment Setup

Create and activate a virtual environment:

```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

Install backend dependencies:

```bash
pip install -r requirements.txt
```

### 3. Environment Configuration

Copy the example environment configuration:

```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

Edit `.env` to configure your database and security settings:

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `PROJECT_NAME` | `CivicSight API` | Name of the FastAPI application |
| `ENVIRONMENT` | `development` | Environment mode (`development` / `production`) |
| `DEBUG` | `True` | Debug flag |
| `DATABASE_URL` | `sqlite:///./civicsight.db` | Connection string (SQLite or PostgreSQL) |
| `SECRET_KEY` | *(Secret string)* | JWT signing key |
| `ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| `1440` (24 hours) | Token validity lifetime in minutes |

> **Note on Databases:** By default, development runs on SQLite (`sqlite:///./civicsight.db`). To connect to PostgreSQL, specify `DATABASE_URL=postgresql://user:password@localhost:5432/civicsight_db`.

### 4. Database Initialization & Seeding

Initialize database tables and seed standard test and demo accounts:

```bash
python -m app.db.init_db
```

#### Pre-seeded Demo Accounts

| Role | Email | Password |
| :--- | :--- | :--- |
| **Municipal Officer** | `officer@civicsight.gov` | `Password123!` |
| **Citizen** | `citizen@civicsight.org` | `Password123!` |
| **Admin** | `admin@civicsight.gov` | `Password123!` |

### 5. Running the Development Server

Start the Uvicorn server:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The application will be accessible at:
- **API Base:** `http://127.0.0.1:8000`
- **Interactive Swagger Docs:** `http://127.0.0.1:8000/docs`
- **ReDoc Documentation:** `http://127.0.0.1:8000/redoc`
- **System Health:** `http://127.0.0.1:8000/health`

---

## API Endpoints Reference

### System & Health

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | API status, version, and phase metadata | No |
| `GET` | `/health` | Application status and database connectivity check | No |

### Authentication (`/api/v1/auth`)

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Register a new user account | No |
| `POST` | `/api/v1/auth/login` | Authenticate with email/password and obtain JWT token | No |
| `GET` | `/api/v1/auth/me` | Fetch profile details of the authenticated user | Yes |

### Reports (`/api/v1/reports`)

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/reports` | Submit a road damage report (supports image upload & triggers ML) | Optional |
| `GET` | `/api/v1/reports` | List reports with filtering (`status`, `priority`, `limit`, `offset`) | No |
| `GET` | `/api/v1/reports/public/summary` | Aggregated metrics for municipal dashboard | No |
| `GET` | `/api/v1/reports/{id}` | Retrieve comprehensive report details including `detection_results` | No |
| `PATCH` | `/api/v1/reports/{id}/verify` | Officer verification: accept, reject, or mark duplicate | Officer / Admin |
| `PATCH` | `/api/v1/reports/{id}/assign` | Assign verified report to maintenance crew | Officer / Admin |
| `PATCH` | `/api/v1/reports/{id}/status` | Update lifecycle stage (`under_repair`, `repaired`, `closed`) | Authenticated Staff |

### Users (`/api/v1/users`)

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/users` | List registered users | Admin / Officer |
| `GET` | `/api/v1/users/{id}` | Get user details by ID | Yes |
| `PATCH` | `/api/v1/users/{id}` | Update user information or role | Admin / Self |

---

## Machine Learning Integration

The backend interacts with the machine learning subsystem residing in `ml/`:
- **Model Checkpoint:** `ml/models/weights/best.pt`
- **Preprocessing:** `ml.src.preprocess.preprocess_report_image` (handles resizing, letterboxing, normalization)
- **Inference Service:** `ml.src.inference.detect_road_damage`
- **Detection Schema (`detection_results`):**
  - `detected_class`: Class code / name (`Pothole`, etc.)
  - `confidence`: Confidence score (0.0 to 1.0)
  - `bbox_xmin`, `bbox_ymin`, `bbox_xmax`, `bbox_ymax`: Pixel coordinates
  - `bbox_normalized`: JSON string containing normalized coordinate array `[x1, y1, x2, y2]`
  - `severity`: Computed severity level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
  - `model_version`: Tagged model identifier (e.g. `YOLOv8n-experiment2_week5`)

---

## Running Tests

Run the full pytest suite:

```bash
pytest -v
```

Execute the End-to-End Prototype Integration test:

```bash
python test_prototype_e2e_week7.py
```

The test validates all 6 fundamental pipeline checks:
1. Citizen incident submission with an image attachment.
2. Background YOLOv8n ML inference execution and database persistence.
3. Verification that detections exist in `detection_results` with valid bboxes and confidence scores.
4. Independent verification by a Municipal Officer without overwriting ML assessment.
5. Assignment of report to maintenance staff.
6. Progressing lifecycle through repair to closure.

---

## License

This project is part of the CivicSight platform. Internal development and demonstration use.
