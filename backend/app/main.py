"""CivicSight Backend Main Application (Week 3)"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.database import check_db_connection
from app.db.init_db import init_db
from app.api.v1.router import api_router
from app.api.v1.endpoints.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown routines."""
    # Initialize database tables on application launch
    init_db()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for CivicSight - Smart Road Damage Detection & Municipal Repair System",
    version="0.3.0",
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

# Mount Versioned API Routes (/api/v1)
app.include_router(api_router)

# Mount /auth at root level for seamless POST /auth/register and POST /auth/login client requests
app.include_router(auth_router)


@app.get("/", tags=["System"])
def read_root():
    """Returns basic service metadata and current phase status."""
    return {
        "project": "CivicSight",
        "service": "CivicSight Backend Core API",
        "version": "0.3.0",
        "phase": "Week 3 - Authentication, Roles & ML Dataset Preparation",
        "workflow": "Report -> Detect -> Prioritize -> Verify -> Assign -> Repair -> Close",
        "status": "online",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "auth_register": "/api/v1/auth/register (or /auth/register)",
            "auth_login": "/api/v1/auth/login (or /auth/login)",
            "auth_me": "/api/v1/auth/me",
            "users": "/api/v1/users",
            "reports": "/api/v1/reports",
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
