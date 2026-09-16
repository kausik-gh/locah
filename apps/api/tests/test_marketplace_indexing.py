"""Stage 3 — Marketplace indexing eligibility and isolation."""

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
from platform_core.models import MarketplaceBusinessProjection, PlatformOutboxEvent
from platform_core.services.marketplace_indexing import MarketplaceIndexingService
from platform_testing.db_helpers import ensure_auth_user
from platform_worker.job_runner import poll_and_execute_jobs
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
        json={"display_name": f"Mkt Co {uuid.uuid4().hex[:8]}", "business_type": "retail"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return cast(dict[str, Any], resp.json()["data"]["business"])


def _drain_website_jobs(business_id: str) -> None:
    async def _run() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            for _ in range(5):
                await poll_and_execute_jobs(session, "mkt-index-worker")
        await engine.dispose()

    asyncio.run(_run())


def _prepare_publishable(client: TestClient, headers: dict[str, str], business_id: str) -> None:
    _drain_website_jobs(business_id)
    client.patch(
        f"/v1/platform/businesses/{business_id}/profile",
        json={
            "description": "Neighborhood retail shop for marketplace tests",
            "tagline": "Local goods",
        },
        headers=headers,
    )
    site = client.get(f"/v1/b/{business_id}/website", headers=headers).json()["data"]
    home = next(p for p in site["draft"]["pages"] if p["slug"] == "home")
    hero = next(s for s in home["sections"] if s["section_type_id"] == "hero")
    client.patch(
        f"/v1/b/{business_id}/website/sections/{hero['id']}",
        json={"content": {"headline": "Shop local", "subheadline": "Open daily"}},
        headers=headers,
    )
    pub = client.post(f"/v1/b/{business_id}/website/publish", headers=headers)
    assert pub.status_code == 200, pub.text


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_ineligible_business_not_indexed(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business = _create_business(client, headers)
    bid = business["id"]

    async def _reindex() -> dict[str, Any]:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            result = await MarketplaceIndexingService.reindex_business(
                session,
                business_id=uuid.UUID(bid),
                correlation_id=str(uuid.uuid4()),
                trigger="test",
            )
            await session.commit()
            proj = (
                await session.execute(
                    select(MarketplaceBusinessProjection).where(
                        MarketplaceBusinessProjection.business_id == uuid.UUID(bid)
                    )
                )
            ).scalars().first()
            assert proj is None
            return result
        await engine.dispose()

    result = asyncio.run(_reindex())
    assert result["status"] == "deindexed"
    assert "visibility_not_discoverable" in result["reasons"]


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_opt_in_indexes_eligible_business(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business = _create_business(client, headers)
    bid = business["id"]
    _prepare_publishable(client, headers, bid)

    denied = client.post(
        f"/v1/b/{bid}/marketplace/opt-in",
        json={"confirmed": False},
        headers=headers,
    )
    assert denied.status_code in (400, 422)

    opt = client.post(
        f"/v1/b/{bid}/marketplace/opt-in",
        json={"confirmed": True},
        headers=headers,
    )
    assert opt.status_code == 200, opt.text
    assert opt.json()["data"]["visibility"] == "discoverable"
    assert opt.json()["data"]["index_result"]["status"] == "indexed"

    async def _check() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            proj = (
                await session.execute(
                    select(MarketplaceBusinessProjection).where(
                        MarketplaceBusinessProjection.business_id == uuid.UUID(bid)
                    )
                )
            ).scalars().first()
            assert proj is not None
            assert proj.is_discoverable is True
            outbox = await session.execute(
                select(PlatformOutboxEvent).where(
                    PlatformOutboxEvent.business_id == uuid.UUID(bid),
                    PlatformOutboxEvent.event_type == "marketplace.indexed",
                )
            )
            assert outbox.scalars().first() is not None
        await engine.dispose()

    asyncio.run(_check())


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_indexing_is_business_isolated(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    a = _create_business(client, headers)
    b = _create_business(client, headers)
    _prepare_publishable(client, headers, a["id"])
    _prepare_publishable(client, headers, b["id"])
    client.post(f"/v1/b/{a['id']}/marketplace/opt-in", json={"confirmed": True}, headers=headers)
    # B remains non-discoverable
    search = client.get(f"/v1/public/search?q={a['display_name']}")
    assert search.status_code == 200
    ids = {row["business_id"] for row in search.json()["data"]["businesses"]}
    assert a["id"] in ids
    assert b["id"] not in ids


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_visibility_opt_out_deindexes(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business = _create_business(client, headers)
    bid = business["id"]
    _prepare_publishable(client, headers, bid)
    client.post(
        f"/v1/b/{bid}/marketplace/opt-in",
        json={"confirmed": True},
        headers=headers,
    )
    out = client.post(
        f"/v1/b/{bid}/marketplace/visibility",
        json={"visibility": "unlisted"},
        headers=headers,
    )
    assert out.status_code == 200, out.text
    assert out.json()["data"]["visibility"] == "unlisted"

    async def _check() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            proj = (
                await session.execute(
                    select(MarketplaceBusinessProjection).where(
                        MarketplaceBusinessProjection.business_id == uuid.UUID(bid)
                    )
                )
            ).scalars().first()
            assert proj is None
        await engine.dispose()

    asyncio.run(_check())
