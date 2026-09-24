"""Marketplace search, discovery and profile read APIs (Doc 11 §13.1, Doc 12 §14).

Everything a listing says comes from the projection, which is built from what
the Business published. Ordering is deterministic and every personal touch
carries the plain reason it was chosen. Nothing here stores anything about the
visitor: the signals arrive with the request (from a first-party cookie the
visitor can clear, or from their own bookings) and are forgotten after it.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.business_categories import (
    FAMILIES_BY_ID,
    FAMILY_ICONS,
    labels as category_labels,
    match_query,
    serialize_taxonomy,
)
from platform_core.context_resolver import bind_public_context
from platform_core.exceptions import ResourceNotFound
from platform_core.geo.india_places import (
    distance_km,
    nearest_place,
    place_by_name,
    place_from_pin,
    suggest_places,
)
from platform_core.marketplace.eligibility import (
    evaluate_eligibility,
    evaluate_live_eligibility_bulk,
)
from platform_core.marketplace.search_provider import (
    CAPABILITY_FILTERS,
    MBP,
    BusinessQuery,
    get_search_provider,
    live_business_ids,
)
from platform_core.models import (
    MarketplaceBusinessProjection,
    MarketplaceOfferingProjection,
)

# How far "near you" reaches. Past this, a listing is shown by what it is,
# not by where it is.
NEARBY_KM = 40.0


@dataclass(frozen=True)
class VisitorPlace:
    """Where the visitor says they are, as precisely as they chose to share.

    `precision` is 'device' for rounded browser coordinates, 'city' for a
    town they picked or typed, 'pin' for a PIN placed by its prefix. Only
    'device' ever produces a distance on screen, and only to a Business whose
    own coordinates are exact.
    """

    lat: float
    lng: float
    label: str
    precision: str = "city"


@dataclass
class Signals:
    """What this visitor did recently, as the request states it."""

    families: dict[str, int] = field(default_factory=dict)
    categories: dict[str, int] = field(default_factory=dict)
    searched: list[str] = field(default_factory=list)
    viewed_slugs: list[str] = field(default_factory=list)
    used_business_ids: list[uuid.UUID] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.families or self.categories or self.searched or self.viewed_slugs or self.used_business_ids)


# ---------------------------------------------------------------------------
# One listing, as every surface shows it
# ---------------------------------------------------------------------------


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def listing_actions(
    row: MarketplaceBusinessProjection, *, flags: dict[str, Any] | None = None
) -> list[dict[str, str]]:
    """What a visitor can do from a listing — only what works right now.

    Each action needs its module switched on *and* somewhere real to land on
    the Business's published site. "Order" additionally needs something live
    to order. Call and WhatsApp use the number the owner already publishes.
    """
    flags = flags if flags is not None else (row.capability_flags or {})
    paths = row.site_paths or {}
    contact = row.public_contact or {}
    base = f"/{row.slug}"
    actions: list[dict[str, str]] = []
    if flags.get("order") and (row.offering_count or 0) > 0:
        actions.append({"action": "order", "label": "Order online", "href": base + paths.get("browse", "")})
    if flags.get("book"):
        actions.append({"action": "book", "label": "Book", "href": f"{base}/book"})
    if flags.get("join") and "join" in paths:
        actions.append({"action": "join", "label": "See plans", "href": base + paths["join"]})
    if flags.get("enquire") and "contact" in paths:
        actions.append({"action": "enquire", "label": "Send an enquiry", "href": base + paths["contact"]})
    whatsapp = _digits(contact.get("whatsapp", ""))
    if len(whatsapp) >= 10:
        actions.append({"action": "whatsapp", "label": "WhatsApp", "href": f"https://wa.me/{whatsapp}"})
    phone = _digits(contact.get("phone", ""))
    if len(phone) >= 10:
        actions.append({"action": "call", "label": "Call", "href": f"tel:+{phone}" if len(phone) > 10 else f"tel:{phone}"})
    actions.append({"action": "visit_website", "label": "Visit website", "href": base})
    return actions


def _shown_distance(row: MarketplaceBusinessProjection, km: float | None, place: VisitorPlace | None) -> float | None:
    if km is None or place is None or place.precision != "device" or row.geo_precision != "exact":
        return None
    return round(km, 1)


def serialize_listing(
    row: MarketplaceBusinessProjection,
    *,
    km: float | None = None,
    place: VisitorPlace | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    placed = category_labels(row.category_family, row.category)
    area = ", ".join(part for part in (row.locality, row.city) if part)
    return {
        # Fields the Stage 3 clients already read.
        "result_type": "business",
        "business_id": str(row.business_id),
        "slug": row.slug,
        "display_name": row.display_name,
        "description": row.description,
        "business_type": row.business_type,
        "city": row.city,
        "primary_category": row.primary_category,
        "tags": list(row.tags or []),
        "capability_flags": row.capability_flags or {},
        "logo_asset_id": str(row.logo_asset_id) if row.logo_asset_id else None,
        # Discovery depth.
        "family": placed["family"],
        "family_label": placed["family_label"],
        "category": placed["category"],
        "category_label": placed["category_label"],
        "icon": FAMILY_ICONS.get(row.category_family or "", "storefront"),
        "locality": row.locality,
        "region": row.region,
        "postal_code": row.postal_code,
        "area_label": area or None,
        "cover_url": row.cover_url,
        "logo_url": row.logo_url,
        "highlights": list(row.highlights or [])[:4],
        "offering_count": int(row.offering_count or 0),
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "actions": listing_actions(row),
        # Only ever a distance between two exact points; see VisitorPlace.
        "distance_km": _shown_distance(row, km, place),
        "reason": reason,
    }


def _nearest_label(place: VisitorPlace | None) -> str | None:
    return place.label if place else None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class MarketplaceSearchService:
    @staticmethod
    def resolve_place(
        *, q: str | None = None, lat: float | None = None, lng: float | None = None
    ) -> VisitorPlace | None:
        """A visitor's place from what they typed, or their rounded coordinates.

        Coordinates are rounded to two decimals (about a kilometre) before
        anything else touches them, whatever precision the browser gave.
        """
        if lat is not None and lng is not None:
            if not (6.0 <= lat <= 37.5 and 68.0 <= lng <= 97.5):
                return None
            rlat, rlng = round(lat, 2), round(lng, 2)
            town = nearest_place(rlat, rlng)
            return VisitorPlace(rlat, rlng, town.city if town else "your area", "device")
        typed = (q or "").strip()
        if not typed:
            return None
        if _digits(typed) and len(_digits(typed)) == 6 and len(typed) <= 7:
            town = place_from_pin(typed)
            if town is None:
                return None
            return VisitorPlace(town.lat, town.lng, town.city, "pin")
        town = place_by_name(typed)
        if town is None:
            return None
        return VisitorPlace(town.lat, town.lng, town.city, "city")

    @staticmethod
    def suggest_places(prefix: str | None) -> list[dict[str, Any]]:
        return [
            {"city": p.city, "state": p.state, "lat": p.lat, "lng": p.lng}
            for p in suggest_places(prefix)
        ]

    @staticmethod
    async def _live_verdicts(session: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, bool]:
        # Belt and braces: the provider already joins live state; this is the
        # original query-time check (Doc 12 §14.4), one query for the page.
        verdicts = await evaluate_live_eligibility_bulk(session, sorted(ids))
        return {bid: v.eligible for bid, v in verdicts.items()}

    @staticmethod
    async def search(
        session: AsyncSession,
        *,
        q: str | None = None,
        location: str | None = None,
        type_: str | None = None,
        limit: int = 20,
        offset: int = 0,
        family: str | None = None,
        category: str | None = None,
        capabilities: tuple[str, ...] = (),
        place: VisitorPlace | None = None,
        sort: str = "relevance",
    ) -> dict[str, Any]:
        provider = get_search_provider()
        family = family if family in FAMILIES_BY_ID else None
        category = category if family and FAMILIES_BY_ID[family].category(category or "") else None
        capabilities = tuple(c for c in capabilities if c in CAPABILITY_FILTERS)
        query = BusinessQuery(
            text=q,
            area=location,
            family=family,
            category=category,
            business_type=type_,
            capabilities=capabilities,
            near=(place.lat, place.lng) if place else None,
            sort=sort if sort in {"relevance", "nearest", "newest", "name"} else "relevance",
            limit=limit,
            offset=offset,
        )
        hits = await provider.find_businesses(session, query)
        offerings = await provider.search_offerings(
            session,
            query=q,
            location=location,
            offering_type=type_,
            limit=min(limit, 12),
            family=family,
            category=category,
        ) if q and q.strip() else []

        candidate_ids = {row.business_id for row, _ in hits.rows} | {
            uuid.UUID(item["business_id"]) for item in offerings
        }
        eligible = await MarketplaceSearchService._live_verdicts(session, candidate_ids)
        businesses = [
            serialize_listing(row, km=km, place=place)
            for row, km in hits.rows
            if eligible.get(row.business_id)
        ]
        offerings = [item for item in offerings if eligible.get(uuid.UUID(item["business_id"]))]
        facets = await provider.facets(session, query)

        market_count = (
            await session.execute(
                select(func.count())
                .select_from(MBP)
                .where(MBP.is_discoverable.is_(True), MBP.business_id.in_(live_business_ids()))
            )
        ).scalar_one()

        total = len(businesses) + len(offerings)
        state = "results"
        if total == 0 and market_count == 0:
            state = "sparse_market"
        elif total == 0:
            state = "no_results"

        return {
            "state": state,
            "match": hits.match,
            "query": {
                "q": q,
                "location": location,
                "type": type_,
                "family": family,
                "category": category,
                "capabilities": list(capabilities),
                "sort": query.sort,
                "near": _nearest_label(place),
            },
            "businesses": businesses,
            "offerings": offerings,
            "facets": facets,
            "suggested_categories": match_query(q) if q else [],
            "page": {"offset": offset, "limit": limit, "total": hits.total},
            "counts": {
                "businesses": len(businesses),
                "offerings": len(offerings),
                "indexed_businesses": int(market_count or 0),
                "matching_businesses": hits.total,
            },
        }

    @staticmethod
    async def category_counts(session: AsyncSession) -> dict[tuple[str, str | None], int]:
        rows = (
            await session.execute(
                select(MBP.category_family, MBP.category, func.count())
                .where(MBP.is_discoverable.is_(True), MBP.business_id.in_(live_business_ids()))
                .group_by(MBP.category_family, MBP.category)
            )
        ).all()
        counts: dict[tuple[str, str | None], int] = {}
        for family_id, category_id, count in rows:
            if not family_id:
                continue
            counts[(family_id, None)] = counts.get((family_id, None), 0) + int(count)
            if category_id:
                counts[(family_id, category_id)] = int(count)
        return counts

    @staticmethod
    async def categories(session: AsyncSession) -> dict[str, Any]:
        counts = await MarketplaceSearchService.category_counts(session)
        return {"families": serialize_taxonomy(counts)}

    @staticmethod
    async def discover(
        session: AsyncSession,
        *,
        place: VisitorPlace | None = None,
        signals: Signals | None = None,
        rail_size: int = 12,
    ) -> dict[str, Any]:
        """The Marketplace home: rails a person can scan, each with its reason.

        Every rail is a deterministic query. "For you" weighs only what the
        request says this visitor looked at, searched or booked; with none of
        that it is simply absent, never filled with guesses.
        """
        provider = get_search_provider()
        signals = signals or Signals()
        near = (place.lat, place.lng) if place else None
        rails: list[dict[str, Any]] = []

        async def _rail(
            rail_id: str,
            title: str,
            explain: str,
            query: BusinessQuery,
            reason: str | None = None,
            href: str | None = None,
        ) -> list[MarketplaceBusinessProjection]:
            hits = await provider.find_businesses(session, query)
            if not hits.rows:
                return []
            rails.append({
                "id": rail_id,
                "title": title,
                "explain": explain,
                "href": href,
                "total": hits.total,
                "items": [serialize_listing(row, km=km, place=place, reason=reason) for row, km in hits.rows],
            })
            return [row for row, _ in hits.rows]

        # 1. Near the visitor, if they shared where they are.
        nearby_count = 0
        if place is not None:
            shown = await _rail(
                "nearby",
                f"Near {place.label}",
                "Closest first, by the town or area each business published."
                if place.precision != "device"
                else "Closest first. Distances only appear where a business published its exact spot.",
                BusinessQuery(near=near, within_km=NEARBY_KM, sort="nearest", limit=rail_size),
                href=None,
            )
            nearby_count = len(shown)

        # 2. Picked for this visitor, from the signals in this request only.
        weights: dict[tuple[str, str | None], float] = {}
        why: dict[tuple[str, str | None], str] = {}
        for family_id, count in signals.families.items():
            if family_id in FAMILIES_BY_ID:
                key = (family_id, None)
                weights[key] = weights.get(key, 0) + min(count, 5)
                why.setdefault(key, f"You browsed {FAMILIES_BY_ID[family_id].label}")
        for category_id, count in signals.categories.items():
            for family in FAMILIES_BY_ID.values():
                category = family.category(category_id)
                if category is not None:
                    key = (family.id, category.id)
                    weights[key] = weights.get(key, 0) + 2 * min(count, 5)
                    why.setdefault(key, f"You looked at {category.label}")
        for term in signals.searched[:3]:
            for hit in match_query(term, limit=2):
                key = (str(hit["family"]), hit["category"])
                weights[key] = weights.get(key, 0) + 3
                why[key] = f"You searched “{term}”"

        used_rows: list[MarketplaceBusinessProjection] = []
        if signals.used_business_ids:
            used_rows = list(
                (
                    await session.execute(
                        select(MBP).where(
                            MBP.business_id.in_(signals.used_business_ids[:20]),
                            MBP.is_discoverable.is_(True),
                            MBP.business_id.in_(live_business_ids()),
                        ).order_by(MBP.display_name.asc())
                    )
                ).scalars().all()
            )
            for row in used_rows:
                if row.category_family:
                    key = (row.category_family, row.category)
                    weights[key] = weights.get(key, 0) + 2
                    why.setdefault(key, "Like places you have booked")

        if weights:
            ranked = sorted(weights.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1] or ""))[:4]
            picked: list[dict[str, Any]] = []
            seen: set[uuid.UUID] = {row.business_id for row in used_rows}
            for (want_family, want_category), _ in ranked:
                hits = await provider.find_businesses(
                    session,
                    BusinessQuery(
                        family=want_family,
                        category=want_category,
                        near=near,
                        sort="nearest" if near else "newest",
                        limit=rail_size,
                    ),
                )
                for row, km in hits.rows:
                    if row.business_id in seen:
                        continue
                    seen.add(row.business_id)
                    picked.append(serialize_listing(row, km=km, place=place, reason=why[(want_family, want_category)]))
                    if len(picked) >= rail_size:
                        break
                if len(picked) >= rail_size:
                    break
            if picked:
                rails.append({
                    "id": "for_you",
                    "title": "Picked for you",
                    "explain": "From what you browsed and searched on this device"
                    + (" and your bookings" if signals.used_business_ids else "")
                    + ". Nothing is shared or kept on our side; clear it any time.",
                    "href": None,
                    "total": len(picked),
                    "items": picked,
                })

        if used_rows:
            rails.append({
                "id": "again",
                "title": "Book again",
                "explain": "Businesses you have booked with through LOCAH.",
                "href": None,
                "total": len(used_rows),
                "items": [serialize_listing(row, place=place, reason="You booked here") for row in used_rows],
            })

        # 3. By what you can do, then what is new.
        await _rail(
            "order_online",
            "Order online",
            "Businesses taking orders on their own LOCAH website right now.",
            BusinessQuery(capabilities=("order",), near=near, sort="nearest" if near else "newest", limit=rail_size),
            href="/marketplace/search?can=order",
        )
        await _rail(
            "book",
            "Book an appointment",
            "Businesses with bookings switched on.",
            BusinessQuery(capabilities=("book",), near=near, sort="nearest" if near else "newest", limit=rail_size),
            href="/marketplace/search?can=book",
        )
        await _rail(
            "new",
            "Recently published",
            "Newest websites on LOCAH, most recent first.",
            BusinessQuery(sort="newest", limit=rail_size),
            href="/marketplace/search?sort=newest",
        )

        counts = await MarketplaceSearchService.category_counts(session)
        total = (
            await session.execute(
                select(func.count())
                .select_from(MBP)
                .where(MBP.is_discoverable.is_(True), MBP.business_id.in_(live_business_ids()))
            )
        ).scalar_one()
        cities = (
            await session.execute(
                select(MBP.city, func.count())
                .where(
                    MBP.is_discoverable.is_(True),
                    MBP.business_id.in_(live_business_ids()),
                    MBP.city.is_not(None),
                )
                .group_by(MBP.city)
                .order_by(func.count().desc(), MBP.city.asc())
                .limit(12)
            )
        ).all()
        return {
            "place": {"label": place.label, "precision": place.precision} if place else None,
            "location_state": (
                "none" if place is None else "nearby" if nearby_count else "none_nearby"
            ),
            "rails": rails,
            "categories": serialize_taxonomy(counts),
            "cities": [{"city": city, "count": int(count)} for city, count in cities],
            "totals": {"businesses": int(total or 0)},
            "personalised": any(r["id"] in {"for_you", "again"} for r in rails),
        }

    @staticmethod
    async def get_marketplace_profile(
        session: AsyncSession, *, slug: str, place: VisitorPlace | None = None
    ) -> dict[str, Any]:
        # Lazy import avoids circular import via entitlements → business.
        from platform_core.services.business import BusinessService

        business = await BusinessService.get_by_slug(session, slug)
        if business is None:
            raise ResourceNotFound("Business")
        await bind_public_context(session, business.id)
        eligibility = await evaluate_eligibility(session, business.id)
        if not eligibility.eligible:
            raise ResourceNotFound("Business")

        projection = (
            (
                await session.execute(
                    select(MarketplaceBusinessProjection).where(
                        MarketplaceBusinessProjection.business_id == business.id,
                        MarketplaceBusinessProjection.is_discoverable.is_(True),
                    )
                )
            )
            .scalars()
            .first()
        )
        if projection is None:
            raise ResourceNotFound("Business")

        offerings = (
            (
                await session.execute(
                    select(MarketplaceOfferingProjection)
                    .where(
                        MarketplaceOfferingProjection.business_id == business.id,
                        MarketplaceOfferingProjection.is_active.is_(True),
                    )
                    .order_by(MarketplaceOfferingProjection.title.asc())
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )

        # Capabilities are read live here (one Business, so it is cheap) rather
        # than from the projection's copy, which can lag a module switch.
        listing = serialize_listing(projection)
        actions = listing_actions(projection, flags=eligibility.capability_flags or {})

        km = None
        if place is not None and projection.lat is not None and projection.lng is not None:
            km = distance_km(place.lat, place.lng, float(projection.lat), float(projection.lng))

        related: list[dict[str, Any]] = []
        if projection.category_family:
            provider = get_search_provider()
            hits = await provider.find_businesses(
                session,
                BusinessQuery(
                    family=projection.category_family,
                    near=(float(projection.lat), float(projection.lng))
                    if projection.lat is not None and projection.lng is not None
                    else None,
                    sort="nearest" if projection.lat is not None else "newest",
                    limit=7,
                ),
            )
            related = [
                serialize_listing(row)
                for row, _ in hits.rows
                if row.business_id != business.id
            ][:6]

        return {
            "business": {
                "id": str(business.id),
                "slug": business.slug,
                "display_name": business.display_name,
                "business_type": business.business_type,
                "description": projection.description,
                "tagline": eligibility.profile.tagline if eligibility.profile else None,
                "city": projection.city,
                "locality": projection.locality,
                "region": projection.region,
                "postal_code": projection.postal_code,
                "area_label": listing["area_label"],
                "family": listing["family"],
                "family_label": listing["family_label"],
                "category": listing["category"],
                "category_label": listing["category_label"],
                "icon": listing["icon"],
                "cover_url": projection.cover_url,
                "logo_url": projection.logo_url,
                "highlights": list(projection.highlights or []),
                "offering_count": int(projection.offering_count or 0),
                "published_at": listing["published_at"],
                "public_contact": dict(projection.public_contact or {}),
                "distance_km": _shown_distance(projection, km, place),
                "logo_asset_id": str(projection.logo_asset_id)
                if projection.logo_asset_id
                else None,
            },
            "actions": actions,
            "related": related,
            "offerings": [
                {
                    "id": str(o.id),
                    "title": o.title,
                    "offering_type": o.offering_type,
                    "description": o.description,
                    "price_from": float(o.price_from) if o.price_from is not None else None,
                    "currency": o.currency,
                    "category": o.category,
                    "handoff": {
                        "business_slug": business.slug,
                        "offering_id": str(o.id),
                        "location_id": str(projection.primary_location_id)
                        if projection.primary_location_id
                        else None,
                        "destination_intent": "offering",
                        "href": (
                            f"/{business.slug}?offering_id={o.id}"
                            + (
                                f"&location_id={projection.primary_location_id}"
                                if projection.primary_location_id
                                else ""
                            )
                            + "&intent=offering"
                        ),
                    },
                }
                for o in offerings
            ],
            "website_handoff": {
                "href": f"/{business.slug}",
                "destination_intent": "visit_website",
                "location_id": str(projection.primary_location_id)
                if projection.primary_location_id
                else None,
            },
        }
