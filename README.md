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

## 📁 Repository Structure (Week 1 Foundation)

This repository is structured as a modular monorepo:

```text
CivicSight/
├── frontend/             # Citizen portal & municipal interface placeholders (Vanilla HTML/CSS/JS)
│   ├── assets/           # Logos, icons, and media
│   ├── css/              # Design tokens and stylesheets
│   ├── js/               # Core vanilla UI interactivity
│   ├── pages/            # Application views and sub-pages
│   └── index.html        # Main landing page
│
├── backend/              # FastAPI REST API & Database engine
│   ├── app/
│   │   ├── core/         # Configuration & environment settings
│   │   ├── db/           # SQLAlchemy engine & session lifecycle
│   │   ├── models/       # Database entities (prepared for Week 2)
│   │   └── main.py       # FastAPI application entrypoint & health endpoints
│   ├── .env.example      # Environment variables template
│   └── requirements.txt  # Backend dependencies
│
├── ml/                   # Computer Vision & Damage Detection subsystem
│   ├── samples/          # Validation road image samples
│   ├── scripts/          # Model inference and verification scripts
│   ├── README.md         # RDD2022 dataset specifications and class taxonomy
│   └── requirements.txt  # PyTorch, Ultralytics YOLO & CV dependencies
│
├── Dataset/              # Local dataset resources
└── README.md             # Project documentation (this file)
```

---

## 🚀 Getting Started

### 1. Frontend Subsystem
The frontend uses pure Vanilla web technologies with no build steps required for Week 1.

- **Option A (Direct)**: Open `frontend/index.html` directly in any modern web browser.
- **Option B (Local HTTP Server)**:
  ```bash
  # From workspace root
  python -m http.server 3000 --directory frontend
  # Open in browser: http://localhost:3000
  ```

### 2. Backend Subsystem
Powered by FastAPI and SQLAlchemy with PostgreSQL.

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables:
   ```bash
   copy .env.example .env
   # Update DATABASE_URL with your PostgreSQL credentials
   ```
5. Start the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
6. Access interactive API documentation:
   - Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
   - Health Check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### 3. ML Subsystem
Powered by Ultralytics YOLO and PyTorch.

1. Navigate to the ML directory:
   ```bash
   cd ml
   ```
2. Activate your Python environment and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the baseline inference test:
   ```bash
   python scripts/test_inference.py
   ```

---

## 📌 Development Roadmap

- [x] **Week 1**: Monorepo Scaffolding, Landing Page, FastAPI + PostgreSQL Health Check, ML Environment Verification
- [ ] **Week 2**: Citizen Reporting Interface (Camera/GPS), Backend Models & CRUD, RDD2022 Training Pipeline Scaffolding
- [ ] **Week 3**: AI Inference Service Integration, Priority Scoring Algorithm, Municipal Map View
- [ ] **Week 4**: Work Order Dispatch, Repair Status Tracking, Verification & Notification Workflows
