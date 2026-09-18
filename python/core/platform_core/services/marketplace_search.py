"""Marketplace search and profile read APIs (Doc 11 §13.1, Doc 12 §14)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.context_resolver import bind_public_context
from platform_core.exceptions import ResourceNotFound
from platform_core.marketplace.eligibility import (
    evaluate_eligibility,
    evaluate_live_eligibility_bulk,
)
from platform_core.marketplace.search_provider import get_search_provider
from platform_core.models import (
    MarketplaceBusinessProjection,
    MarketplaceOfferingProjection,
)


class MarketplaceSearchService:
    @staticmethod
    async def search(
        session: AsyncSession,
        *,
        q: str | None = None,
        location: str | None = None,
        type_: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        provider = get_search_provider()
        # Dual enforcement: projections already require is_discoverable; re-check live eligibility
        # for each result before returning (Doc 12 §14.4).
        businesses = await provider.search_businesses(
            session,
            query=q,
            location=location,
            business_type=type_,
            limit=limit,
        )
        offerings = await provider.search_offerings(
            session,
            query=q,
            location=location,
            offering_type=type_,
            limit=limit,
        )

        # One live check for every candidate on the page, businesses and
        # offerings together. The previous version bound tenant context and
        # re-read four tables per result, which is where 243 queries for a page
        # of twenty came from; see evaluate_live_eligibility_bulk for why the
        # security-relevant half of the check is the half that stays live.
        candidate_ids = {
            uuid.UUID(item["business_id"]) for item in (*businesses, *offerings)
        }
        verdicts = await evaluate_live_eligibility_bulk(session, sorted(candidate_ids))

        def _is_eligible(item: dict[str, Any]) -> bool:
            verdict = verdicts.get(uuid.UUID(item["business_id"]))
            return verdict is not None and verdict.eligible

        # capability_flags stay as the projection recorded them. They are
        # refreshed by the marketplace.index subscriber, which module.enabled /
        # module.disabled / module.deactivated now trigger.
        filtered_businesses = [item for item in businesses if _is_eligible(item)]
        filtered_offerings = [item for item in offerings if _is_eligible(item)]

        total = len(filtered_businesses) + len(filtered_offerings)
        market_count = (
            await session.execute(
                select(func.count())
                .select_from(MarketplaceBusinessProjection)
                .where(MarketplaceBusinessProjection.is_discoverable.is_(True))
            )
        ).scalar_one()

        state = "results"
        if total == 0 and market_count == 0:
            state = "sparse_market"
        elif total == 0:
            state = "no_results"

        return {
            "state": state,
            "query": {"q": q, "location": location, "type": type_},
            "businesses": filtered_businesses,
            "offerings": filtered_offerings,
            "counts": {
                "businesses": len(filtered_businesses),
                "offerings": len(filtered_offerings),
                "indexed_businesses": int(market_count or 0),
            },
        }

    @staticmethod
    async def get_marketplace_profile(session: AsyncSession, *, slug: str) -> dict[str, Any]:
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

        flags = eligibility.capability_flags or {}
        actions: list[dict[str, str]] = []
        if flags.get("visit_website"):
            actions.append(
                {
                    "action": "visit_website",
                    "label": "Visit Website",
                    "href": f"/{business.slug}",
                }
            )
        if flags.get("order"):
            actions.append(
                {
                    "action": "order",
                    "label": "Order",
                    "href": f"/{business.slug}?intent=order",
                }
            )
        if flags.get("book"):
            actions.append(
                {
                    "action": "book",
                    "label": "Book",
                    "href": f"/{business.slug}?intent=book",
                }
            )
        if flags.get("enquire"):
            actions.append(
                {
                    "action": "enquire",
                    "label": "Contact",
                    "href": f"/{business.slug}/enquire?intent=enquire",
                }
            )
        if flags.get("join"):
            actions.append(
                {
                    "action": "join",
                    "label": "Join",
                    "href": f"/{business.slug}/join?intent=join",
                }
            )

        return {
            "business": {
                "id": str(business.id),
                "slug": business.slug,
                "display_name": business.display_name,
                "business_type": business.business_type,
                "description": projection.description,
                "city": projection.city,
                "logo_asset_id": str(projection.logo_asset_id)
                if projection.logo_asset_id
                else None,
            },
            "actions": actions,
            "offerings": [
                {
                    "id": str(o.id),
                    "title": o.title,
                    "offering_type": o.offering_type,
                    "description": o.description,
                    "price_from": float(o.price_from) if o.price_from is not None else None,
                    "currency": o.currency,
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
