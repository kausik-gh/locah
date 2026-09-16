"""Stage 6 — Orders, Sales & Commerce Kernel tests."""

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


def _create_business(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"Orders Co {uuid.uuid4().hex[:8]}", "business_type": "retail"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    business_id = cast(str, resp.json()["data"]["business"]["id"])
    # Gate [7] (Doc 12 SS8.9): optional-module operations require an active module.
    for module_id in ("offerings-catalog", "orders", "customer-relationships", "inventory",):
        enabled = client.post(
            f"/v1/b/{business_id}/modules/{module_id}/enable", headers=headers
        )
        assert enabled.status_code == 200, enabled.text
    return business_id


def _primary_location_id(client: TestClient, headers: dict[str, str], business_id: str) -> str:
    resp = client.get(f"/v1/platform/businesses/{business_id}/locations", headers=headers)
    assert resp.status_code == 200, resp.text
    for loc in resp.json()["data"]:
        if loc["is_primary"]:
            return cast(str, loc["id"])
    raise AssertionError("primary location missing")


def _create_customer(client: TestClient, headers: dict[str, str], business_id: str) -> str:
    resp = client.post(
        f"/v1/platform/businesses/{business_id}/customers",
        json={"display_name": "Order Buyer", "email": f"{uuid.uuid4()}@example.com"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return cast(str, resp.json()["data"]["id"])


def _create_tracked_product(client: TestClient, headers: dict[str, str], business_id: str) -> str:
    product_id = client.post(
        f"/v1/platform/businesses/{business_id}/products",
        json={
            "title": f"Order Widget {uuid.uuid4().hex[:6]}",
            "sku": f"ORD-{uuid.uuid4().hex[:8]}",
            "track_inventory": True,
            "status": "active",
            "price_amount": 50.0,
            "tax_rate": 10.0,
        },
        headers=headers,
    ).json()["data"]["id"]
    return cast(str, product_id)


def _stock_product(
    client: TestClient,
    headers: dict[str, str],
    business_id: str,
    product_id: str,
    location_id: str,
    quantity: int = 100,
) -> None:
    resp = client.post(
        f"/v1/platform/businesses/{business_id}/inventory/opening-stock",
        json={
            "offering_id": product_id,
            "location_id": location_id,
            "quantity": quantity,
            "reason": "Test stock",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_order_create_lifecycle_and_inventory(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)
    location_id = _primary_location_id(client, headers, business_id)
    customer_id = _create_customer(client, headers, business_id)
    product_id = _create_tracked_product(client, headers, business_id)
    _stock_product(client, headers, business_id, product_id, location_id, quantity=20)

    idempotency_key = str(uuid.uuid4())
    create_resp = client.post(
        f"/v1/platform/businesses/{business_id}/orders",
        json={
            "location_id": location_id,
            "customer_contact_id": customer_id,
            "payment_method": "cod",
            "idempotency_key": idempotency_key,
            "items": [{"offering_id": product_id, "quantity": 3}],
        },
        headers=headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    order = create_resp.json()["data"]
    order_id = order["id"]
    assert order["status"] == "pending"
    assert order["total_amount"] == 165.0  # 150 + 10% tax
    assert len(order["items"]) == 1
    assert order["items"][0]["quantity_reserved"] == 3

    dup_resp = client.post(
        f"/v1/platform/businesses/{business_id}/orders",
        json={
            "location_id": location_id,
            "idempotency_key": idempotency_key,
            "items": [{"offering_id": product_id, "quantity": 1}],
        },
        headers=headers,
    )
    assert dup_resp.status_code == 200, dup_resp.text
    assert dup_resp.json()["data"]["id"] == order_id

    for status in ("accepted", "preparing", "ready"):
        resp = client.post(
            f"/v1/platform/businesses/{business_id}/orders/{order_id}/status",
            json={"status": status},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

    complete_resp = client.post(
        f"/v1/platform/businesses/{business_id}/orders/{order_id}/complete",
        json={},
        headers=headers,
    )
    assert complete_resp.status_code == 200, complete_resp.text
    assert complete_resp.json()["data"]["status"] == "completed"
    assert complete_resp.json()["data"]["items"][0]["quantity_deducted"] == 3

    inv_resp = client.get(
        f"/v1/platform/businesses/{business_id}/inventory?offering_id={product_id}",
        headers=headers,
    )
    assert inv_resp.status_code == 200, inv_resp.text
    assert inv_resp.json()["data"][0]["quantity_on_hand"] == 17

    history_resp = client.get(
        f"/v1/platform/businesses/{business_id}/orders/{order_id}/history",
        headers=headers,
    )
    assert history_resp.status_code == 200, history_resp.text
    assert history_resp.json()["meta"]["count"] >= 5


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_order_cancel_releases_inventory(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)
    location_id = _primary_location_id(client, headers, business_id)
    product_id = _create_tracked_product(client, headers, business_id)
    _stock_product(client, headers, business_id, product_id, location_id, quantity=10)

    order_id = client.post(
        f"/v1/platform/businesses/{business_id}/orders",
        json={
            "location_id": location_id,
            "items": [{"offering_id": product_id, "quantity": 4}],
        },
        headers=headers,
    ).json()["data"]["id"]

    cancel_resp = client.post(
        f"/v1/platform/businesses/{business_id}/orders/{order_id}/cancel",
        json={"reason": "Customer changed mind"},
        headers=headers,
    )
    assert cancel_resp.status_code == 200, cancel_resp.text
    assert cancel_resp.json()["data"]["status"] == "cancelled"

    inv_resp = client.get(
        f"/v1/platform/businesses/{business_id}/inventory?offering_id={product_id}",
        headers=headers,
    )
    record = inv_resp.json()["data"][0]
    assert record["quantity_on_hand"] == 10
    assert record["quantity_reserved"] == 0


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_order_insufficient_stock(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)
    location_id = _primary_location_id(client, headers, business_id)
    product_id = _create_tracked_product(client, headers, business_id)
    _stock_product(client, headers, business_id, product_id, location_id, quantity=2)

    resp = client.post(
        f"/v1/platform/businesses/{business_id}/orders",
        json={
            "location_id": location_id,
            "items": [{"offering_id": product_id, "quantity": 5}],
        },
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_order_business_isolation(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_a = _create_business(client, headers)
    business_b = _create_business(client, headers)
    location_id = _primary_location_id(client, headers, business_a)
    product_id = _create_tracked_product(client, headers, business_a)
    _stock_product(client, headers, business_a, product_id, location_id, quantity=5)

    order_id = client.post(
        f"/v1/platform/businesses/{business_a}/orders",
        json={
            "location_id": location_id,
            "items": [{"offering_id": product_id, "quantity": 1}],
        },
        headers=headers,
    ).json()["data"]["id"]

    denied = client.get(
        f"/v1/platform/businesses/{business_b}/orders/{order_id}",
        headers=headers,
    )
    assert denied.status_code == 404, denied.text


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_order_audit_and_outbox(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)
    location_id = _primary_location_id(client, headers, business_id)
    product_id = _create_tracked_product(client, headers, business_id)
    _stock_product(client, headers, business_id, product_id, location_id, quantity=5)

    order_id = client.post(
        f"/v1/platform/businesses/{business_id}/orders",
        json={
            "location_id": location_id,
            "items": [{"offering_id": product_id, "quantity": 1}],
        },
        headers=headers,
    ).json()["data"]["id"]

    note_resp = client.post(
        f"/v1/platform/businesses/{business_id}/orders/{order_id}/notes",
        json={"body": "Pack carefully"},
        headers=headers,
    )
    assert note_resp.status_code == 200, note_resp.text

    async def _assert_events() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            outbox = await session.execute(
                select(PlatformOutboxEvent.event_type).where(
                    PlatformOutboxEvent.business_id == uuid.UUID(business_id),
                    PlatformOutboxEvent.event_type.in_(
                        ["order.created", "order.note.created"]
                    ),
                )
            )
            types = {row[0] for row in outbox.all()}
            assert "order.created" in types
            assert "order.note.created" in types
            audit = await session.execute(
                select(PlatformAuditEvent.action).where(
                    PlatformAuditEvent.business_id == uuid.UUID(business_id),
                    PlatformAuditEvent.resource_type == "order",
                )
            )
            assert "created" in {row[0] for row in audit.all()}
        await engine.dispose()

    asyncio.run(_assert_events())
