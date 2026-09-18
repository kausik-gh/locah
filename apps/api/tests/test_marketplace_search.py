"""Stage 3 — Marketplace search relevance, states, and dual eligibility."""

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
from platform_core.models import Business, MarketplaceBusinessProjection
from platform_testing.db_helpers import ensure_auth_user
from platform_worker.job_runner import poll_and_execute_jobs
from sqlalchemy import update
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
                await poll_and_execute_jobs(session, "mkt-search-worker")
        await engine.dispose()

    asyncio.run(_run())


def _create_discoverable(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str,
    business_type: str = "retail",
) -> dict[str, Any]:
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": name, "business_type": business_type},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    business = cast(dict[str, Any], resp.json()["data"]["business"])
    bid = business["id"]
    _drain_website_jobs(bid)
    client.patch(
        f"/v1/platform/businesses/{bid}/profile",
        json={"description": f"{name} description for discovery", "tagline": name},
        headers=headers,
    )
    site = client.get(f"/v1/b/{bid}/website", headers=headers).json()["data"]
    home = next(p for p in site["draft"]["pages"] if p["slug"] == "home")
    hero = next(s for s in home["sections"] if s["section_type_id"] == "hero")
    client.patch(
        f"/v1/b/{bid}/website/sections/{hero['id']}",
        json={"content": {"headline": name, "subheadline": "Open"}},
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
def test_search_relevance_and_profile(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    unique = f"CedarPeak-{uuid.uuid4().hex[:6]}"
    business = _create_discoverable(client, headers, name=unique, business_type="retail")

    search = client.get(f"/v1/public/search?q={unique}")
    assert search.status_code == 200, search.text
    body = search.json()["data"]
    assert body["state"] == "results"
    assert any(b["slug"] == business["slug"] for b in body["businesses"])

    profile = client.get(f"/v1/public/businesses/{business['slug']}")
    assert profile.status_code == 200, profile.text
    pdata = profile.json()["data"]
    assert pdata["business"]["slug"] == business["slug"]
    assert any(a["action"] == "visit_website" for a in pdata["actions"])
    assert pdata["website_handoff"]["destination_intent"] == "visit_website"
    assert "intent=" in pdata["website_handoff"]["href"] or pdata["website_handoff"][
        "href"
    ].startswith("/")


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_search_no_results_and_type_filter(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    unique = f"TypeFilter-{uuid.uuid4().hex[:6]}"
    _create_discoverable(client, headers, name=unique, business_type="retail")

    miss = client.get("/v1/public/search?q=zzz-no-such-marketplace-term-999")
    assert miss.status_code == 200
    miss_body = miss.json()["data"]
    assert miss_body["state"] in {"no_results", "sparse_market"}
    assert miss_body["counts"]["businesses"] == 0

    typed = client.get(f"/v1/public/search?q={unique}&type=restaurant")
    assert typed.status_code == 200
    assert typed.json()["data"]["counts"]["businesses"] == 0

    retail = client.get(f"/v1/public/search?q={unique}&type=retail")
    assert retail.status_code == 200
    assert retail.json()["data"]["counts"]["businesses"] >= 1


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_query_time_eligibility_blocks_stale_projection(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    """Eligibility is enforced twice — index time and query time (Doc 12 §14.4)."""
    headers, _ = owner
    client = TestClient(app)
    unique = f"StaleGate-{uuid.uuid4().hex[:6]}"
    business = _create_discoverable(client, headers, name=unique)
    bid = uuid.UUID(business["id"])

    async def _make_ineligible_but_keep_projection() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await session.execute(
                update(Business).where(Business.id == bid).values(visibility="private")
            )
            # Leave projection discoverable to simulate drift.
            await session.execute(
                update(MarketplaceBusinessProjection)
                .where(MarketplaceBusinessProjection.business_id == bid)
                .values(is_discoverable=True)
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(_make_ineligible_but_keep_projection())

    search = client.get(f"/v1/public/search?q={unique}")
    assert search.status_code == 200
    assert not any(b["business_id"] == str(bid) for b in search.json()["data"]["businesses"])

    profile = client.get(f"/v1/public/businesses/{business['slug']}")
    assert profile.status_code == 404


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_location_refinement(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    unique = f"CityBiz-{uuid.uuid4().hex[:6]}"
    business = _create_discoverable(client, headers, name=unique)
    bid = business["id"]
    # Business creation already provisions the primary location; a second
    # primary POST correctly conflicts.
    dup_primary = client.post(
        f"/v1/platform/businesses/{bid}/locations",
        json={"name": "Main", "is_primary": True},
        headers=headers,
    )
    assert dup_primary.status_code == 409, dup_primary.text

    # Refine the existing primary location with the city under test.
    locations = client.get(f"/v1/platform/businesses/{bid}/locations", headers=headers).json()[
        "data"
    ]
    primary_loc_id = next(loc["id"] for loc in locations if loc["is_primary"])
    refined = client.patch(
        f"/v1/platform/businesses/{bid}/locations/{primary_loc_id}",
        json={
            "address": {"city": "PuneTestCity", "line1": "1 Main St"},
            "timezone": "Asia/Kolkata",
        },
        headers=headers,
    )
    assert refined.status_code == 200, refined.text
    # Re-index after location update (API may emit location.created; call service path via opt visibility toggle no-op or reindex)
    from platform_core.services.marketplace_indexing import MarketplaceIndexingService

    async def _reindex() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await MarketplaceIndexingService.reindex_business(
                session,
                business_id=uuid.UUID(bid),
                correlation_id=str(uuid.uuid4()),
                trigger="test_location",
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(_reindex())

    hit = client.get(f"/v1/public/search?q={unique}&location=PuneTestCity")
    assert hit.status_code == 200
    assert hit.json()["data"]["counts"]["businesses"] >= 1

    miss = client.get(f"/v1/public/search?q={unique}&location=NowhereVilleXYZ")
    assert miss.status_code == 200
    assert miss.json()["data"]["counts"]["businesses"] == 0


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_sparse_market_state_when_empty_index() -> None:
    client = TestClient(app)
    # When nothing matches and index is empty-ish, API reports sparse_market or no_results.
    resp = client.get("/v1/public/search?q=utterly-impossible-term-xyz-000")
    assert resp.status_code == 200
    assert resp.json()["data"]["state"] in {"sparse_market", "no_results"}


def _drift(bid: uuid.UUID, **live_state: Any) -> None:
    """Change live business state while leaving the projection saying otherwise.

    The projection is what search reads for the card's contents, so forcing it
    to stay discoverable is what makes these tests meaningful: anything still
    filtering the business out has to be doing a live check.
    """

    async def _run() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await session.execute(update(Business).where(Business.id == bid).values(**live_state))
            await session.execute(
                update(MarketplaceBusinessProjection)
                .where(MarketplaceBusinessProjection.business_id == bid)
                .values(is_discoverable=True)
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(_run())


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
@pytest.mark.parametrize(
    ("label", "live_state"),
    [
        ("suspended", {"status": "suspended"}),
        ("deactivated", {"state": "closed"}),
        ("soft_deleted", {"deleted_at": datetime.now(timezone.utc)}),
        ("private", {"visibility": "private"}),
        # `unlisted` passes the public arm of the businesses RLS policy, so it
        # is the case a bulk read is most likely to get wrong: reachable by
        # direct link, but never by browsing.
        ("unlisted", {"visibility": "unlisted"}),
    ],
)
def test_live_state_removes_business_from_search_despite_stale_projection(
    owner: tuple[dict[str, str], uuid.UUID],
    label: str,
    live_state: dict[str, Any],
) -> None:
    """Every live-state fact must still hide a business with a stale projection.

    Search stopped re-reading four tables per result to kill an N+1, and reads
    capability_flags and the blurb off the projection instead. What it must not
    stop doing is the live check on `businesses` — these are the facts where
    being wrong means listing a business that asked not to be listed.
    """
    headers, _ = owner
    client = TestClient(app)
    unique = f"LiveGate{label.title().replace('_', '')}-{uuid.uuid4().hex[:6]}"
    business = _create_discoverable(client, headers, name=unique)
    bid = uuid.UUID(business["id"])

    # Visible to begin with, otherwise the assertion below proves nothing.
    before = client.get(f"/v1/public/search?q={unique}")
    assert before.status_code == 200, before.text
    assert any(b["business_id"] == str(bid) for b in before.json()["data"]["businesses"]), (
        f"{label}: business was not discoverable before the drift, so the test is vacuous"
    )

    _drift(bid, **live_state)

    after = client.get(f"/v1/public/search?q={unique}")
    assert after.status_code == 200, after.text
    assert not any(b["business_id"] == str(bid) for b in after.json()["data"]["businesses"]), (
        f"{label}: still listed in search after live state changed"
    )


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_bulk_eligibility_does_not_leak_another_tenants_rows(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    """The bulk read must answer per business, not leak one verdict across many.

    `evaluate_live_eligibility_bulk` takes a list of ids and returns a map. A
    plausible way to get that wrong is to let one row satisfy the whole batch,
    which would make a suspended business ride along beside a healthy one.
    """
    headers, _ = owner
    client = TestClient(app)
    tag = uuid.uuid4().hex[:6]
    good = _create_discoverable(client, headers, name=f"PairOk-{tag}")
    bad = _create_discoverable(client, headers, name=f"PairGone-{tag}")

    _drift(uuid.UUID(bad["id"]), status="suspended")

    # Both share the tag, so a single query returns them as one batch.
    search = client.get(f"/v1/public/search?q={tag}")
    assert search.status_code == 200, search.text
    listed = {b["business_id"] for b in search.json()["data"]["businesses"]}
    assert good["id"] in listed, "healthy business was filtered out alongside the suspended one"
    assert bad["id"] not in listed, "suspended business rode along with a healthy one in the batch"
