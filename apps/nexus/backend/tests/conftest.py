"""Test configuration. The environment is set before the application is imported."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

TMP_DIR = Path(tempfile.mkdtemp(prefix="nexus-tests-"))
ADMIN_EMAIL = "admin@test.local"
ADMIN_PASSWORD = "test-admin-password-1"

os.environ.update(
    {
        "ENVIRONMENT": "test",
        "SECRET_KEY": "test-secret-key-not-for-production-0123456789",
        "DATABASE_URL": f"sqlite:///{TMP_DIR / 'test.db'}",
        "DATABASE_AUTO_CREATE": "true",
        "BOOTSTRAP_ADMIN_EMAIL": ADMIN_EMAIL,
        "BOOTSTRAP_ADMIN_PASSWORD": ADMIN_PASSWORD,
        "EMBEDDED_WORKER": "false",
        "INGESTION_ENABLED": "false",
        "PUBLISH_DIR": str(TMP_DIR / "published"),
        "PIPELINE_LOCK_PATH": str(TMP_DIR / "pipeline.lock"),
        "ALLOWED_ORIGINS": "http://testserver",
        "LOG_JSON": "false",
        "HEALTH_ALLOW_TCP": "false",
        "LOGIN_RATE_LIMIT": "10000",
        "REGISTER_RATE_LIMIT": "10000",
        "ALLOW_REGISTRATION": "true",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    AuditLog,
    AuthSession,
    Configuration,
    ConfigurationSource,
    Deployment,
    HealthTest,
    HealthTestJob,
    PipelineRun,
    SourceFetch,
    SubscriptionProfile,
    SubscriptionToken,
    Base,
)
from app.services.seed import bootstrap  # noqa: E402
from app.core.db import engine  # noqa: E402

CLEANUP_ORDER = [
    HealthTest,
    HealthTestJob,
    SubscriptionToken,
    SubscriptionProfile,
    ConfigurationSource,
    Configuration,
    SourceFetch,
    PipelineRun,
    AuditLog,
    AuthSession,
    Deployment,
]


@pytest.fixture(scope="session", autouse=True)
def offline_network():
    """No test may reach an external service. DNS answers are deterministic."""
    import socket
    import httpx
    from app.services import fetcher
    patch = pytest.MonkeyPatch()
    patch.setattr(fetcher, "_resolve", lambda host, port: ["93.184.216.34"])
    def deny_http(*args, **kwargs):
        raise httpx.ConnectError("external networking disabled in tests")
    patch.setattr(httpx.HTTPTransport, "handle_request", deny_http)
    yield
    patch.undo()


@pytest.fixture(scope="session")
def client(offline_network):
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_database(client):
    yield
    from app.services import health
    with health._ACTIVE_LOCK:
        threads = list(health._ACTIVE_THREADS.values())
    for thread in threads:
        thread.join(timeout=5)
    db = SessionLocal()
    try:
        for model in CLEANUP_ORDER:
            db.query(model).delete()
        db.commit()
        bootstrap(db)
    finally:
        db.close()
    client.cookies.clear()


def login(client: TestClient, email: str = ADMIN_EMAIL, password: str = ADMIN_PASSWORD) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


@pytest.fixture
def admin(client):
    return {"client": client, "csrf": login(client)}


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
