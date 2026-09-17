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
    """The gate reports outbox lag and agrees with its own threshold.

    Asserting a flat 200 here asserts that the ambient queue happens to be
    drained, which is a fact about the environment rather than about this code.
    It holds on CI's throwaway Postgres because the database starts empty and
    this is an early test; against a long-lived database it fails whenever any
    pending event is older than the threshold and no worker is running — which
    says nothing about whether the endpoint works.

    So assert the contract instead: the gate always reports lag_seconds and
    pending_count, and its verdict follows its own rule. That also covers the
    503 branch, which a flat 200 assertion never reaches.
    """
    import os

    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL required")
    threshold = int(os.getenv("WORKER_LAG_THRESHOLD_SECONDS", "300"))
    with TestClient(app) as client:
        response = client.get("/health/worker")
        assert response.status_code in (200, 503)
        body = response.json()
        assert isinstance(body["lag_seconds"], int)
        assert isinstance(body["pending_count"], int)

        backlog_is_stale = body["lag_seconds"] > threshold and body["pending_count"] > 0
        if backlog_is_stale:
            assert response.status_code == 503
            assert body["status"] == "error"
            assert body["worker"] == "lag_exceeded"
        else:
            assert response.status_code == 200
            assert body["status"] == "ok"
            assert body["worker"] == "healthy"
