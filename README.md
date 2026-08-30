# CivicSight 🏛️🛣️

> **Smart Road Damage Detection and Municipal Repair Management System**

CivicSight is an intelligent civic-tech platform bridging the gap between citizen road hazard reporting, AI-driven computer vision damage triage, and municipal maintenance dispatch.

---

## 🔄 End-to-End Workflow

```text
[ Citizen ] ──> Report (Road Hazard / Damage)
                     │
                     ▼
[ ML Engine ] ─> Detect (YOLO Damage Classification: D00, D10, D20, D40)
                     │
                     ▼
[ Backend ] ───> Prioritize (Severity Scoring & Location Clustering)
                     │
                     ▼
[ Municipal ] ─> Verify (Official Inspection & Validation)
                     │
                     ▼
[ Ops Hub ] ───> Assign (Contractor / Work Order Dispatch)
                     │
                     ▼
[ Field Crew ] ─> Repair (Maintenance Execution)
                     │
                     ▼
[ System ] ────> Close (Resolution Verification & Citizen Notification)
```

---

## 📁 Repository Structure (Week 2 Architecture)

This repository is structured as a modular monorepo:

```text
CivicSight/
├── frontend/                     # Citizen portal & reporting interface (Vanilla HTML/CSS/JS)
│   ├── assets/                   # Logos, icons, and media
│   ├── css/                      # Design tokens, hero styles, and report form layout
│   ├── js/
│   │   ├── app.js                # Core landing page interactivity and notifications
│   │   └── report.js             # Interactive photo dropzone, preview, & location toggles
│   ├── pages/
│   │   ├── report.html           # Citizen Damage Reporting Page (Week 2)
│   │   └── index.html            # Redirect helper
│   └── index.html                # Main landing page
│
├── backend/                      # FastAPI REST API & Database engine
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── users.py      # User entity CRUD REST endpoints
│   │   │   │   └── reports.py    # Road damage Report CRUD & status transition endpoints
│   │   │   └── router.py         # Versioned API router mounting (/api/v1)
│   │   ├── core/                 # Configuration & environment settings
│   │   ├── db/
│   │   │   ├── database.py       # SQLAlchemy engine & session lifecycle
│   │   │   └── init_db.py        # Table auto-initialization module
│   │   ├── models/
│   │   │   └── models.py         # SQLAlchemy ORM models (User, Report, ReportStatus)
│   │   ├── schemas/
│   │   │   └── schemas.py        # Pydantic validation models (User & Report CRUD)
│   │   └── main.py               # FastAPI entrypoint, CORS, lifespan, & health checks
│   ├── test_crud.py              # Automated 100% CRUD test suite against PostgreSQL
│   ├── .env.example              # Environment variables template
│   └── requirements.txt          # Backend dependencies
│
├── ml/                           # Computer Vision & Damage Detection subsystem
│   ├── runs/                     # Detection runs & dataset distribution charts
│   ├── samples/                  # Validation road image samples
│   ├── scripts/
│   │   ├── analyze_dataset.py    # RDD2022 pairing, format verification & class distribution analysis (Week 2)
│   │   └── test_inference.py     # Pretrained YOLOv8n baseline verification
│   ├── notes.md                  # Research notes, class distribution, & GPU training requirements (Week 2)
│   ├── README.md                 # RDD2022 dataset specifications and class taxonomy
│   └── requirements.txt          # PyTorch, Ultralytics YOLO & CV dependencies
│
├── Dataset/                      # Local RDD2022 splits (train/val/test)
└── README.md                     # Monorepo documentation (this file)
```

---

## 🌟 Week 2 Progress Summary

### 1. Frontend Subsystem (`/frontend`)
- **Enhanced Landing Page Navigation**: Clear call-to-actions in the hero section and navigation bar directing citizens to report road hazards.
- **New Citizen Damage Reporting Page (`pages/report.html`)**:
  - **Image Upload Dropzone**: Interactive drag-and-drop file picker with instant client-side image preview and metadata display.
  - **Damage Description & Chips**: Context textarea and quick damage type selector chips (`D00`, `D10`, `D20`, `D40`).
  - **Structured Location Placeholders**: Segmented toggles for "Use Current Location (GPS)" and "Select Location Manually" with clean field IDs (`latitude`, `longitude`, `address_text`) ready for Week 3 API/GIS wiring.

### 2. ML Subsystem (`/ml`)
- **Dataset Pairing & YOLO Format Verification**: Verified 100% image-annotation pairing and bounding box compliance on RDD2022.
- **Class Distribution Analysis (`scripts/analyze_dataset.py`)**:
  - Longitudinal Crack (`D00`): **41.0%**
  - Transverse Crack (`D10`): **31.0%**
  - Alligator Crack (`D20`): **8.7%**
  - Pothole (`D40`): **16.5%**
- **Research Notes & Hardware Benchmark (`ml/notes.md`)**: Documented data imbalance mitigations (focal loss / data augmentations) and identified requirement for GPU-accelerated infrastructure for full model training.

### 3. Backend Subsystem (`/backend`)
- **SQLAlchemy Relational Models (`app/models/models.py`)**:
  - `User`: Citizen contact profile (`id`, `name`, `email`, `phone`, `created_at`, `updated_at`).
  - `Report`: Incident hazard report (`id`, `reporter_id`, `description`, `latitude`, `longitude`, `address_text`, `image_url`, `status`, `severity_score`, `damage_type`, `created_at`, `updated_at`).
  - `ReportStatus` lifecycle enum: `submitted` → `detected` → `prioritized` → `verified` → `assigned` → `repaired` → `closed`.
- **Database Table Initialization (`app/db/init_db.py`)**: Automatic table generation in PostgreSQL via FastAPI lifespan startup.
- **Full REST CRUD Endpoints (`/api/v1/users` & `/api/v1/reports`)**: Complete Create, Read (single + list), Update, Status Transition, and Delete capabilities.
- **Automated Test Suite (`backend/test_crud.py`)**: Verified 100% end-to-end CRUD coverage against live PostgreSQL.

---

## 🚀 Getting Started & Execution Guide

### 1. Frontend Subsystem
The frontend uses pure Vanilla web technologies with no build steps required.

- **Option A (Direct)**: Open `frontend/index.html` or `frontend/pages/report.html` in your web browser.
- **Option B (Local Dev Server)**:
  ```bash
  python -m http.server 3000 --directory frontend
  # Open in browser: http://localhost:3000
  ```

---

### 2. Backend Subsystem (PostgreSQL & FastAPI)

#### Step 1: Install Dependencies & Setup Environment
```bash
cd backend
pip install -r requirements.txt
```

Configure your `.env` file with your PostgreSQL connection:
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/civicsight_db
```

#### Step 2: Initialize Database Tables
Tables are automatically verified and created when FastAPI starts, or you can run the initialization script directly:
```bash
python -c "from app.db.init_db import init_db; init_db()"
```

#### Step 3: Start the Backend Server
```bash
uvicorn app.main:app --reload --port 8000
```
- **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

#### Step 4: Run Automated Backend Tests
```bash
python test_crud.py
```

---

### 3. Backend CRUD API Reference (Examples)

#### User Endpoints (`/api/v1/users`)

- **Create User (`POST /api/v1/users`)**:
  ```bash
  curl -X POST "http://127.0.0.1:8000/api/v1/users" \
    -H "Content-Type: application/json" \
    -d '{
      "name": "Jane Citizen",
      "email": "jane.citizen@example.com",
      "phone": "+1-555-0199"
    }'
  ```

- **List Users (`GET /api/v1/users`)**:
  ```bash
  curl -X GET "http://127.0.0.1:8000/api/v1/users?skip=0&limit=10"
  ```

- **Get User by ID (`GET /api/v1/users/{user_id}`)**:
  ```bash
  curl -X GET "http://127.0.0.1:8000/api/v1/users/1"
  ```

- **Update User (`PUT /api/v1/users/{user_id}`)**:
  ```bash
  curl -X PUT "http://127.0.0.1:8000/api/v1/users/1" \
    -H "Content-Type: application/json" \
    -d '{
      "name": "Jane Citizen Updated",
      "phone": "+1-555-9999"
    }'
  ```

- **Delete User (`DELETE /api/v1/users/{user_id}`)**:
  ```bash
  curl -X DELETE "http://127.0.0.1:8000/api/v1/users/1"
  ```

#### Report Endpoints (`/api/v1/reports`)

- **Create Report (`POST /api/v1/reports`)**:
  ```bash
  curl -X POST "http://127.0.0.1:8000/api/v1/reports" \
    -H "Content-Type: application/json" \
    -d '{
      "reporter_id": 1,
      "description": "Deep pothole causing vehicle swerving near the library entrance",
      "latitude": 37.7749,
      "longitude": -122.4194,
      "address_text": "100 Main St, Civic Center",
      "image_url": "https://storage.civicsight.org/reports/pothole_01.jpg",
      "damage_type": "D40",
      "status": "submitted"
    }'
  ```

- **List Reports with Optional Status Filter (`GET /api/v1/reports`)**:
  ```bash
  # List all reports
  curl -X GET "http://127.0.0.1:8000/api/v1/reports"

  # Filter by status
  curl -X GET "http://127.0.0.1:8000/api/v1/reports?status=submitted"
  ```

- **Get Report by ID (`GET /api/v1/reports/{report_id}`)**:
  ```bash
  curl -X GET "http://127.0.0.1:8000/api/v1/reports/1"
  ```

- **Update Report Details (`PUT /api/v1/reports/{report_id}`)**:
  ```bash
  curl -X PUT "http://127.0.0.1:8000/api/v1/reports/1" \
    -H "Content-Type: application/json" \
    -d '{
      "description": "Critical pothole with exposed aggregate",
      "severity_score": 0.88
    }'
  ```

- **Transition Lifecycle Status (`PATCH /api/v1/reports/{report_id}/status`)**:
  ```bash
  curl -X PATCH "http://127.0.0.1:8000/api/v1/reports/1/status" \
    -H "Content-Type: application/json" \
    -d '{
      "status": "assigned"
    }'
  ```

- **Delete Report (`DELETE /api/v1/reports/{report_id}`)**:
  ```bash
  curl -X DELETE "http://127.0.0.1:8000/api/v1/reports/1"
  ```

---

### 4. ML Subsystem

1. Navigate to the ML directory:
   ```bash
   cd ml
   ```
2. Run the dataset format verification and class distribution analysis:
   ```bash
   python scripts/analyze_dataset.py 2000
   ```
3. Run baseline inference verification:
   ```bash
   python scripts/test_inference.py
   ```

---

## 📌 Development Roadmap

- [x] **Week 1**: Monorepo Scaffolding, Landing Page, FastAPI + PostgreSQL Health Check, ML Environment Verification
- [x] **Week 2**: Citizen Reporting Interface (Photo/GPS Scaffolding), Backend Models & CRUD REST API, RDD2022 Dataset Analysis & Verification
- [ ] **Week 3**: AI Inference Service Integration, Priority Scoring Algorithm, Municipal Map View & GPS Geolocation
- [ ] **Week 4**: Work Order Dispatch, Repair Status Tracking, Verification & Notification Workflows
