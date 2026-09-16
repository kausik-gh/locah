"""Stage 2A — Business creation end-to-end tests."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_core.db import get_database_url
from platform_core.models import Business, BusinessMembership, PlatformAuditEvent, PlatformOutboxEvent
from platform_core.permissions import ROLE_PRIMARY_OWNER
from platform_core.services.business import BusinessService
from platform_core.services.identity import IdentityService
from platform_core.services.outbox import OutboxService
from platform_testing.db_helpers import ensure_auth_user
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"


def _make_token(sub: str, email: str) -> str:
    return jwt.encode(
        {
            "sub": sub,
            "email": email,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def auth_headers(monkeypatch: Any) -> dict[str, str]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = str(uuid.uuid4())
    email = f"{user_id}@example.com"
    if get_database_url():
        import asyncio

        async def _seed() -> None:
            url = get_database_url()
            assert url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            engine = create_async_engine(url, echo=False, poolclass=NullPool)
            factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with factory() as session:
                await ensure_auth_user(session, uuid.UUID(user_id), email)
                await session.commit()
            await engine.dispose()

        asyncio.run(_seed())
    return {"Authorization": f"Bearer {_make_token(user_id, email)}"}


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_create_business_success_hydrated(
    auth_headers: dict[str, str], monkeypatch: Any
) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    with TestClient(app) as client:
        response = client.post(
            "/v1/platform/businesses",
            json={
                "display_name": "Sunrise Salon",
                "business_type": "salon",
                "timezone": "Asia/Kolkata",
                "currency": "INR",
                "country": "IN",
                "language": "en",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()["data"]
        assert body["business"]["display_name"] == "Sunrise Salon"
        assert body["business"]["business_type"] == "salon"
        assert body["business"]["state"] == "draft"
        assert body["business"]["settings"]["currency"] == "INR"
        assert body["business"]["settings"]["country"] == "IN"
        assert body["business"]["settings"]["language"] == "en"
        assert body["business"]["settings"]["timezone"] == "Asia/Kolkata"
        assert body["business"]["primary_location"]["timezone"] == "Asia/Kolkata"
        assert body["membership"]["role"] == ROLE_PRIMARY_OWNER
        assert body["membership"]["status"] == "active"
        assert body["context"]["active_context"] == "business"
        assert body["context"]["business_id"] == body["business"]["id"]
        assert body["context"]["is_current_business"] is True
        assert body["context"]["is_default_business"] is True
        assert body["context"]["is_primary_business"] is True
        assert "business.read" in body["context"]["permissions"]

        # Remembered default restores Business context without X-Business-Id
        ctx = client.get(
            "/v1/me/context",
            headers={**auth_headers, "X-Operating-Context": "business"},
        )
        assert ctx.status_code == 200
        ctx_data = ctx.json()["data"]
        assert ctx_data["active_context"] == "business"
        assert ctx_data["business_id"] == body["business"]["id"]
        assert ctx_data["default_business_id"] == body["business"]["id"]
        assert ctx_data["primary_business_id"] == body["business"]["id"]


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_create_business_unauthenticated(monkeypatch: Any) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    with TestClient(app) as client:
        response = client.post(
            "/v1/platform/businesses",
            json={"display_name": "No Auth Co", "business_type": "retail"},
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_create_business_rejects_empty_and_whitespace_name(
    auth_headers: dict[str, str], monkeypatch: Any
) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    with TestClient(app) as client:
        empty = client.post(
            "/v1/platform/businesses",
            json={"display_name": "   ", "business_type": "retail"},
            headers=auth_headers,
        )
        assert empty.status_code == 422
        assert empty.json()["error"]["code"] == "VALIDATION_ERROR"

        short = client.post(
            "/v1/platform/businesses",
            json={"display_name": "A", "business_type": "retail"},
            headers=auth_headers,
        )
        assert short.status_code == 422
        assert short.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_create_business_rejects_unsupported_type(
    auth_headers: dict[str, str], monkeypatch: Any
) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    with TestClient(app) as client:
        response = client.post(
            "/v1/platform/businesses",
            json={"display_name": "Weird Co", "business_type": "spaceship"},
            headers=auth_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_create_business_rejects_invalid_locale_currency_timezone(
    auth_headers: dict[str, str], monkeypatch: Any
) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    with TestClient(app) as client:
        response = client.post(
            "/v1/platform/businesses",
            json={
                "display_name": "Locale Co",
                "business_type": "retail",
                "currency": "XYZ",
                "country": "ZZ",
                "language": "xx",
                "timezone": "Mars/Phobos",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        errors = response.json()["error"]["details"]["errors"]
        fields = {e["field"] for e in errors}
        assert {"currency", "country", "language", "timezone"} <= fields


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_create_business_duplicate_slug_conflict(
    auth_headers: dict[str, str], monkeypatch: Any
) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    slug = f"unique-slug-{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        first = client.post(
            "/v1/platform/businesses",
            json={
                "display_name": "First Biz",
                "business_type": "retail",
                "slug": slug,
            },
            headers=auth_headers,
        )
        assert first.status_code == 200, first.text

        second = client.post(
            "/v1/platform/businesses",
            json={
                "display_name": "Second Biz",
                "business_type": "retail",
                "slug": slug,
            },
            headers=auth_headers,
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "CONFLICT"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_create_business_rejects_reserved_slug(
    auth_headers: dict[str, str], monkeypatch: Any
) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    with TestClient(app) as client:
        response = client.post(
            "/v1/platform/businesses",
            json={
                "display_name": "Admin Co",
                "business_type": "retail",
                "slug": "admin",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_create_business_rejects_malformed_and_large_payload(
    auth_headers: dict[str, str], monkeypatch: Any
) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    with TestClient(app) as client:
        malformed = client.post(
            "/v1/platform/businesses",
            json={
                "display_name": "Extra Co",
                "business_type": "retail",
                "unexpected_field": True,
            },
            headers=auth_headers,
        )
        # Pydantic extra=forbid → FastAPI request validation
        assert malformed.status_code == 422

        large: dict[str, Any] = {f"field_{i}": i for i in range(30)}
        large["display_name"] = "Huge Co"
        large["business_type"] = "retail"
        huge = client.post(
            "/v1/platform/businesses",
            json=large,
            headers=auth_headers,
        )
        assert huge.status_code == 422


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_create_business_audit_and_outbox(
    auth_headers: dict[str, str], monkeypatch: Any
) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    with TestClient(app) as client:
        response = client.post(
            "/v1/platform/businesses",
            json={"display_name": "Audit Co", "business_type": "gym"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        business_id = response.json()["data"]["business"]["id"]

    import asyncio

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
                    PlatformOutboxEvent.business_id == uuid.UUID(business_id)
                )
            )
            event_types = set(outbox.scalars().all())
            assert {
                "business.created",
                "membership.created",
                "business.initialized",
            } <= event_types

            audits = await session.execute(
                select(PlatformAuditEvent.event_type).where(
                    PlatformAuditEvent.business_id == uuid.UUID(business_id)
                )
            )
            audit_types = set(audits.scalars().all())
            assert {
                "business.created",
                "membership.owner_assigned",
                "business.configuration_initialized",
            } <= audit_types

            memberships = await session.execute(
                select(BusinessMembership).where(
                    BusinessMembership.business_id == uuid.UUID(business_id)
                )
            )
            members = list(memberships.scalars().all())
            assert len(members) == 1
            assert members[0].role == ROLE_PRIMARY_OWNER
            assert members[0].status == "active"
        await engine.dispose()

    asyncio.run(_assert_events())


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
async def test_create_business_transaction_rollback_on_outbox_failure(
    monkeypatch: Any,
) -> None:
    url = get_database_url()
    assert url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    identity_id = uuid.uuid4()
    email = f"rollback-{identity_id.hex[:8]}@test.local"
    display_name = f"Rollback Co {identity_id.hex[:8]}"

    async with factory() as session:
        await ensure_auth_user(session, identity_id, email)
        await IdentityService.bootstrap_identity(session, identity_id, email)
        await session.commit()

    async def _failing_publish(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("forced outbox failure")

    monkeypatch.setattr(OutboxService, "publish", staticmethod(_failing_publish))

    async with factory() as session:
        with pytest.raises(RuntimeError, match="forced outbox failure"):
            await BusinessService.create_business(
                session,
                identity_id=identity_id,
                display_name=display_name,
                business_type="retail",
                correlation_id=str(uuid.uuid4()),
            )
        await session.rollback()

    async with factory() as session:
        businesses = await session.execute(
            select(func.count()).select_from(Business).where(Business.display_name == display_name)
        )
        assert businesses.scalar_one() == 0
        creation_audits = await session.execute(
            select(func.count())
            .select_from(PlatformAuditEvent)
            .where(
                PlatformAuditEvent.actor_identity_id == identity_id,
                PlatformAuditEvent.event_type == "business.created",
            )
        )
        assert creation_audits.scalar_one() == 0
        memberships = await session.execute(
            select(func.count())
            .select_from(BusinessMembership)
            .where(BusinessMembership.identity_id == identity_id)
        )
        assert memberships.scalar_one() == 0
    await engine.dispose()
