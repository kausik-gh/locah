"""Stage 5 — Inventory & Offerings Catalog Kernel tests."""

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
from platform_core.permissions import INVENTORY_READ, OFFERINGS_READ
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
        json={"display_name": f"Inventory Co {uuid.uuid4().hex[:8]}", "business_type": "retail"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    business_id = cast(str, resp.json()["data"]["business"]["id"])
    # Gate [7] (Doc 12 SS8.9): optional-module operations require an active module.
    for module_id in ("offerings-catalog", "inventory",):
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


def _create_tracked_product(
    client: TestClient,
    headers: dict[str, str],
    business_id: str,
    *,
    sku: str | None = None,
    threshold: int = 5,
) -> str:
    resp = client.post(
        f"/v1/platform/businesses/{business_id}/products",
        json={
            "title": f"Widget {uuid.uuid4().hex[:6]}",
            "sku": sku or f"SKU-{uuid.uuid4().hex[:8]}",
            "track_inventory": True,
            "low_stock_threshold": threshold,
            "status": "active",
            "price_amount": 99.99,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return cast(str, resp.json()["data"]["id"])


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_product_category_and_crud(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)

    cat_resp = client.post(
        f"/v1/platform/businesses/{business_id}/product-categories",
        json={"name": "Electronics"},
        headers=headers,
    )
    assert cat_resp.status_code == 200, cat_resp.text
    category_id = cat_resp.json()["data"]["id"]
    assert cat_resp.json()["data"]["slug"] == "electronics"

    sku = f"DUP-{uuid.uuid4().hex[:8]}"
    product_id = _create_tracked_product(client, headers, business_id, sku=sku)

    dup_resp = client.post(
        f"/v1/platform/businesses/{business_id}/products",
        json={"title": "Duplicate SKU", "sku": sku, "track_inventory": False},
        headers=headers,
    )
    assert dup_resp.status_code == 409, dup_resp.text

    patch_resp = client.patch(
        f"/v1/platform/businesses/{business_id}/products/{product_id}",
        json={"category_id": category_id, "status": "active"},
        headers=headers,
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["data"]["category_id"] == category_id

    search_resp = client.get(
        f"/v1/platform/businesses/{business_id}/products?search=Widget",
        headers=headers,
    )
    assert search_resp.status_code == 200, search_resp.text
    assert search_resp.json()["meta"]["count"] >= 1

    archive_resp = client.post(
        f"/v1/platform/businesses/{business_id}/products/{product_id}/archive",
        json={},
        headers=headers,
    )
    assert archive_resp.status_code == 200, archive_resp.text
    assert archive_resp.json()["data"]["status"] == "archived"

    restore_resp = client.post(
        f"/v1/platform/businesses/{business_id}/products/{product_id}/restore",
        json={},
        headers=headers,
    )
    assert restore_resp.status_code == 200, restore_resp.text
    assert restore_resp.json()["data"]["status"] == "draft"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_inventory_opening_stock_adjust_and_status(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, owner_id = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)
    location_id = _primary_location_id(client, headers, business_id)
    product_id = _create_tracked_product(client, headers, business_id, threshold=10)

    opening_resp = client.post(
        f"/v1/platform/businesses/{business_id}/inventory/opening-stock",
        json={
            "offering_id": product_id,
            "location_id": location_id,
            "quantity": 25,
            "reason": "Initial count",
        },
        headers=headers,
    )
    assert opening_resp.status_code == 200, opening_resp.text
    assert opening_resp.json()["data"]["quantity_on_hand"] == 25
    assert opening_resp.json()["data"]["stock_status"] == "available"

    adjust_resp = client.post(
        f"/v1/platform/businesses/{business_id}/inventory/adjust",
        json={
            "offering_id": product_id,
            "location_id": location_id,
            "quantity_delta": -20,
            "reason": "Cycle count correction",
        },
        headers=headers,
    )
    assert adjust_resp.status_code == 200, adjust_resp.text
    assert adjust_resp.json()["data"]["quantity_on_hand"] == 5
    assert adjust_resp.json()["data"]["stock_status"] == "low_stock"

    zero_resp = client.post(
        f"/v1/platform/businesses/{business_id}/inventory/adjust",
        json={
            "offering_id": product_id,
            "location_id": location_id,
            "quantity_delta": -5,
            "reason": "Sold through",
        },
        headers=headers,
    )
    assert zero_resp.status_code == 200, zero_resp.text
    assert zero_resp.json()["data"]["stock_status"] == "out_of_stock"

    over_resp = client.post(
        f"/v1/platform/businesses/{business_id}/inventory/adjust",
        json={
            "offering_id": product_id,
            "location_id": location_id,
            "quantity_delta": -1,
            "reason": "Should fail",
        },
        headers=headers,
    )
    assert over_resp.status_code == 422, over_resp.text

    list_resp = client.get(
        f"/v1/platform/businesses/{business_id}/inventory?stock_status=out_of_stock",
        headers=headers,
    )
    assert list_resp.status_code == 200, list_resp.text
    assert list_resp.json()["meta"]["count"] >= 1

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
                        [
                            "offering.created",
                            "inventory.opening_stock.set",
                            "inventory.adjusted",
                            "inventory.stock.updated",
                            "inventory.stock.low",
                            "inventory.stock.zero",
                        ]
                    ),
                )
            )
            types = {row[0] for row in outbox.all()}
            assert "offering.created" in types
            assert "inventory.stock.zero" in types
            audit = await session.execute(
                select(PlatformAuditEvent.action).where(
                    PlatformAuditEvent.business_id == uuid.UUID(business_id),
                    PlatformAuditEvent.resource_type == "inventory_record",
                )
            )
            actions = {row[0] for row in audit.all()}
            assert "adjusted" in actions
        await engine.dispose()

    asyncio.run(_assert_events())
    _ = owner_id


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_business_isolation_for_inventory(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_a = _create_business(client, headers)
    business_b = _create_business(client, headers)
    product_a = _create_tracked_product(client, headers, business_a)

    denied = client.get(
        f"/v1/platform/businesses/{business_b}/products/{product_a}",
        headers=headers,
    )
    assert denied.status_code == 404, denied.text


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_inventory_read_permission_required(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, owner_id = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)

    member_id = uuid.uuid4()
    member_email = f"{member_id}@example.com"
    _seed(member_id, member_email)
    member_headers = _headers(member_id, member_email)

    # Onboard the member through the real invitation flow.
    invite = client.post(
        f"/v1/platform/businesses/{business_id}/invitations",
        json={"invited_email": member_email, "invited_role": "member"},
        headers=headers,
    )
    assert invite.status_code == 200, invite.text
    accepted = client.post(
        f"/v1/platform/businesses/{business_id}/invitations/{invite.json()['data']['id']}/accept",
        headers=member_headers,
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["data"]["membership"]["status"] == "active"

    # A plain member has no inventory.read grant.
    denied = client.get(
        f"/v1/platform/businesses/{business_id}/inventory",
        headers=member_headers,
    )
    assert denied.status_code == 403, denied.text

    _ = OFFERINGS_READ
    _ = INVENTORY_READ
