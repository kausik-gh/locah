"""Stage 2G — Entitlement resolution engine tests."""

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
from platform_core.entitlements import (
    BusinessEntitlementResolver,
    PlatformCapabilityResolver,
)
from platform_core.entitlements.plan_registry import DEFAULT_PLAN_ID
from platform_core.models import PlatformAuditEvent, PlatformOutboxEvent
from platform_core.services.business_entitlements import BusinessEntitlementService
from platform_testing.db_helpers import ensure_auth_user
from sqlalchemy import func, select, text
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
        json={"display_name": f"Entitlement Co {uuid.uuid4().hex[:8]}", "business_type": "retail"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return cast(str, resp.json()["data"]["business"]["id"])


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_list_catalog_and_module_details(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        plans = client.get("/v1/platform/plans", headers=headers)
        assert plans.status_code == 200
        plan_ids = {item["plan_id"] for item in plans.json()["data"]}
        assert DEFAULT_PLAN_ID in plan_ids

        modules = client.get("/v1/platform/modules", headers=headers)
        assert modules.status_code == 200
        module_ids = {item["module_id"] for item in modules.json()["data"]}
        assert "inventory" in module_ids
        assert "core-website" in module_ids

        module = client.get("/v1/platform/modules/inventory", headers=headers)
        assert module.status_code == 200
        assert any(f["feature_id"] == "inventory.core" for f in module.json()["data"]["features"])


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_business_entitlements_and_capabilities(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        biz = _create_business(client, headers)
        entitlements = client.get(f"/v1/platform/businesses/{biz}/entitlements", headers=headers)
        assert entitlements.status_code == 200, entitlements.text
        data = entitlements.json()["data"]
        assert data["plan_id"] == DEFAULT_PLAN_ID
        assert "inventory" in data["entitled_modules"]
        assert "core-website" in data["entitled_modules"]
        assert data["layers"]["usage_enforcement"]["status"] == "placeholder"

        capabilities = client.get(f"/v1/platform/businesses/{biz}/capabilities", headers=headers)
        assert capabilities.status_code == 200
        caps = capabilities.json()["data"]["capabilities"]
        assert caps["use_inventory"] is True
        assert caps["use_crm"] is True
        assert caps["use_analytics"] is False


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_override_enable_feature_and_module(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        biz = _create_business(client, headers)
        patched = client.patch(
            f"/v1/platform/businesses/{biz}/entitlements/overrides",
            json={
                "features": {
                    "inventory.stock_transfer": {"entitled": True, "enabled": True},
                },
                "limits": {"locations": {"max": 5}},
            },
            headers=headers,
        )
        assert patched.status_code == 200, patched.text
        data = patched.json()["data"]
        assert data["usage_limits"]["locations"] == 5
        assert data["feature_states"]["inventory.stock_transfer"]["enabled"] is True


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_plan_change(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        biz = _create_business(client, headers)
        changed = client.patch(
            f"/v1/platform/businesses/{biz}/entitlements/plan",
            json={"plan_id": "growth"},
            headers=headers,
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["data"]["plan_id"] == "growth"
        assert "analytics" in changed.json()["data"]["entitled_modules"]


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_entitlement_failures(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    other_id = uuid.uuid4()
    _seed(other_id, f"{other_id}@example.com")
    other_headers = _headers(other_id, f"{other_id}@example.com")

    with TestClient(app) as client:
        biz = _create_business(client, headers)

        unauth = client.get(f"/v1/platform/businesses/{biz}/entitlements")
        assert unauth.status_code == 401

        denied = client.patch(
            f"/v1/platform/businesses/{biz}/entitlements/overrides",
            json={"modules": {"inventory": {"entitled": False}}},
            headers=other_headers,
        )
        assert denied.status_code == 403

        bad_module = client.patch(
            f"/v1/platform/businesses/{biz}/entitlements/overrides",
            json={"modules": {"not-a-module": {"entitled": True}}},
            headers=headers,
        )
        assert bad_module.status_code == 422

        bad_feature = client.patch(
            f"/v1/platform/businesses/{biz}/entitlements/overrides",
            json={"features": {"unknown.feature": {"enabled": True}}},
            headers=headers,
        )
        assert bad_feature.status_code == 422

        broken_dep = client.patch(
            f"/v1/platform/businesses/{biz}/entitlements/overrides",
            json={
                "modules": {
                    "orders": {"entitled": False},
                    "payments": {"entitled": True},
                }
            },
            headers=headers,
        )
        assert broken_dep.status_code == 422

        same_plan = client.patch(
            f"/v1/platform/businesses/{biz}/entitlements/plan",
            json={"plan_id": DEFAULT_PLAN_ID},
            headers=headers,
        )
        assert same_plan.status_code == 409

        async def _close() -> None:
            url = get_database_url()
            assert url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            engine = create_async_engine(url, echo=False, poolclass=NullPool)
            factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with factory() as session:
                await session.execute(
                    text("UPDATE businesses SET state = 'closed' WHERE id = :id"),
                    {"id": biz},
                )
                await session.commit()
            await engine.dispose()

        asyncio.run(_close())
        closed = client.patch(
            f"/v1/platform/businesses/{biz}/entitlements/plan",
            json={"plan_id": "growth"},
            headers=headers,
        )
        assert closed.status_code == 409


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_entitlement_audit_and_outbox(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        biz = _create_business(client, headers)
        client.patch(
            f"/v1/platform/businesses/{biz}/entitlements/overrides",
            json={"limits": {"employees": {"max": 25}}},
            headers=headers,
        )

    async def _assert() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            outbox = await session.execute(
                select(PlatformOutboxEvent.event_type).where(
                    PlatformOutboxEvent.business_id == uuid.UUID(biz),
                    PlatformOutboxEvent.event_type.in_(
                        ["entitlement.updated", "business.override.updated"]
                    ),
                )
            )
            event_types = {row[0] for row in outbox.all()}
            assert "entitlement.updated" in event_types
            assert "business.override.updated" in event_types

            audit = await session.execute(
                select(func.count())
                .select_from(PlatformAuditEvent)
                .where(
                    PlatformAuditEvent.business_id == uuid.UUID(biz),
                    PlatformAuditEvent.event_type == "entitlement.updated",
                )
            )
            assert audit.scalar_one() >= 1
        await engine.dispose()

    asyncio.run(_assert())


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_resolver_determinism(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        biz = _create_business(client, headers)

    async def _assert() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            first = await BusinessEntitlementService.get_business_entitlements(
                session, uuid.UUID(biz)
            )
            second = await BusinessEntitlementService.get_business_entitlements(
                session, uuid.UUID(biz)
            )
            assert first == second
            resolved = await BusinessEntitlementResolver.resolve(session, uuid.UUID(biz))
            caps = PlatformCapabilityResolver.resolve_from_entitlement(resolved)
            assert caps.serialize()["capabilities"]["use_bookings"] is True
        await engine.dispose()

    asyncio.run(_assert())
