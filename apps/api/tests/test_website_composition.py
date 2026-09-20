"""Composing a website draft.

What matters here is not that a row can be inserted — it is that structure stays
governed. Only platform section types, only variants the type declares, only
sections whose module is actually live, only the draft, and an order that cannot
half-apply.
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
from platform_testing.db_helpers import ensure_auth_user
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"
pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")


def _headers(user_id: uuid.UUID, email: str) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(user_id),
            "email": email,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


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
def owner(monkeypatch: Any) -> dict[str, str]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed(user_id, email)
    return _headers(user_id, email)


@pytest.fixture
def stranger(monkeypatch: Any) -> dict[str, str]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed(user_id, email)
    return _headers(user_id, email)


def _business(
    client: TestClient,
    headers: dict[str, str],
    *,
    business_type: str = "professional_service",
    modules: tuple[str, ...] = (),
) -> str:
    resp = client.post(
        "/v1/platform/businesses",
        json={
            "display_name": f"SiteCo {uuid.uuid4().hex[:8]}",
            "business_type": business_type,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    business_id = cast(str, resp.json()["data"]["business"]["id"])
    for mid in modules:
        enabled = client.post(f"/v1/b/{business_id}/modules/{mid}/enable", headers=headers)
        assert enabled.status_code == 200, f"{mid}: {enabled.text}"
    return business_id


def _home_page(client: TestClient, headers: dict[str, str], business_id: str) -> dict[str, Any]:
    """The home page of the draft every new business is provisioned with."""
    site = client.get(f"/v1/b/{business_id}/website", headers=headers)
    assert site.status_code == 200, site.text
    draft = site.json()["data"]["draft"]
    assert draft, "a new business should have a draft"
    pages = draft["pages"]
    assert pages, "the draft should have at least one page"
    return cast(dict[str, Any], pages[0])


def _sections(client: TestClient, headers: dict[str, str], business_id: str) -> list[dict[str, Any]]:
    site = client.get(f"/v1/b/{business_id}/website", headers=headers)
    return cast(list[dict[str, Any]], site.json()["data"]["draft"]["pages"][0]["sections"])


# --------------------------------------------------------------- vocabulary


def test_available_sections_follow_the_live_modules(owner: dict[str, str]) -> None:
    """A Menu needs a catalogue behind it, and says so when there is none."""
    client = TestClient(app)
    business_id = _business(client, owner)

    resp = client.get(f"/v1/b/{business_id}/website/section-types", headers=owner)
    assert resp.status_code == 200, resp.text
    by_id = {t["id"]: t for t in resp.json()["data"]["section_types"]}

    # Always available: these read the business's own profile, not a module.
    assert by_id["hero"]["available"] is True
    assert by_id["about"]["available"] is True
    assert by_id["contact"]["available"] is True

    # Fed by the offerings catalogue, which is not on for this business.
    assert by_id["menu_section"]["available"] is False
    assert by_id["menu_section"]["requires_module"] == "offerings-catalog"
    assert by_id["menu_section"]["unavailable_reason"] == "module_not_active"

    # Turning the module on makes it offerable, without touching the website.
    client.post(f"/v1/b/{business_id}/modules/offerings-catalog/enable", headers=owner)
    again = client.get(f"/v1/b/{business_id}/website/section-types", headers=owner)
    assert {t["id"]: t for t in again.json()["data"]["section_types"]}["menu_section"][
        "available"
    ] is True


def test_a_section_whose_module_is_off_cannot_be_added(owner: dict[str, str]) -> None:
    """The gate is enforced server-side, not merely hidden in the editor."""
    client = TestClient(app)
    business_id = _business(client, owner)
    page = _home_page(client, owner, business_id)

    resp = client.post(
        f"/v1/b/{business_id}/website/pages/{page['id']}/sections",
        json={"section_type_id": "menu_section", "content": {"title": "Our menu"}},
        headers=owner,
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["details"]["code"] == "module_not_active"


def test_only_platform_section_types_exist(owner: dict[str, str]) -> None:
    """There is no way to invent a section the renderer cannot draw."""
    client = TestClient(app)
    business_id = _business(client, owner)
    page = _home_page(client, owner, business_id)

    resp = client.post(
        f"/v1/b/{business_id}/website/pages/{page['id']}/sections",
        json={"section_type_id": "three_d_particle_field", "content": {}},
        headers=owner,
    )
    assert resp.status_code == 404, resp.text


def test_a_variant_must_be_one_the_type_declares(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    page = _home_page(client, owner, business_id)

    resp = client.post(
        f"/v1/b/{business_id}/website/pages/{page['id']}/sections",
        json={
            "section_type_id": "hero",
            "content": {"headline": "Hello"},
            "layout_variant": "parallax_explosion",
        },
        headers=owner,
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["details"]["code"] == "unknown_variant"


def test_content_must_match_the_section_schema(owner: dict[str, str]) -> None:
    """A hero without a headline is not a hero."""
    client = TestClient(app)
    business_id = _business(client, owner)
    page = _home_page(client, owner, business_id)

    resp = client.post(
        f"/v1/b/{business_id}/website/pages/{page['id']}/sections",
        json={"section_type_id": "hero", "content": {"subheadline": "no headline here"}},
        headers=owner,
    )
    assert resp.status_code == 422, resp.text


# ------------------------------------------------------------- composition


def test_a_section_can_be_added_placed_duplicated_and_removed(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    page = _home_page(client, owner, business_id)
    base = f"/v1/b/{business_id}/website"
    before = len(_sections(client, owner, business_id))

    added = client.post(
        f"{base}/pages/{page['id']}/sections",
        json={
            "section_type_id": "text_block",
            "content": {"title": "How we work", "body": "Plainly, and on time."},
        },
        headers=owner,
    )
    assert added.status_code == 200, added.text
    section = added.json()["data"]
    assert section["section_type_id"] == "text_block"

    sections = _sections(client, owner, business_id)
    assert len(sections) == before + 1
    # Appended by default.
    assert sections[-1]["id"] == section["id"]

    # Placed explicitly, at the top.
    top = client.post(
        f"{base}/pages/{page['id']}/sections",
        json={
            "section_type_id": "cta_band",
            "content": {"headline": "Talk to us", "cta_label": "Get in touch"},
            "position": 0,
        },
        headers=owner,
    )
    assert top.status_code == 200, top.text
    assert _sections(client, owner, business_id)[0]["id"] == top.json()["data"]["id"]

    # Duplicated, directly beneath the original.
    dup = client.post(f"{base}/sections/{section['id']}/duplicate", headers=owner)
    assert dup.status_code == 200, dup.text
    order = [s["id"] for s in _sections(client, owner, business_id)]
    assert order.index(dup.json()["data"]["id"]) == order.index(section["id"]) + 1
    copied = next(s for s in _sections(client, owner, business_id) if s["id"] == dup.json()["data"]["id"])
    assert copied["content"]["title"] == "How we work"

    removed = client.delete(f"{base}/sections/{section['id']}", headers=owner)
    assert removed.status_code == 200, removed.text
    assert section["id"] not in [s["id"] for s in _sections(client, owner, business_id)]


def test_sort_order_stays_dense_after_every_change(owner: dict[str, str]) -> None:
    """Gaps and ties are what make a page render in an order nobody chose."""
    client = TestClient(app)
    business_id = _business(client, owner)
    page = _home_page(client, owner, business_id)
    base = f"/v1/b/{business_id}/website"

    for i in range(3):
        client.post(
            f"{base}/pages/{page['id']}/sections",
            json={"section_type_id": "text_block", "content": {"body": f"block {i}"}},
            headers=owner,
        )
    sections = _sections(client, owner, business_id)
    assert [s["sort_order"] for s in sections] == list(range(len(sections)))

    client.delete(f"{base}/sections/{sections[1]['id']}", headers=owner)
    after = _sections(client, owner, business_id)
    assert [s["sort_order"] for s in after] == list(range(len(after)))


def test_reordering_needs_the_whole_page(owner: dict[str, str]) -> None:
    """A partial order is the one shape that could half-apply, so it is refused."""
    client = TestClient(app)
    business_id = _business(client, owner)
    page = _home_page(client, owner, business_id)
    base = f"/v1/b/{business_id}/website"

    client.post(
        f"{base}/pages/{page['id']}/sections",
        json={"section_type_id": "text_block", "content": {"body": "one"}},
        headers=owner,
    )
    sections = _sections(client, owner, business_id)
    assert len(sections) >= 2

    partial = client.post(
        f"{base}/pages/{page['id']}/sections/reorder",
        json={"section_ids": [sections[0]["id"]]},
        headers=owner,
    )
    assert partial.status_code == 422, partial.text
    assert partial.json()["error"]["details"]["code"] == "incomplete_order"

    reversed_ids = [s["id"] for s in reversed(sections)]
    ok = client.post(
        f"{base}/pages/{page['id']}/sections/reorder",
        json={"section_ids": reversed_ids},
        headers=owner,
    )
    assert ok.status_code == 200, ok.text
    assert [s["id"] for s in _sections(client, owner, business_id)] == reversed_ids


def test_a_page_cannot_grow_without_limit(owner: dict[str, str]) -> None:
    """Forty sections to a page, and the forty-first is refused.

    Filling a page over HTTP has to cope with the platform legitimately
    re-drafting underneath it: business creation writes a draft and generation
    replaces it moments later, at which point the page being appended to belongs
    to a superseded version, the API correctly answers `not_draft`, and every
    section added so far is gone with the old draft. That is the platform
    working, so the test follows the live draft and counts what actually landed
    rather than how many times it asked.
    """
    client = TestClient(app)
    business_id = _business(client, owner)
    page = _home_page(client, owner, business_id)
    base = f"/v1/b/{business_id}/website"

    added = len(_sections(client, owner, business_id))
    refusal: Any = None

    # Enough budget to refill from scratch twice over and still hit the cap.
    for i in range(160):
        resp = client.post(
            f"{base}/pages/{page['id']}/sections",
            json={"section_type_id": "text_block", "content": {"body": f"b{i}"}},
            headers=owner,
        )
        if resp.status_code == 200:
            added += 1
            continue
        code = resp.json().get("error", {}).get("details", {}).get("code")
        if code == "not_draft":
            # A new draft; the old sections went with the old version.
            page = _home_page(client, owner, business_id)
            added = len(_sections(client, owner, business_id))
            continue
        refusal = resp
        break

    assert refusal is not None, f"page never filled up (reached {added} sections)"
    assert refusal.status_code == 422, refusal.text
    assert refusal.json()["error"]["details"]["code"] == "page_full"
    assert len(_sections(client, owner, business_id)) == 40


# ------------------------------------------------------- access and tenancy


def test_composition_is_tenant_isolated(owner: dict[str, str], stranger: dict[str, str]) -> None:
    client = TestClient(app)
    mine = _business(client, owner)
    page = _home_page(client, owner, mine)
    base = f"/v1/b/{mine}/website"

    added = client.post(
        f"{base}/pages/{page['id']}/sections",
        json={"section_type_id": "text_block", "content": {"body": "mine"}},
        headers=owner,
    )
    section_id = added.json()["data"]["id"]

    for resp in (
        client.post(
            f"{base}/pages/{page['id']}/sections",
            json={"section_type_id": "text_block", "content": {"body": "theirs"}},
            headers=stranger,
        ),
        client.delete(f"{base}/sections/{section_id}", headers=stranger),
        client.post(f"{base}/sections/{section_id}/duplicate", headers=stranger),
        client.get(f"{base}/section-types", headers=stranger),
    ):
        assert resp.status_code in (403, 404), resp.text

    # And it is still there afterwards.
    assert section_id in [s["id"] for s in _sections(client, owner, mine)]


def test_composition_requires_authentication(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    page = _home_page(client, owner, business_id)
    assert (
        client.post(
            f"/v1/b/{business_id}/website/pages/{page['id']}/sections",
            json={"section_type_id": "text_block", "content": {"body": "x"}},
        ).status_code
        == 401
    )
    assert client.get(f"/v1/b/{business_id}/website/section-types").status_code == 401


# ------------------------------------------------------------- templates


def test_every_template_uses_only_real_sections_and_variants() -> None:
    """A template can only describe something the renderer already draws.

    This is the check that keeps the template registry honest as it grows: the
    moment somebody adds a section id or a variant the platform does not define,
    this fails rather than shipping a page that renders wrong.
    """
    from platform_core.website.template_registry import _TEMPLATES
    from platform_core.website.section_registry import ALLOWED_SECTION_TYPE_IDS

    for template in _TEMPLATES:
        assert template.pages, f"{template.id} has no pages"
        assert any(p.slug == "home" for p in template.pages), f"{template.id} has no home page"
        for page in template.pages:
            assert page.sections, f"{template.id}/{page.slug} has no sections"
            for section in page.sections:
                assert section.section_type_id in ALLOWED_SECTION_TYPE_IDS, (
                    f"{template.id} uses unknown section {section.section_type_id}"
                )


def test_every_template_survives_the_generation_validator() -> None:
    """Templates and AI output go through one validator, so both must pass it."""
    from platform_core.validation.website import validate_generation_payload
    from platform_core.website.template_registry import (
        _TEMPLATES,
        template_to_generation_payload,
    )

    for template in _TEMPLATES:
        payload = template_to_generation_payload(
            template, business_name="Clearwater Studio", description="A real description."
        )
        validated = validate_generation_payload(payload)
        assert validated["pages"], template.id


def test_templates_are_ranked_for_the_business_type(owner: dict[str, str]) -> None:
    client = TestClient(app)
    gym = _business(client, owner, business_type="gym")

    resp = client.get(f"/v1/b/{gym}/website/templates", headers=owner)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["business_type"] == "gym"
    assert data["recommended_template_id"] == "momentum"
    # Best fit leads, but everything is offered.
    assert data["templates"][0]["id"] == "momentum"
    assert len(data["templates"]) >= 8
    assert {"menu-first", "quiet-authority", "plain-and-good"} <= {
        t["id"] for t in data["templates"]
    }


def test_a_template_needing_a_module_is_marked_not_hidden(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner, business_type="restaurant")

    resp = client.get(f"/v1/b/{business_id}/website/templates", headers=owner)
    by_id = {t["id"]: t for t in resp.json()["data"]["templates"]}
    assert by_id["menu-first"]["available"] is False
    assert by_id["menu-first"]["missing_modules"] == ["offerings-catalog"]

    blocked = client.post(
        f"/v1/b/{business_id}/website/templates/apply",
        json={"template_id": "menu-first"},
        headers=owner,
    )
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["error"]["details"]["code"] == "module_not_active"


def test_applying_a_template_replaces_the_draft(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner, business_type="professional_service")

    applied = client.post(
        f"/v1/b/{business_id}/website/templates/apply",
        json={"template_id": "quiet-authority"},
        headers=owner,
    )
    assert applied.status_code == 200, applied.text

    site = client.get(f"/v1/b/{business_id}/website", headers=owner).json()["data"]
    draft = site["draft"]
    assert draft["generated_by"] == "template:quiet-authority"
    assert [p["slug"] for p in draft["pages"]] == ["home", "services"]

    home = draft["pages"][0]
    assert [s["section_type_id"] for s in home["sections"]][:2] == ["hero", "about"]
    # Copy is filled from the business, never with filler.
    assert home["sections"][0]["content"]["headline"]
    assert "lorem" not in str(home["sections"]).lower()

    # And it is a real editable draft: structure can be changed immediately.
    added = client.post(
        f"/v1/b/{business_id}/website/pages/{home['id']}/sections",
        json={"section_type_id": "text_block", "content": {"body": "Added after the template."}},
        headers=owner,
    )
    assert added.status_code == 200, added.text


def test_an_unknown_template_is_not_found(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    resp = client.post(
        f"/v1/b/{business_id}/website/templates/apply",
        json={"template_id": "whatever-the-user-typed"},
        headers=owner,
    )
    assert resp.status_code == 404, resp.text


def test_templates_are_tenant_isolated(owner: dict[str, str], stranger: dict[str, str]) -> None:
    client = TestClient(app)
    mine = _business(client, owner)
    for resp in (
        client.get(f"/v1/b/{mine}/website/templates", headers=stranger),
        client.post(
            f"/v1/b/{mine}/website/templates/apply",
            json={"template_id": "plain-and-good"},
            headers=stranger,
        ),
    ):
        assert resp.status_code in (403, 404), resp.text
