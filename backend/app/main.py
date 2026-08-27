from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.database import check_db_connection

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for CivicSight - Smart Road Damage Detection & Municipal Repair System",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["System"])
def read_root():
    """Returns basic service metadata and current phase status."""
    return {
        "project": "CivicSight",
        "service": "CivicSight Backend Core API",
        "version": "0.1.0",
        "phase": "Week 1 Foundation",
        "workflow": "Report -> Detect -> Prioritize -> Verify -> Assign -> Repair -> Close",
        "status": "online"
    }


@app.get("/health", tags=["System"])
def health_check():
    """System health check endpoint verifying application status and PostgreSQL connectivity."""
    db_status = check_db_connection()
    overall_status = "ok" if db_status["reachable"] else "degraded"

    return {
        "status": "ok",
        "system_health": overall_status,
        "database": db_status
    }
