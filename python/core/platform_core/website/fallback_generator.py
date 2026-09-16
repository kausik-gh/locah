"""Deterministic website draft generator (Doc 12 §12.1 — mandatory fallback).

This runs whenever the AI provider is unavailable, rate-limited or slow, which
in practice is often. It is therefore NOT a stub: the site it produces is the
one a real owner may publish, so it has to read like finished copy rather than
an invitation to go and write some.

It never invents facts. Everything specific comes from the Business's own
profile — display name, tagline, description — and everything else is framing
written per business-type family. Where the owner has given us nothing, the
copy stays truthful and general instead of inserting a placeholder.
"""

from __future__ import annotations

from typing import Any

from platform_core.website.section_registry import DEFAULT_PAGES, PAGES_BY_BUSINESS_TYPE

# Business types grouped by how their customers actually buy. Drives wording,
# CTA verbs and what the catalogue page is called.
_FAMILY: dict[str, str] = {
    "restaurant": "food",
    "cafe": "food",
    "hotel": "stay",
    "homestay": "stay",
    "salon": "appointment",
    "spa": "appointment",
    "clinic": "appointment",
    "gym": "membership",
    "studio": "membership",
    "education": "membership",
    "retail": "retail",
    "professional_service": "professional",
}

# Per family: the verb a visitor acts on, and the framing sentences.
_VOICE: dict[str, dict[str, str]] = {
    "food": {
        "cta": "See the menu",
        "hero_fallback": "Cooked fresh, served warm",
        "catalogue_lead": "Everything we cook, with today's prices.",
        "about_frame": "What we cook, and how we go about it.",
        "expect_title": "What to expect",
        "expect_body": (
            "Order ahead for collection or delivery where we offer it, and we will have "
            "it ready at the time you choose. If anything on the list is off for the day, "
            "it comes off the menu here first."
        ),
        "closing_head": "Hungry?",
        "closing_body": "Browse the menu and order in a couple of minutes.",
        "closing_cta": "Order now",
    },
    "appointment": {
        "cta": "See our services",
        "hero_fallback": "Careful work, by appointment",
        "catalogue_lead": "Our services and what each one costs.",
        "about_frame": "Who we are, and how we work.",
        "expect_title": "Before you book",
        "expect_body": (
            "Every appointment is held for one person at a time, so please let us know "
            "in advance if you need to move it. If you are not sure which service you "
            "need, get in touch and we will talk it through."
        ),
        "closing_head": "Ready when you are.",
        "closing_body": "Pick a service and a time that suits you.",
        "closing_cta": "Book an appointment",
    },
    "membership": {
        "cta": "See plans",
        "hero_fallback": "Somewhere to keep going",
        "catalogue_lead": "Plans, terms and what each one includes.",
        "about_frame": "What we teach, and who it is for.",
        "expect_title": "How it works",
        "expect_body": (
            "Plans run for a fixed period and cover everything listed against them. "
            "If you are new, start with a shorter commitment and move up once you know "
            "the routine suits you."
        ),
        "closing_head": "Start this week.",
        "closing_body": "Choose a plan and we will take it from there.",
        "closing_cta": "See the plans",
    },
    "stay": {
        "cta": "See rooms",
        "hero_fallback": "A quiet place to stay",
        "catalogue_lead": "Our rooms and what each night includes.",
        "about_frame": "The place, and what staying here is like.",
        "expect_title": "Good to know",
        "expect_body": (
            "Rates are per night and include what is listed against each room. Tell us "
            "your dates and how many of you there are, and we will confirm availability "
            "before anything is charged."
        ),
        "closing_head": "Come and stay.",
        "closing_body": "Check the rooms and tell us your dates.",
        "closing_cta": "Check availability",
    },
    "retail": {
        "cta": "Browse products",
        "hero_fallback": "Things worth keeping",
        "catalogue_lead": "What we stock, and what it costs.",
        "about_frame": "What we sell, and where it comes from.",
        "expect_title": "Ordering and delivery",
        "expect_body": (
            "Order online for collection or delivery where we offer it. If something is "
            "out of stock it will say so here rather than at the checkout."
        ),
        "closing_head": "Have a look around.",
        "closing_body": "Browse what is in stock today.",
        "closing_cta": "Browse products",
    },
    "professional": {
        "cta": "See what we do",
        "hero_fallback": "Straightforward professional help",
        "catalogue_lead": "What we do, and what engagements typically cost.",
        "about_frame": "How we work, and who we work with.",
        "expect_title": "How we start",
        "expect_body": (
            "Most work begins with a short conversation so we both know whether it is a "
            "good fit. Tell us what you are trying to do and we will tell you honestly "
            "whether we can help."
        ),
        "closing_head": "Tell us what you need.",
        "closing_body": "Send us a note and we will come back to you.",
        "closing_cta": "Get in touch",
    },
    "general": {
        "cta": "See what we offer",
        "hero_fallback": "Your local business, online",
        "catalogue_lead": "What we offer, and what it costs.",
        "about_frame": "About us.",
        "expect_title": "Getting in touch",
        "expect_body": (
            "Have a look at what we offer, and contact us if you cannot find what you "
            "are after. We would rather point you in the right direction than not hear "
            "from you at all."
        ),
        "closing_head": "Get in touch.",
        "closing_body": "We are happy to answer questions before you commit.",
        "closing_cta": "Contact us",
    },
}

_CATALOGUE_PAGE_TYPES = {"offerings", "services", "menu", "rooms", "plans", "classes"}


def _offerings_section(title: str, subtitle: str, *, max_items: int) -> dict[str, Any]:
    """A list bound to the Offerings module — real records, never fixed copy."""
    return {
        "section_type_id": "offerings_list",
        "layout_variant": "cards",
        "content": {"title": title, "subtitle": subtitle, "max_items": max_items},
        "module_binding": {"module": "offerings-catalog"},
        "is_visible": True,
    }


def build_deterministic_draft(
    *,
    display_name: str,
    business_type: str | None,
    tagline: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Always returns a valid WebsiteGenerationSchema payload."""
    name = (display_name or "Your Business").strip() or "Your Business"
    btype = (business_type or "other").strip().lower()
    pages_spec = PAGES_BY_BUSINESS_TYPE.get(btype, DEFAULT_PAGES)
    voice = _VOICE[_FAMILY.get(btype, "general")]

    tagline_text = (tagline or "").strip() or voice["hero_fallback"]
    about_body = (description or "").strip() or (
        f"{name} is a local business serving its neighbourhood. Everything we offer is "
        f"listed here with current prices, so you know what to expect before you arrive."
    )

    # The catalogue page, if this business type has one — used for hero CTAs.
    catalogue = next(
        ((slug, title) for slug, title, ptype in pages_spec if ptype in _CATALOGUE_PAGE_TYPES),
        None,
    )
    primary_cta_url = f"/{catalogue[0]}" if catalogue else "/contact"
    primary_cta_label = voice["cta"] if catalogue else "Contact us"

    pages: list[dict[str, Any]] = []
    navigation: list[dict[str, str]] = []

    for sort_idx, (slug, title, page_type) in enumerate(pages_spec):
        navigation.append({"label": title, "path": "/" if slug == "home" else f"/{slug}"})
        sections: list[dict[str, Any]] = []

        if page_type == "home":
            sections = [
                {
                    "section_type_id": "hero",
                    "layout_variant": "centered",
                    "content": {
                        "headline": name,
                        "subheadline": tagline_text,
                        "cta_label": primary_cta_label,
                        "cta_url": primary_cta_url,
                    },
                    "is_visible": True,
                },
                {
                    "section_type_id": "about",
                    "layout_variant": "text_only",
                    "content": {"title": voice["about_frame"], "body": about_body},
                    "is_visible": True,
                },
            ]
            if catalogue:
                sections.append(
                    _offerings_section(
                        catalogue[1], voice["catalogue_lead"], max_items=6
                    )
                )
            sections.append(
                {
                    "section_type_id": "cta_band",
                    "layout_variant": "centered",
                    "content": {
                        "headline": voice["closing_head"],
                        "body": voice["closing_body"],
                        "cta_label": voice["closing_cta"],
                        "cta_url": primary_cta_url,
                    },
                    "is_visible": True,
                }
            )

        elif page_type == "about":
            sections = [
                {
                    "section_type_id": "about",
                    "layout_variant": "text_only",
                    "content": {"title": f"About {name}", "body": about_body},
                    "is_visible": True,
                },
                {
                    "section_type_id": "text_block",
                    "layout_variant": "default",
                    "content": {
                        "title": voice["expect_title"],
                        "body": voice["expect_body"],
                    },
                    "is_visible": True,
                },
            ]

        elif page_type == "contact":
            sections = [
                {
                    "section_type_id": "contact",
                    "layout_variant": "full",
                    "content": {
                        "title": "Find us",
                        "hours_summary": "Get in touch for our current opening hours.",
                        "show_map": False,
                    },
                    "is_visible": True,
                },
                {
                    "section_type_id": "cta_band",
                    "layout_variant": "centered",
                    "content": {
                        "headline": voice["closing_head"],
                        "body": voice["closing_body"],
                        "cta_label": voice["closing_cta"],
                        "cta_url": primary_cta_url,
                    },
                    "is_visible": True,
                },
            ]

        elif page_type in _CATALOGUE_PAGE_TYPES:
            sections = [
                {
                    "section_type_id": "hero",
                    "layout_variant": "left_aligned",
                    "content": {"headline": title, "subheadline": voice["catalogue_lead"]},
                    "is_visible": True,
                },
                _offerings_section(title, "", max_items=24),
            ]

        elif page_type == "enquire":
            sections = [
                {
                    "section_type_id": "text_block",
                    "layout_variant": "default",
                    "content": {
                        "title": "Tell us what you need",
                        "body": voice["expect_body"],
                    },
                    "is_visible": True,
                },
                {
                    "section_type_id": "contact",
                    "layout_variant": "full",
                    "content": {"title": "Get in touch", "show_map": False},
                    "is_visible": True,
                },
            ]

        else:
            sections = [
                {
                    "section_type_id": "text_block",
                    "layout_variant": "default",
                    "content": {"title": title, "body": about_body},
                    "is_visible": True,
                }
            ]

        pages.append(
            {
                "slug": slug,
                "title": title,
                "page_type": page_type,
                "seo_title": f"{name}" if page_type == "home" else f"{title} | {name}",
                "seo_description": (tagline_text if page_type == "home" else about_body)[:160],
                "sort_order": sort_idx,
                "sections": sections,
            }
        )

    return {
        "pages": pages,
        "navigation": navigation,
        "theme_hints": _THEME_BY_FAMILY.get(
            _FAMILY.get(btype, "general"), _THEME_BY_FAMILY["general"]
        ),
    }


# A palette per family so two businesses of different kinds never arrive
# looking like the same site. Still overridable by the owner's theme choice.
_THEME_BY_FAMILY: dict[str, dict[str, Any]] = {
    "food": {
        "primary_color": "#8A3A1E",
        "accent_color": "#C9762F",
        "font_style": "warm",
        "density": "comfortable",
    },
    "appointment": {
        "primary_color": "#1F3D34",
        "accent_color": "#B08D57",
        "font_style": "elegant",
        "density": "airy",
    },
    "membership": {
        "primary_color": "#15161A",
        "accent_color": "#D64933",
        "font_style": "bold",
        "density": "compact",
    },
    "stay": {
        "primary_color": "#2C4A52",
        "accent_color": "#C2A878",
        "font_style": "elegant",
        "density": "airy",
    },
    "retail": {
        "primary_color": "#20304A",
        "accent_color": "#D98A3C",
        "font_style": "clean",
        "density": "comfortable",
    },
    "professional": {
        "primary_color": "#17457A",
        "accent_color": "#4A90A4",
        "font_style": "clean",
        "density": "comfortable",
    },
    "general": {
        "primary_color": "#0F766E",
        "accent_color": "#F59E0B",
        "font_style": "clean",
        "density": "comfortable",
    },
}
