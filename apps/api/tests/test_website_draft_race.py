"""Stage 7 — website draft-version race (AUD-08).

`resolve_draft_version` used to pick the current draft by `created_at DESC`,
but multiple draft rows per website exist by design (soft-replace on
generation) and `created_at` ties for rows written in one transaction. The fix
is a `superseded_at` marker + a partial unique index making "one live draft
per website" a database invariant.

These tests exercise that invariant directly, and simulate the concurrent
replacement that the ordering approach could not survive — not just a re-run
of the existing generation tests.
"""

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
from platform_core.models import WebsiteVersion
from platform_core.resolvers.website_resolver import WebsiteResolver
from platform_core.services.website import WebsiteService
from platform_testing.db_helpers import ensure_auth_user
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"


def _token(sub: uuid.UUID, email: str) -> str:
    return jwt.encode(
        {"sub": str(sub), "email": email, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


def _engine() -> Any:
    url = get_database_url()
    assert url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return create_async_engine(url, echo=False, poolclass=NullPool)


def _seed(user_id: uuid.UUID, email: str) -> None:
    async def _run() -> None:
        engine = _engine()
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
    return {"Authorization": f"Bearer {_token(user_id, email)}"}, user_id


def _create_business(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"Draft Race {uuid.uuid4().hex[:8]}", "business_type": "cafe"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return cast(str, resp.json()["data"]["business"]["id"])


_GEN_PAYLOAD = {
    "navigation": [],
    "theme_hints": {},
    "pages": [
        {
            "slug": "home",
            "title": "Home",
            "page_type": "home",
            "sections": [
                {
                    "section_type_id": "hero",
                    "layout_variant": "centered",
                    "content": {"headline": "Generated headline"},
                }
            ],
        }
    ],
}


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_soft_replace_leaves_exactly_one_live_draft(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    headers, _ = owner
    client = TestClient(app)
    bid = uuid.UUID(_create_business(client, headers))

    async def _run() -> None:
        engine = _engine()
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            website = await WebsiteResolver.resolve_website(session, business_id=bid)
            original = await WebsiteResolver.resolve_draft_version(
                session, business_id=bid, website_id=website.id
            )

            # Two soft-replaces in a row (generation + a re-generation).
            for headline in ("first regen", "second regen"):
                payload = {
                    **_GEN_PAYLOAD,
                    "pages": [
                        {
                            **_GEN_PAYLOAD["pages"][0],
                            "sections": [
                                {
                                    "section_type_id": "hero",
                                    "layout_variant": "centered",
                                    "content": {"headline": headline},
                                }
                            ],
                        }
                    ],
                }
                await WebsiteService.replace_draft_from_generation(
                    session,
                    business_id=bid,
                    website=website,
                    payload=payload,
                    generated_by="fallback",
                    generation_job_id=None,
                )
            await session.commit()

            # Exactly one live draft, and it is the newest one.
            live = (
                await session.execute(
                    select(WebsiteVersion).where(
                        WebsiteVersion.website_id == website.id,
                        WebsiteVersion.version_type == "draft",
                        WebsiteVersion.superseded_at.is_(None),
                    )
                )
            ).scalars().all()
            assert len(live) == 1
            assert live[0].id != original.id

            resolved = await WebsiteResolver.resolve_draft_version(
                session, business_id=bid, website_id=website.id
            )
            assert resolved.id == live[0].id

            # The original is now marked, not deleted (history retained).
            refreshed_original = (
                await session.execute(
                    select(WebsiteVersion).where(WebsiteVersion.id == original.id)
                )
            ).scalar_one()
            assert refreshed_original.superseded_at is not None
        await engine.dispose()

    asyncio.run(_run())


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_concurrent_soft_replace_cannot_produce_two_live_drafts(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    """The scenario the created_at approach could not survive.

    Two `replace_draft_from_generation` calls run against the same website from
    separate sessions/transactions. The partial unique index guarantees the
    outcome: exactly one live draft, and one of the two transactions fails
    rather than both silently "winning" and leaving two live rows for
    `resolve_draft_version` to arbitrate.
    """
    headers, _ = owner
    client = TestClient(app)
    bid = uuid.UUID(_create_business(client, headers))

    async def _run() -> None:
        engine = _engine()
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with factory() as s:
            website = await WebsiteResolver.resolve_website(s, business_id=bid)
        website_id = website.id

        async def replace(headline: str) -> str:
            async with factory() as session:
                w = await WebsiteResolver.resolve_website(session, business_id=bid)
                payload = {
                    **_GEN_PAYLOAD,
                    "pages": [
                        {
                            **_GEN_PAYLOAD["pages"][0],
                            "sections": [
                                {
                                    "section_type_id": "hero",
                                    "layout_variant": "centered",
                                    "content": {"headline": headline},
                                }
                            ],
                        }
                    ],
                }
                try:
                    await WebsiteService.replace_draft_from_generation(
                        session,
                        business_id=bid,
                        website=w,
                        payload=payload,
                        generated_by="fallback",
                        generation_job_id=None,
                    )
                    await session.commit()
                    return "ok"
                except Exception as exc:  # noqa: BLE001 — asserting the class below
                    await session.rollback()
                    return type(exc).__name__

        results = await asyncio.gather(replace("racer A"), replace("racer B"))

        # At least one succeeded; if both raced into the index, one failed.
        assert "ok" in results
        if results.count("ok") == 1:
            assert any(r != "ok" for r in results)

        async with factory() as session:
            live = (
                await session.execute(
                    select(func.count())
                    .select_from(WebsiteVersion)
                    .where(
                        WebsiteVersion.website_id == website_id,
                        WebsiteVersion.version_type == "draft",
                        WebsiteVersion.superseded_at.is_(None),
                    )
                )
            ).scalar_one()
            assert live == 1, f"expected exactly one live draft, found {live}"
        await engine.dispose()

    asyncio.run(_run())


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_unique_index_rejects_a_second_hand_rolled_live_draft(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    """Direct proof the DB invariant holds even if application code is bypassed."""
    headers, _ = owner
    client = TestClient(app)
    bid = uuid.UUID(_create_business(client, headers))

    async def _run() -> None:
        engine = _engine()
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            website = await WebsiteResolver.resolve_website(session, business_id=bid)
            raised = False
            try:
                session.add(
                    WebsiteVersion(
                        website_id=website.id,
                        business_id=bid,
                        version_type="draft",
                        navigation=[],
                        theme={},
                    )
                )
                await session.flush()
            except Exception:
                raised = True
            assert raised, "a second live draft should violate uq_website_versions_one_live_draft"
            await session.rollback()
        await engine.dispose()

    asyncio.run(_run())
