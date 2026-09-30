"""Manual pictures in the Website editor — for every section that can carry one.

Nine unrelated businesses are built through the ordinary interview (no
business-specific code anywhere), then the editor's "Generate a picture" is
called on every picture its sections can carry, as the server's image_policy
describes them. Gemini is stubbed only at its boundary (the image bytes and
the storage upload). What must hold:

* hero / story / closing band and representative cards can be drawn, and each
  drawn picture is persisted as a gemini_generated draft with its slot;
* factual evidence is never drawn: a developer's named projects, a gallery;
* a section of another business is never touched;
* an owner's own uploaded hero is never replaced by a drawn one.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app

from platform_core.website.image_generation import GeneratedImage
from platform_testing.phase_b import sql
from test_start_conversation import owner  # noqa: F401 — the signed-in owner fixture
from test_website_conversation import Talk, sections

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")

JPEG = GeneratedImage(mime_type="image/jpeg", bytes=b"\xff\xd8 drawn", model="stub", latency_ms=1, prompt="")

# (category, subcategory, name, what the owner says) — only ordinary answers.
OWNERS = [
    ("home_food", "home_kitchen", "Amma's Kitchen",
     "We cook sambar rice, curd rice and chicken biryani at home. People order on WhatsApp."),
    ("food_service", "restaurant", "Saffron Table",
     "We are a South Indian restaurant serving dosa, meals and filter coffee. People book a table by phone."),
    ("fitness", "gym", "Iron Yard", "A strength gym with powerlifting and personal training. People WhatsApp us to join."),
    ("real_estate", "developer", "Aranya Homes",
     "We build villas and apartments. Our projects are Aranya Greens and Aranya Heights. Buyers call to book a "
     "site visit."),
    ("industrial", "industrial_supplier", "Torque Flow",
     "We supply centrifugal pumps, valves and motors to factories. Buyers call us for a quote."),
    ("healthcare", "clinic", "Care Point Clinic",
     "A family clinic for general check-ups, vaccinations and diabetes care. Patients book on WhatsApp."),
    ("beauty", "salon", "Mirror Salon", "Haircuts, bridal makeup and facials. Customers book on WhatsApp."),
    ("education", "tuition_centre", "Apex Tuition",
     "Maths and science tuition for classes 8 to 12. Parents call us to enrol."),
    ("home_services", "appliance_repair", "Fixit Appliance Care",
     "We repair washing machines, fridges and ACs at home. Customers call us to book a repair."),
]


# What each sells, said the way an owner lists it.
LISTS = {
    "home_kitchen": "sambar rice, curd rice and chicken biryani",
    "restaurant": "dosa, meals and filter coffee",
    "gym": "powerlifting, strength classes and personal training",
    "developer": "Aranya Greens villas and Aranya Heights apartments",
    "industrial_supplier": "centrifugal pumps, valves and motors",
    "clinic": "general check-ups, vaccinations and diabetes care",
    "salon": "haircuts, bridal makeup and facials",
    "tuition_centre": "maths tuition, science tuition and JEE foundation",
    "appliance_repair": "washing machine repair, fridge repair and AC service",
}


@pytest.fixture
def drawn(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Gemini's picture bytes and the storage upload — nothing else is stubbed."""
    from unittest.mock import AsyncMock

    import platform_core.media.supabase_storage as storage
    import platform_core.services.website_images as website_images

    prompts: list[str] = []

    async def generate(prompt: str, *, aspect_ratio: str = "16:9", **_: Any) -> GeneratedImage:
        prompts.append(prompt)
        return JPEG

    monkeypatch.setattr(website_images, "generate_image_bytes", generate)
    monkeypatch.setattr(storage, "put_generated_object", AsyncMock())
    monkeypatch.setattr(storage, "public_url", lambda bucket, key: f"https://storage.test/{bucket}/{key}")
    return prompts


def _build(client: TestClient, owner: dict[str, str], spec: tuple[str, str, str, str]) -> Talk:  # noqa: F811
    cat, sub, name, said = spec
    started = client.post("/v1/platform/businesses/start", headers=owner, json={
        "category_key": cat, "subcategory_key": sub}).json()["data"]
    business_id = started["business"]["id"]
    talk = Talk(client, {**owner, "X-Business-Id": business_id, "X-Operating-Context": "business"}, business_id)
    talk.say(said)
    talk.say(f"We offer {LISTS[sub]}. Call or WhatsApp 98401 2{abs(hash(name)) % 10000:04d}, we are in Anna Nagar, Chennai.")
    talk.send("correct", slot="name", values=[], text=name)
    talk.send("build")
    return talk


def _generate(talk: Talk, section_id: str, **target: Any) -> dict[str, Any]:
    res = talk.client.post(f"/v1/b/{talk.id}/website/sections/{section_id}/generate-image",
                           headers=talk.headers, json=target)
    assert res.status_code == 200, res.text
    data: dict[str, Any] = res.json()["data"]
    return data


def _provenance(asset_id: str) -> tuple[str, str, str]:
    source, slot, approval = sql("select source_type, generated_for, approval_state from media_assets "
                                 "where id = :a", a=asset_id)[0]
    return str(source), str(slot), str(approval)


@pytest.mark.parametrize("spec", OWNERS, ids=[o[1] for o in OWNERS])
def test_every_picture_a_section_can_carry_is_offered_honestly(owner, drawn, spec) -> None:  # noqa: F811
    with TestClient(app) as client:
        talk = _build(client, owner, spec)
        site = talk.site()
        offered = 0
        for section in sections(site):
            policy = section.get("image_policy") or {}
            kind = section["section_type_id"]
            if policy.get("self") == "draw":
                before = len(drawn)
                result = _generate(talk, section["id"])
                assert result["ok"], (kind, result)
                assert len(drawn) == before + 1
                assert _provenance(result["asset"]["id"]) == ("gemini_generated", f"editor:{kind}", "draft")
                offered += 1
            for list_key in ("items", "categories"):
                rows = section["content"].get(list_key) or []
                if not policy.get("items") or not rows:
                    continue
                before = len(drawn)
                result = _generate(talk, section["id"], list_key=list_key, index=0)
                if policy["items"] == "draw":
                    assert result["ok"], (kind, list_key, result)
                    assert _provenance(result["asset"]["id"])[1] == f"editor:{kind}:{list_key}.0"
                    subject = str(rows[0].get("name", ""))
                    assert subject.split()[0].lower() in drawn[-1].lower()  # drawn for THAT card
                else:
                    assert result == {"ok": False, "reason": "needs_real_photo",
                                      "detail": "This should be a real photo of your work — upload one instead."}
                    assert len(drawn) == before  # never drawn
                offered += 1
        assert offered >= 2, [(s["section_type_id"], s.get("image_policy")) for s in sections(site)]
        # Everything drawn is on the page now, in the right place.
        after = talk.site()
        hero = next(s for s in sections(after) if s["section_type_id"] == "hero")
        assert hero["content"].get("image_asset_id") and hero["assets"]["image_asset_id"]["draft"] is True


def test_a_developers_projects_are_never_drawn(owner, drawn) -> None:  # noqa: F811
    with TestClient(app) as client:
        talk = _build(client, owner, OWNERS[3])
        # The owner adds their projects in the editor.
        home = next(p for p in talk.site()["pages"] if p["slug"] == "home")
        added = client.post(f"/v1/b/{talk.id}/website/pages/{home['id']}/sections", headers=talk.headers, json={
            "section_type_id": "product_showcase", "layout_variant": "project_cards",
            "content": {"title": "Our projects", "items": [{"name": "Aranya Greens"}, {"name": "Aranya Heights"}]}})
        assert added.status_code == 200, added.text
        projects = next(s for s in sections(talk.site()) if s["section_type_id"] == "product_showcase")
        assert projects["layout_variant"] == "project_cards"
        assert projects["image_policy"] == {"items": "real_photo"}
        assert _generate(talk, projects["id"], list_key="items", index=0)["reason"] == "needs_real_photo"
        assert drawn == []


def test_another_business_section_is_never_touched(owner, drawn) -> None:  # noqa: F811
    with TestClient(app) as client:
        mine = _build(client, owner, OWNERS[0])
        theirs = _build(client, owner, OWNERS[2])
        their_hero = next(s for s in sections(theirs.site()) if s["section_type_id"] == "hero")
        result = _generate(mine, their_hero["id"])
        assert result == {"ok": False, "reason": "section_missing"}
        assert drawn == []


def test_the_owners_uploaded_hero_is_never_replaced(owner, monkeypatch) -> None:  # noqa: F811
    """Automatic drafts fill what is missing; the owner's own hero stays."""
    from unittest.mock import AsyncMock

    import platform_core.interview.media_director as md
    import platform_core.media.supabase_storage as storage
    import platform_core.website.image_generation as images
    from test_website_creative_v4 import _run_job

    prompts: list[str] = []

    async def draw(prompt: str, *, aspect_ratio: str = "16:9", timeout_seconds: int = 60) -> Any:
        prompts.append(prompt)
        return JPEG, ""

    monkeypatch.setattr(images, "image_generation_available", lambda: True)
    monkeypatch.setattr(md, "generate_image", draw)
    monkeypatch.setattr(storage, "put_generated_object", AsyncMock())
    monkeypatch.setattr(storage, "public_url", lambda bucket, key: f"https://storage.test/{bucket}/{key}")
    with TestClient(app) as client:
        cat, sub, name, said = OWNERS[0]
        started = client.post("/v1/platform/businesses/start", headers=owner, json={
            "category_key": cat, "subcategory_key": sub}).json()["data"]
        business_id = started["business"]["id"]
        talk = Talk(client, {**owner, "X-Business-Id": business_id, "X-Operating-Context": "business"},
                    business_id)
        talk.say(said)
        talk.send("correct", slot="name", values=[], text=name)
        mine = str(uuid.uuid4())
        sql("insert into media_assets (id, business_id, mime_type, bucket, storage_key, purpose, status, public_url) "
            "values (:id, :b, 'image/jpeg', 'media', :k, 'website', 'ready', :u)",
            id=mine, b=business_id, k=f"x/{mine}.jpg", u=f"https://storage.test/media/x/{mine}.jpg")
        talk.send("media", media={"asset_id": mine, "role": "hero", "label": "Our kitchen", "source": "USER_UPLOAD"})
        data = talk.send("build")
        _run_job(data["blueprint"]["completion_state"]["generation_job_id"])
        hero = next(s for s in sections(talk.site()) if s["section_type_id"] == "hero")
        assert hero["content"]["image_asset_id"] == mine
        blueprint = client.get(f"/v1/b/{business_id}/interview", headers=talk.headers).json()["data"]["blueprint"]
        plan = {p["key"]: p for p in blueprint["media_plan"]}
        assert plan["hero"]["source"] == "owner_uploaded" and str(plan["hero"]["asset_id"]) == mine
        # Drafts still fill the other slots (the owner uploaded only a hero) — never the hero.
        assert any(p["source"] == "gemini_generated" for k, p in plan.items() if k != "hero")
