"""CivicSight Backend Main Application (Week 4)"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.db.database import check_db_connection
from app.db.init_db import init_db
from app.api.v1.router import api_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.reports import router as reports_router


# Ensure base upload directories exist
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_BASE_DIR = os.path.join(BACKEND_DIR, "uploads")
os.makedirs(os.path.join(UPLOAD_BASE_DIR, "reports"), exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown routines."""
    init_db()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for CivicSight - Smart Road Damage Detection & Municipal Repair System",
    version="0.4.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files for Uploaded Report Photos
app.mount("/uploads", StaticFiles(directory=UPLOAD_BASE_DIR), name="uploads")

# Mount Versioned API Routes (/api/v1)
app.include_router(api_router)

# Mount /auth at root level for seamless client requests
app.include_router(auth_router)

# Mount /reports at root level as well for direct POST /reports requests
app.include_router(reports_router)


@app.get("/", tags=["System"])
def read_root():
    """Returns basic service metadata and current phase status."""
    return {
        "project": "CivicSight",
        "service": "CivicSight Backend Core API",
        "version": "0.4.0",
        "phase": "Week 4 - End-to-End Reporting Workflow, Spatial Maps & ML Baseline",
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
