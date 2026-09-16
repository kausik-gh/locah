"""Stage 4 — Fulfilment kernel: zones, status machine, isolation."""

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
from platform_core.models import PlatformAuditEvent, PlatformOutboxEvent
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


def _create_business(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"Fulfil Co {uuid.uuid4().hex[:8]}", "business_type": "retail"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    business = cast(dict[str, Any], resp.json()["data"]["business"])
    # A fresh Business defaults to visibility="private" (no public URL) —
    # promote to "unlisted" so public checkout endpoints can resolve it.
    assert (
        client.post(
            f"/v1/b/{business['id']}/marketplace/visibility",
            json={"visibility": "unlisted"},
            headers=headers,
        ).status_code
        == 200
    )
    return business


def _enable_modules(client: TestClient, headers: dict[str, str], business_id: str) -> None:
    for mid in ("offerings-catalog", "orders", "inventory", "payments", "fulfilment"):
        resp = client.post(
            f"/v1/b/{business_id}/modules/{mid}/enable",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text


def _primary_location(client: TestClient, headers: dict[str, str], business_id: str) -> str:
    locs = client.get(f"/v1/platform/businesses/{business_id}/locations", headers=headers).json()[
        "data"
    ]
    return cast(str, next(loc["id"] for loc in locs if loc["is_primary"]))


def _product(client: TestClient, headers: dict[str, str], business_id: str) -> str:
    return cast(
        str,
        client.post(
            f"/v1/platform/businesses/{business_id}/products",
            json={
                "title": "Widget",
                "sku": f"W-{uuid.uuid4().hex[:6]}",
                "status": "active",
                "price_amount": 100,
                "visibility": "public",
            },
            headers=headers,
        ).json()["data"]["id"],
    )


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_zone_charge_and_status_machine(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business = _create_business(client, headers)
    bid = business["id"]
    slug = business["slug"]
    _enable_modules(client, headers, bid)
    location_id = _primary_location(client, headers, bid)
    product_id = _product(client, headers, bid)

    zone = client.post(
        f"/v1/b/{bid}/fulfilment/zones",
        json={"name": "Pune", "match_type": "city", "city": "Pune", "charge_amount": 40},
        headers=headers,
    )
    assert zone.status_code == 200, zone.text
    assert zone.json()["data"]["charge_amount"] == 40.0

    settings = client.patch(
        f"/v1/b/{bid}/fulfilment/settings",
        json={"pickup_enabled": True, "delivery_enabled": True},
        headers=headers,
    )
    assert settings.status_code == 200, settings.text

    checkout = client.post(
        f"/v1/public/websites/{slug}/checkout",
        json={
            "items": [{"offering_id": product_id, "quantity": 1}],
            "fulfilment_mode": "delivery",
            "payment_method": "cod",
            "location_id": location_id,
            "delivery_address": {"city": "Pune", "line1": "FC Road"},
            "guest": {"name": "Buyer", "email": f"{uuid.uuid4()}@example.com"},
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert checkout.status_code == 200, checkout.text
    data = checkout.json()["data"]
    job_id = data["fulfilment"]["id"]
    assert data["fulfilment"]["mode"] == "delivery"
    assert data["fulfilment"]["delivery_charge"] == 40.0
    assert data["order"]["total_amount"] == 140.0  # 100 + delivery fee line

    for status in ("preparing", "ready", "out_for_delivery", "delivered"):
        resp = client.patch(
            f"/v1/b/{bid}/fulfilment/jobs/{job_id}/status",
            json={"status": status},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

    async def _audit_outbox() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            outbox = (
                (
                    await session.execute(
                        select(PlatformOutboxEvent).where(
                            PlatformOutboxEvent.business_id == uuid.UUID(bid),
                            PlatformOutboxEvent.event_type == "fulfilment.delivered",
                        )
                    )
                )
                .scalars()
                .first()
            )
            assert outbox is not None
            audit = (
                (
                    await session.execute(
                        select(PlatformAuditEvent).where(
                            PlatformAuditEvent.business_id == uuid.UUID(bid),
                            PlatformAuditEvent.event_type == "fulfilment.status_changed",
                        )
                    )
                )
                .scalars()
                .first()
            )
            assert audit is not None
        await engine.dispose()

    asyncio.run(_audit_outbox())


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_pickup_cannot_out_for_delivery(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business = _create_business(client, headers)
    bid = business["id"]
    slug = business["slug"]
    _enable_modules(client, headers, bid)
    product_id = _product(client, headers, bid)
    client.patch(
        f"/v1/b/{bid}/fulfilment/settings",
        json={"pickup_enabled": True, "delivery_enabled": False},
        headers=headers,
    )
    checkout = client.post(
        f"/v1/public/websites/{slug}/checkout",
        json={
            "items": [{"offering_id": product_id, "quantity": 1}],
            "fulfilment_mode": "pickup",
            "payment_method": "cod",
            "guest": {"name": "Pickup", "email": f"{uuid.uuid4()}@example.com"},
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert checkout.status_code == 200, checkout.text
    job_id = checkout.json()["data"]["fulfilment"]["id"]
    client.patch(
        f"/v1/b/{bid}/fulfilment/jobs/{job_id}/status",
        json={"status": "preparing"},
        headers=headers,
    )
    client.patch(
        f"/v1/b/{bid}/fulfilment/jobs/{job_id}/status",
        json={"status": "ready"},
        headers=headers,
    )
    bad = client.patch(
        f"/v1/b/{bid}/fulfilment/jobs/{job_id}/status",
        json={"status": "out_for_delivery"},
        headers=headers,
    )
    assert bad.status_code in (400, 422)


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_fulfilment_business_isolation(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    a = _create_business(client, headers)
    b = _create_business(client, headers)
    _enable_modules(client, headers, a["id"])
    _enable_modules(client, headers, b["id"])
    client.post(
        f"/v1/b/{a['id']}/fulfilment/zones",
        json={"name": "A-City", "match_type": "city", "city": "Alpha", "charge_amount": 10},
        headers=headers,
    )
    zones_b = client.get(f"/v1/b/{b['id']}/fulfilment/zones", headers=headers)
    assert zones_b.status_code == 200
    assert zones_b.json()["data"] == []
