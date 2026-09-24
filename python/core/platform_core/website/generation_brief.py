"""Type-aware generation brief (Doc 12 §12.1–§12.6).

AI writes content and visual direction only. Page sets, SectionTypes, and
module-bound catalogue sections stay platform-defined. This module is the
mega-prompt: business context + recommended structure + voice, handed to
`generate_structured` once.
"""

from __future__ import annotations

from typing import Any

from platform_core.website.fallback_generator import _FAMILY, _THEME_BY_FAMILY, _VOICE
from platform_core.website.generation_plan import GenerationPlan, describe_plan_for_prompt
from platform_core.website.questionnaire import PALETTE_PRESETS, build_intake_brief
from platform_core.website.section_registry import (
    DEFAULT_PAGES,
    PAGES_BY_BUSINESS_TYPE,
    SECTION_CATALOGUE_PROMPT,
)

# What the catalogue page is for, in the owner's terms — never invent checkout
# or booking mechanics in generated copy.
_CATALOGUE_INTENT: dict[str, str] = {
    "food": (
        "This is a food business. Home should feel like walking in: appetite, "
        "place, today's cooking. The menu page must carry a menu_section (or "
        "offerings_list bound to the catalogue). Talk about food, hours, and "
        "ordering for collection or delivery — never invent a cart UI."
    ),
    "appointment": (
        "This is an appointment business. Lead with the service, the care, and "
        "how to book. Services page lists treatments. Copy may invite booking; "
        "do not invent a calendar widget or payment flow."
    ),
    "membership": (
        "This is a membership / class business. Plans and classes are the "
        "product. Home should make joining feel obvious. Use plans_section and "
        "classes_section on the matching pages."
    ),
    "stay": (
        "This is a stay / rooms business. Rooms, amenities, and the feel of "
        "the place. Use rooms_section on the rooms page. Invite checking "
        "availability — do not invent a booking engine."
    ),
    "retail": (
        "This is a retail shop. Products, categories, and why these things are "
        "worth buying. Use offerings_list on the products page."
    ),
    "professional": (
        "This is a professional practice. Expertise, how work starts, and a "
        "clear enquiry path. Use offerings_list on services and enquiry_form "
        "on the enquire page."
    ),
    "general": (
        "Adapt to what this business actually does. Prefer a short, specific "
        "site over a generic template."
    ),
}

_LAYOUT_BY_FAMILY: dict[str, str] = {
    "food": "hero layout_variant image_right or full_width; dense, appetising copy",
    "appointment": "hero layout_variant centered or image_left; calm, precise copy",
    "membership": "hero layout_variant left_aligned; energetic, direct copy",
    "stay": "hero layout_variant full_width or image_left; unhurried, sensory copy",
    "retail": "hero layout_variant image_right; clear product-led copy",
    "professional": "hero layout_variant centered; plain, confident copy",
    "general": "hero layout_variant centered; specific, unfussy copy",
}


def personality_for_type(business_type: str | None) -> str:
    family = _FAMILY.get((business_type or "").strip().lower(), "general")
    return {
        "food": "warm",
        "appointment": "premium",
        "membership": "bold",
        "stay": "premium",
        "retail": "clean",
        "professional": "clean",
        "general": "clean",
    }.get(family, "clean")


def default_theme_for_type(business_type: str | None) -> dict[str, Any]:
    family = _FAMILY.get((business_type or "").strip().lower(), "general")
    theme = dict(_THEME_BY_FAMILY.get(family, _THEME_BY_FAMILY["general"]))
    theme["personality"] = personality_for_type(business_type)
    return theme


def apply_intake_theme(
    theme: dict[str, Any], intake: dict[str, Any] | None
) -> dict[str, Any]:
    """Owner palette wins over family defaults. Never invent colours."""
    merged = dict(theme)
    if not intake:
        return merged
    preset = PALETTE_PRESETS.get(str(intake.get("palette") or ""))
    if preset:
        merged["primary_color"] = preset["primary"]
        merged["accent_color"] = preset["accent"]
        merged["palette"] = str(intake["palette"])
    return merged


def recommended_pages(business_type: str | None) -> list[tuple[str, str, str]]:
    btype = (business_type or "").strip().lower()
    return list(PAGES_BY_BUSINESS_TYPE.get(btype, DEFAULT_PAGES))


def build_generation_prompt(
    context: dict[str, Any],
    intake: dict[str, Any] | None = None,
    plan: GenerationPlan | None = None,
) -> str:
    """The mega-prompt, with a reference composition when one has been chosen.

    A plan replaces the two weakest parts of the original brief — a page list
    derived from the business type alone, and a one-line layout hint — with a
    real template composition and this business's actual capability inventory.
    The tone direction stays either way: what a food business should sound like
    does not change because it started from a different layout.
    """
    name = str(context.get("display_name") or "this business").strip()
    btype = str(context.get("business_type") or "other").strip().lower()
    family = _FAMILY.get(btype, "general")
    voice = _VOICE.get(family, _VOICE["general"])
    theme = default_theme_for_type(btype)

    prompt = (
        f"Generate a structured multi-page website draft for {name} "
        f"(business type: {btype}).\n\n"
        "This must read as THAT business's site, not a generic template with "
        "the name swapped in. Use the facts below. Invent atmosphere and "
        "phrasing, never fake addresses, phone numbers, prices, awards, or "
        "reviews. No lorem ipsum, no placeholders, no bracketed instructions.\n\n"
        f"BUSINESS TYPE DIRECTION:\n{_CATALOGUE_INTENT[family]}\n"
        f"Default CTA verb: {voice['cta']}.\n"
    )

    if plan is not None:
        prompt += describe_plan_for_prompt(plan) + "\n"
    else:
        pages = recommended_pages(btype)
        page_lines = ", ".join(
            f"{title} (/{slug}, page_type={ptype})" for slug, title, ptype in pages
        )
        prompt += (
            f"Layout hint: {_LAYOUT_BY_FAMILY[family]}.\n\n"
            f"RECOMMENDED PAGES (use this set unless the facts demand one extra "
            f"custom page): {page_lines}.\n"
            f"theme_hints MUST include: primary_color {theme['primary_color']}, "
            f"accent_color {theme['accent_color']}, personality "
            f"\"{theme['personality']}\" "
            "(unless the intake specifies a palette — then use that palette).\n"
        )

    prompt += (
        "\nEvery page needs a hero plus at least one more section. Catalogue "
        "pages must include the matching list SectionType (menu_section, "
        "rooms_section, plans_section, classes_section, or offerings_list) "
        "and must NOT invent individual items — those render from the live "
        "catalogue.\n"
        "Do not invent navigation chrome, cart, checkout, or booking widgets. "
        "Content only. CTA urls must be relative paths on this site.\n\n"
        f"{SECTION_CATALOGUE_PROMPT}"
    )
    if context.get("tagline"):
        prompt += f"\nTagline: {context['tagline']}."
    if context.get("description"):
        prompt += f"\nAbout: {context['description']}."
    prompt += build_intake_brief(context, intake)
    return str(prompt)
