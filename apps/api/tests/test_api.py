from fastapi.testclient import TestClient
from platform_api.main import app
from typing import Any
import pytest


def test_liveness_check() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "message": "Liveness check passed"}


def test_readiness_check_unconfigured(monkeypatch: Any) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with TestClient(app) as client:
        client.app.state.db_session_factory = None  # type: ignore[attr-defined]
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {
            "status": "error",
            "database": "not_configured",
            "message": "Database is not configured",
        }


def test_worker_health_check_configured(monkeypatch: Any) -> None:
    import os

    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL required")
    with TestClient(app) as client:
        response = client.get("/health/worker")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["worker"] == "healthy"
