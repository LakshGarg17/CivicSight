# CivicSight — Production Deployment Checklist & Smoke Test Guide

**Target Release:** `v1.0.0-rc3`  
**System:** CivicSight — Smart Road Damage Detection & Municipal Repair Management  
**Stack:** FastAPI, PostgreSQL / SQLite (WAL), PyTorch / YOLOv8s, Modern HTML5/ES6 Frontend with Google Maps JavaScript API

---

## 1. Pre-Deployment Configuration Audit

Before deploying to staging or production, verify every configuration value. **Never commit production secrets to Git.**

| Variable | Recommended Production Setting | Verification Method | Security Note |
|---|---|---|---|
| `ENVIRONMENT` | `production` | Check `backend/.env` | Disables debug logs and development reloads |
| `SECRET_KEY` | 64+ char random hex string | `openssl rand -hex 32` | Critical: signs all JWT access tokens |
| `ALGORITHM` | `HS256` | Check `backend/.env` | Standard HMAC-SHA256 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` (or `30` for high security) | Check `backend/.env` | Limits exposure window of stolen tokens |
| `DATABASE_URL` | `postgresql://user:pass@host:5432/civicsight` | Verify via `psql` connection | Highly recommended over SQLite for production |
| `CORS_ORIGINS` | Explicit domain list (e.g. `https://civicsight.city.gov`) | Never set to `*` | Prevents cross-origin credential leaks |
| `GOOGLE_MAPS_API_KEY` | Restricted Google Cloud API key | Check Google Cloud Console | Restrict to HTTP referrers matching production domain |
| `GOOGLE_MAPS_MAP_ID` | Production Vector Map ID | Google Cloud Console | Required for `AdvancedMarkerElement` |
| `MAX_IMAGE_SIZE_BYTES` | `15728640` (15 MB) | Check `backend/app/core/config.py` | Enforced by multipart upload validator |

---

## 2. Database Migration & Setup (PostgreSQL)

While development uses SQLite with WAL mode, production deployments must use PostgreSQL to support high-concurrency connection pools.

### Step 2.1: Provision Database
```bash
sudo -u postgres psql -c "CREATE USER civicsight_app WITH PASSWORD 'SECURE_RANDOM_PASSWORD';"
sudo -u postgres psql -c "CREATE DATABASE civicsight_prod OWNER civicsight_app;"
```

### Step 2.2: Execute Schema Initialization
```bash
cd backend
python -c "from app.db.init_db import init_db; init_db()"
```

### Step 2.3: Verify Indexes & Integrity
Verify in `psql` that the following composite indexes and unique constraints are active:
```sql
\c civicsight_prod
-- Verify composite spatial and triage indexes
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'reports';
-- ix_reports_lat_lng: (latitude, longitude)
-- ix_reports_status_priority: (status, priority)
-- ix_reports_created_at: (created_at DESC)

-- Verify Single Active Assignment Constraint
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'assignments';
-- ux_assignments_active_per_report: UNIQUE(report_id) WHERE (is_active = TRUE)
```

---

## 3. Web Server & Reverse Proxy Configuration (Nginx)

### Mandatory HTTPS Requirement
> [!IMPORTANT]
> The HTML5 Geolocation API (`navigator.geolocation`) **requires a secure context (HTTPS)**. Browsers will refuse location permissions over plain HTTP (except on `localhost`).

```nginx
# /etc/nginx/sites-available/civicsight.conf

upstream fastapi_backend {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name civicsight.city.gov;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name civicsight.city.gov;

    ssl_certificate /etc/letsencrypt/live/civicsight.city.gov/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/civicsight.city.gov/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Baseline Security Headers
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "geolocation=(self)" always;

    # Maximum upload size for citizen damage photos
    client_max_body_size 20M;

    # Frontend Static UI
    location / {
        root /var/www/civicsight/frontend;
        index index.html;
        try_files $uri $uri/ =404;
    }

    # Public Citizen Report Photos (Read-Only)
    location /uploads/reports/ {
        alias /var/www/civicsight/backend/uploads/reports/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    # NOTE: /uploads/evidence/ MUST NOT be mapped to a static route!
    # Evidence photos are strictly authenticated via GET /api/v1/reports/{id}/evidence/{eid}/file

    # FastAPI Core API & Health Endpoints
    location /api/ {
        proxy_pass http://fastapi_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health {
        proxy_pass http://fastapi_backend/health;
    }
}
```

---

## 4. Process Supervision (Systemd)

Create a systemd service file `/etc/systemd/system/civicsight.service`:

```ini
[Unit]
Description=CivicSight FastAPI Backend Application
After=network.target postgresql.service

[Service]
Type=simple
User=civicsight
Group=civicsight
WorkingDirectory=/var/www/civicsight/backend
Environment="PATH=/var/www/civicsight/.venv/bin"
ExecStart=/var/www/civicsight/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4 --proxy-headers
Restart=always
RestartSec=5

# Sandboxing & Resource Limits
LimitNOFILE=65535
MemoryHigh=3500M
MemoryMax=4000M

[Install]
WantedBy=multi-user.target
```

Reload and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now civicsight
```

---

## 5. Maintenance Cron Jobs

Add daily scheduled cleanup for orphaned upload files:
```bash
# /etc/cron.daily/civicsight-maintenance
#!/bin/bash
cd /var/www/civicsight
.venv/bin/python scripts/cleanup_orphan_uploads.py >> /var/log/civicsight_cleanup.log 2>&1
```

---

## 6. 5-Minute Post-Deployment Smoke Test Protocol

Execute the following sequential test to guarantee end-to-end operational health:

### Step 1: Health & Database Connectivity Check
```bash
curl -f -s https://civicsight.city.gov/health
```
**Expected Response:** `{"status":"ok","database":{"reachable":true,...}}`

### Step 2: Authentication Handshake
```bash
TOKEN=$(curl -s -X POST https://civicsight.city.gov/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"officer1@civicsight.gov","password":"PROD_PASSWORD"}' | jq -r .access_token)
test -n "$TOKEN" && echo "Auth Token Acquired: PASS" || echo "Auth FAILED"
```

### Step 3: Citizen Incident Report Creation
```bash
curl -s -X POST https://civicsight.city.gov/api/v1/reports \
  -F "description=Smoke test pothole" \
  -F "latitude=37.7749" \
  -F "longitude=-122.4194" \
  -F "image=@samples/pothole.jpg" | jq -r '{id, status, ml_status}'
```
**Expected Response:** `{"id": <ID>, "status": "submitted", "ml_status": "ML_PENDING" or "ML_COMPLETE"}`

### Step 4: ML Inference & Priority Verification
Wait 2 seconds and fetch report details:
```bash
curl -s https://civicsight.city.gov/api/v1/reports/<ID> | jq -r '{status, priority, priority_score, ml_status, detections: (.detection_results | length)}'
```
**Expected Output:** `ml_status: "ML_COMPLETE"`, `priority: "HIGH"`, `priority_score: > 60`

### Step 5: Officer Lifecycle Transitions
```bash
# Verify
curl -s -X POST https://civicsight.city.gov/api/v1/reports/<ID>/verify \
  -H "Authorization: Bearer $TOKEN" | jq -r .status
# Expected: "verified"

# Assign
curl -s -X POST https://civicsight.city.gov/api/v1/reports/<ID>/assign \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"staff_id": 5, "note": "Dispatch crew"}' | jq -r .status
# Expected: "assigned"
```

### Smoke Test Passed! System is verified and ready for live operations.
