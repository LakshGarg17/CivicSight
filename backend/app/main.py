"""CivicSight Backend Main Application (Week 4)"""

import json
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.db.database import check_db_connection
from app.db.init_db import init_db
from app.api.v1.router import api_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.reports import router as reports_router
from app.api.v1.endpoints.relations import router as relations_router

logger = logging.getLogger("civicsight.main")

# Ensure base upload directories exist
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_BASE_DIR = os.path.join(BACKEND_DIR, "uploads")
UPLOAD_REPORTS_DIR = os.path.join(UPLOAD_BASE_DIR, "reports")
os.makedirs(UPLOAD_REPORTS_DIR, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_BASE_DIR, "evidence"), exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown routines."""
    init_db()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for CivicSight - Smart Road Damage Detection & Municipal Repair System",
    version="1.0.0-rc1",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Enable strict CORS (never wildcard '*' when allow_credentials=True)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Applies baseline HTTP security headers across all responses."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(self)")
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Prevents leaking stack traces, SQL queries, or server file paths to clients."""
    logger.error("Unhandled server error on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again later."},
    )


# Mount Static Files ONLY for Citizen Report Photos (NEVER mount /uploads/evidence publicly!)
# Repair evidence files are served exclusively through authenticated GET /api/v1/reports/{id}/evidence/{eid}/file
app.mount("/uploads/reports", StaticFiles(directory=UPLOAD_REPORTS_DIR), name="uploads_reports")

FRONTEND_DIR = os.path.join(os.path.dirname(BACKEND_DIR), "frontend")


def _load_public_maps_config() -> dict:
    """Reads ONLY public browser Google Maps config from frontend/.env if present (never logs keys)."""
    cfg = {}
    env_path = os.path.join(FRONTEND_DIR, ".env")
    if os.path.isfile(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    trimmed = line.strip()
                    if not trimmed or trimmed.startswith("#") or "=" not in trimmed:
                        continue
                    k, v = trimmed.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k in ("GOOGLE_MAPS_API_KEY", "VITE_GOOGLE_MAPS_API_KEY") and v:
                        cfg["GOOGLE_MAPS_API_KEY"] = v
                    elif k in ("GOOGLE_MAPS_MAP_ID", "VITE_GOOGLE_MAPS_MAP_ID") and v:
                        cfg["GOOGLE_MAPS_MAP_ID"] = v
        except Exception:
            pass
    return cfg


@app.get("/frontend/js/config.local.js", include_in_schema=False)
def serve_frontend_local_config():
    """Serves local frontend Google Maps config if present, or a clean empty stub (no 404 console errors)."""
    local_cfg_path = os.path.join(FRONTEND_DIR, "js", "config.local.js")
    if os.path.isfile(local_cfg_path):
        with open(local_cfg_path, "r", encoding="utf-8") as fh:
            return Response(content=fh.read(), media_type="application/javascript")
    cfg = _load_public_maps_config()
    body = f"window.CIVICSIGHT_CONFIG = Object.assign({{}}, window.CIVICSIGHT_CONFIG || {{}}, {json.dumps(cfg)});\n"
    return Response(content=body, media_type="application/javascript")


# Mount Static Files for Frontend Web Application
if os.path.isdir(FRONTEND_DIR):
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

# Mount Versioned API Routes (/api/v1)
app.include_router(api_router)

# Mount /auth at root level for seamless client requests
app.include_router(auth_router)

# Mount /reports at root level as well for direct POST /reports requests
app.include_router(reports_router)

# Mount /report-relations at root level for direct PATCH /report-relations/{id} requests
app.include_router(relations_router)


@app.get("/", tags=["System"])
def read_root():
    """Returns basic service metadata and current phase status."""
    return {
        "project": "CivicSight",
        "service": "CivicSight Backend Core API",
        "version": "0.7.0",
        "phase": "Week 7 - Prototype Integration (End-to-End Real Pipeline)",
        "workflow": "Report -> Detect -> Prioritize -> Verify -> Assign -> Repair -> Close",
        "status": "online",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "reports": "/api/v1/reports (or /reports)",
            "auth_register": "/api/v1/auth/register (or /auth/register)",
            "auth_login": "/api/v1/auth/login (or /auth/login)",
            "auth_me": "/api/v1/auth/me",
            "users": "/api/v1/users",
        },
    }


@app.get("/health", tags=["System"])
def health_check():
    """System health check endpoint verifying application status and PostgreSQL connectivity."""
    db_status = check_db_connection()
    overall_status = "ok" if db_status["reachable"] else "degraded"

    return {
        "status": "ok",
        "system_health": overall_status,
        "database": db_status,
    }
