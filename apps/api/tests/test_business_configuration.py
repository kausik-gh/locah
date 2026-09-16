"""Stage 2F — Business-Type Configuration Engine tests."""

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
from platform_core.services.business_configuration import (
    BusinessConfigurationResolver,
    BusinessConfigurationService,
)
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


def _create_business(
    client: TestClient, headers: dict[str, str], business_type: str = "retail"
) -> str:
    resp = client.post(
        "/v1/platform/businesses",
        json={
            "display_name": f"Config Co {uuid.uuid4().hex[:8]}",
            "business_type": business_type,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return cast(str, resp.json()["data"]["business"]["id"])


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_list_and_get_type_profiles(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        listed = client.get("/v1/platform/business-types", headers=headers)
        assert listed.status_code == 200
        types = listed.json()["data"]
        assert len(types) == 14
        type_ids = {item["type_id"] for item in types}
        assert "restaurant" in type_ids
        assert "clinic" in type_ids

        profile = client.get("/v1/platform/business-types/restaurant/profile", headers=headers)
        assert profile.status_code == 200
        data = profile.json()["data"]
        assert data["type_id"] == "restaurant"
        assert data["terminology"]["customer"] == "Guest"
        # Recommendations must name modules that actually exist and can be
        # enabled — "catalog-orders" was a stale id that 403'd on enable.
        seeded = {seed["module_id"] for seed in data["module_seeds"]}
        assert {"offerings-catalog", "orders"} <= seeded


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_resolve_configuration_and_profile(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        biz = _create_business(client, headers, business_type="clinic")
        resolved = client.get(f"/v1/platform/businesses/{biz}/configuration", headers=headers)
        assert resolved.status_code == 200, resolved.text
        data = resolved.json()["data"]
        assert data["business_type"] == "clinic"
        assert data["resolved"]["terminology"]["customer"] == "Patient"
        assert data["layers"]["entitlements"]["status"] == "active"
        assert data["layers"]["permissions"]["status"] == "placeholder"

        assigned = client.get(
            f"/v1/platform/businesses/{biz}/configuration/profile", headers=headers
        )
        assert assigned.status_code == 200
        assert assigned.json()["data"]["assigned_to_business"] is True


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_settings_merge_in_resolver(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        biz = _create_business(client, headers, business_type="gym")
        patched = client.patch(
            f"/v1/platform/businesses/{biz}/settings",
            json={
                "configuration": {
                    "terminology": {"customer": "Athlete"},
                    "operational_defaults": {"booking_enabled": False},
                }
            },
            headers=headers,
        )
        assert patched.status_code == 422 or patched.status_code == 200
        # Settings endpoint may reject unknown top-level keys — merge via direct DB for test
        if patched.status_code == 422:
            async def _merge_settings() -> None:
                url = get_database_url()
                assert url
                if url.startswith("postgresql://"):
                    url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
                engine = create_async_engine(url, echo=False, poolclass=NullPool)
                factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
                async with factory() as session:
                    await session.execute(
                        text(
                            """
                            UPDATE businesses
                            SET settings = settings || CAST(:patch AS jsonb)
                            WHERE id = :id
                            """
                        ),
                        {
                            "id": biz,
                            "patch": '{"configuration": {"terminology": {"customer": "Athlete"}, '
                            '"operational_defaults": {"booking_enabled": false}}}',
                        },
                    )
                    await session.commit()
                await engine.dispose()

            asyncio.run(_merge_settings())

        resolved = client.get(f"/v1/platform/businesses/{biz}/configuration", headers=headers)
        assert resolved.status_code == 200
        resolved_data = resolved.json()["data"]["resolved"]
        assert resolved_data["terminology"]["customer"] == "Athlete"
        assert resolved_data["operational_defaults"]["booking_enabled"] is False


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_patch_business_type_success(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        biz = _create_business(client, headers, business_type="retail")
        changed = client.patch(
            f"/v1/platform/businesses/{biz}/configuration/type",
            json={"business_type": "restaurant"},
            headers=headers,
        )
        assert changed.status_code == 200, changed.text
        data = changed.json()["data"]
        assert data["business_type"] == "restaurant"
        assert data["resolved"]["terminology"]["customer"] == "Guest"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_configuration_failures(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    other_id = uuid.uuid4()
    _seed(other_id, f"{other_id}@example.com")
    other_headers = _headers(other_id, f"{other_id}@example.com")

    with TestClient(app) as client:
        biz = _create_business(client, headers, business_type="salon")

        unauth = client.get(f"/v1/platform/businesses/{biz}/configuration")
        assert unauth.status_code == 401

        denied = client.patch(
            f"/v1/platform/businesses/{biz}/configuration/type",
            json={"business_type": "spa"},
            headers=other_headers,
        )
        assert denied.status_code == 403

        unsupported = client.patch(
            f"/v1/platform/businesses/{biz}/configuration/type",
            json={"business_type": "hospital"},
            headers=headers,
        )
        assert unsupported.status_code == 422

        same_type = client.patch(
            f"/v1/platform/businesses/{biz}/configuration/type",
            json={"business_type": "salon"},
            headers=headers,
        )
        assert same_type.status_code == 409

        client.patch(
            f"/v1/platform/businesses/{biz}/preferences",
            json={"onboarding_completed": True},
            headers=headers,
        )
        needs_confirm = client.patch(
            f"/v1/platform/businesses/{biz}/configuration/type",
            json={"business_type": "spa"},
            headers=headers,
        )
        assert needs_confirm.status_code == 422

        confirmed = client.patch(
            f"/v1/platform/businesses/{biz}/configuration/type",
            json={"business_type": "spa", "confirm_type_change": True},
            headers=headers,
        )
        assert confirmed.status_code == 200

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
            f"/v1/platform/businesses/{biz}/configuration/type",
            json={"business_type": "gym", "confirm_type_change": True},
            headers=headers,
        )
        assert closed.status_code == 409


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_configuration_audit_and_outbox(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        biz = _create_business(client, headers, business_type="cafe")
        client.patch(
            f"/v1/platform/businesses/{biz}/configuration/type",
            json={"business_type": "restaurant"},
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
                        [
                            "business_type.changed",
                            "configuration.resolved",
                            "configuration.profile.updated",
                        ]
                    ),
                )
            )
            event_types = {row[0] for row in outbox.all()}
            assert "business_type.changed" in event_types
            assert "configuration.resolved" in event_types
            assert "configuration.profile.updated" in event_types

            audit = await session.execute(
                select(func.count())
                .select_from(PlatformAuditEvent)
                .where(
                    PlatformAuditEvent.business_id == uuid.UUID(biz),
                    PlatformAuditEvent.event_type == "business_type.changed",
                )
            )
            assert audit.scalar_one() >= 1
        await engine.dispose()

    asyncio.run(_assert())


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_resolver_determinism(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        biz = _create_business(client, headers, business_type="education")

    async def _assert() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            first = await BusinessConfigurationService.get_resolved_configuration(
                session, uuid.UUID(biz)
            )
            second = await BusinessConfigurationService.get_resolved_configuration(
                session, uuid.UUID(biz)
            )
            assert first == second
            resolved = await BusinessConfigurationResolver.resolve(session, uuid.UUID(biz))
            assert resolved.serialize() == first
        await engine.dispose()

    asyncio.run(_assert())


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_null_business_type_fallback(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        biz = _create_business(client, headers, business_type="retail")

    async def _null_type() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await session.execute(
                text("UPDATE businesses SET business_type = NULL WHERE id = :id"),
                {"id": biz},
            )
            await session.commit()
            resolved = await BusinessConfigurationService.get_resolved_configuration(
                session, uuid.UUID(biz)
            )
            assert resolved["business_type"] == "not_sure"
        await engine.dispose()

    asyncio.run(_null_type())

    with TestClient(app) as client:
        got = client.get(f"/v1/platform/businesses/{biz}/configuration", headers=headers)
        assert got.status_code == 200
        assert got.json()["data"]["business_type"] == "not_sure"
