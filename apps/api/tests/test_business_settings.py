"""Stage 2E — Business settings & configuration engine tests."""

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
from platform_core.services.business import BusinessService
from platform_core.services.business_settings import BusinessSettingsService
from platform_core.services.identity import IdentityService
from platform_core.services.outbox import OutboxService
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
        json={"display_name": f"Settings Co {uuid.uuid4().hex[:8]}", "business_type": "retail"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return cast(str, resp.json()["data"]["business"]["id"])


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_get_and_patch_settings(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        biz = _create_business(client, headers)
        got = client.get(f"/v1/platform/businesses/{biz}/settings", headers=headers)
        assert got.status_code == 200
        assert got.json()["data"]["regional"]["currency"] == "INR"

        patched = client.patch(
            f"/v1/platform/businesses/{biz}/settings",
            json={"regional": {"currency": "USD", "country": "US", "language": "en"}},
            headers=headers,
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["data"]["regional"]["currency"] == "USD"
        assert patched.json()["data"]["regional"]["locale"] == "en-US"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_partial_profile_and_branding_update(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        biz = _create_business(client, headers)
        profile = client.patch(
            f"/v1/platform/businesses/{biz}/profile",
            json={"description": "A great shop", "tagline": "Quality goods"},
            headers=headers,
        )
        assert profile.status_code == 200
        assert profile.json()["data"]["description"] == "A great shop"

        branding = client.patch(
            f"/v1/platform/businesses/{biz}/branding",
            json={"brand_color": "#336699", "font_theme": "modern"},
            headers=headers,
        )
        assert branding.status_code == 200
        assert branding.json()["data"]["brand_color"] == "#336699"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_preferences_update(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        biz = _create_business(client, headers)
        resp = client.patch(
            f"/v1/platform/businesses/{biz}/preferences",
            json={
                "visibility": "unlisted",
                "onboarding_completed": True,
                "date_format": "DMY",
                "time_format": "24h",
                "measurement_system": "metric",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["visibility"] == "unlisted"
        assert data["onboarding_completed"] is True
        assert data["date_format"] == "DMY"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_settings_failures(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    other_id = uuid.uuid4()
    _seed(other_id, f"{other_id}@example.com")
    other_headers = _headers(other_id, f"{other_id}@example.com")

    with TestClient(app) as client:
        biz = _create_business(client, headers)

        unauth = client.get(f"/v1/platform/businesses/{biz}/settings")
        assert unauth.status_code == 401

        denied = client.patch(
            f"/v1/platform/businesses/{biz}/settings",
            json={"regional": {"currency": "USD"}},
            headers=other_headers,
        )
        assert denied.status_code == 403

        bad_tz = client.patch(
            f"/v1/platform/businesses/{biz}/settings",
            json={"regional": {"timezone": "Invalid/Zone"}},
            headers=headers,
        )
        assert bad_tz.status_code == 422

        bad_locale = client.patch(
            f"/v1/platform/businesses/{biz}/settings",
            json={"regional": {"locale": "not-valid"}},
            headers=headers,
        )
        assert bad_locale.status_code == 422

        immutable = client.patch(
            f"/v1/platform/businesses/{biz}/settings",
            json={"slug": "new-slug"},
            headers=headers,
        )
        assert immutable.status_code == 422

        # Bump the version once so a genuinely stale (but valid) version exists.
        bumped = client.patch(
            f"/v1/platform/businesses/{biz}/settings",
            json={"regional": {"currency": "USD"}},
            headers=headers,
        )
        assert bumped.status_code == 200, bumped.text
        current = bumped.json()["data"]["version"]
        stale = client.patch(
            f"/v1/platform/businesses/{biz}/settings",
            json={"version": current - 1, "regional": {"currency": "EUR"}},
            headers=headers,
        )
        assert stale.status_code == 409, stale.text

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
            f"/v1/platform/businesses/{biz}/preferences",
            json={"visibility": "private"},
            headers=headers,
        )
        assert closed.status_code == 409


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_settings_audit_and_outbox(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        biz = _create_business(client, headers)
        client.patch(
            f"/v1/platform/businesses/{biz}/settings",
            json={"notifications": {"marketing_email": True}},
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
                    PlatformOutboxEvent.event_type == "business.settings.updated",
                )
            )
            assert outbox.scalars().first() == "business.settings.updated"
            audit = await session.execute(
                select(PlatformAuditEvent.event_type).where(
                    PlatformAuditEvent.business_id == uuid.UUID(biz),
                    PlatformAuditEvent.event_type == "business.settings.updated",
                )
            )
            assert audit.scalars().first() == "business.settings.updated"
        await engine.dispose()

    asyncio.run(_assert())


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
async def test_settings_transaction_rollback(monkeypatch: Any) -> None:
    url = get_database_url()
    assert url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    owner_id = uuid.uuid4()
    email = f"set-rb-{owner_id.hex[:8]}@test.local"
    async with factory() as session:
        await ensure_auth_user(session, owner_id, email)
        await IdentityService.bootstrap_identity(session, owner_id, email)
        business, _, _, _ = await BusinessService.create_business(
            session,
            identity_id=owner_id,
            display_name=f"Settings RB {owner_id.hex[:8]}",
            business_type="retail",
            correlation_id=str(uuid.uuid4()),
        )
        await session.commit()
        business_id = business.id
        before_currency = business.settings.get("currency")

    async def _fail(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("forced settings outbox failure")

    monkeypatch.setattr(OutboxService, "publish", staticmethod(_fail))

    async with factory() as session:
        with pytest.raises(RuntimeError, match="forced settings outbox failure"):
            await BusinessSettingsService.patch_settings(
                session,
                business_id=business_id,
                raw={"currency": "USD", "country": "US", "language": "en"},
                actor_id=owner_id,
                correlation_id=str(uuid.uuid4()),
            )
        await session.rollback()

    async with factory() as session:
        biz = await BusinessService.get_by_id(session, business_id)
        assert biz
        assert biz.settings.get("currency") == before_currency
        audits = await session.execute(
            select(func.count())
            .select_from(PlatformAuditEvent)
            .where(
                PlatformAuditEvent.business_id == business_id,
                PlatformAuditEvent.event_type == "business.settings.updated",
            )
        )
        assert audits.scalar_one() == 0

    await engine.dispose()
