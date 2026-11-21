# CivicSight — Week 10 Quality Gate Test Report

**Project:** CivicSight — Smart Road Damage Detection & Municipal Repair Management System  
**Date:** November 18, 2026  
**Quality Gate Status:** **PASS** (65/65 automated tests passed, 0 open defects, 84% backend coverage, 5/5 E2E scenarios passed)  
**Companion Deliverables:** [`BUG_LOG.md`](BUG_LOG.md) · [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) · [`ml/experiments/results.md`](ml/experiments/results.md)

---

## 1. Environment & Phase 0 Audit

### 1.1 Software & Runtime Versions
| Component | Version |
|:---|:---|
| OS | Windows (PowerShell) |
| Python | `3.14.8` (`.venv`) |
| Node.js / npm | `v26.10.0` / `11.19.1` |
| Git | `2.56.0.windows.3` *(workspace is not initialized as a git repository)* |
| PostgreSQL (installed & listening `127.0.0.1:5432`) | `18.6` |
| Active Local DB Dialect (`backend/.env`) | SQLite (`WAL` mode + `PRAGMA foreign_keys=ON`) |
| FastAPI / Uvicorn / Starlette | `0.142.2` / `0.54.0` |
| SQLAlchemy / Pydantic / psycopg2-binary | `2.1.3` / `2.13.5` / `2.9.13` |
| bcrypt / PyJWT | `5.0.0` / `2.12.1` |
| Ultralytics / PyTorch | `8.4.173` / `2.14.1+cpu` |
| OpenCV / Pillow | `5.0.0` / `12.3.0` |
| Pytest / pytest-cov / pip-audit | `9.1.1` / `7.1.0` / `2.10.1` |
| Playwright Browsers | `1.65.2` — Chromium `159` & Firefox `159` |

### 1.2 Phase 0.6 Alignment & Static Security Checks
- **ML Alignment:** **PASS** — `ml/runs/detect/clean_rdd2022_yolov8s/weights/best.pt` (21.48 MB), `model_version = YOLOv8s-clean_rdd2022_yolov8s`, `model.task = detect`, `model.names = {0: 'D00', 1: 'D10', 2: 'D20', 3: 'D40'}` matches `CLASS_METADATA` and `PriorityConfig.class_weights`.
- **Map Library Purity:** **PASS** — Zero Leaflet, OpenStreetMap, or Nominatim references across `frontend/`, `backend/`, `ml/`, and `README.md`. 100% unified under `CivicSightMap` (`frontend/js/maps.js`) using Google Maps dynamic loader (`importLibrary`) and `AdvancedMarkerElement`.
- **Report Form Simplification:** **PASS** — Zero `"Observed Defect Category"` selector or `"Automatic AI Detection"` button; description label reads `"Description"`.
- **Monochrome Theme Audit:** **PASS** — Zero CSS gradients (`linear-gradient` / `radial-gradient`) and zero hardcoded hex colors outside `:root` / `[data-theme]` after BUG-021 fix.
- **Visual Upgrade Check:** Spline 3D hero is **not implemented**; GSAP + Lottie (`frontend/js/animations.js`) present with `prefers-reduced-motion` support.
- **Workspace Secret Scan:** **PASS** — Zero hardcoded Google Maps keys (`AIza...`), DB passwords, or production JWT secrets across workspace files (`.env` and `config.local.js` gitignored).
- **Phase 0.1 README & Config Verification:** **PASS** — Confirmed all 23 `Settings` keys in `backend/app/core/config.py` are documented in `backend/.env.example`, `.gitignore` excludes all 10 required patterns, and fixed two README startup/config discrepancies (`uvicorn backend.app.main:app` -> `uvicorn app.main:app --app-dir backend`, and `JWT_SECRET_KEY` -> `SECRET_KEY`).
- **Dependency Audit (`pip-audit --format columns`):** Recorded **60 advisories across 5 installed packages** (`certifi 2026.7.22`, `filelock 4.0.11`, `opentelemetry-api 1.45.0`, `pillow 12.3.0`, `setuptools 84.0.0`); logged in [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md).

---

## 2. Test Execution Summary

| Area | Suite / Script | Tests Run | Passed | Failed | Skipped | Command / Evidence |
|:---|:---|:---:|:---:|:---:|:---:|:---|
| Backend Auth & Roles | `backend/test_auth.py` | 1 | 1 | 0 | 0 | `pytest ... --cov=backend/app` |
| Backend Core CRUD | `backend/test_crud.py` | 3 | 3 | 0 | 0 | `pytest ... --cov=backend/app` |
| Backend Reports API | `backend/test_reports_api.py` | 5 | 5 | 0 | 0 | `pytest ... --cov=backend/app` |
| Municipal Reports API | `backend/test_municipal_reports_api.py` | 1 | 1 | 0 | 0 | `pytest ... --cov=backend/app` |
| Lifecycle API (Week 6) | `backend/test_lifecycle_api.py` | 1 | 1 | 0 | 0 | `pytest ... --cov=backend/app` |
| Priority & Proximity (Week 8) | `backend/test_priority_and_relations.py` | 20 | 20 | 0 | 0 | `pytest ... --cov=backend/app` |
| Maintenance Lifecycle (Week 9) | `backend/test_week9_lifecycle.py` | 8 | 8 | 0 | 0 | `pytest ... --cov=backend/app` |
| **Week 10 Backend Security, Matrix, DB, Concurrency, 2k Perf** | `tests/test_week10_backend.py` | 11 | 11 | 0 | 0 | `tests/auth_matrix_results.json`, `state_matrix_results.json`, `perf_2000_results.json` |
| **Week 10 ML Pipeline, Edge Cases, Failure Resilience** | `tests/test_week10_ml.py` | 6 | 6 | 0 | 0 | `tests/ml_conditions_and_timing.json` |
| **Week 10 Frontend UI, Themes, A11y, 8 Viewports, Firefox** | `tests/test_week10_frontend_and_scenarios.py` (Phase 2) | 4 | 4 | 0 | 0 | `tests/frontend_ux_a11y_perf.json`, `responsive_results.json`, `tests/screenshots/` |
| **Week 10 Five End-to-End Scenarios (+ Broken ML 5B)** | `tests/test_week10_frontend_and_scenarios.py` (Phase 4) | 5 | 5 | 0 | 0 | `tests/screenshots/scenario*.png` |
| **TOTAL AUTOMATED TESTS** | **All Suites Combined** | **65** | **65** | **0** | **0** | **100% Pass Rate** |
| Independent ML Held-Out Eval | `scripts/eval_week10_ml.py` | 160 imgs | — | — | — | `tests/ml_heldout_eval.json` |
| Demo Seed & Reset Script | `backend/scripts/seed_demo.py --reset` | 1 | 1 | 0 | 0 | RC `0` (`users_ready: 7, reports_created: 8`) |

---

## 3. Complete 35 × 7 API Authorization Matrix (`tests/auth_matrix_results.json`)

Every endpoint was invoked live against FastAPI via `tests/test_week10_backend.py::test_phase1_2_full_openapi_authorization_matrix_and_idor`. (`400`/`404`/`422` for privileged callers indicates the caller **passed** auth/RBAC and hit domain state/validation logic.)

| Method | Route | Anon | Citizen Owner | Citizen Other | Officer | Assigned Staff | Unassigned Staff | Admin |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `GET` | `/` | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| `GET` | `/health` | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| `GET` | `/api/v1/auth/me` | 401 | 200 | 200 | 200 | 200 | 200 | 200 |
| `GET` | `/api/v1/auth/protected-role-example` | 401 | 403 | 403 | 200 | 403 | 403 | 200 |
| `GET` | `/api/v1/users` | 401 | 403 | 403 | 200 | 403 | 403 | 200 |
| `GET` | `/api/v1/users/{owner_id}` | 401 | 200 | 403 | 200 | 403 | 403 | 200 |
| `POST` | `/api/v1/users` | 401 | 403 | 403 | 403 | 403 | 403 | 201 |
| `PUT` | `/api/v1/users/{id}` | 401 | 403 | 403 | 403 | 403 | 403 | 200 |
| `DELETE` | `/api/v1/users/{id}` | 401 | 403 | 403 | 403 | 403 | 403 | 404 |
| `GET` | `/api/v1/reports` | 401 | 403 | 403 | 200 | 403 | 403 | 200 |
| `GET` | `/api/v1/reports/{id}` | 401 | 200 | 403 | 200 | 200 | 403 | 200 |
| `GET` | `/api/v1/reports/{id}/ml-status` | 401 | 200 | 403 | 200 | 200 | 403 | 200 |
| `GET` | `/api/v1/reports/{id}/related` | 401 | 403 | 403 | 200 | 403 | 403 | 200 |
| `GET` | `/api/v1/reports/{id}/priority-history` | 401 | 403 | 403 | 200 | 403 | 403 | 200 |
| `GET` | `/api/v1/reports/{id}/history` | 401 | 403 | 403 | 200 | 403 | 403 | 200 |
| `GET` | `/api/v1/reports/{id}/evidence` | 401 | 200 | 403 | 200 | 200 | 403 | 200 |
| `GET` | `/api/v1/reports/{id}/evidence/{eid}/file` | 401 | 200 | 403 | 200 | 200 | 403 | 200 |
| `POST` | `/api/v1/reports/{id}/recalculate-priority` | 401 | 403 | 403 | 200 | 403 | 403 | 200 |
| `POST` | `/api/v1/reports/{id}/override-priority` | 401 | 403 | 403 | 200 | 403 | 403 | 200 |
| `POST` | `/api/v1/reports/{id}/verify` | 401 | 403 | 403 | 400 | 403 | 403 | 400 |
| `POST` | `/api/v1/reports/{id}/reject` | 401 | 403 | 403 | 400 | 403 | 403 | 400 |
| `POST` | `/api/v1/reports/{id}/duplicate` | 401 | 403 | 403 | 400 | 403 | 403 | 400 |
| `POST` | `/api/v1/reports/{id}/assign` | 401 | 403 | 403 | 400 | 403 | 403 | 400 |
| `POST` | `/api/v1/reports/{id}/reassign` | 401 | 403 | 403 | 400 | 403 | 403 | 400 |
| `POST` | `/api/v1/reports/{id}/unassign` | 401 | 403 | 403 | 400 | 403 | 403 | 400 |
| `POST` | `/api/v1/reports/{id}/repair/start` | 401 | 403 | 403 | 403 | 400 | 403 | 400 |
| `POST` | `/api/v1/reports/{id}/final-verify` | 401 | 403 | 403 | 400 | 403 | 403 | 400 |
| `POST` | `/api/v1/reports/{id}/reopen` | 401 | 403 | 403 | 403 | 403 | 403 | 400 |
| `PUT` | `/api/v1/reports/{id}` | 401 | 403 | 403 | 200 | 403 | 403 | 200 |
| `PATCH` | `/api/v1/reports/{id}/status` | 401 | 403 | 403 | 400 | 403 | 403 | 400 |
| `DELETE` | `/api/v1/reports/{id}` | 401 | 403 | 403 | 403 | 403 | 403 | 404 |
| `PATCH` | `/api/v1/report-relations/{id}` | 401 | 403 | 403 | 200 | 403 | 403 | 400 |
| `GET` | `/api/v1/staff` | 401 | 403 | 403 | 200 | 403 | 403 | 200 |
| `GET` | `/api/v1/staff/me/assignments` | 401 | 403 | 403 | 403 | 200 | 200 | 403 |
| `POST` | `/api/v1/reports/detect` | 401 | 422 | 422 | 422 | 422 | 422 | 422 |

**Result:** **245 / 245 route × identity assertions PASSED** (0 auth holes, 0 IDOR leaks). Direct static fetch to `/uploads/evidence/...` verified `404`.

### 3.1 Manual `curl.exe` Live Server Evidence (`scripts/verify_curl_evidence.py`)
Executed directly via `curl.exe` against a live Uvicorn instance (`127.0.0.1:8769`) backed by a fresh SQLite DB, verifying live HTTP status codes, JSON responses, and security headers (`x-content-type-options: nosniff`, `x-frame-options: DENY`, `referrer-policy: strict-origin-when-cross-origin`, `permissions-policy: geolocation=(self)`):

| Check | `curl.exe` Request | HTTP Status | Observed Response |
|:---|:---|:---:|:---|
| Health Check | `GET /health` | `200 OK` | `{"status":"ok","system_health":"ok","database":{"reachable":true,"database":"SQLite",...}}` |
| Anonymous Reports Block | `GET /api/v1/reports` | `401 Unauthorized` | `{"detail":"Authentication token required."}` |
| Public Evidence Block | `GET /uploads/evidence/1/test.jpg` | `404 Not Found` | `{"detail":"Not Found"}` |
| Role Escalation Block | `POST /api/v1/auth/register` (`role: "Admin"`) | `403 Forbidden` | `{"detail":"Public registration is restricted to Citizen accounts..."}` |
| Officer Login | `POST /api/v1/auth/login` (`officer1`) | `200 OK` | Issued Bearer JWT + `role: "Municipal Officer"` (token redacted) |
| Authenticated Profile | `GET /api/v1/auth/me` (Bearer) | `200 OK` | `officer1@civicsight.gov` (`is_active: true`) |
| Officer Reports List | `GET /api/v1/reports` (Bearer) | `200 OK` | `[]` (empty fresh DB) |

---

## 4. State-Transition Matrix (`tests/state_matrix_results.json`)

- **Matrix Dimensions:** 9 states × 9 target states × 4 roles = **324 transitions evaluated**.
- **Allowed Transitions:** **31** (all strictly canonical; `CLOSED` reachable only via `repair_evidence_submitted -> final-verify APPROVED`; `REOPEN` Admin-only from terminal states).
- **Denied Transitions:** **293** (100% blocked cleanly with `400`/`403`, including `under_repair -> closed`, `rejected -> assigned`, and `closed -> verified`).

---

## 5. Backend Code Coverage (`pytest-cov`, 56 Backend + ML Tests)

| Module | Statements | Missed | Coverage |
|:---|---:|---:|---:|
| `backend/app/api/v1/endpoints/auth.py` | 47 | 0 | **100%** |
| `backend/app/api/v1/router.py` | 12 | 0 | **100%** |
| `backend/app/models/__init__.py` | 3 | 0 | **100%** |
| `backend/app/schemas/__init__.py` | 3 | 0 | **100%** |
| `backend/app/api/v1/endpoints/relations.py` | 51 | 2 | **96%** |
| `backend/app/models/models.py` | 203 | 9 | **96%** |
| `backend/app/core/config.py` | 46 | 3 | **93%** |
| `backend/app/core/security.py` | 35 | 3 | **91%** |
| `backend/app/core/state_machine.py` | 47 | 4 | **91%** |
| `backend/app/api/v1/endpoints/staff.py` | 37 | 4 | **89%** |
| `backend/app/core/dependencies.py` | 45 | 5 | **89%** |
| `backend/app/services/ml_service.py` | 150 | 17 | **89%** |
| `backend/app/db/init_db.py` | 208 | 25 | **88%** |
| `backend/app/schemas/schemas.py` | 406 | 47 | **88%** |
| `backend/app/db/database.py` | 36 | 5 | **86%** |
| `backend/app/services/proximity.py` | 165 | 28 | **83%** |
| `backend/app/api/v1/endpoints/users.py` | 70 | 13 | **81%** |
| `backend/app/api/v1/endpoints/reports.py` | 942 | 198 | **79%** |
| `backend/app/services/priority.py` | 196 | 49 | **75%** |
| `backend/app/main.py` | 84 | 26 | **69%** |
| **TOTAL (`backend/app`)** | **2,786** | **438** | **84%** |

---

## 6. Database Scale Performance & Query Plans (`tests/perf_2000_results.json`)

Seeded **2,000** reports into an isolated SQLite DB (`init_db()` with Week 10 additive composite indexes, plus rollback verified via `rollback_week10_indexes()`):

| Query | Query Plan (`EXPLAIN QUERY PLAN`) | Mean Latency | Verdict |
|:---|:---|:---:|:---:|
| Filtered Municipal Listing (`status=? AND priority=? ORDER BY created_at DESC LIMIT 20`) | `SEARCH reports USING INDEX ix_reports_status_priority (status=? AND priority=?)` | **2.90 ms** | **PASS** |
| Proximity Bounding Box (`latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?`) | `SEARCH reports USING COVERING INDEX ix_reports_lat_lng (latitude>? AND latitude<?)` | **0.78 ms** | **PASS** |

---

## 7. Frontend Quality, Themes, Accessibility, Performance & Responsive Matrix

### 7.1 Page-Level UX, Theme, A11y & Performance (`tests/frontend_ux_a11y_perf.json`, Chromium 159)
| Page | Light BG | Dark BG | Console Errors | Missing `alt` | Unlabeled Inputs | `<main>` & `<h1>` | `DOMContentLoaded` | `load` Event |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `index.html` (Landing) | `rgb(255,255,255)` | `rgb(10,10,10)` | 0 | 0 | 0 | Yes | 44 ms | 44 ms |
| `login.html` | `rgb(255,255,255)` | `rgb(10,10,10)` | 0 | 0 | 0 | Yes | 21 ms | 26 ms |
| `register.html` | `rgb(255,255,255)` | `rgb(10,10,10)` | 0 | 0 | 0 | Yes | 22 ms | 28 ms |
| `report.html` | `rgb(255,255,255)` | `rgb(10,10,10)` | 0 | 0 | 0 | Yes | 105 ms | 106 ms |
| `dashboard.html` | `rgb(255,255,255)` | `rgb(10,10,10)` | 0 | 0 | 0 | Yes | 125 ms | 127 ms |
| `maintenance.html` | `rgb(255,255,255)` | `rgb(10,10,10)` | 0 | 0 | 0 | Yes | 29 ms | 30 ms |

- **Theme persistence across reload:** Verified PASS on all 6 pages (`localStorage` persists `dark` across full reload).
- **Firefox 159 Multi-Engine Check:** Verified PASS — landing page load, theme toggle to dark, officer login, dashboard load with 0 console errors (`tests/screenshots/firefox_dashboard.png`).
- **Dashboard Filters & Keyboard Dismissal:** Verified PASS — changing `#statusFilter` and `#priorityFilter` fires live `GET /api/v1/reports?status=...&priority=...` queries; `Escape` closes all 9 dashboard modals cleanly.

### 7.2 Responsive Matrix (6 Pages × 8 Viewports = 48 Checks, `tests/responsive_results.json`)
| Page | 360×740 | 390×844 | 844×390 (Land.) | 768×1024 | 1024×768 | 1280×800 | 1440×900 | 1920×1080 |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `landing` | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS |
| `login` | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS |
| `register` | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS |
| `report` | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS |
| `dashboard` | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS |
| `maintenance` | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS | 0px PASS |

*37 visual proof screenshots saved under `tests/screenshots/`.*

---

## 8. ML Subsystem Summary (Full Details in [`ml/experiments/results.md`](ml/experiments/results.md))

- **Official 3,285-image test metrics (`full_training_results.json`):** `mAP@0.5 = 0.5472`, `mAP@0.5:0.95 = 0.2708`, `P = 0.6081`, `R = 0.5097` (`D00: 0.5389`, `D10: 0.5352`, `D20: 0.6459`, `D40: 0.4688`).
- **Week 10 160-image multi-domain operating-point evaluation (`conf=0.25`, `iou=0.45`, IoU ≥ 0.50):**
  - Macro Precision@0.25: **0.7896** · Macro Recall@0.25: **0.5155**
  - `D00`: P `0.6591` / R `0.5118` / F1 `0.5762`
  - `D10`: P `0.8036` / R `0.5056` / F1 `0.6207`
  - `D20`: P `0.7959` / R `0.6000` / F1 `0.6842`
  - `D40`: P `0.9000` / R `0.4444` / F1 `0.5950` *(weakest recall class)*
- **CPU Inference Latency (160 images):** Mean **130.13 ms**, p95 **170.18 ms**, Min **116.60 ms**, Max **213.84 ms**.
- **Edge Cases & Failure Resilience:** Cleanly handles EXIF rotation, Grayscale/RGBA/CMYK/Palette, 4096×3072, 16×16, dark/blurry, non-road (0 FP), and missing/corrupted weights (`ML_FAILED` never blocks report submission or lifecycle closure).

---

## 9. Five End-to-End Scenarios (Phase 4 — Live Uvicorn + Chromium + SQLite)

### Scenario 1 — Valid Citizen Report, ML Detection, Priority & Backend Restart Persistence
- **Preconditions:** Clean live Uvicorn server (`127.0.0.1:8765`), geolocation permission granted `(37.7749, -122.4194)`.
- **Steps:** `citizen1` logs in via UI -> uploads `sample_pothole_d40.jpg` + description -> submits -> waits for background ML -> `officer1` views report in `dashboard.html` -> **Uvicorn process stopped and restarted** -> dashboard reloaded & API queried.
- **Expected:** Report saved with disk image, `DetectionResult` + `YOLOv8s-clean_rdd2022_yolov8s`, `priority` + `priority_reasons`, `ReportStatusHistory`, and full survival across server restart.
- **Actual:** All assertions passed (including rendered SVG bounding-box `<rect class="bbox-rect">` coordinate verification in `#mlSvgOverlay`); persisted identically after full Uvicorn restart.
- **Evidence:** `tests/screenshots/scenario1_citizen_view.png`, `tests/screenshots/scenario1_officer_view.png`, `tests/screenshots/scenario1_officer_bbox_modal.png` — **PASS**.

### Scenario 2 — GPS Permission Denied, Invalid Coords Blocked, Google Maps Blocked
- **Preconditions:** Browser geolocation overridden to return `PERMISSION_DENIED (code 1)`; `**/maps.googleapis.com/**` aborted via Playwright network route.
- **Steps:** `citizen1` opens `report.html` -> verifies `"Permission Denied"` notice -> enters out-of-range latitude `125.0` -> attempts submit -> enters valid manual coords `(37.768123, -122.429456)` -> submits.
- **Expected:** Invalid latitude blocked client-side with clear field error; valid manual submission succeeds and persists exact manual coordinates even with GPS denied and Google Maps blocked.
- **Actual:** Invalid latitude blocked cleanly; valid manual report created with DB coords matching within `1e-5`.
- **Evidence:** `tests/screenshots/scenario2_gps_denied_manual.png` — **PASS**.

### Scenario 3 — Officer Rejects Report, Citizen Visibility & Spatial Exclusion
- **Preconditions:** `citizen1` submits `non_road.jpg` at `(37.7200, -122.4700)`.
- **Steps:** Attempt reject with whitespace reason (`422`) -> `officer1` rejects via dashboard modal with reason -> attempt assign/verify (`400`) -> `citizen1` opens `report.html?id=<id>` -> submit new report at identical coordinates -> check `/related` -> verify already-assigned report cannot be rejected (`400`).
- **Expected:** Status `rejected` distinct from `closed`, reason logged in history & visible to citizen, rejected report excluded from spatial proximity matching.
- **Actual:** All assertions matched expected behavior.
- **Evidence:** `tests/screenshots/scenario3_citizen_sees_rejected.png` — **PASS**.

### Scenario 4 — Spatial Proximity & Duplicate Review Flow
- **Preconditions:** Isolated cluster around `(37.8100, -122.4900)`.
- **Steps:** Submit 5 reports (`R1` D40, `R2` D40 ~5m away, `R3` D40 ~30m away, `R4` D00 same spot, `R5` D40 ~5km away) -> inspect `/related` -> verify no auto-merge -> verify `/priority-history` -> `officer1` confirms `R1–R2` duplicate once (`200`) -> second review rejected (`400`) -> inspect `Related & Nearby Reports` in dashboard UI.
- **Expected:** `R2 = POTENTIAL_DUPLICATE`, `R3/R4 = NEARBY_RELATED`, `R5` absent; confirming duplicate sets newer `R2` to `duplicate` pointing to `R1` while preserving `R1`.
- **Actual:** Exact relation classification, single-review lock, and UI rendering confirmed.
- **Evidence:** `tests/screenshots/scenario4_related_reports_modal.png` — **PASS**.

### Scenario 5 (and 5B) — Complete Maintenance Lifecycle, Rework Loop, Anti-IDOR & Broken-ML Resilience
- **Preconditions:** `citizen1`, `citizen2`, `officer1`, `officer2`, `staff1`, `staff2` active.
- **Steps:** `citizen1` submits pothole -> `officer1` verifies & assigns to `staff1` -> `staff2`/`citizen1` blocked from repair (`403`) & `staff2` portal omits work order -> `staff1` starts repair -> Submit button disabled until AFTER photo uploaded -> bad PDF rejected -> uploads `after_repair.jpg` & submits -> `staff1` blocked from closing (`403`) -> `officer1` opens Final Verify modal (Before/After authenticated Blob image rendered) & **Sends Back** with rework note -> `staff1` sees rework note on card, uploads 2nd AFTER photo, resubmits -> `officer2` **Approves & Closes** -> `citizen1` sees `CLOSED` + read-only Before/After Blob images -> `citizen2` gets `403 Access Denied`. **Scenario 5B:** Restart server with `MODEL_PATH=ml/DELIBERATELY_BROKEN_MODEL.pt` -> submit report (`ml_status == ML_FAILED`, `status == submitted`) -> execute full verify → assign → repair → AFTER evidence → submit → approve & close.
- **Expected:** Full closed-loop lifecycle succeeds both with healthy ML and with deliberately broken ML.
- **Actual:** Every UI, API, RBAC, Blob-image, rework, and broken-ML assertion passed.
- **Evidence:** `scenario5_staff_evidence_uploaded.png`, `scenario5_officer_final_verify_modal.png`, `scenario5_staff_rework_banner.png`, `scenario5_citizen_closed_before_after.png` — **PASS**.

---

## 10. Bug Summary

All **22 bugs** discovered during Week 10 were fixed with minimal, targeted edits and covered by automated regression tests (**6 CRITICAL, 8 HIGH, 6 MEDIUM, 2 LOW — 22 Fixed, 0 Open**). Full details and Prime Directive 3 test-update justifications are recorded in [`BUG_LOG.md`](BUG_LOG.md).

---

## 11. Explicitly UNVERIFIED Items (Honest Disclosure)

Per Prime Directive 2 (*"Evidence or it did not happen — if you cannot verify something, mark it UNVERIFIED and say why"*):

1. **Git Commit History Secret Scan & Git Release Tag (`v1.0.0-rc1`):** **UNVERIFIED** — The workspace `d:\Projects\CivicSight` is not a Git repository (no `.git` directory). All current workspace files were scanned directly (0 leaked secrets found), but historical git commits could not be scanned and no git commit hash or tag exists.
2. **Live Google Maps Tile Rendering & Reverse Geocoding Against Google Cloud Billing:** **UNVERIFIED** — Per prompt rules, no Google Maps API key or Map ID was requested or hardcoded. Dynamic loader behavior, fallback UI, XSS escaping in InfoWindows, manual pin/coordinate flows, and blocked `maps.googleapis.com` resilience were fully verified; live tile rendering requires the user's real key in `frontend/.env` or `frontend/js/config.local.js`.
3. **Live PostgreSQL 18.6 Migration & Runtime Execution:** **UNVERIFIED** — PostgreSQL 18.6 is installed and listening on `127.0.0.1:5432`, and `init_db.py` SQL was fixed for PostgreSQL boolean defaults (`DEFAULT TRUE`/`DEFAULT FALSE`), but `backend/.env` is currently configured for SQLite and no PostgreSQL credentials were queried or logged.
4. **Google Lighthouse CLI Numeric Scores (Performance / Accessibility / Best Practices):** **UNVERIFIED** — Lighthouse CLI was not installed; instead, real Chromium Navigation Timing (`DOMContentLoaded` 21–125 ms, `load` 26–127 ms) and automated DOM accessibility audits (landmarks, `h1`, image `alt`, form `<label>`, Escape modal dismissal, zero console errors) were executed via Playwright across all 6 pages.
5. **Spline 3D Hero Performance:** **N/A / NOT IMPLEMENTED** — Confirmed absent during Phase 0.6e audit.
