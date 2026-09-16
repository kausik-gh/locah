import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi.testclient import TestClient
from platform_api.main import app

TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"


def _make_token(
    *,
    sub: str | None = None,
    email: str = "test@example.com",
    secret: str = TEST_JWT_SECRET,
    expired: bool = False,
) -> str:
    auth_user_id = sub or str(uuid.uuid4())
    exp = datetime.now(timezone.utc) + (timedelta(hours=-1) if expired else timedelta(hours=1))
    return jwt.encode(
        {"sub": auth_user_id, "email": email, "exp": exp},
        secret,
        algorithm="HS256",
    )


def test_me_requires_authorization_header() -> None:
    with TestClient(app) as client:
        response = client.get("/me")
        assert response.status_code == 401


def test_me_rejects_invalid_token(monkeypatch: Any) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    with TestClient(app) as client:
        response = client.get(
            "/me",
            headers={"Authorization": "Bearer not-a-valid-token"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid token"


def test_me_rejects_expired_token(monkeypatch: Any) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    token = _make_token(expired=True)

    with TestClient(app) as client:
        response = client.get(
            "/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Token has expired"


def test_me_hs256_token_without_configured_secret_is_401(monkeypatch: Any) -> None:
    # Dual-mode verifier: an HS256 token it cannot check (no SUPABASE_JWT_SECRET,
    # and no JWKS config for this alg) is an unverifiable token -> 401, not a
    # 500. The operator sees `jwt.verifier_misconfigured` in the logs.
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_JWKS_URL", raising=False)
    token = _make_token()

    with TestClient(app) as client:
        response = client.get(
            "/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid token"
