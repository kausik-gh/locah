"""What a visitor can actually do with a business, right now (Founder §14–16; Guide §4).

The website, the Marketplace listing and the website's own navigation all read
this one answer, so they can never disagree. It comes from real module
*readiness* — built, switched on and set up (a priced product, a published
plan, a bookable service) — never from the business category and never from a
module merely being switched on.

When a module becomes ready its customer surface appears on the website without
a rebuild: `auto_sections` adds the module's section to the home page if the
owner's design has none (Plans for Memberships, a booking band for Bookings,
the shop for Orders, reviews once there are reviews). The owner can hide any of
them; a module that stops being ready takes its actions away again.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import BusinessTrait, Offering

# Actions every surface understands. The first ready one that a business's own
# way of trading leads with becomes its primary call to action.
_PRIMARY_BY_TRAIT: tuple[tuple[str, str], ...] = (
    ("donation_led", "donate"), ("booking_led", "book"), ("subscription_led", "join"),
    ("order_led", "order"), ("quote_led", "request_quote"), ("project_led", "request_quote"),
    ("enquiry_led", "enquire"),
)
PRIMARY_LABELS = {
    "order": "Order now", "book": "Book now", "join": "See plans", "request_quote": "Get a quote",
    "enquire": "Enquire", "donate": "Donate", "site_visit": "Book a site visit", "call": "Call", "whatsapp": "WhatsApp",
}
PRIMARY_PATHS = {
    "order": "/checkout", "book": "/book", "join": "/#plans", "request_quote": "/enquire?purpose=quote_request",
    "enquire": "/enquire", "site_visit": "/enquire?purpose=site_visit",
}


def decide(ready: Mapping[str, bool], kinds: Mapping[str, int], traits: Iterable[str], *,
           has_whatsapp: bool = False, has_phone: bool = False) -> dict[str, Any]:
    """Pure: which customer actions are real for this business, and which leads.

    `ready` is module → ready (built, enabled, configured); `kinds` counts live,
    public offerings by kind; `traits` are the business's operating traits."""
    t = set(traits)

    def live(*names: str) -> bool:
        return any(kinds.get(n, 0) > 0 for n in names)

    leads = bool(ready.get("leads"))
    flags: dict[str, Any] = {
        "order": bool(ready.get("orders")),
        "book": bool(ready.get("bookings")),
        "join": bool(ready.get("memberships")),
        "enquire": leads,
        # A request for a quote lands as a lead the team quotes from (RFQ intake).
        "request_quote": bool(ready.get("quotes")) and leads,
        "site_visit": leads and live("property_project", "unit"),
        "test_drive": leads and live("vehicle"),
        # A cause takes gifts through the same checkout (P1-03).
        "donate": bool(ready.get("orders")) and live("cause"),
        "track": bool(ready.get("orders")) and bool(ready.get("fulfilment")),
        "reviews": bool(ready.get("reviews")),
        "contact": True,
        "visit_website": True,
        # Presentation traits (§22): digital-only businesses publish no address.
        "show_address": "digital_only" not in t,
    }
    flags.update(pick_primary(flags, t, landings={}, has_whatsapp=has_whatsapp, has_phone=has_phone))
    return flags


def _candidates(flags: Mapping[str, Any], traits: set[str]) -> list[str]:
    """Ready actions, the business's own way of trading first (§22)."""
    out = [action for trait, action in _PRIMARY_BY_TRAIT if trait in traits and flags.get(action)]
    for action in ("order", "book", "join", "request_quote", "site_visit", "donate", "enquire"):
        if flags.get(action) and action not in out:
            out.append(action)
    return out


def pick_primary(flags: Mapping[str, Any], traits: Iterable[str], *, landings: Mapping[str, str | None],
                 has_whatsapp: bool = False, has_phone: bool = False) -> dict[str, Any]:
    """The header's main button. An action whose landing place is known to be
    missing (`landings[action] is None` — say the owner hid the only Plans
    section) is skipped, so the button never points at nothing."""
    for action in _candidates(flags, set(traits)):
        if action in landings:
            if landings[action] is None:
                continue
            path = landings[action]
        else:
            path = PRIMARY_PATHS.get(action)
        return {"primary": action, "primary_label": PRIMARY_LABELS[action], "primary_path": path}
    fallback = "whatsapp" if has_whatsapp else "call" if has_phone else None
    return {"primary": fallback, "primary_label": PRIMARY_LABELS.get(fallback or ""), "primary_path": None}


# Sections a visitor lands on for an action (the rest have their own page).
LANDING_SECTIONS = {
    "order": ({"offerings_list", "menu_section", "product_showcase", "category_showcase"}, "shop"),
    "donate": ({"offerings_list", "menu_section", "product_showcase", "category_showcase"}, "shop"),
    "join": ({"plans_section"}, "plans"),
}


async def gather(session: AsyncSession, business_id: uuid.UUID) -> tuple[dict[str, bool], dict[str, int], list[str]]:
    from platform_core.services.module_readiness import readiness

    states = await readiness(session, business_id)
    ready = {k: bool(v["ready"]) for k, v in states.items()}
    kinds = {row[0]: int(row[1]) for row in (await session.execute(
        select(Offering.offering_type, func.count()).where(
            Offering.business_id == business_id, Offering.deleted_at.is_(None), Offering.status == "active",
            Offering.visibility == "public").group_by(Offering.offering_type))).all()}
    traits = [row[0] for row in (await session.execute(select(BusinessTrait.trait_key).where(
        BusinessTrait.business_id == business_id, BusinessTrait.enabled.is_(True)))).all()]
    return ready, kinds, traits


async def site_capabilities(session: AsyncSession, business_id: uuid.UUID, *, has_whatsapp: bool = False,
                            has_phone: bool = False) -> dict[str, Any]:
    ready, kinds, traits = await gather(session, business_id)
    flags = decide(ready, kinds, traits, has_whatsapp=has_whatsapp, has_phone=has_phone)
    flags["_kinds"] = kinds
    flags["_traits"] = traits
    return flags


# ---------------------------------------------------------------- sections a ready module adds
_BROWSE = {"offerings_list", "menu_section", "product_showcase", "category_showcase"}
AUTO_SECTION_MODULES = ("orders", "bookings", "memberships", "reviews", "leads")


def auto_sections(flags: Mapping[str, Any], existing_types: set[str], *, hidden: Iterable[str],
                  published_reviews: int, traits: Iterable[str]) -> list[dict[str, Any]]:
    """Sections the home page gains because a module is ready and the owner's
    design has nothing that shows it. Pure; the renderer draws them like any
    other section, filled from live records."""
    kinds = flags.get("_kinds") or {}
    off = set(hidden)
    t = set(traits)
    out: list[dict[str, Any]] = []

    def add(module: str, section_type: str, content: dict[str, Any], variant: str | None = None) -> None:
        if module in off:
            return
        out.append({"id": f"auto-{module}-{section_type}", "section_type_id": section_type,
                    "layout_variant": variant, "content": content, "module_binding": None,
                    "is_visible": True, "is_auto": True, "module": module})

    if flags.get("order") and not (existing_types & _BROWSE):
        add("orders", "offerings_list", {"title": "Order online", "anchor": "shop"})
    if flags.get("join") and "plans_section" not in existing_types:
        add("memberships", "plans_section", {"title": "Plans", "anchor": "plans"})
    if flags.get("book"):
        if kinds.get("class", 0) + kinds.get("class_session", 0) and "classes_section" not in existing_types:
            add("bookings", "classes_section", {"title": "Classes", "offering_types": ["class", "class_session"]})
        elif (kinds.get("room_type", 0) + kinds.get("accommodation", 0)) and "rooms_section" not in existing_types:
            add("bookings", "rooms_section", {"title": "Rooms", "offering_types": ["room_type", "accommodation"]})
        elif "cta_band" not in existing_types and "rooms_section" not in existing_types \
                and "classes_section" not in existing_types:
            add("bookings", "cta_band", {"headline": "Book a time that suits you", "cta_label": "Book now",
                                         "cta_url": "/book"})
    if flags.get("reviews") and published_reviews > 0 and "reviews_section" not in existing_types:
        add("reviews", "reviews_section", {"title": "What customers say"})
    leads_first = bool(t & {"quote_led", "enquiry_led", "project_led"}) or flags.get("site_visit") \
        or flags.get("test_drive")
    if flags.get("enquire") and leads_first and "enquiry_form" not in existing_types:
        add("leads", "enquiry_form", {"title": "Get a quote" if flags.get("request_quote") else "Send an enquiry",
                                      "anchor": "enquire"})
    return out


async def published_review_count(session: AsyncSession, business_id: uuid.UUID) -> int:
    row = (await session.execute(text(
        "SELECT count(*) FROM reviews_reviews WHERE business_id = CAST(:b AS uuid) AND status = 'published'"),
        {"b": str(business_id)})).scalar()
    return int(row or 0)


async def section_types(session: AsyncSession, version_id: uuid.UUID | None) -> set[str]:
    """Visible section types across every page of one website version."""
    if version_id is None:
        return set()
    from platform_core.models import WebsitePage, WebsiteSection

    rows = (await session.execute(
        select(WebsiteSection.section_type_id).join(WebsitePage, WebsitePage.id == WebsiteSection.page_id)
        .where(WebsitePage.website_version_id == version_id, WebsiteSection.is_visible.is_(True)))).all()
    return {row[0] for row in rows}


# Where a Marketplace action lands when the section it needs is one a tool added
# to the home page (so the listing and the site always agree).
_AUTO_PATHS = {"orders": ("browse", "#shop"), "memberships": ("join", "#plans"), "leads": ("contact", "#enquire")}


async def published_auto_paths(session: AsyncSession, business_id: uuid.UUID, *, version_id: uuid.UUID | None,
                               hidden: Iterable[str]) -> dict[str, str]:
    if version_id is None:
        return {}
    flags = await site_capabilities(session, business_id)
    extra = auto_sections(flags, await section_types(session, version_id), hidden=hidden,
                          published_reviews=await published_review_count(session, business_id),
                          traits=flags.get("_traits") or [])
    out: dict[str, str] = {}
    for section in extra:
        key_path = _AUTO_PATHS.get(section["module"])
        if key_path:
            out.setdefault(key_path[0], key_path[1])
    return out
