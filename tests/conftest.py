"""Shared isolated test fixtures for Week 10 Quality Gate suites."""

import os
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.db.database import Base, get_db
from app.db.init_db import init_db
from app.models.models import User, UserRole
from app.core.security import get_password_hash, create_access_token


@pytest.fixture(scope="session")
def isolated_db_path(tmp_path_factory):
    db_dir = tmp_path_factory.mktemp("civicsight_w10_db")
    return db_dir / "week10_test.db"


@pytest.fixture(scope="session")
def test_engine(isolated_db_path):
    engine = create_engine(
        f"sqlite:///{isolated_db_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 15},
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.close()

    init_db(target_engine=engine, seed_users=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def TestSessionLocal(test_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session")
def client(TestSessionLocal, test_engine, monkeypatch_session=None):
    def _override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Patch SessionLocal in ml_service and database so background ML uses the isolated test DB
    import app.db.database as db_mod
    import app.services.ml_service as ml_mod

    orig_db_session = db_mod.SessionLocal
    orig_ml_session = ml_mod.SessionLocal
    db_mod.SessionLocal = TestSessionLocal
    ml_mod.SessionLocal = TestSessionLocal
    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app, raise_server_exceptions=False) as tc:
        yield tc

    app.dependency_overrides.clear()
    db_mod.SessionLocal = orig_db_session
    ml_mod.SessionLocal = orig_ml_session


@pytest.fixture(scope="session")
def seeded_accounts(TestSessionLocal):
    """Returns all 7 Phase 0.7 accounts with tokens and headers."""
    db = TestSessionLocal()
    try:
        specs = {
            "citizen1": ("citizen1@civicsight.org", "Citizen One", UserRole.CITIZEN, "Password123!"),
            "citizen2": ("citizen2@civicsight.org", "Citizen Two", UserRole.CITIZEN, "Password123!"),
            "officer1": ("officer1@civicsight.gov", "Officer Sarah", UserRole.MUNICIPAL_OFFICER, "Password123!"),
            "officer2": ("officer2@civicsight.gov", "Officer Marcus", UserRole.MUNICIPAL_OFFICER, "Password123!"),
            "staff1": ("staff1@civicsight.gov", "Alex Rivera", UserRole.MAINTENANCE_STAFF, "Password123!"),
            "staff2": ("staff2@civicsight.gov", "Marcus Vance", UserRole.MAINTENANCE_STAFF, "Password123!"),
            "admin1": ("admin1@civicsight.gov", "Admin Director", UserRole.ADMIN, "Password123!"),
        }
        accounts = {}
        for key, (email, name, role, pwd) in specs.items():
            user = db.query(User).filter(User.email == email).first()
            if not user:
                user = User(
                    email=email,
                    name=name,
                    role=role,
                    hashed_password=get_password_hash(pwd),
                    is_active=True,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            token = create_access_token(
                subject=user.id,
                claims={"email": user.email, "role": role.value, "name": user.name},
            )
            accounts[key] = {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": role.value,
                "password": pwd,
                "token": token,
                "headers": {"Authorization": f"Bearer {token}"},
            }
        return accounts
    finally:
        db.close()
