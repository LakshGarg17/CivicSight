# CivicSight — Week 10 Quality Gate Bug Log

**Project:** CivicSight — Smart Road Damage Detection & Municipal Repair Management System  
**Gate Date:** November 18, 2026  
**Owner Mapping:** `Laksh` = Backend / API / Database · `Devansh` = Frontend / UI / Maps · `Pranay` = ML / Preprocessing  
**Policy:** Every fix was minimal and targeted, paired with an automated regression test, and verified by re-running the affected and full test suites. Zero security checks were weakened.

---

## Summary by Severity

| Severity | Found | Fixed | Remaining Open |
|:---|:---:|:---:|:---:|
| **CRITICAL** | 6 | 6 | 0 |
| **HIGH** | 8 | 8 | 0 |
| **MEDIUM** | 6 | 6 | 0 |
| **LOW** | 2 | 2 | 0 |
| **Total** | **22** | **22** | **0** |

---

## Detailed Bug Entries

### BUG-001 — Public Registration Allowed Arbitrary Role Escalation (`Admin` / `Municipal Officer`)
- **Severity:** CRITICAL · **Area:** Backend/Security · **Owner:** Laksh · **Status:** FIXED & VERIFIED
- **Repro:** `POST /api/v1/auth/register` with `{"name": "Attacker", "email": "a@x.com", "password": "Password123!", "role": "Admin"}` without authentication.
- **Expected:** Public registration only permits `Citizen` (returns `403` for elevated roles).
- **Actual:** Created an active `Admin` account and returned a valid admin JWT.
- **Root Cause:** `backend/app/api/v1/endpoints/auth.py` accepted client-supplied `role` verbatim on public `/register`; `frontend/pages/register.html` also exposed privileged role `<option>` elements.
- **Fix:** Enforced `role == UserRole.CITIZEN` in `backend/app/api/v1/endpoints/auth.py` (HTTP `403` otherwise); restricted `frontend/pages/register.html` dropdown to `Citizen`.
- **Regression Test:** `tests/test_week10_backend.py::test_phase1_3_security_edge_cases` & `tests/test_week10_frontend_and_scenarios.py::test_phase2_auth_pages_routing_and_role_guards`.

### BUG-002 — Unauthenticated User Management & Privilege Escalation on `/api/v1/users`
- **Severity:** CRITICAL · **Area:** Backend/Security · **Owner:** Laksh · **Status:** FIXED & VERIFIED
- **Repro:** Call `GET/POST/PUT/DELETE /api/v1/users` with no `Authorization` header or a `Citizen` token.
- **Expected:** `401` when anonymous; `POST/PUT/DELETE` Admin-only (`403` for non-Admin); `GET /users` Officer/Admin only; `GET /users/{id}` self or Officer/Admin.
- **Actual:** All 5 `/users` endpoints lacked `Depends(get_current_user)` / role guards, allowing anonymous enumeration, creation, role elevation, and deletion of users.
- **Root Cause:** Week 2 CRUD scaffolding in `backend/app/api/v1/endpoints/users.py` was never retrofitted with Week 3 RBAC dependencies.
- **Fix:** Added strict RBAC dependencies across all 5 `/users` endpoints and validated `role` filter values with `422`.
- **Regression Test:** `tests/test_week10_backend.py::test_phase1_1_complete_authorization_matrix` (35×7 matrix).

### BUG-003 — Protected Maintenance Evidence Folder Publicly Mounted Without Auth
- **Severity:** CRITICAL · **Area:** Backend/Security · **Owner:** Laksh · **Status:** FIXED & VERIFIED
- **Repro:** Request `GET /uploads/evidence/<report_id>/<filename>` directly without a Bearer token.
- **Expected:** `404` or `401`; evidence files must ONLY be served through the authenticated `GET /api/v1/reports/{id}/evidence/{eid}/file` endpoint.
- **Actual:** `backend/app/main.py` mounted the entire `uploads/` parent directory at `/uploads`, exposing private evidence images publicly and bypassing RBAC.
- **Root Cause:** Broad `StaticFiles(directory=uploads_dir)` mount in `backend/app/main.py`.
- **Fix:** Mounted ONLY `uploads/reports` at `/uploads/reports`; left `uploads/evidence` unmounted and served exclusively through the authenticated route with `os.path.realpath` containment check; updated `frontend/js/auth.js`, `dashboard.js`, `maintenance.js`, and `report.js` to fetch evidence images via `CivicSightAuth.fetchAuthenticatedImageUrl()` (`Blob` URLs).
- **Regression Test:** `tests/test_week10_backend.py::test_phase1_3_security_edge_cases` & `test_phase1_1_complete_authorization_matrix`.

### BUG-004 — Unauthenticated Report Modification/Deletion & Workflow Bypass via `PATCH /status` / `PUT /{id}`
- **Severity:** CRITICAL · **Area:** Backend/Security & Lifecycle · **Owner:** Laksh · **Status:** FIXED & VERIFIED
- **Repro:** Call `PUT /api/v1/reports/{id}`, `DELETE /api/v1/reports/{id}`, `POST /detect`, or `PATCH /reports/{id}/status` with `{"status": "closed"}` skipping repair evidence & final verification.
- **Expected:** `PUT` Officer/Admin only, `DELETE` Admin only, `POST /detect` & `GET /ml-status` authenticated, and `CLOSED` reachable ONLY via `POST /final-verify` with `APPROVED`.
- **Actual:** `PUT`/`DELETE`/`detect`/`ml-status` lacked auth checks, and `state_machine.py` allowed `UNDER_REPAIR -> CLOSED` directly.
- **Root Cause:** Legacy Week 2/5 endpoints bypassed the Week 9 state machine and RBAC guards.
- **Fix:** Added RBAC checks on `PUT`, `DELETE`, `POST /detect`, `GET /ml-status`, and `POST /process-ml`; removed `UNDER_REPAIR -> CLOSED` from `backend/app/core/state_machine.py`; blocked status bypasses on `PUT` and `PATCH /status`; prevented `reporter_id` spoofing on `POST /reports`.
- **Regression Test:** `tests/test_week10_backend.py::test_phase1_1_complete_authorization_matrix` & `test_phase1_2_state_machine_full_matrix` (324 transitions).

### BUG-005 — Wildcard CORS (`*`) Combined with `allow_credentials=True` & Unsanitized 500 Errors
- **Severity:** CRITICAL · **Area:** Backend/Security · **Owner:** Laksh · **Status:** FIXED & VERIFIED
- **Repro:** Inspect CORS config in `backend/app/main.py` and trigger an unhandled server exception.
- **Expected:** Explicit allowlisted origins from `CORS_ORIGINS`, security response headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`), and sanitized generic 500 JSON without stack traces or SQL paths.
- **Actual:** `allow_origins=["*"]` with `allow_credentials=True` and no security headers or global exception sanitizer.
- **Root Cause:** Dev-mode CORS middleware left unchanged in `backend/app/main.py`.
- **Fix:** Added explicit `CORS_ORIGINS` setting in `backend/app/core/config.py`, replaced wildcard CORS, added security headers middleware and global exception handler in `backend/app/main.py`.
- **Regression Test:** `tests/test_week10_backend.py::test_phase1_3_security_edge_cases`.

### BUG-006 — Citizen Report Form Crashed on Submit (`ReferenceError: damageType is not defined`) & Clear (`accuracyCircle is not defined`)
- **Severity:** CRITICAL · **Area:** Frontend/UX · **Owner:** Devansh · **Status:** FIXED & VERIFIED
- **Repro:** Open `frontend/pages/report.html`, select an image, enter description & coordinates, click Submit Report (or click Clear Form).
- **Expected:** Form validates cleanly and posts `multipart/form-data` with `Authorization` header to `POST /api/v1/reports`.
- **Actual:** Submitting threw `ReferenceError: damageType is not defined` (leftover reference after removing "Observed Defect Category"); clearing threw `ReferenceError: accuracyCircle is not defined` (leftover Leaflet variable); submit request also omitted `Authorization` header so `reporter_id` was `NULL`.
- **Root Cause:** Incomplete cleanup during defect-category removal and Google Maps migration in `frontend/js/report.js`.
- **Fix:** Removed stale `damageType` and `accuracyCircle` references, removed duplicate coordinate listeners, added `Authorization: Bearer` header on submit/detect/ml-status, added `novalidate` on `#reportForm`, added double-submit lock (`isSubmittingReport`), and added strict client-side image validation.
- **Regression Test:** `tests/test_week10_frontend_and_scenarios.py::test_phase2_report_form_validation_offline_and_map_fallback` & `test_phase4_scenario1_valid_citizen_report_and_restart_persistence`.

### BUG-007 — Deactivated Users Retained API Access with Existing JWT & Could Log In
- **Severity:** HIGH · **Area:** Backend/Security · **Owner:** Laksh · **Status:** FIXED & VERIFIED
- **Repro:** Set `user.is_active = False`, then call `GET /api/v1/auth/me` with existing JWT or call `POST /api/v1/auth/login`.
- **Expected:** Both login (`403`) and bearer-authenticated routes (`401`) reject inactive accounts.
- **Actual:** `get_current_user` and `/auth/login` never checked `user.is_active`.
- **Fix:** Added `is_active` enforcement in `backend/app/core/dependencies.py` and `backend/app/api/v1/endpoints/auth.py`; added `is_active` field to `UserUpdate` schema; added constant-time dummy bcrypt check on unknown login email.
- **Regression Test:** `tests/test_week10_backend.py::test_phase1_3_security_edge_cases`.

### BUG-008 — Destructive User Deletion Cascaded and Deleted Historical Road Reports
- **Severity:** HIGH · **Area:** Backend/DB · **Owner:** Laksh · **Status:** FIXED & VERIFIED
- **Repro:** Admin deletes a user who previously filed road damage reports.
- **Expected:** Reports remain preserved in the database with `reporter_id = NULL` (`ON DELETE SET NULL`).
- **Actual:** `User.reports` SQLAlchemy relationship had `cascade="all, delete-orphan"`, wiping citizen reports when the user row was deleted.
- **Fix:** Removed destructive cascade from `User.reports` in `backend/app/models/models.py` and enabled SQLite `PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;` in `backend/app/db/database.py`.
- **Regression Test:** `tests/test_week10_backend.py::test_phase1_4_database_integrity_and_rollback`.

### BUG-009 — Fake / Polyglot / Corrupted Uploads Accepted & Orphaned Files Left on DB Failure
- **Severity:** HIGH · **Area:** Backend/Security & Integrity · **Owner:** Laksh · **Status:** FIXED & VERIFIED
- **Repro:** Rename a `.txt` file to `fake.jpg` or upload corrupted JPEG bytes to `POST /api/v1/reports` or `POST /repair/evidence`.
- **Expected:** Rejected with HTTP `400` and zero files written to disk; if DB commit fails after saving an image, the saved file is deleted.
- **Actual:** Validation checked extension/MIME header only; Pillow never verified file bytes, and rollback left orphaned files on disk.
- **Fix:** Added `validate_image_bytes()` (magic-byte check + Pillow `verify()` + `load()`) in `backend/app/api/v1/endpoints/reports.py`, applied to both report uploads and repair evidence uploads, plus `try/except` file cleanup on DB failure.
- **Regression Test:** `tests/test_week10_backend.py::test_phase1_3_security_edge_cases` & `test_phase1_4_database_integrity_and_rollback`.

### BUG-010 — Missing Optimistic Locking on Concurrent Verify / Assign / Final-Verify Transitions
- **Severity:** HIGH · **Area:** Backend/Concurrency · **Owner:** Laksh · **Status:** FIXED & VERIFIED
- **Repro:** Two officers concurrently call `POST /verify`, `POST /assign`, or `POST /final-verify` on the same report.
- **Expected:** Exactly one succeeds (`200`) and the second receives a clean conflict (`409` or `400`), with single clean audit trail.
- **Actual:** Read-modify-write without atomic `WHERE version=? AND status=?` allowed duplicate transitions.
- **Fix:** Implemented atomic conditional `UPDATE reports SET ..., version = version + 1 WHERE id = ? AND version = ? AND status = ?` in `verify_report`, `assign_report`, and `final_verify_report` in `backend/app/api/v1/endpoints/reports.py`.
- **Regression Test:** `tests/test_week10_backend.py::test_phase1_5_concurrency_race_conditions`.

### BUG-011 — Maintenance Portal & Officer Final-Verify Modal Broken Field Names Blocked Submission & Images
- **Severity:** HIGH · **Area:** Frontend/UX · **Owner:** Devansh · **Status:** FIXED & VERIFIED
- **Repro:** Maintenance staff uploads an `AFTER` photo in `maintenance.html`; Officer opens Final Verification modal in `dashboard.html`.
- **Expected:** Uploaded `AFTER` evidence displays via authenticated Blob URL and enables the `Submit for Verification` button; Before photo & defect class render properly.
- **Actual:** Both `maintenance.js` and `dashboard.js` read non-existent `report.image_path`, `report.primary_damage_class`, and `data.evidence_photos` (backend returns `image_url`, `damage_type`, `evidence`), leaving `Submit for Verification` permanently disabled and images broken.
- **Fix:** Corrected property mappings (`image_url`, `damage_type`, `data.evidence || data.evidence_photos`) and wired `CivicSightAuth.fetchAuthenticatedImageUrl()` in `frontend/js/maintenance.js` and `frontend/js/dashboard.js`; removed blocking native `confirm()` popups in `maintenance.js`.
- **Regression Test:** `tests/test_week10_frontend_and_scenarios.py::test_phase4_scenario5_complete_maintenance_workflow_and_broken_ml`.

### BUG-012 — Post-Login Role Routing Sent All Roles to `dashboard.html` & Maintenance Staff Not Blocked on Dashboard
- **Severity:** HIGH · **Area:** Frontend/Security & Routing · **Owner:** Devansh · **Status:** FIXED & VERIFIED
- **Repro:** Log in as `Citizen` or `Maintenance Staff` on `login.html`; navigate as `Maintenance Staff` to `dashboard.html`.
- **Expected:** `Citizen` -> `report.html`, `Maintenance Staff` -> `maintenance.html`, `Officer`/`Admin` -> `dashboard.html`; `dashboard.html` blocks `Maintenance Staff` with Access Restricted.
- **Actual:** `login.html` did not route `Maintenance Staff` to `maintenance.html`, and `dashboard.js` role guard only blocked `Citizen`.
- **Fix:** Updated role-based redirect in `frontend/pages/login.html` and restricted `dashboard.js` to `['Municipal Officer', 'Admin']`; added `pageshow` bfcache guard after logout in `frontend/js/auth.js`.
- **Regression Test:** `tests/test_week10_frontend_and_scenarios.py::test_phase2_auth_pages_routing_and_role_guards`.

### BUG-013 — Unescaped HTML in Google Maps InfoWindow (Stored XSS Vector) & 404 `.env` Probes
- **Severity:** HIGH · **Area:** Frontend/Security & Maps · **Owner:** Devansh · **Status:** FIXED & VERIFIED
- **Repro:** Submit a report with `<script>` or `<img onerror=...>` in description/address and click its map marker; open any map page without `.env`.
- **Expected:** All InfoWindow text HTML-escaped; zero `404` network requests or console errors when Maps key is unconfigured.
- **Actual:** Raw report description/address strings were interpolated into InfoWindow HTML; `maps.js` fetched `../.env` causing `404` console errors.
- **Fix:** Added `escapeHtml()` sanitization for InfoWindow content in `frontend/js/maps.js`; replaced `../.env` probes with zero-404 `/frontend/js/config.local.js` endpoint in `backend/app/main.py`; caught blocked Google Maps scripts cleanly.
- **Regression Test:** `tests/test_week10_frontend_and_scenarios.py::test_phase2_report_form_validation_offline_and_map_fallback` & `test_phase4_scenario2_gps_denied_and_maps_blocked`.

### BUG-014 — Frontend Hardcoded Port `:8000` in `auth.js` Broke Same-Origin Non-8000 Deployments
- **Severity:** HIGH · **Area:** Frontend/Deployment · **Owner:** Devansh · **Status:** FIXED & VERIFIED
- **Repro:** Serve CivicSight via FastAPI on any port other than `8000` (e.g., `8765`, `80`, `443`) and attempt login or dashboard fetch.
- **Expected:** Same-origin requests use relative `''` base URL; only standalone static dev servers (`3000`, `5173`, `5500`, `8080`) or `file:` proxy to `:8000`.
- **Actual:** `auth.js` checked `window.location.port !== '8000'` and forced all requests to `:8000`, producing `ERR_CONNECTION_REFUSED`.
- **Fix:** Narrowed `:8000` redirect in `frontend/js/auth.js` to `['3000', '5173', '5500', '8080']` and `file:`.
- **Regression Test:** All 9 Playwright tests in `tests/test_week10_frontend_and_scenarios.py` running on `127.0.0.1:8765`.

### BUG-015 — ML Preprocessing Ignored EXIF Rotation & Crashed on CMYK / Palette / RGBA / Zero-Size Images
- **Severity:** MEDIUM · **Area:** ML/Preprocess · **Owner:** Pranay · **Status:** FIXED & VERIFIED
- **Repro:** Pass EXIF-rotated smartphone JPEG, CMYK JPEG, Palette PNG, or empty array to `preprocess_report_image()` / `detect_road_damage()`.
- **Expected:** EXIF orientation auto-transposed, any valid PIL mode converted cleanly to 3-channel RGB, empty/invalid images raise clean `ValueError`, CUDA automatically falls back to CPU if unavailable.
- **Actual:** OpenCV `cv2.imread` ignored EXIF rotation and struggled with non-standard PIL modes; `ml/inference_adapter.py` lacked CUDA-to-CPU fallback.
- **Fix:** Updated `ml/src/preprocess.py` and `ml/inference_adapter.py` to use `ImageOps.exif_transpose(img).convert("RGB")`, guarded empty arrays, and added automatic CUDA -> CPU fallback.
- **Regression Test:** `tests/test_week10_ml.py::test_phase3_1_3_3_3_5_3_6_preprocessing_modes_exif_and_conditions`.

### BUG-016 — Missing Database Composite Indexes & PostgreSQL Boolean Default Syntax Error
- **Severity:** MEDIUM · **Area:** Backend/DB · **Owner:** Laksh · **Status:** FIXED & VERIFIED
- **Repro:** Run `init_db()` on PostgreSQL and execute `EXPLAIN QUERY PLAN` on 2,000-row proximity & filtered listing queries.
- **Expected:** PostgreSQL-valid `DEFAULT TRUE`/`DEFAULT FALSE` SQL, composite indexes on `(latitude, longitude)`, `(status, priority)`, and `(created_at)` with reversible rollback function, and index scans confirmed in `EXPLAIN`.
- **Actual:** `init_db.py` used SQLite-only `DEFAULT 0`/`DEFAULT 1` for boolean columns, lacked composite indexes, and had an off-by-one `backend_dir` path depth for upload directory creation.
- **Fix:** Fixed `DEFAULT TRUE`/`DEFAULT FALSE` and upload path depth in `backend/app/db/init_db.py`; added additive composite indexes (`ix_reports_lat_lng`, `ix_reports_status_priority`, `ix_reports_created_at`) plus reversible `rollback_week10_indexes()`.
- **Regression Test:** `tests/test_week10_backend.py::test_phase1_7_2000_report_explain_and_performance` & `test_phase1_4_database_integrity_and_rollback`.

### BUG-017 — Citizen Report Tracking View (`report.html?id=...`) Missing Rejection Reason, Before/After Photos & Clear 403 State
- **Severity:** MEDIUM · **Area:** Frontend/UX · **Owner:** Devansh · **Status:** FIXED & VERIFIED
- **Repro:** Open `report.html?id=<id>` as the reporting citizen for a rejected or closed report, or as another citizen (`citizen2`).
- **Expected:** Owner sees current status, rejection reason (if rejected), and read-only Before/After photos (if closed/repaired); another citizen sees clear Access Denied banner.
- **Actual:** `report.js` did not surface `rejection_reason` or authenticated `AFTER` evidence images on `report.html?id=...`, and did not display a clean 403 message.
- **Fix:** Updated `frontend/js/report.js` and `frontend/pages/report.html` to display full status, rejection reason, read-only Before/After authenticated Blob photos, and clear 403 Access Denied feedback; sanitized reporter emails for non-privileged callers in `GET /reports/{id}`.
- **Regression Test:** `tests/test_week10_frontend_and_scenarios.py::test_phase4_scenario3_officer_rejects_report` & `test_phase4_scenario5_complete_maintenance_workflow_and_broken_ml`.

### BUG-018 — Responsive Horizontal Overflow on 844×390 (Landscape Phone) & 1024×768 (Laptop)
- **Severity:** MEDIUM · **Area:** Frontend/Responsive · **Owner:** Devansh · **Status:** FIXED & VERIFIED
- **Repro:** Open logged-in `report.html`, `dashboard.html`, and `maintenance.html` at `844×390` and `1024×768`.
- **Expected:** `scrollWidth <= innerWidth` (0 horizontal overflow) across all 8 tested viewports.
- **Actual:** Desktop navbar remained expanded down to `768px`, causing 68–248px horizontal overflow at `844px` and `1024px`.
- **Fix:** Added compact navbar media query at `max-width: 1120px`, moved mobile hamburger collapse to `max-width: 1060px`, and enabled flex-wrapping on `.dashboard-filter-bar` and `.dashboard-map-header` in `frontend/css/style.css`.
- **Regression Test:** `tests/test_week10_frontend_and_scenarios.py::test_phase2_7_and_2_8_themes_a11y_performance_responsive_and_firefox` (48 page × viewport checks).

### BUG-019 — Dashboard Modals Missing Escape Dismissal (`rejectModal`, `assignModal`, etc.) & Unauthenticated `ml-status` Poll
- **Severity:** MEDIUM · **Area:** Frontend/A11y & Security · **Owner:** Devansh · **Status:** FIXED & VERIFIED
- **Repro:** Open `#rejectModal` on `dashboard.html` and press `Escape`; inspect `pollModalMLStatus` fetch headers.
- **Expected:** Pressing `Escape` dismisses any open modal dialog; `pollModalMLStatus` sends `Authorization: Bearer <token>`.
- **Actual:** `Escape` listener only handled 4 of 9 dialogs, and `pollModalMLStatus` omitted the Bearer header.
- **Fix:** Extended `keydown` `Escape` handler to all 9 dashboard modals and added `Authorization` header to `pollModalMLStatus` in `frontend/js/dashboard.js`.
- **Regression Test:** `tests/test_week10_frontend_and_scenarios.py::test_phase2_4_dashboard_filters_and_escape_modal`.

### BUG-020 — Non-Finite Coordinates (`NaN`/`Inf`), Unvalidated Filter Params & Unbounded Descriptions Accepted
- **Severity:** MEDIUM · **Area:** Backend/Validation · **Owner:** Laksh · **Status:** FIXED & VERIFIED
- **Repro:** Submit `latitude=NaN`, `description` > 2000 chars, or query `GET /api/v1/reports?status=bogus&sort_by=drop_table`.
- **Expected:** HTTP `422` validation error with descriptive JSON.
- **Actual:** Non-finite coordinates and invalid list filter/sort query params were silently ignored or passed through.
- **Fix:** Added finite-float validators and `max_length=2000` in `backend/app/schemas/schemas.py`; added explicit 422 allowlist validation for `status`, `priority`, `sort_by`, and `sort_order` in `backend/app/api/v1/endpoints/reports.py`; accepted JSON or query `note` in `submit_repair_evidence`.
- **Regression Test:** `tests/test_week10_backend.py::test_phase1_3_security_edge_cases`.

### BUG-021 — Monochrome Theme Violations (11 Gradients, 11 Hardcoded Hex Colors, Broken CSS Token)
- **Severity:** LOW · **Area:** Frontend/Theme · **Owner:** Devansh · **Status:** FIXED & VERIFIED
- **Repro:** Audit `frontend/css/style.css` for `linear-gradient`, `radial-gradient`, hardcoded hex colors outside `:root` / `[data-theme]`, and stray escape sequences.
- **Expected:** Zero gradients and zero hardcoded hex colors outside theme variable definitions.
- **Actual:** 11 gradients, 11 hardcoded hex colors, and a literal `` `r`n `` token existed in `frontend/css/style.css`.
- **Fix:** Replaced all gradients and hardcoded colors with semantic CSS variables (`var(--...)`) and removed the stray token in `frontend/css/style.css`.
- **Regression Test:** Phase 0.6d static CSS audit (0 gradients, 0 hardcoded hex outside theme blocks) + `test_phase2_7_and_2_8_themes_a11y_performance_responsive_and_firefox`.

### BUG-022 — Stray Literal `` `r`n `` Text Inside Dashboard Status Filter Dropdown
- **Severity:** LOW · **Area:** Frontend/HTML · **Owner:** Devansh · **Status:** FIXED & VERIFIED
- **Repro:** Inspect `frontend/pages/dashboard.html` line 167 (`<select id="statusFilter">`).
- **Expected:** Clean HTML `<option>` tags with proper newline.
- **Actual:** Literal PowerShell escape `` `r`n `` appeared between `under_repair` and `repair_evidence_submitted` options.
- **Fix:** Replaced literal `` `r`n `` with newline in `frontend/pages/dashboard.html`; scanned entire `frontend/` and `backend/` tree (`STRAY_RN: []`).
- **Regression Test:** `tests/test_week10_frontend_and_scenarios.py::test_phase2_4_dashboard_filters_and_escape_modal`.

---

## Prime Directive 3 — Written Justification for Legacy Test Adjustments

Per Prime Directive 3 (*"Fix the code, never the test — only change a test if the test itself is provably wrong, and justify it in writing"*), exactly **4 legacy test files** from Weeks 2–6 were updated ONLY because they asserted behavior that was provably insecure or bypassed the Week 9 workflow:

1. **`backend/test_auth.py` (line 322):** Previously sent an **unauthenticated** `POST /api/v1/reports` containing `reporter_id` in the body and asserted `reporter_id` was accepted. After BUG-004 fixed `reporter_id` spoofing, unauthenticated requests rightly ignore `reporter_id`. Updated the test to pass `Authorization: Bearer <citizen_token>` so it tests legitimate authenticated reporting.
2. **`backend/test_crud.py`:** Legacy Week 2 unauthenticated `/users` and `/reports` CRUD tests ran before Week 3 RBAC existed. Updated test requests to authenticate with appropriate Admin/Officer tokens rather than disabling RBAC.
3. **`backend/test_lifecycle_api.py`:** Helper seeded a `"closed"` report by passing `status="closed"` to unauthenticated `POST /reports` and asserted `UNDER_REPAIR -> CLOSED` directly. After BUG-004 closed workflow bypasses, updated the test helper to pass Admin headers and follow canonical transitions.
4. **`backend/test_municipal_reports_api.py` (line 220):** Helper similarly passed `status="closed"` on unauthenticated `POST /reports`. Updated helper to pass Admin authentication headers.
