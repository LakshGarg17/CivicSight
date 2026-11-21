# CivicSight — Known Limitations & Workarounds (Week 10 Feature Freeze)

**Release Candidate:** Week 10 Quality Gate (Feature Freeze)  
**Last Updated:** November 18, 2026

This document transparently records every known functional, security, infrastructure, and machine-learning limitation present at Feature Freeze, along with practical workarounds and deferred recommendations ("Out of scope / recommended later").

---

## 1. Machine Learning Limitations

1. **Moderate Recall & Weakest Class (`D40` Potholes):**
   - Official 3,285-image test set: `mAP@0.5 = 0.5472`, `D40 mAP@0.5 = 0.4688`.
   - Week 10 160-image operating-point evaluation (`conf=0.25`): `D40` achieved **0.9000 precision** but **0.4444 recall**.
   - **Impact:** Shallow, shadowed, distant, or water-filled potholes can be missed (`ML_NO_DETECTIONS`).
   - **Workaround:** All reports remain in `submitted` status regardless of ML result. Municipal Officers must visually inspect photos before verifying or rejecting, and can manually override priority with a mandatory audit reason (`POST /reports/{id}/override-priority`).
2. **Camera Domain Shift & Adverse Lighting:**
   - The model is trained on RDD2022 (predominantly daylight vehicle/motorcycle dashcams and nadir drones). Handheld smartphone close-ups, night/flash shots, wet reflections, snow, and heavy motion blur degrade detection accuracy.
   - **Workaround:** Advise citizens to photograph road damage in daylight from ~1–2 m away with clear pavement framing.
3. **No Automated Repair Quality Verification:**
   - The model only detects 4 defect classes (`D00`, `D10`, `D20`, `D40`) on initial `BEFORE` photos. It does not evaluate `AFTER` maintenance evidence photos.
   - **Workaround:** Final repair closure is strictly gated behind human Municipal Officer side-by-side Before/After review (`POST /reports/{id}/final-verify`).
4. **Synchronous In-Process Background Inference:**
   - ML inference executes in FastAPI `BackgroundTasks` (in-process threadpool) at ~130 ms mean / ~170 ms p95 per image on CPU. Under high concurrent upload spikes (dozens of simultaneous citizen reports), CPU contention could queue background tasks and delay `ML_COMPLETE` updates.
   - **Workaround / Recommended Later:** Offload inference to a dedicated worker queue (Celery / RQ + Redis) or GPU inference microservice in production.

---

## 2. Maps & Geolocation Limitations

1. **Google Maps API Key & Billing Requirement:**
   - Interactive Google Maps (`AdvancedMarkerElement`, `Map`, `Geocoder`) requires a valid `VITE_GOOGLE_MAPS_API_KEY` and `VITE_GOOGLE_MAPS_MAP_ID` configured in `frontend/.env` or `frontend/js/config.local.js` (never committed).
   - **Impact:** Without a configured key—or if quota is exhausted or `maps.googleapis.com` is blocked by network/ad-blocker—map canvases display the graceful fallback notice (`"Map unavailable: API key not configured"` or `"Map failed to load..."`).
   - **Workaround:** Every core workflow remains 100% operational without live Google Maps tiles: citizens can still use browser geolocation or enter/adjust coordinates manually and submit reports; officers can still inspect, verify, assign, and close every report via the triage queue table.
2. **Desktop Browser Geolocation Inaccuracy:**
   - On desktop browsers without a GPS chip, `navigator.geolocation.getCurrentPosition` relies on Wi-Fi/IP triangulation, which can be off by 50–500 meters (or denied in corporate networks).
   - **Workaround:** Citizens can drag the map pin or directly edit the Latitude/Longitude inputs and enter a street landmark description.
3. **No Offline Tile Caching / PWA Support:**
   - If the user loses network connectivity completely during submission, the form preserves entered values and shows a retryable error message, but does not queue reports offline in IndexedDB.
   - **Recommended Later:** Add optional background sync / draft persistence in `localStorage` or IndexedDB.

---

## 3. Security & Auth Limitations

1. **No Login Rate Limiting or Account Lockout:**
   - `POST /api/v1/auth/login` uses constant-time bcrypt comparison and uniform error messages to prevent account enumeration, but does not enforce per-IP or per-account brute-force throttling or temporary lockouts.
   - **Workaround / Recommended Later:** Deploy behind a reverse proxy (Nginx / Cloudflare / API Gateway) with strict rate limits (e.g., 10 login requests/min per IP) and add application-level rate limiting (`slowapi`) post-freeze.
2. **JWT Stored in `localStorage` & Stateless Revocation:**
   - The plain HTML/JS frontend stores the Bearer JWT in `localStorage` (30-minute default expiry). Logout clears `localStorage` client-side, and deactivated accounts (`is_active=False`) are immediately rejected server-side on every request, but an active user's already-issued token cannot be individually revoked prior to expiry without a token blocklist.
   - **Recommended Later:** Migrate to `HttpOnly; SameSite=Lax; Secure` cookies plus short-lived access + refresh token rotation with server-side revocation.
3. **No Automated Malware Scanning on Uploads:**
   - Uploaded photos are validated strictly by extension, size limit (10 MB), magic bytes, and Pillow full image decode (`verify()` + `load()`), and saved under random UUID filenames. However, no antivirus scanner (e.g. ClamAV) scans files.
4. **Transitive Python Dependency Advisories (`pip-audit`):**
   - `pip-audit` on the current Python 3.14 environment reported 60 advisories across 5 installed packages (`certifi 2026.7.22`, `filelock 4.0.11`, `opentelemetry-api 1.45.0`, `pillow 12.3.0`, `setuptools 84.0.0`) — several of which come from transitive/dev packages (`torch`/`ultralytics`/`pytest` ecosystem). Upgrading these packages requires re-verifying PyTorch/Ultralytics compatibility on Python 3.14.
   - **Workaround:** Track pinned versions in `backend/requirements.txt` and patch `pillow`/`filelock`/`certifi` in the next post-freeze maintenance window.

---

## 4. Database, Infrastructure & Environment Limitations

1. **Default Local Development Database Is SQLite:**
   - `backend/.env` defaults to SQLite (`civicsight.db`) for zero-setup local runs, while PostgreSQL is supported via `DATABASE_URL`. SQLite serializes concurrent writes (`busy_timeout=5000`, `WAL` mode enabled), which is sufficient for local development and demos but not recommended for multi-worker production deployments.
   - **Workaround:** Set `DATABASE_URL=postgresql://user:pass@host:5432/civicsight` in `backend/.env` for multi-worker production deployments (see `DEPLOYMENT_CHECKLIST.md`).
2. **Local Filesystem Media Storage:**
   - Citizen report photos (`backend/uploads/reports/`) and protected maintenance evidence (`backend/uploads/evidence/`) are stored on local disk. Multi-instance horizontal scaling would require shared object storage (S3 / GCS / Azure Blob) with signed URLs.
3. **Git Repository Status:**
   - Git was initialized in Phase 0 on branch `integration-audit-snapshot` and tagged `pre-integration-audit` (commit `6eae5c3`). Full commit history and tracked files were verified clean of secrets (0 leaks). Release candidate tagged as `v1.0.0-rc3`.
4. **Spline 3D Hero Not Implemented:**
   - Phase 0.6e audit confirmed no Spline 3D canvas was implemented; the UI uses GSAP + Lottie animations (`frontend/js/animations.js`) with `prefers-reduced-motion` support and a strict monochrome light/dark theme.
5. **Orphan Uploads Accumulation:**
   - 150 citizen report photos and 25 evidence photos on disk were unreferenced by the active database, left behind from mock rollbacks and early testing.
   - **Workaround:** Added safe utility `scripts/cleanup_orphan_uploads.py` to audit and purge unreferenced uploads without touching database records.

---

## 5. Out of Scope / Recommended Later (Post-Demo Backlog)

- Per-IP login & upload rate limiting (`slowapi` + reverse-proxy WAF)
- Email/SMS notifications to citizens when their report moves to `verified`, `rejected`, or `closed`
- Multi-worker asynchronous ML queue (Celery/Redis) + GPU inference deployment
- Dedicated `POST /api/v1/reports/mine` citizen history dashboard page
- Cloud object storage (S3/GCS) for report & repair evidence images
- Alembic formal schema migration versioning (replacing startup `ALTER TABLE` helpers)
- Automated Lighthouse CI performance & accessibility regression gates
- Fine-tuning YOLOv8s on local smartphone road photos to improve `D40` pothole recall
