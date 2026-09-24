"""What a Marketplace listing may say about a Business, read from what it published.

Every fact here comes from something the owner made public: their published
website, their public catalogue, their profile and their primary location.
Nothing is inferred about quality, popularity, price level or opening hours —
a listing that does not know says nothing.

Kept apart from the indexing service so the rules for *which* published words
count are in one readable place.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.business_categories import Placement, classify, search_terms
from platform_core.geo.india_places import place_from_address
from platform_core.models import (
    Business,
    BusinessLocation,
    BusinessProfile,
    MediaAsset,
    Website,
    WebsitePage,
    WebsiteSection,
    WebsiteVersion,
)

# Sections whose items are things the Business offers. A "How ordering works"
# strip lists steps, not products; an About section lists nothing.
OFFERING_SECTIONS = frozenset({
    "product_showcase",
    "category_showcase",
    "menu_section",
    "offerings_list",
    "feature_grid",
    "plans_section",
    "rooms_section",
    "classes_section",
})
_ITEM_LISTS = ("items", "categories", "plans", "rooms", "classes")
_IMAGE_SECTIONS_FOR_COVER = ("hero", "about", "cta_band", "product_showcase", "category_showcase")
_POSTAL = re.compile(r"(?<!\d)(\d{6})(?!\d)")


@dataclass
class ListingFacts:
    placement: Placement = field(default_factory=lambda: Placement(None, None))
    keywords: list[str] = field(default_factory=list)
    highlights: list[dict[str, Any]] = field(default_factory=list)
    cover_url: str | None = None
    logo_url: str | None = None
    published_at: datetime | None = None
    city: str | None = None
    locality: str | None = None
    region: str | None = None
    postal_code: str | None = None
    lat: float | None = None
    lng: float | None = None
    geo_precision: str | None = None
    # A number to call or WhatsApp, exactly as the owner published it on
    # their own site (website_publish._public_contact reads the same fields).
    public_contact: dict[str, str] = field(default_factory=dict)
    # Where on their published site a visitor goes for each action, as a path
    # under /<slug> ("#contact", "/menu#shop"; "" is the home page). An action
    # with nowhere to land is not offered.
    site_paths: dict[str, str] = field(default_factory=dict)


# Which published page a Marketplace action hands off to.
_BROWSE_SECTIONS = frozenset({"product_showcase", "category_showcase", "menu_section", "offerings_list"})
_JOIN_SECTIONS = frozenset({"plans_section", "classes_section"})
_CONTACT_SECTIONS = frozenset({"contact", "enquiry_form", "lead_form"})


def _item_name(item: dict[str, Any]) -> str | None:
    for key in ("title", "name", "label"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _is_home(page: WebsitePage) -> bool:
    return bool(page.slug == "home" or page.page_type == "home")


async def _published_sections(
    session: AsyncSession, website: Website | None
) -> tuple[list[WebsiteSection], dict[uuid.UUID, str], datetime | None]:
    """Visible sections of the published version, home page first.

    Also returns each page's path under the Business's site: "" for the home
    page, "/<slug>" for the others.
    """
    if website is None or not website.published_version_id:
        return [], {}, None
    version = (
        await session.execute(
            select(WebsiteVersion).where(WebsiteVersion.id == website.published_version_id)
        )
    ).scalars().first()
    if version is None:
        return [], {}, None
    pages = (
        await session.execute(
            select(WebsitePage)
            .where(WebsitePage.website_version_id == version.id, WebsitePage.is_published.is_(True))
            .order_by(WebsitePage.sort_order.asc())
        )
    ).scalars().all()
    if not pages:
        return [], {}, version.published_at
    home_first = sorted(pages, key=lambda p: (0 if _is_home(p) else 1, p.sort_order))
    order = {page.id: index for index, page in enumerate(home_first)}
    paths = {page.id: "" if _is_home(page) else f"/{page.slug}" for page in pages}
    sections = (
        await session.execute(
            select(WebsiteSection).where(
                WebsiteSection.page_id.in_(list(order)),
                WebsiteSection.is_visible.is_(True),
            )
        )
    ).scalars().all()
    ordered = sorted(sections, key=lambda s: (order.get(s.page_id, 99), s.sort_order))
    return list(ordered), paths, version.published_at


async def _asset_urls(
    session: AsyncSession, business_id: uuid.UUID, ids: set[uuid.UUID]
) -> dict[str, str]:
    if not ids:
        return {}
    rows = (
        await session.execute(
            select(MediaAsset.id, MediaAsset.public_url).where(
                MediaAsset.id.in_(ids),
                MediaAsset.business_id == business_id,
                MediaAsset.status == "ready",
                MediaAsset.deleted_at.is_(None),
            )
        )
    ).all()
    return {str(row[0]): row[1] for row in rows if row[1]}


def _uuid(raw: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(raw)) if raw else None
    except ValueError:
        return None


async def gather_listing_facts(
    session: AsyncSession,
    *,
    business: Business,
    profile: BusinessProfile | None,
    website: Website | None,
    location: BusinessLocation | None,
    offering_titles: list[str],
) -> ListingFacts:
    facts = ListingFacts()
    sections, page_paths, facts.published_at = await _published_sections(session, website)

    # ---- what the website lists, and the pictures it already shows --------
    wanted: set[uuid.UUID] = set()
    items: list[tuple[str, uuid.UUID | None]] = []
    address_text: str | None = None
    for section in sections:
        content = section.content or {}
        if section.section_type_id == "contact" and isinstance(content.get("address"), str):
            address_text = address_text or content["address"]
        # The first page that holds each kind of section is where that
        # Marketplace action lands. The contact section always renders with
        # id="contact"; other sections only have the anchor they were given.
        page_path = page_paths.get(section.page_id, "")
        anchor = content.get("anchor") if isinstance(content.get("anchor"), str) else ""
        if section.section_type_id in _CONTACT_SECTIONS:
            facts.site_paths.setdefault("contact", page_path + "#contact")
        elif section.section_type_id in _BROWSE_SECTIONS:
            facts.site_paths.setdefault("browse", page_path + (f"#{anchor}" if anchor else ""))
        elif section.section_type_id in _JOIN_SECTIONS:
            facts.site_paths.setdefault("join", page_path + (f"#{anchor}" if anchor else ""))
        if section.section_type_id in _IMAGE_SECTIONS_FOR_COVER:
            image_id = _uuid(content.get("image_asset_id"))
            if image_id:
                wanted.add(image_id)
        if section.section_type_id not in OFFERING_SECTIONS:
            continue
        for list_key in _ITEM_LISTS:
            for row in content.get(list_key) or []:
                if not isinstance(row, dict):
                    continue
                name = _item_name(row)
                if not name:
                    continue
                image_id = _uuid(row.get("image_asset_id"))
                if image_id:
                    wanted.add(image_id)
                items.append((name, image_id))
    if profile is not None:
        for raw in (profile.logo_asset_id, profile.cover_asset_id):
            image_id = _uuid(raw)
            if image_id:
                wanted.add(image_id)
    urls = await _asset_urls(session, business.id, wanted)

    # What the site lists, pictured ones first. A card shows the names; the
    # profile gallery shows only the ones with a picture.
    seen: set[str] = set()
    pictured: list[dict[str, Any]] = []
    unpictured: list[dict[str, Any]] = []
    for name, image_id in items:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        url = urls.get(str(image_id)) if image_id else None
        (pictured if url else unpictured).append({"title": name, "image_url": url})
    facts.highlights = (pictured + unpictured)[:8]

    # The cover is the picture the Business put at the top of its own site,
    # then its profile cover; never a stock image.
    for section in sections:
        if section.section_type_id in _IMAGE_SECTIONS_FOR_COVER:
            url = urls.get(str(_uuid((section.content or {}).get("image_asset_id"))))
            if url:
                facts.cover_url = url
                break
    if facts.cover_url is None and profile is not None and profile.cover_asset_id:
        facts.cover_url = urls.get(str(profile.cover_asset_id))
    if profile is not None and profile.logo_asset_id:
        facts.logo_url = urls.get(str(profile.logo_asset_id))

    raw_contact = profile.contact if profile is not None and isinstance(profile.contact, dict) else {}
    for key in ("phone", "whatsapp"):
        value = raw_contact.get(key)
        if isinstance(value, str) and re.sub(r"\D", "", value):
            facts.public_contact[key] = value.strip()

    # ---- where it is ------------------------------------------------------
    address = location.address if location is not None and isinstance(location.address, dict) else {}
    structured = " ".join(
        str(address.get(k) or "") for k in ("line1", "line2", "locality", "area", "city", "state", "postal_code")
    ).strip()
    place = place_from_address(structured) or place_from_address(address_text or "")
    facts.city = (address.get("city") or (place.city if place else None)) or None
    facts.region = (address.get("state") or (place.state if place else None)) or None
    facts.locality = (address.get("locality") or address.get("area") or (place.locality if place else None)) or None
    postal = address.get("postal_code") or address.get("pincode")
    if not postal:
        match = _POSTAL.search(f"{structured} {address_text or ''}")
        postal = match.group(1) if match else None
    facts.postal_code = str(postal) if postal else None
    if location is not None and location.latitude is not None and location.longitude is not None:
        facts.lat, facts.lng, facts.geo_precision = float(location.latitude), float(location.longitude), "exact"
    elif place is not None:
        facts.lat, facts.lng, facts.geo_precision = place.lat, place.lng, "city"

    # ---- what kind of business it is --------------------------------------
    item_names = [name for name, _ in items]
    facts.placement = classify(
        business.business_type,
        [
            " ".join(item_names[:60]),
            " ".join(offering_titles[:60]),
            profile.description if profile else None,
            profile.tagline if profile else None,
            business.display_name,
        ],
    )

    keywords: list[str] = []
    for word in [
        *search_terms(facts.placement.family_id, facts.placement.category_id),
        *item_names,
        *offering_titles,
    ]:
        if word and word.lower() not in {k.lower() for k in keywords}:
            keywords.append(word)
        if len(keywords) >= 80:
            break
    facts.keywords = keywords
    return facts
