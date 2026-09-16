"""Type-aware website generation brief + structured section validation.

No database. Guards the First Launch contract: catalogue SectionTypes survive
validation, and different business types get different page sets and voice.
"""

from __future__ import annotations

from platform_core.validation.website import validate_generation_payload
from platform_core.website.fallback_generator import build_deterministic_draft
from platform_core.website.generation_brief import (
    build_generation_prompt,
    personality_for_type,
    recommended_pages,
)
from platform_core.website.section_registry import ALLOWED_SECTION_TYPE_IDS


def test_catalogue_section_types_are_platform_allowed() -> None:
    for section_type in (
        "menu_section",
        "rooms_section",
        "plans_section",
        "classes_section",
        "enquiry_form",
        "gallery",
        "offerings_list",
    ):
        assert section_type in ALLOWED_SECTION_TYPE_IDS


def test_restaurant_prompt_and_pages_are_food_specific() -> None:
    pages = recommended_pages("restaurant")
    slugs = [slug for slug, _title, _ptype in pages]
    assert "menu" in slugs
    prompt = build_generation_prompt(
        {"display_name": "Ragi House", "business_type": "restaurant", "tagline": "Millet kitchen"}
    )
    assert "menu_section" in prompt
    assert "Ragi House" in prompt
    assert "food business" in prompt.lower()
    assert personality_for_type("restaurant") == "warm"


def test_gym_and_hotel_prompts_diverge() -> None:
    gym = build_generation_prompt({"display_name": "Iron Hall", "business_type": "gym"})
    hotel = build_generation_prompt({"display_name": "Lake Stay", "business_type": "hotel"})
    assert "plans_section" in gym
    assert "classes_section" in gym
    assert "rooms_section" in hotel
    assert personality_for_type("gym") == "bold"
    assert personality_for_type("hotel") == "premium"


def test_fallback_restaurant_keeps_menu_section_after_validation() -> None:
    payload = validate_generation_payload(
        build_deterministic_draft(
            display_name="Ragi House",
            business_type="restaurant",
            tagline="Millet kitchen",
            description="Home-style ragi meals in Koramangala.",
        )
    )
    menu = next(p for p in payload["pages"] if p["page_type"] == "menu" or p["slug"] == "menu")
    types = [s["section_type_id"] for s in menu["sections"]]
    assert "menu_section" in types
    assert payload["theme_hints"].get("personality") == "warm"


def test_fallback_clinic_includes_enquiry_form() -> None:
    payload = validate_generation_payload(
        build_deterministic_draft(
            display_name="South Clinic",
            business_type="clinic",
            tagline=None,
            description=None,
        )
    )
    enquire = next(p for p in payload["pages"] if p["page_type"] == "enquire")
    types = [s["section_type_id"] for s in enquire["sections"]]
    assert "enquiry_form" in types


def test_complete_structure_normalises_home_nav_path() -> None:
    from platform_core.services.website_generation import WebsiteGenerationService

    payload = {
        "pages": [
            {
                "slug": "home",
                "title": "Home",
                "page_type": "home",
                "sections": [{"section_type_id": "hero", "content": {"headline": "Hi"}}],
            }
        ],
        "navigation": [{"label": "Home", "path": "/home"}],
        "theme_hints": {},
    }
    out = WebsiteGenerationService._complete_structure(
        payload, {"display_name": "Ragi House", "business_type": "restaurant"}
    )
    assert out["navigation"][0]["path"] == "/"
    assert out["theme_hints"]["personality"] == "warm"
