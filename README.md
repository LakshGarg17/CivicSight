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

## 📁 Repository Structure (Week 3 Architecture)

This repository is structured as a modular monorepo:

```text
CivicSight/
├── frontend/                     # Citizen portal & reporting interface (Vanilla HTML/CSS/JS)
│   ├── assets/                   # Logos, icons, and media
│   ├── css/
│   │   └── style.css             # Design tokens, auth forms, role badges, and layout
│   ├── js/
│   │   ├── app.js                # Core landing page interactivity and notifications
│   │   ├── auth.js               # JWT session management & dynamic role-based navigation (Week 3)
│   │   └── report.js             # Interactive photo dropzone, preview, & live API submission (Week 3)
│   ├── pages/
│   │   ├── login.html            # User Sign In interface with error handling (Week 3)
│   │   ├── register.html         # User Registration with role selection & validation (Week 3)
│   │   ├── report.html           # Citizen Damage Reporting Page
│   │   └── index.html            # Redirect helper
│   └── index.html                # Main landing page with dynamic post-login navigation
│
├── backend/                      # FastAPI REST API & Database engine
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── auth.py       # Registration, Login, Profile & RBAC example endpoints (Week 3)
│   │   │   │   ├── users.py      # User entity CRUD REST endpoints (extended with roles/hashes)
│   │   │   │   └── reports.py    # Road damage Report CRUD & status transition endpoints
│   │   │   └── router.py         # Versioned API router mounting (/api/v1)
│   │   ├── core/
│   │   │   ├── config.py         # App settings, DB URI & JWT configuration (Week 3)
│   │   │   ├── dependencies.py   # Auth & RoleChecker RBAC dependencies (Week 3)
│   │   │   └── security.py       # Bcrypt hashing & PyJWT token encoding/decoding (Week 3)
│   │   ├── db/
│   │   │   ├── database.py       # SQLAlchemy engine & session lifecycle
│   │   │   └── init_db.py        # Table initialization & column migration (Week 3)
│   │   ├── models/
│   │   │   └── models.py         # SQLAlchemy models (User with role/hash, Report, ReportStatus)
│   │   ├── schemas/
│   │   │   ├── schemas.py        # Pydantic models (UserRegister, UserLogin, Token, UserResponse)
│   │   │   └── __init__.py       # Schema exports
│   │   └── main.py               # FastAPI entrypoint, CORS, lifespan, auth routers, & health checks
│   ├── test_auth.py              # Automated test suite for registration, login, JWT, & RBAC (Week 3)
│   ├── test_crud.py              # Automated 100% CRUD test suite against PostgreSQL
│   ├── .env.example              # Environment variables template
│   └── requirements.txt          # Backend dependencies (fastapi, bcrypt, pyjwt, sqlalchemy, etc.)
│
├── ml/                           # Computer Vision & Damage Detection subsystem
│   ├── data.yaml                 # Standard YOLOv8 dataset configuration (Week 3)
│   ├── runs/                     # Detection runs & dataset distribution charts
│   ├── samples/
│   │   ├── verified_boxes/       # Visual bounding box verification overlays (Week 3)
│   │   └── sample_road.jpg       # Sample baseline road image
│   ├── scripts/
│   │   ├── analyze_dataset.py    # RDD2022 pairing, format verification & distribution analysis
│   │   ├── test_inference.py     # Pretrained YOLOv8n baseline verification
│   │   └── verify_dataset_and_visualize.py # Dataset split audit & visual overlay renderer (Week 3)
│   ├── notes.md                  # Dataset notes, YAML specifications, & verification steps (Week 3)
│   ├── README.md                 # RDD2022 dataset specifications and class taxonomy
│   └── requirements.txt          # PyTorch, Ultralytics YOLO & CV dependencies
│
├── Dataset/                      # Local RDD2022 splits (train/val/test)
│   └── RDD_SPLIT/                # 38,385 organized image/label pairs across train/val/test
└── README.md                     # Monorepo documentation (this file)
```

---

## 🌟 Week 3 Progress Summary

### 1. Backend Subsystem (`/backend` — Authentication & Roles)
- **User Model Extension (`app/models/models.py`)**:
  - Added `hashed_password` field (stored securely using direct `bcrypt` hashing — never in plaintext).
  - Added `role` field using `UserRole` enum supporting:
    - **`Citizen`**: Public user reporting hazards and viewing resolution status.
    - **`Municipal Officer`**: Official validating reports, estimating scopes, and authorizing dispatches.
    - **`Maintenance Staff`**: Field technicians receiving work orders and executing asphalt repairs.
    - **`Admin`**: System administrator with global oversight and configuration management.
- **Independent Backend Validation**:
  - `UserRegister` and `UserLogin` schemas independently enforce email format regex, password length (min 6 chars), required fields, and duplicate email prevention, regardless of client-side validation.
- **Authentication Endpoints (`app/api/v1/endpoints/auth.py`)**:
  - `POST /auth/register` (and `/api/v1/auth/register`): Hashes password via bcrypt, persists User record, returns sanitized `UserResponse`.
  - `POST /auth/login` (and `/api/v1/auth/login`): Verifies credentials against bcrypt hash, issues signed PyJWT token, handles invalid credentials uniformly without leaking user existence.
  - `GET /api/v1/auth/me`: Authenticated profile endpoint decoding JWT Bearer token.
- **Separation of Authentication & Authorization (`app/core/dependencies.py`)**:
  - `get_current_user`: Authentication dependency verifying JWT signature and database user.
  - `RoleChecker` / `require_roles`: Reusable authorization dependency. Demonstrated on `GET /api/v1/auth/protected-role-example` (accessible to `Admin` & `Municipal Officer`, returns `403 Forbidden` for other roles).
- **Automated Test Suite (`backend/test_auth.py`)**: 100% pass rate across edge cases, duplicate email checks, wrong passwords, JWT validation, and RBAC gating.

### 2. Frontend Subsystem (`/frontend` — Auth Screens & Navigation)
- **Registration Page (`pages/register.html`)**:
  - Collects Full Name, Email, Phone, Role selection, and Password with confirmation.
  - Includes client-side UX validation (matching passwords, email regex, min length) and direct asynchronous connection to backend `POST /api/v1/auth/register`.
- **Login Page (`pages/login.html`)**:
  - Secure credential form connecting to `POST /api/v1/auth/login`.
  - Displays structured error banners on failed attempts without leaking credential details.
  - Automatically captures prefilled email when redirected from registration.
- **Dynamic Role-Aware Navigation (`js/auth.js`)**:
  - Reusable auth module managing `localStorage` JWT tokens and user session data.
  - Dynamically updates header: logged-in state shows user avatar, name, color-coded role badge (`Citizen`, `Municipal Officer`, `Maintenance Staff`, `Admin`), and a Sign Out button.
  - Prepares role-specific navigation sections in the menu bar.
- **Report Damage Integration (`pages/report.html`)**:
  - Form now connects to live backend `POST /api/v1/reports`, automatically associating the report with the logged-in user ID when authenticated.

### 3. ML Subsystem (`/ml` — Dataset Preparation & Visual Verification)
- **Dataset Split Organization (`Dataset/RDD_SPLIT/`)**:
  - Standardized **38,385** image-label pairs into `train/` (26,869 pairs, ~70%), `val/` (5,758 pairs, ~15%), and `test/` (5,758 pairs, ~15%).
- **YOLO Dataset Configuration (`ml/data.yaml`)**:
  - Mapped paths and 4-class taxonomy: `0: D00 (Longitudinal Crack)`, `1: D10 (Transverse Crack)`, `2: D20 (Alligator Crack)`, `3: D40 (Pothole)`.
- **Class Consistency & Coordinate Validation (`ml/scripts/verify_dataset_and_visualize.py`)**:
  - Verified 100% of non-empty labels are mapped to `{0, 1, 2, 3}` and coordinates are bounded within `[0.0, 1.0]`.
- **Visual Bounding Box Verification Overlays**:
  - Rendered colored bounding boxes with labeled banners for all damage classes into `ml/samples/verified_boxes/` confirming ground-truth alignment with pavement defects.
- **Documentation (`ml/notes.md`)**: Comprehensive documentation of dataset prep, class mappings, and repeatable verification procedures. Model training remains scheduled for Week 4.

---

## 👥 System Role Specifications (Week 3)

| Role | Target Persona | Week 3 Permissions / Access Scope |
|:---|:---|:---|
| **`Citizen`** | General Public | Register, log in, submit damage reports with photos/coordinates, view own report status. |
| **`Municipal Officer`** | Public Works Inspector / Engineer | Log in, access protected triage verification endpoints (`/api/v1/auth/protected-role-example`), review incident priority. |
| **`Maintenance Staff`** | Field Repair Crew Technician | Log in, view work order queue (pre-wired in nav), submit repair completion data. |
| **`Admin`** | System Administrator | Full access across all municipal endpoints, user role audits, and administrative operations. |

> [!NOTE]
> Role-Based Access Control (RBAC) has been introduced and proven on example endpoints (`/auth/protected-role-example`). Endpoints will be progressively locked down to specific roles in upcoming phases.

---

## 🚀 Getting Started & Execution Guide

### 1. Backend Authentication & API Reference

#### Install Dependencies & Migrate Tables
```bash
cd backend
pip install -r requirements.txt
python -c "from app.db.init_db import init_db; init_db()"
uvicorn app.main:app --reload --port 8000
```

#### Run Automated Test Suites
```bash
# Run Week 3 Authentication & RBAC Test Suite
python test_auth.py

# Run Week 2 CRUD Test Suite
python test_crud.py
```

#### Example Auth API Requests

- **1. Register a New User (`POST /api/v1/auth/register` or `/auth/register`)**:
  ```bash
  curl -X POST "http://127.0.0.1:8000/api/v1/auth/register" \
    -H "Content-Type: application/json" \
    -d '{
      "name": "Jane Citizen",
      "email": "jane.citizen@example.com",
      "password": "SecurePassword123!",
      "phone": "+1-555-0199",
      "role": "Citizen"
    }'
  ```

- **2. Authenticate & Obtain JWT Token (`POST /api/v1/auth/login` or `/auth/login`)**:
  ```bash
  curl -X POST "http://127.0.0.1:8000/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d '{
      "email": "jane.citizen@example.com",
      "password": "SecurePassword123!"
    }'
  ```
  *Response:*
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1Ni...",
    "token_type": "bearer",
    "user": {
      "id": 1,
      "name": "Jane Citizen",
      "email": "jane.citizen@example.com",
      "role": "Citizen"
    }
  }
  ```

- **3. Get Authenticated Profile (`GET /api/v1/auth/me`)**:
  ```bash
  curl -X GET "http://127.0.0.1:8000/api/v1/auth/me" \
    -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>"
  ```

- **4. Access Role-Gated Endpoint (`GET /api/v1/auth/protected-role-example`)**:
  ```bash
  # Returns 200 OK for 'Admin' or 'Municipal Officer' tokens
  # Returns 403 Forbidden for 'Citizen' or 'Maintenance Staff' tokens
  curl -X GET "http://127.0.0.1:8000/api/v1/auth/protected-role-example" \
    -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>"
  ```

---

### 2. Frontend Subsystem

- Open `frontend/index.html` in your browser, or serve via local server:
  ```bash
  python -m http.server 3000 --directory frontend
  ```
- **Registration**: Navigate to `http://localhost:3000/pages/register.html`
- **Login**: Navigate to `http://localhost:3000/pages/login.html`
- **Report Damage**: Navigate to `http://localhost:3000/pages/report.html`

---

### 3. ML Subsystem (Dataset Verification)

```bash
cd ml
# Run the dataset split audit and generate visual bounding box overlays
python scripts/verify_dataset_and_visualize.py
```
Visual verification overlays will be generated in `ml/samples/verified_boxes/`.

---

## 📌 Development Roadmap

- [x] **Week 1**: Monorepo Scaffolding, Landing Page, FastAPI + PostgreSQL Health Check, ML Environment Verification
- [x] **Week 2**: Citizen Reporting Interface (Photo/GPS Scaffolding), Backend Models & CRUD REST API, RDD2022 Dataset Analysis
- [x] **Week 3**: Authentication & JWT Sessions, Multi-Role Architecture (`Citizen`, `Municipal Officer`, `Maintenance Staff`, `Admin`), Frontend Auth Pages & Role-Aware Nav, ML Dataset Preparation (`data.yaml`, Splits & Visual Auditing)
- [ ] **Week 4**: YOLOv8 Model Training on GPU, AI Inference Service Integration, Municipal Damage Heatmaps & Triage Prioritization
- [ ] **Week 5**: Maintenance Work Order Dispatch, Repair Status Tracking, & Citizen Notification Workflows
