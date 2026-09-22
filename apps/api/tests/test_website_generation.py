"""Stage 2 — Website generation: AI failure → fallback, never blocks creation."""

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
from platform_core.models import PlatformOutboxEvent
from platform_core.models import WebsiteGenerationJob as WGJ
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
        json={"display_name": f"Gen Co {uuid.uuid4().hex[:8]}", "business_type": "restaurant"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return cast(str, resp.json()["data"]["business"]["id"])


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_generation_fallback_always_produces_draft(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    """With no AI provider configured, `execute_job` must still land a valid
    draft and emit the events. Driven directly (own job row, no async job) so a
    locally-running worker cannot race us for it."""
    import platform_core.services.website_generation as gen_mod

    headers, user_id = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)
    biz_uuid = uuid.UUID(business_id)

    async def _run() -> dict[str, Any]:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            # Business creation no longer auto-enqueues generation (see
            # test_creation_never_enqueues_or_calls_ai), so there is no existing
            # WebsiteGenerationJob row to borrow triggered_by from. Use the owner's
            # own identity, exactly as the real interview/manual-generate paths do.
            triggered_by = user_id
            job = WGJ(
                business_id=biz_uuid,
                status="pending",
                prompt_version="v1",
                triggered_by=triggered_by,
            )
            session.add(job)
            await session.flush()
            await session.commit()
            res = await gen_mod.WebsiteGenerationService.execute_job(
                session, generation_job_id=job.id, correlation_id=str(uuid.uuid4())
            )
            await session.commit()
            outbox = await session.execute(
                select(PlatformOutboxEvent).where(
                    PlatformOutboxEvent.business_id == biz_uuid,
                    PlatformOutboxEvent.event_type == "website.draft_generated",
                )
            )
            assert outbox.scalars().first() is not None
        await engine.dispose()
        return res

    res = asyncio.run(_run())
    # No XAI_API_KEY in the suite (conftest) → deterministic fallback.
    assert res["status"] == "fallback_used"
    assert res["generated_by"] == "deterministic_fallback"
    assert res["version_id"]

    site = client.get(f"/v1/b/{business_id}/website", headers=headers)
    assert site.status_code == 200, site.text
    draft = site.json()["data"]["draft"]
    assert draft["generated_by"] == "deterministic_fallback"
    assert len(draft["pages"]) >= 3
    slugs = {p["slug"] for p in draft["pages"]}
    assert "home" in slugs
    assert "menu" in slugs  # restaurant page set
    # A fallback draft is built from the business type and never sees a
    # template, so it must not claim one — the picker shows "your site was
    # built from this" on the strength of exactly this field.
    assert "template_id" not in (draft.get("theme") or {}), draft.get("theme")


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_manual_generate_idempotent_while_running(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)

    # Pending job from create still running/pending → second enqueue conflicts.
    resp = client.post(f"/v1/b/{business_id}/website/generate", json={}, headers=headers)
    # Either conflict (pending) or success if prior job already finished.
    assert resp.status_code in (200, 409), resp.text


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_fallback_unit_schema_valid() -> None:
    from platform_core.validation.website import validate_generation_payload
    from platform_core.website.fallback_generator import build_deterministic_draft

    payload = build_deterministic_draft(
        display_name="Unit Cafe",
        business_type="cafe",
        tagline="Fresh coffee",
        description="Neighborhood cafe",
    )
    validated = validate_generation_payload(payload)
    assert validated["pages"][0]["slug"] == "home"


class _StubProvider:
    """Deterministic stand-in for GrokProvider — records the prompt it saw."""

    provider_name = "xai"
    model_name = "test-grok"

    last_prompt: str = ""

    async def generate_structured(self, prompt, schema, model_config, timeout_seconds):  # type: ignore[no-untyped-def]
        _StubProvider.last_prompt = prompt
        return {
            "pages": [
                {
                    "slug": "home",
                    "title": "Home",
                    "page_type": "home",
                    "sections": [
                        {
                            "section_type_id": "hero",
                            "layout_variant": "centered",
                            "content": {"headline": "Stubbed headline", "subheadline": "from AI"},
                            "is_visible": True,
                        }
                    ],
                }
            ],
            "navigation": [{"label": "Home", "path": "/"}],
            "theme_hints": {"primary_color": "#4B6B5A"},
        }


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_generation_uses_ai_provider_and_intake(
    owner: tuple[dict[str, str], uuid.UUID], monkeypatch: Any
) -> None:
    """Drives `execute_job` directly with a stub provider and a job row we
    create ourselves — no `platform_async_jobs` row, so a locally-running
    worker cannot race us for it."""
    import platform_core.services.website_generation as gen_mod

    monkeypatch.setattr(gen_mod, "get_ai_provider", lambda: _StubProvider())

    headers, user_id = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)
    biz_uuid = uuid.UUID(business_id)

    intake = {
        "lead_with": "offerings",
        "palette": "sage",
        "words_prefer": "hand-rolled, small-batch",
        "menu_items": [{"name": "Ragi dosa", "description": "crisp, stone-ground"}],
    }

    async def _run() -> dict[str, Any]:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            # Business creation no longer auto-enqueues generation (see
            # test_creation_never_enqueues_or_calls_ai), so there is no existing
            # WebsiteGenerationJob row to borrow triggered_by from. Use the owner's
            # own identity, exactly as the real interview/manual-generate paths do.
            triggered_by = user_id
            job = WGJ(
                business_id=biz_uuid,
                status="pending",
                prompt_version="v1",
                triggered_by=triggered_by,
                intake=intake,
            )
            session.add(job)
            await session.flush()
            await session.commit()
            res = await gen_mod.WebsiteGenerationService.execute_job(
                session, generation_job_id=job.id, correlation_id=str(uuid.uuid4())
            )
            await session.commit()
        await engine.dispose()
        return res

    res = asyncio.run(_run())
    assert res["generated_by"] == "ai_generation", res
    assert res["status"] == "completed"
    # the one generate_structured call saw the assembled intake brief
    assert "Ragi dosa" in _StubProvider.last_prompt
    assert "hand-rolled" in _StubProvider.last_prompt
    assert "offerings" in _StubProvider.last_prompt


class _InvalidProvider:
    provider_name = "xai"
    model_name = "invalid-grok"

    async def generate_structured(self, prompt, schema, model_config, timeout_seconds):  # type: ignore[no-untyped-def]
        return {"pages": [], "navigation": [], "theme_hints": {}}


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_invalid_ai_output_falls_back_to_deterministic_draft(
    owner: tuple[dict[str, str], uuid.UUID], monkeypatch: Any
) -> None:
    import platform_core.services.website_generation as gen_mod

    monkeypatch.setattr(gen_mod, "get_ai_provider", lambda: _InvalidProvider())

    headers, user_id = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)
    biz_uuid = uuid.UUID(business_id)

    async def _run() -> dict[str, Any]:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            # Business creation no longer auto-enqueues generation (see
            # test_creation_never_enqueues_or_calls_ai), so there is no existing
            # WebsiteGenerationJob row to borrow triggered_by from. Use the owner's
            # own identity, exactly as the real interview/manual-generate paths do.
            triggered_by = user_id
            job = WGJ(
                business_id=biz_uuid,
                status="pending",
                prompt_version="v1",
                triggered_by=triggered_by,
            )
            session.add(job)
            await session.flush()
            await session.commit()
            res = await gen_mod.WebsiteGenerationService.execute_job(
                session, generation_job_id=job.id, correlation_id=str(uuid.uuid4())
            )
            await session.commit()
        await engine.dispose()
        return res

    res = asyncio.run(_run())
    assert res["generated_by"] == "deterministic_fallback"
    assert res["status"] == "fallback_used"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_questionnaire_endpoint_is_business_type_aware(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)  # restaurant

    resp = client.get(f"/v1/b/{business_id}/website/questionnaire", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["business_type"] == "restaurant"
    section_ids = {s["id"] for s in data["sections"]}
    assert "essentials" in section_ids
    assert "optional" in section_ids
    assert "type_specific" in section_ids
    ts = next(s for s in data["sections"] if s["id"] == "type_specific")
    assert ts["questions"][0]["id"] == "menu_items"
    essentials = next(s for s in data["sections"] if s["id"] == "essentials")
    for q in essentials["questions"]:
        assert q["optional"] is True
        assert q.get("example")


class _OverreachingProvider:
    """A model that answers with sections this business may not be entitled to.

    Not a straw man: the section types are real, the schema accepts them, and a
    model reading "you are a gym" has every reason to reach for a plans
    comparison. Whether the business has that module switched on is a fact only
    the platform holds, which is exactly why the check cannot live in the
    prompt.
    """

    provider_name = "xai"
    model_name = "test-grok"

    last_prompt: str = ""

    async def generate_structured(self, prompt, schema, model_config, timeout_seconds):  # type: ignore[no-untyped-def]
        _OverreachingProvider.last_prompt = prompt
        return {
            "pages": [
                {
                    "slug": "home",
                    "title": "Home",
                    "page_type": "home",
                    "sections": [
                        {
                            "section_type_id": "hero",
                            "layout_variant": "full_width",
                            "content": {"headline": "Lift"},
                            "is_visible": True,
                        },
                        {
                            "section_type_id": "plans_section",
                            "layout_variant": "comparison",
                            "content": {"title": "Membership"},
                            "is_visible": True,
                        },
                        {
                            "section_type_id": "enquiry_form",
                            "layout_variant": "default",
                            "content": {"title": "Ask us"},
                            "is_visible": True,
                        },
                    ],
                }
            ],
            "navigation": [{"label": "Home", "path": "/"}],
            # A personality the stylesheet does not implement, and a colour
            # that is not a colour. Both reach the DOM unchallenged unless
            # something clamps them.
            "theme_hints": {"primary_color": "industrial grey", "personality": "brutalist"},
        }


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_generated_draft_cannot_contain_sections_the_business_lacks(
    owner: tuple[dict[str, str], uuid.UUID], monkeypatch: Any
) -> None:
    """The capability fence, proved on the persisted draft rather than in a unit.

    This is the claim that matters in production: whatever the model returns,
    what lands in `website_sections` is a subset of what this business could
    have added by hand. The same run also checks the two halves that make
    generation a personalisation rather than an invention — the prompt carried
    a named reference composition, and the theme that survived is one the
    stylesheet can actually render.
    """
    import platform_core.services.website_generation as gen_mod
    from platform_core.models import WebsitePage, WebsiteSection, WebsiteVersion
    from platform_core.services.website_composition import WebsiteCompositionService
    from platform_core.website.generation_plan import PERSONALITIES

    monkeypatch.setattr(gen_mod, "get_ai_provider", lambda: _OverreachingProvider())

    headers, user_id = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)
    biz_uuid = uuid.UUID(business_id)

    async def _run() -> dict[str, Any]:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            # Business creation no longer auto-enqueues generation (see
            # test_creation_never_enqueues_or_calls_ai), so there is no existing
            # WebsiteGenerationJob row to borrow triggered_by from. Use the owner's
            # own identity, exactly as the real interview/manual-generate paths do.
            triggered_by = user_id
            job = WGJ(
                business_id=biz_uuid,
                status="pending",
                prompt_version="v2",
                triggered_by=triggered_by,
            )
            session.add(job)
            await session.flush()
            await session.commit()

            # What this business could add by hand — the standard the draft is
            # held to, read from the same service the editor uses.
            capabilities = await WebsiteCompositionService.available_section_types(
                session, business_id=biz_uuid
            )
            allowed = {row["id"] for row in capabilities if row["available"]}

            await gen_mod.WebsiteGenerationService.execute_job(
                session, generation_job_id=job.id, correlation_id=str(uuid.uuid4())
            )
            await session.commit()

            draft = (
                await session.execute(
                    select(WebsiteVersion).where(
                        WebsiteVersion.business_id == biz_uuid,
                        WebsiteVersion.version_type == "draft",
                        WebsiteVersion.superseded_at.is_(None),
                    )
                )
            ).scalars().one()
            section_types = (
                (
                    await session.execute(
                        select(WebsiteSection.section_type_id)
                        .join(WebsitePage, WebsiteSection.page_id == WebsitePage.id)
                        .where(WebsitePage.website_version_id == draft.id)
                    )
                )
                .scalars()
                .all()
            )
            result = {
                "allowed": allowed,
                "section_types": set(section_types),
                "theme": dict(draft.theme or {}),
            }
        await engine.dispose()
        return result

    out = asyncio.run(_run())

    assert out["section_types"], "generation must still produce a draft"
    unentitled = out["section_types"] - out["allowed"]
    assert not unentitled, f"draft contains sections this business cannot have: {unentitled}"

    # Guard against the assertion above going quietly vacuous. A business is
    # created with the core modules only, so the two sections the stub reached
    # for are genuinely out of reach and the fence really did have work to do.
    assert "plans_section" not in out["allowed"], "fixture no longer exercises the fence"
    assert "plans_section" not in out["section_types"]
    assert "enquiry_form" not in out["allowed"], "fixture no longer exercises the fence"
    assert "enquiry_form" not in out["section_types"]
    assert "hero" in out["section_types"], "the entitled section must survive"

    # The reference composition reached the model.
    assert "REFERENCE COMPOSITION" in _OverreachingProvider.last_prompt
    assert "AVAILABLE SECTION TYPES" in _OverreachingProvider.last_prompt

    # A theme the renderer can use, and a record of where the draft came from.
    theme = out["theme"]
    assert theme["personality"] in PERSONALITIES, theme
    assert str(theme["primary_color"]).startswith("#"), theme
    assert theme.get("template_id"), "a generated draft must name its reference"
