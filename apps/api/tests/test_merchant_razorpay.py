"""Razorpay merchant credential connect + verify.

Covers: credentials are encrypted at rest (no plaintext secret in the row),
the status machine (not_connected -> pending -> active | invalid_credentials),
and that a bad key pair is reported, not raised. The live Razorpay call is
stubbed — no network, no real keys.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_core.db import get_database_url
from platform_core.payments.razorpay import VerificationResult
from platform_core.services import merchant as merchant_mod
from platform_testing.db_helpers import ensure_auth_user
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"
pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")


def _async_url() -> str:
    url = get_database_url()
    assert url
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


def _token(sub: uuid.UUID, email: str) -> str:
    return jwt.encode(
        {"sub": str(sub), "email": email, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


def _seed(user_id: uuid.UUID, email: str) -> None:
    async def _run() -> None:
        engine = create_async_engine(_async_url(), poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await ensure_auth_user(session, user_id, email)
            await session.commit()
        await engine.dispose()

    asyncio.run(_run())


def _merchant_row(business_id: str) -> dict[str, Any] | None:
    async def _run() -> dict[str, Any] | None:
        engine = create_async_engine(_async_url(), poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            res = await session.execute(
                text(
                    "SELECT status, encrypted_credentials, provider_metadata, verification_error "
                    "FROM payments_merchant_connections "
                    "WHERE business_id = :b AND provider = 'razorpay'"
                ),
                {"b": business_id},
            )
            r = res.first()
        await engine.dispose()
        return dict(r._mapping) if r else None

    return asyncio.run(_run())


@pytest.fixture
def owner(monkeypatch: Any) -> dict[str, str]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    uid = uuid.uuid4()
    email = f"{uid}@example.com"
    _seed(uid, email)
    return {"Authorization": f"Bearer {_token(uid, email)}"}


def _make_business(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"RZP {uuid.uuid4().hex[:8]}", "business_type": "retail"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    bid = str(resp.json()["data"]["business"]["id"])
    r = client.post(f"/v1/b/{bid}/modules/payments/enable", headers=headers)
    assert r.status_code == 200, r.text
    return bid


def _stub_verify(monkeypatch: Any, result: VerificationResult) -> None:
    async def _fake(key_id: str, key_secret: str) -> VerificationResult:
        return result

    # merchant.py imported `verify_key_pair` by name — patch it there.
    monkeypatch.setattr(merchant_mod, "verify_key_pair", _fake)


def test_connect_stores_encrypted_and_verifies(owner: dict[str, str], monkeypatch: Any) -> None:
    _stub_verify(monkeypatch, VerificationResult(True, "ok"))

    with TestClient(app) as client:
        bid = _make_business(client, owner)
        resp = client.post(
            f"/v1/platform/businesses/{bid}/payments/razorpay/connect",
            json={"key_id": "rzp_test_ABCDEF123456", "key_secret": "supersecretvalue"},
            headers=owner,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "active"
        assert data["key_id"] == "rzp_test_ABCDEF123456"
        assert data["has_credentials"] is True
        assert "supersecretvalue" not in str(data)

        row = _merchant_row(bid)
        assert row is not None
        assert "supersecretvalue" not in (row["encrypted_credentials"] or "")
        assert row["encrypted_credentials"]
        assert "key_secret" not in (row["provider_metadata"] or {})


def test_bad_credentials_reported_not_raised(owner: dict[str, str], monkeypatch: Any) -> None:
    _stub_verify(monkeypatch, VerificationResult(False, "Razorpay rejected these credentials (401)."))

    with TestClient(app) as client:
        bid = _make_business(client, owner)
        resp = client.post(
            f"/v1/platform/businesses/{bid}/payments/razorpay/connect",
            json={"key_id": "rzp_live_wrongwrong99", "key_secret": "nope"},
            headers=owner,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "invalid_credentials"
        assert "401" in data["verification_error"]


def test_malformed_key_id_rejected(owner: dict[str, str], monkeypatch: Any) -> None:
    _stub_verify(monkeypatch, VerificationResult(True, ""))
    with TestClient(app) as client:
        bid = _make_business(client, owner)
        resp = client.post(
            f"/v1/platform/businesses/{bid}/payments/razorpay/connect",
            json={"key_id": "not-a-razorpay-key", "key_secret": "x"},
            headers=owner,
        )
        assert resp.status_code == 422
        assert "Razorpay Key ID" in resp.text


def test_verify_without_connect_is_a_clean_error(owner: dict[str, str]) -> None:
    with TestClient(app) as client:
        bid = _make_business(client, owner)
        resp = client.post(
            f"/v1/platform/businesses/{bid}/payments/razorpay/verify", headers=owner
        )
        assert resp.status_code == 422
        assert "Connect Razorpay first" in resp.text


def test_crypto_round_trip(monkeypatch: Any) -> None:
    monkeypatch.delenv("PAYMENT_CREDENTIAL_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    import importlib

    from platform_core import crypto

    importlib.reload(crypto)
    try:
        token = crypto.encrypt_secret("rzp_secret_material")
        assert token != "rzp_secret_material"
        assert crypto.decrypt_secret(token) == "rzp_secret_material"
        with pytest.raises(ValueError):
            crypto.decrypt_secret("not-a-valid-token")
    finally:
        importlib.reload(crypto)
