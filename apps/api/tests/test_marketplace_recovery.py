"""Stage 3 — stale-index detection, admin re-index, failure visibility."""

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
from platform_core.models import (
    MarketplaceBusinessProjection,
    MarketplaceIndexHealth,
    PlatformOutboxEvent,
)
from platform_core.services.identity import IdentityService
from platform_core.services.marketplace_indexing import MarketplaceIndexingService
from platform_testing.db_helpers import ensure_auth_user
from platform_worker.job_runner import poll_and_execute_jobs
from sqlalchemy import select, text, update
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


def _grant_admin(admin_id: uuid.UUID, email: str) -> None:
    async def _run() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await ensure_auth_user(session, admin_id, email)
            await IdentityService.bootstrap_identity(session, admin_id, email)
            await session.execute(
                text(
                    "INSERT INTO platform_admin_grants (identity_id, granted_by, reason) "
                    "VALUES (:id, :id, 'marketplace recovery test')"
                ),
                {"id": str(admin_id)},
            )
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
                await poll_and_execute_jobs(session, "mkt-recovery-worker")
        await engine.dispose()

    asyncio.run(_run())


def _create_discoverable(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"Recovery Co {uuid.uuid4().hex[:8]}", "business_type": "retail"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    business = cast(dict[str, Any], resp.json()["data"]["business"])
    bid = business["id"]
    _drain_website_jobs(bid)
    client.patch(
        f"/v1/platform/businesses/{bid}/profile",
        json={"description": "Recovery indexing business", "tagline": "Recover me"},
        headers=headers,
    )
    site = client.get(f"/v1/b/{bid}/website", headers=headers).json()["data"]
    home = next(p for p in site["draft"]["pages"] if p["slug"] == "home")
    hero = next(s for s in home["sections"] if s["section_type_id"] == "hero")
    client.patch(
        f"/v1/b/{bid}/website/sections/{hero['id']}",
        json={"content": {"headline": "Ready", "subheadline": "Open"}},
        headers=headers,
    )
    assert client.post(f"/v1/b/{bid}/website/publish", headers=headers).status_code == 200
    opt = client.post(
        f"/v1/b/{bid}/marketplace/opt-in",
        json={"confirmed": True},
        headers=headers,
    )
    assert opt.status_code == 200, opt.text
    return business


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_reconcile_repairs_stale_projection(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business = _create_discoverable(client, headers)
    bid = uuid.UUID(business["id"])

    async def _corrupt_and_reconcile() -> dict[str, Any]:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await session.execute(
                update(MarketplaceBusinessProjection)
                .where(MarketplaceBusinessProjection.business_id == bid)
                .values(display_name="STALE NAME DRIFT")
            )
            await session.commit()
            result = await MarketplaceIndexingService.reconcile_all(
                session, correlation_id=str(uuid.uuid4()), limit=200
            )
            await session.commit()
            proj = (
                await session.execute(
                    select(MarketplaceBusinessProjection).where(
                        MarketplaceBusinessProjection.business_id == bid
                    )
                )
            ).scalars().first()
            assert proj is not None
            assert proj.display_name == business["display_name"]
            return result
        await engine.dispose()

    result = asyncio.run(_corrupt_and_reconcile())
    assert result["scanned"] >= 1


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_admin_manual_reindex_audited(
    owner: tuple[dict[str, str], uuid.UUID], monkeypatch: Any
) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    headers, _ = owner
    client = TestClient(app)
    business = _create_discoverable(client, headers)
    bid = business["id"]

    admin_id = uuid.uuid4()
    admin_email = f"{admin_id}@example.com"
    _grant_admin(admin_id, admin_email)
    admin_headers = _headers(admin_id, admin_email)

    health = client.get(f"/v1/admin/marketplace/indexing/{bid}", headers=admin_headers)
    assert health.status_code == 200, health.text
    assert health.json()["data"]["health"]["last_status"] == "indexed"

    reindex = client.post(
        f"/v1/admin/marketplace/indexing/{bid}/reindex",
        headers=admin_headers,
    )
    assert reindex.status_code == 200, reindex.text
    assert reindex.json()["data"]["status"] == "indexed"

    listing = client.get("/v1/admin/marketplace/indexing", headers=admin_headers)
    assert listing.status_code == 200, listing.text
    assert "dead_letters" in listing.json()["data"]
    assert any(h["business_id"] == bid for h in listing.json()["data"]["health"])

    async def _check_audit() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT actor_identity_id, event_type FROM platform_audit_events "
                        "WHERE business_id = :bid AND event_type = 'marketplace.reindex_triggered' "
                        "ORDER BY occurred_at DESC LIMIT 1"
                    ),
                    {"bid": bid},
                )
            ).first()
            assert row is not None
            assert str(row.actor_identity_id) == str(admin_id)
            outbox = (
                await session.execute(
                    select(PlatformOutboxEvent).where(
                        PlatformOutboxEvent.business_id == uuid.UUID(bid),
                        PlatformOutboxEvent.event_type == "marketplace.indexed",
                    )
                )
            ).scalars().first()
            assert outbox is not None
        await engine.dispose()

    asyncio.run(_check_audit())


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_index_failure_recorded_on_health(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business = _create_discoverable(client, headers)
    bid = uuid.UUID(business["id"])

    async def _force_fail() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            health = (
                await session.execute(
                    select(MarketplaceIndexHealth).where(
                        MarketplaceIndexHealth.business_id == bid
                    )
                )
            ).scalars().first()
            assert health is not None
            health.last_status = "failed"
            health.last_error = "simulated index failure"
            health.last_attempt_at = datetime.now(timezone.utc)
            await session.flush()
            await session.execute(
                text(
                    """
                    INSERT INTO platform_dead_letter_events
                        (source_table, source_id, event_type, payload, final_error, attempt_count)
                    VALUES (
                        'platform_outbox_events',
                        gen_random_uuid(),
                        'marketplace.index_failed',
                        CAST(:payload AS jsonb),
                        'simulated index failure',
                        5
                    )
                    """
                ),
                {"payload": f'{{"business_id": "{bid}"}}'},
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(_force_fail())

    admin_id = uuid.uuid4()
    admin_email = f"{admin_id}@example.com"
    _grant_admin(admin_id, admin_email)
    listing = client.get(
        "/v1/admin/marketplace/indexing?status=failed",
        headers=_headers(admin_id, admin_email),
    )
    assert listing.status_code == 200
    data = listing.json()["data"]
    assert any(h["business_id"] == str(bid) for h in data["health"])
    assert any(d["event_type"] == "marketplace.index_failed" for d in data["dead_letters"])


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_opt_in_requires_auth(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"Auth Gate {uuid.uuid4().hex[:6]}", "business_type": "retail"},
        headers=headers,
    )
    bid = resp.json()["data"]["business"]["id"]
    denied = client.post(f"/v1/b/{bid}/marketplace/opt-in", json={"confirmed": True})
    assert denied.status_code in (401, 403)
