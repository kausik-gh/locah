"""Stage 4 — Guest checkout end-to-end (WEB-007)."""

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
from platform_testing.db_helpers import ensure_auth_user
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


def _setup_commerce(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    business = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"Checkout Co {uuid.uuid4().hex[:6]}", "business_type": "retail"},
        headers=headers,
    ).json()["data"]["business"]
    bid = business["id"]
    # A fresh Business defaults to visibility="private" (no public URL) —
    # promote to "unlisted" so the public checkout endpoints below can
    # actually resolve it.
    assert (
        client.post(
            f"/v1/b/{bid}/marketplace/visibility",
            json={"visibility": "unlisted"},
            headers=headers,
        ).status_code
        == 200
    )
    for mid in ("offerings-catalog", "orders", "inventory", "payments", "fulfilment"):
        assert client.post(f"/v1/b/{bid}/modules/{mid}/enable", headers=headers).status_code == 200
    client.patch(
        f"/v1/b/{bid}/fulfilment/settings",
        json={"pickup_enabled": True, "delivery_enabled": True},
        headers=headers,
    )
    client.post(
        f"/v1/b/{bid}/fulfilment/zones",
        json={"name": "City", "match_type": "city", "city": "Mumbai", "charge_amount": 25},
        headers=headers,
    )
    product = client.post(
        f"/v1/platform/businesses/{bid}/products",
        json={
            "title": "Tea",
            "sku": f"T-{uuid.uuid4().hex[:6]}",
            "status": "active",
            "price_amount": 50,
            "visibility": "public",
        },
        headers=headers,
    ).json()["data"]
    return {"business": business, "product": product}


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_guest_checkout_pickup_cod(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    setup = _setup_commerce(client, headers)
    slug = setup["business"]["slug"]
    product_id = setup["product"]["id"]
    key = str(uuid.uuid4())

    first = client.post(
        f"/v1/public/websites/{slug}/checkout",
        json={
            "items": [{"offering_id": product_id, "quantity": 2}],
            "fulfilment_mode": "pickup",
            "payment_method": "cod",
            "guest": {"name": "Guest", "email": f"{uuid.uuid4()}@example.com"},
            "idempotency_key": key,
        },
    )
    assert first.status_code == 200, first.text
    body = first.json()["data"]
    assert body["fulfilment"]["mode"] == "pickup"
    assert body["tracking"]["token"]
    assert body["confirmation"]["order_number"]
    order_id = body["order"]["id"]

    dup = client.post(
        f"/v1/public/websites/{slug}/checkout",
        json={
            "items": [{"offering_id": product_id, "quantity": 2}],
            "fulfilment_mode": "pickup",
            "payment_method": "cod",
            "guest": {"name": "Guest", "email": f"{uuid.uuid4()}@example.com"},
            "idempotency_key": key,
        },
    )
    assert dup.status_code == 200
    assert dup.json()["data"]["order"]["id"] == order_id


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_empty_cart_and_invalid_item(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    setup = _setup_commerce(client, headers)
    slug = setup["business"]["slug"]

    empty = client.post(
        f"/v1/public/websites/{slug}/checkout",
        json={
            "items": [],
            "fulfilment_mode": "pickup",
            "payment_method": "cod",
            "guest": {"name": "G", "email": f"{uuid.uuid4()}@example.com"},
        },
    )
    assert empty.status_code in (400, 422)

    invalid = client.post(
        f"/v1/public/websites/{slug}/checkout",
        json={
            "items": [{"offering_id": str(uuid.uuid4()), "quantity": 1}],
            "fulfilment_mode": "pickup",
            "payment_method": "cod",
            "guest": {"name": "G", "email": f"{uuid.uuid4()}@example.com"},
        },
    )
    assert invalid.status_code in (400, 422)


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_checkout_options_only_active_modes(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    setup = _setup_commerce(client, headers)
    slug = setup["business"]["slug"]
    bid = setup["business"]["id"]
    client.patch(
        f"/v1/b/{bid}/fulfilment/settings",
        json={"pickup_enabled": True, "delivery_enabled": False},
        headers=headers,
    )
    opts = client.get(f"/v1/public/websites/{slug}/checkout/options")
    assert opts.status_code == 200
    modes = opts.json()["data"]["fulfilment_modes"]
    assert "pickup" in modes
    assert "delivery" not in modes
