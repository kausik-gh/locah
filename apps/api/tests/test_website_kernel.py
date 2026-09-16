"""Stage 2 — Website kernel CRUD, isolation, audit/outbox."""

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
from platform_core.models import PlatformAuditEvent, Website
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
    monkeypatch.setenv("WEBSITE_PREVIEW_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed(user_id, email)
    return _headers(user_id, email), user_id


def _create_business(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"Web Co {uuid.uuid4().hex[:8]}", "business_type": "retail"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return cast(dict[str, Any], resp.json()["data"]["business"])


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_website_provisioned_on_business_create(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business = _create_business(client, headers)
    business_id = business["id"]

    resp = client.get(f"/v1/b/{business_id}/website", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["website"]["business_id"] == business_id
    assert data["website"]["status"] == "draft"
    assert data["draft"]["version_type"] == "draft"
    assert len(data["draft"]["pages"]) >= 1

    async def _check() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            result = await session.execute(
                select(Website).where(Website.business_id == uuid.UUID(business_id))
            )
            assert result.scalars().first() is not None
        await engine.dispose()

    asyncio.run(_check())


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_website_edit_and_isolation(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers_a, _ = owner
    client = TestClient(app)
    business_a = _create_business(client, headers_a)
    bid_a = business_a["id"]

    site = client.get(f"/v1/b/{bid_a}/website", headers=headers_a).json()["data"]
    page_id = site["draft"]["pages"][0]["id"]
    section_id = site["draft"]["pages"][0]["sections"][0]["id"]

    patch_page = client.patch(
        f"/v1/b/{bid_a}/website/pages/{page_id}",
        json={"title": "Welcome Home", "seo_title": "Welcome | Store"},
        headers=headers_a,
    )
    assert patch_page.status_code == 200, patch_page.text
    assert patch_page.json()["data"]["title"] == "Welcome Home"

    patch_section = client.patch(
        f"/v1/b/{bid_a}/website/sections/{section_id}",
        json={"content": {"headline": "Hello shoppers", "subheadline": "Open daily"}},
        headers=headers_a,
    )
    assert patch_section.status_code == 200, patch_section.text
    assert patch_section.json()["data"]["content"]["headline"] == "Hello shoppers"

    # Reject arbitrary HTML
    bad = client.patch(
        f"/v1/b/{bid_a}/website/sections/{section_id}",
        json={"content": {"headline": "<script>alert(1)</script>"}},
        headers=headers_a,
    )
    assert bad.status_code in (400, 422)

    user_b = uuid.uuid4()
    email_b = f"{user_b}@example.com"
    _seed(user_b, email_b)
    headers_b = _headers(user_b, email_b)
    business_b = _create_business(client, headers_b)
    # Isolation: Business B cannot mutate Business A page IDs in its own path.
    denied_patch = client.patch(
        f"/v1/b/{business_b['id']}/website/pages/{page_id}",
        json={"title": "Hijack"},
        headers=headers_b,
    )
    assert denied_patch.status_code in (403, 404)


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_website_theme_edit_audited(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business = _create_business(client, headers)
    bid = business["id"]

    resp = client.patch(
        f"/v1/b/{bid}/website/theme",
        json={
            "navigation": [{"label": "Home", "path": "/"}],
            "theme": {"primary_color": "#111827"},
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    async def _check() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            audit = await session.execute(
                select(PlatformAuditEvent).where(
                    PlatformAuditEvent.business_id == uuid.UUID(bid),
                    PlatformAuditEvent.event_type == "website.content_edited",
                )
            )
            assert audit.scalars().first() is not None
        await engine.dispose()

    asyncio.run(_check())
