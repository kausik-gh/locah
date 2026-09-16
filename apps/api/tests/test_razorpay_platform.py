"""Platform Razorpay Route — unit tests with no live Razorpay network.

Covers amount split, webhook event mapping, and Enable Online Payments when
platform credentials or Route are missing (honest failure, COD still works).
"""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

import pytest

from platform_core.payments.provider_adapter import normalize_payment_event
from platform_core.payments.razorpay import split_amount, platform_credentials


def test_split_amount_zero_fee() -> None:
    fee, business = split_amount(Decimal("100.00"), 0)
    assert fee == Decimal("0.00")
    assert business == Decimal("100.00")


def test_split_amount_two_percent() -> None:
    fee, business = split_amount(Decimal("100.00"), 200)
    assert fee == Decimal("2.00")
    assert business == Decimal("98.00")


def test_platform_credentials_absent(monkeypatch: Any) -> None:
    monkeypatch.delenv("RAZORPAY_KEY_ID", raising=False)
    monkeypatch.delenv("RAZORPAY_KEY_SECRET", raising=False)
    assert platform_credentials() is None


def test_platform_credentials_reject_non_razorpay_prefix(monkeypatch: Any) -> None:
    monkeypatch.setenv("RAZORPAY_KEY_ID", "pk_test_not_razorpay")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret")
    assert platform_credentials() is None


def test_normalize_razorpay_captured_event() -> None:
    event = normalize_payment_event(
        "razorpay",
        {
            "id": "evt_1",
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_1",
                        "order_id": "order_1",
                        "status": "captured",
                        "notes": {"locah_payment_id": "11111111-1111-1111-1111-111111111111"},
                    }
                }
            },
        },
    )
    assert event["status"] == "succeeded"
    assert event["order_id"] == "order_1"
    assert event["payment_id"] == "11111111-1111-1111-1111-111111111111"


def test_normalize_stub_payload_unchanged() -> None:
    event = normalize_payment_event(
        "stub",
        {"payment_id": "abc", "status": "succeeded", "event_id": "e1"},
    )
    assert event["payment_id"] == "abc"
    assert event["status"] == "succeeded"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_enable_platform_payments_without_route_is_honest(
    monkeypatch: Any,
) -> None:
    """Owners never paste keys. Missing Route is reported, not faked as active."""
    import uuid
    from datetime import datetime, timedelta, timezone

    import jwt
    from fastapi.testclient import TestClient
    from platform_api.main import app
    from platform_core.payments.razorpay import LinkedAccountResult
    from platform_core.services import merchant as merchant_mod
    from platform_testing.db_helpers import ensure_auth_user
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    from platform_core.db import get_database_url
    import asyncio

    TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    async def _fake(*_args: Any, **_kwargs: Any) -> LinkedAccountResult:
        return LinkedAccountResult(
            ok=False,
            account_id=None,
            status=None,
            detail="Razorpay Route is not enabled on the LOCAH platform account.",
            external_dependency=True,
        )

    monkeypatch.setattr(merchant_mod, "create_linked_account", _fake)

    uid = uuid.uuid4()
    email = f"{uid}@example.com"

    async def _seed() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await ensure_auth_user(session, uid, email)
            await session.commit()
        await engine.dispose()

    asyncio.run(_seed())
    token = jwt.encode(
        {"sub": str(uid), "email": email, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(app) as client:
        resp = client.post(
            "/v1/platform/businesses",
            json={"display_name": f"Pay {uuid.uuid4().hex[:8]}", "business_type": "retail"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        bid = resp.json()["data"]["business"]["id"]
        enabled = client.post(f"/v1/b/{bid}/modules/payments/enable", headers=headers)
        assert enabled.status_code == 200, enabled.text
        r = client.post(
            f"/v1/platform/businesses/{bid}/payments/razorpay/enable",
            headers=headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["status"] != "active"
        assert data["connection_mode"] == "platform_route"
        assert data["requires_merchant_keys"] is False
        assert "Route" in (data.get("verification_error") or "")
        assert "key_secret" not in str(data).lower()
