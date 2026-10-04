# CivicSight 🏛️🛣️

### Smart Road Damage Reporting, Detection & Municipal Management System

CivicSight is a civic-tech platform designed to improve how **road damage is reported, verified, prioritized, and managed**.

Citizens can report road damage using photographs, descriptions, and precise locations. Municipal authorities can then review and verify these reports through a centralized dashboard, prioritize incidents, and manage them through the maintenance workflow. CivicSight also includes a **computer vision pipeline using YOLOv8** to identify common types of road damage.

The goal is to connect **citizen reporting, location data, AI-assisted detection, and municipal operations** in one system.

---

## 🌟 Key Features

### 👤 Citizen Reporting

Citizens can:

- Register and securely log in
- Submit road-damage reports with photographs
- Add descriptions and damage information
- Automatically capture their location using GPS
- Select or adjust locations using an interactive map
- View the status of their submitted reports

The reporting interface supports **drag-and-drop image uploads, image previews, location selection, validation, and submission feedback**.

### 🏛️ Municipal Management

Municipal officers have access to a dedicated operations dashboard where they can:

- View reported road hazards
- Inspect photographs and report details
- View reports on an interactive map
- Filter reports by **status and priority**
- Review AI-generated damage information
- Verify submitted reports
- Prioritize incidents for maintenance
- Track reports through the repair workflow

### 🤖 AI-Based Road Damage Detection

CivicSight includes a YOLOv8-based computer vision subsystem built around the **RDD2022 road-damage dataset**.

The current pipeline works with four damage categories:

| Class | Damage Type |
|---|---|
| **D00** | Longitudinal Crack |
| **D10** | Transverse Crack |
| **D20** | Alligator Crack |
| **D40** | Pothole |

The ML subsystem includes:

- Dataset organization and validation
- YOLO-format annotation verification
- Image preprocessing
- Bounding-box visualization
- YOLOv8 training experiments
- Detection evaluation
- Storage of structured detection results

The current model serves as a **baseline for further improvement**, with additional training and deeper application integration planned.

---

## 🔄 How CivicSight Works

```text
┌──────────────┐
│   Citizen    │
└──────┬───────┘
       │
       │ Photo + Description + Location
       ▼
┌──────────────────────┐
│      CivicSight      │
│                      │
│  Validate & Store    │
│  Damage Analysis     │
│  Priority Assignment│
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Municipal Officer   │
│                      │
│  Review → Verify     │
│  → Prioritize        │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   Maintenance Team   │
│                      │
│  Repair & Update     │
│      Status          │
└──────────┬───────────┘
           │
           ▼
      Report Closed
```

---

## 🗺️ Location & Mapping

Location is a core part of CivicSight because a road-damage report needs to be geographically actionable.

The reporting system uses **Leaflet and OpenStreetMap** to provide:

- Browser-based GPS detection
- Interactive map-based location selection
- Click-to-place markers
- Draggable markers
- Latitude and longitude capture
- Manual location selection when GPS is unavailable

This allows municipal teams to identify exactly where reported damage is located.

---

## 🔐 Authentication & User Roles

CivicSight uses **JWT-based authentication** and **Role-Based Access Control (RBAC)**.

| Role | Responsibilities |
|---|---|
| **Citizen** | Submit and track road-damage reports |
| **Municipal Officer** | Review, verify and prioritize reports |
| **Maintenance Staff** | Handle repair and maintenance operations |
| **Admin** | Manage users and system-wide operations |

Passwords are securely hashed using **bcrypt**, while protected backend resources are controlled through authentication and role-based authorization.

---

## 🏗️ System Architecture

CivicSight follows a modular architecture separating the web interface, backend services, and machine-learning components.

```text
CivicSight/
│
├── frontend/          # Citizen interface & municipal dashboard
│   ├── assets/
│   ├── css/
│   ├── js/
│   └── pages/
│
├── backend/           # REST API & database layer
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   └── schemas/
│   ├── tests/
│   └── requirements.txt
│
├── ml/                # Computer vision pipeline
│   ├── scripts/
│   ├── src/
│   ├── samples/
│   ├── experiments/
│   └── data.yaml
│
├── Dataset/           # RDD2022 dataset
│   └── RDD_SPLIT/
│
└── README.md
```

### Technology Stack

**Frontend:** HTML · CSS · JavaScript · Leaflet · OpenStreetMap

**Backend:** Python · FastAPI · SQLAlchemy · PostgreSQL · Pydantic

**Authentication:** JWT · bcrypt · Role-Based Access Control

**AI/ML:** Python · PyTorch · YOLOv8 · OpenCV · PIL · NumPy · RDD2022

---

## 🔧 Backend

The FastAPI backend provides the core services required by the platform:

- User registration and authentication
- JWT session management
- Role-based authorization
- Road-damage report creation and management
- Image upload and validation
- PostgreSQL database operations
- Report status and priority management
- Municipal report verification
- AI detection result storage
- REST API endpoints for frontend integration

Uploaded images are stored separately from the database, while the database maintains the corresponding report information and image paths.

---

## 📊 Municipal Dashboard

The municipal operations center provides a centralized view of road-damage reports.

It includes:

- Active hazard statistics
- Priority and status indicators
- Interactive filtering
- Report tables
- Map-based report locations
- Detailed inspection views
- AI detection visualization
- Report verification
- Real-time UI updates after report actions

This allows municipal users to move from **individual citizen reports to an organized maintenance workflow** rather than handling complaints as isolated submissions.

---

## 🧠 Machine Learning Pipeline

The ML subsystem uses the **RDD2022 dataset** and YOLOv8 for object-detection-based road damage analysis.

The pipeline consists of:

```text
RDD2022 Dataset
      ↓
Dataset Validation
      ↓
Train / Validation / Test Split
      ↓
Image Preprocessing
      ↓
YOLOv8 Training
      ↓
Model Evaluation
      ↓
Damage Detection
      ↓
Bounding Boxes + Detection Results
```

The project includes preprocessing utilities for resizing and normalizing images, dataset auditing tools, visual bounding-box verification, and experiments for improving the baseline detector.

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/LakshGarg17/CivicSight.git
cd CivicSight
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
```

Initialize the database:

```bash
python -c "from app.db.init_db import init_db; init_db()"
```

Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

### 3. Frontend

From the project root:

```bash
python -m http.server 3000 --directory frontend
```

Then open:

```text
http://localhost:3000
```

### 4. ML Environment

```bash
cd ml
pip install -r requirements.txt
```

Dataset verification:

```bash
python scripts/verify_dataset_and_visualize.py
```

---

## 📌 Project Status

### Completed

- [x] Citizen registration and login
- [x] JWT authentication and RBAC
- [x] Citizen road-damage reporting
- [x] Image upload and validation
- [x] GPS and interactive map integration
- [x] PostgreSQL database integration
- [x] Report CRUD operations
- [x] Municipal dashboard
- [x] Status and priority filtering
- [x] Report verification workflow
- [x] RDD2022 dataset preparation
- [x] YOLOv8 preprocessing and validation
- [x] Initial ML training experiments
- [x] AI detection visualization

### Planned

- [ ] Improved road-damage detection accuracy
- [ ] Direct ML inference integration with report submission
- [ ] Automated severity estimation
- [ ] Advanced priority scoring
- [ ] Maintenance work-order dispatch
- [ ] Repair progress tracking
- [ ] Citizen notifications
- [ ] Expanded municipal analytics

---

## 🔗 Explore CivicSight

### 🧩 Visual Architecture
**[GitDiagram](https://gitdiagram.com/lakshgarg17/civicsight)**  
Explore CivicSight's repository structure and component relationships through an interactive architecture diagram.

### 🧠 Codebase Explanation
**[ExplainGitHub](https://explaingithub.com/LakshGarg17/CivicSight)**  
Get an AI-assisted explanation and walkthrough of the CivicSight codebase.

### 💻 Source Code
**[GitHub Repository](https://github.com/LakshGarg17/CivicSight)**  
Explore the complete source code and development history.

---

## 🎯 Vision

> **Make reporting road damage easy for citizens and make acting on those reports easier for municipalities.**

CivicSight brings together **citizen participation, geospatial reporting, computer vision, and municipal management** to create a more structured and data-driven approach to road maintenance.
