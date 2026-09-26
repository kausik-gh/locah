"""The website design system as a gate: 23 businesses, their first websites, zero AI.

Every fixture business is interviewed (scripted model readings), then its
website is composed exactly as "Build my website" composes it. Checked:

* every payload is a valid website and passes the semantic validator (any
  wrong meaning was repaired, none shipped);
* design is evidence-driven: all ten families appear, no family takes over,
  and no two businesses that said different things share a design signature;
* same category, different brands: a premium butcher, a family butcher, a
  modern delivery brand and an everyday meat shop are four different looks —
  and not all dark red and black;
* the truth rule: nothing is drawn where a picture would be evidence.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from platform_core.ai_guard import blocked_calls
from platform_core.interview.creative_director import direct
from platform_core.interview.design_system import FAMILIES
from platform_core.interview.distinctness import differences
from platform_core.interview.media_director import may_draw, plan_slots
from platform_core.interview.models import BusinessBlueprint, CategorySeed, Fact
from platform_core.interview.semantic_design import validate
from platform_core.validation.website import validate_generation_payload
from platform_testing.website_fixtures import FIXTURE_PERSONAS, build_all, distinctness


@pytest.fixture(scope="module")
def fixtures():
    import asyncio

    return asyncio.run(build_all())


def test_there_are_at_least_twenty_fixture_businesses(fixtures) -> None:
    assert len(fixtures) >= 20
    assert len({f.key for f in fixtures}) == len(FIXTURE_PERSONAS)


def test_every_first_website_is_valid_and_means_what_the_business_is(fixtures) -> None:
    for f in fixtures:
        validate_generation_payload(f.payload)  # raises when invalid
        quality = f.payload["theme_hints"]["quality"]
        assert quality["valid"], (f.key, quality["issues"])
        # Anything that meant the wrong thing was repaired — re-checking finds nothing to fail.
        _, again = validate(f.payload, f.bp, direct(f.bp, None))
        assert not [x for x in again if x.severity == "fail"], (f.key, [x.as_dict() for x in again])
        text = str(f.payload).lower()
        assert "add to cart" not in text and "lorem" not in text
    assert not blocked_calls()


def test_design_is_evidence_driven_not_one_look_per_category(fixtures) -> None:
    rep = distinctness(fixtures)
    assert rep.ok, (rep.clusters, rep.identical)
    used = {f.signature["family"] for f in fixtures}
    assert used == set(FAMILIES), f"families never chosen: {set(FAMILIES) - used}"


def test_same_category_different_brands(fixtures) -> None:
    meat = {f.key: f for f in fixtures if f.key in {"meat-shop", "premium-butcher", "family-butcher",
                                                     "meat-delivery-app"}}
    assert len(meat) == 4
    keys = sorted(meat)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            assert differences(meat[a].signature, meat[b].signature) >= 3, (a, b)
    dark_red = [k for k, f in meat.items() if f.signature["hue"] == "red"
                and f.payload["theme_hints"]["palette_mode"] == "dark"]
    assert len(dark_red) <= 1, dark_red
    assert meat["premium-butcher"].signature["family"] == "premium_dark"
    assert meat["meat-delivery-app"].signature["family"] == "modern_commerce"


def test_each_trade_speaks_in_its_own_words(fixtures) -> None:
    by_key = {f.key: f for f in fixtures}

    def nav(key: str) -> list[str]:
        return [n["label"] for n in by_key[key].payload["navigation"]]

    def hero_cta(key: str) -> str:
        hero = next(s for s in by_key[key].payload["pages"][0]["sections"] if s["section_type_id"] == "hero")
        return str(hero["content"].get("cta_label", ""))

    assert "Menu" in nav("restaurant") and "Programmes" not in " ".join(nav("florist"))
    assert "Projects" not in nav("law-firm") and "Services" in nav("law-firm")
    assert hero_cta("photographer") == "See the work"
    assert hero_cta("industrial") in {"See the range", "Ask for a quote"}
    assert not hero_cta("industrial").lower().startswith("book")
    assert hero_cta("gym") == "Book a free trial"


def test_truth_rule_nothing_drawn_where_a_picture_is_evidence(fixtures) -> None:
    by_key = {f.key: f for f in fixtures}
    for key in ("photographer", "interiors", "real-estate"):
        f = by_key[key]
        direction = direct(f.bp, None)
        assert not may_draw(f.bp, direction), key
        assert plan_slots(f.bp, direction) == [], key
    for f in fixtures:
        for slot in plan_slots(f.bp, direct(f.bp, None)):
            assert not slot.key.startswith(("item:", "project:")), (f.key, slot.key)


# ------------------------------------------------ the validator's own rules


def _bp(category: tuple[str, str, str]) -> BusinessBlueprint:
    bp = BusinessBlueprint(business_id=uuid4(),
                           identity={"display_name": Fact(value="X", source="PLATFORM", confirmation="confirmed")})
    bp.category = CategorySeed(category_key=category[0], subcategory_key=category[1], label=category[2])
    return bp


def _payload(nav: list[str], hero_cta: str, title: str) -> dict[str, Any]:
    return {
        "pages": [{"slug": "home", "title": "Home", "page_type": "home", "sections": [
            {"section_type_id": "hero", "content": {"headline": "X", "cta_label": hero_cta, "cta_url": "#shop"}},
            {"section_type_id": "category_showcase", "content": {"title": title, "anchor": "shop", "items": []}},
        ]}],
        "navigation": [{"label": label, "path": "/#shop"} for label in nav],
        "theme_hints": {},
    }


@pytest.mark.parametrize("category, nav, cta, title, code", [
    (("retail", "florist", "Florist"), ["Programmes"], "Shop now", "Bouquets", "class_language_for_non_class_business"),
    (("industrial", "industrial_supplier", "Industrial supplier"), ["Products"], "Book a class", "Product range",
     "class_language_for_non_class_business"),
    (("food_service", "restaurant", "Restaurant"), ["Menu"], "Book a table", "Procurement & bulk orders",
     "procurement_language_for_consumer_business"),
    (("food_service", "restaurant", "Restaurant"), ["Menu"], "Book a table", "Services", "generic_services_heading"),
    (("professional", "lawyer", "Lawyer"), ["Services"], "Book a consultation", "Featured projects",
     "projects_for_non_project_business"),
])
def test_wrong_meaning_fails_and_is_repaired(category, nav, cta, title, code) -> None:
    bp = _bp(category)
    payload, found = validate(_payload(nav, cta, title), bp, direct(bp, None))
    fails = [f for f in found if f.severity == "fail"]
    assert any(f.code == code for f in fails), [f.as_dict() for f in found]
    _, again = validate(payload, bp, direct(bp, None))
    assert not [f for f in again if f.severity == "fail"]


def test_a_meat_shop_menu_is_a_question_not_a_repair() -> None:
    bp = _bp(("fresh_grocery", "meat_shop", "Meat shop"))
    _, found = validate(_payload(["Menu"], "Shop now", "Shop by category"), bp, direct(bp, None))
    assert [(f.code, f.severity) for f in found] == [("menu_for_weighed_products", "flag")]
