"""Stage 5 — Booking deposits via PaymentAttemptService."""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import jwt
import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_core.db import get_database_url
from platform_core.models import PlatformOutboxEvent
from platform_testing.db_helpers import ensure_auth_user
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"


def _token(sub: uuid.UUID, email: str) -> str:
    return jwt.encode(
        {
            "sub": str(sub),
            "email": email,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


def _headers(user_id: uuid.UUID, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(user_id, email)}"}


def _seed(user_id: uuid.UUID, email: str) -> None:
    async def _run() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await ensure_auth_user(session, user_id, email)
            await session.commit()
        await engine.dispose()

    asyncio.run(_run())


@pytest.fixture
def owner(monkeypatch: Any) -> tuple[dict[str, str], uuid.UUID]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed(user_id, email)
    return _headers(user_id, email), user_id


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_deposit_collection_and_payment_status(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    headers, _ = owner
    client = TestClient(app)
    business = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"Deposit Co {uuid.uuid4().hex[:6]}", "business_type": "salon"},
        headers=headers,
    ).json()["data"]["business"]
    bid = cast(str, business["id"])
    for mid in ("bookings", "payments", "workforce", "offerings-catalog"):
        assert client.post(f"/v1/b/{bid}/modules/{mid}/enable", headers=headers).status_code == 200

    policy = client.patch(
        f"/v1/platform/businesses/{bid}/bookings-policy",
        json={"require_deposit": True, "deposit_amount": 25.0},
        headers=headers,
    )
    assert policy.status_code == 200, policy.text
    assert policy.json()["data"]["require_deposit"] is True

    location_id = next(
        loc["id"]
        for loc in client.get(
            f"/v1/platform/businesses/{bid}/locations", headers=headers
        ).json()["data"]
        if loc["is_primary"]
    )
    start = (datetime.now(timezone.utc) + timedelta(hours=20)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(hours=21)).isoformat()
    created = client.post(
        f"/v1/platform/businesses/{bid}/bookings",
        json={
            "location_id": location_id,
            "reservation_mode": "appointment",
            "title": "Deposit booking",
            "starts_at": start,
            "ends_at": end,
            "payment_method": "cod",
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["deposit_required"] is True
    assert float(data["deposit_amount"]) == 25.0
    # Offline deposit attempt → pending_offline (or deposit_paid if auto-succeeds)
    assert data["payment_status"] in {"pending_offline", "deposit_paid", "pending"}

    async def _outbox() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            row = await session.execute(
                select(PlatformOutboxEvent.event_type).where(
                    PlatformOutboxEvent.business_id == uuid.UUID(bid),
                    PlatformOutboxEvent.event_type == "booking.deposit_collected",
                )
            )
            assert row.first() is not None
        await engine.dispose()

    asyncio.run(_outbox())
