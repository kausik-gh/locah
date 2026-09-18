"""Joined-Business-only eligibility (Doc 12 §14.4, Doc 11 §13.3)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import (
    Business,
    BusinessModuleState,
    BusinessProfile,
    Website,
)

@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    reasons: tuple[str, ...]
    business: Business | None = None
    profile: BusinessProfile | None = None
    website: Website | None = None
    capability_flags: dict[str, bool] | None = None


async def _capability_flags(
    session: AsyncSession, business_id: uuid.UUID
) -> dict[str, bool]:
    result = await session.execute(
        select(BusinessModuleState.module_id, BusinessModuleState.activation_state).where(
            BusinessModuleState.business_id == business_id
        )
    )
    active = {
        row[0]: row[1] == "active"
        for row in result.all()
    }
    return {
        "order": bool(active.get("orders")),
        "book": bool(active.get("bookings")),
        "contact": True,  # Core website/contact always available when published
        "visit_website": True,
        "enquire": bool(active.get("leads")),
        "join": bool(active.get("memberships")),
    }


async def evaluate_eligibility(
    session: AsyncSession, business_id: uuid.UUID
) -> EligibilityResult:
    business = (
        await session.execute(
            select(Business).where(Business.id == business_id, Business.deleted_at.is_(None))
        )
    ).scalars().first()
    if business is None:
        return EligibilityResult(False, ("business_not_found",))

    reasons: list[str] = []
    if business.state != "active":
        reasons.append("business_not_active")
    if business.status not in {"in_good_standing"}:
        reasons.append("business_status_blocked")
    if business.visibility != "discoverable":
        reasons.append("visibility_not_discoverable")

    profile = (
        await session.execute(
            select(BusinessProfile).where(BusinessProfile.business_id == business_id)
        )
    ).scalars().first()
    if profile is None:
        reasons.append("profile_missing")
    elif not (profile.description or profile.tagline):
        # Public facts required for Marketplace projection (Doc 11 §13.3).
        reasons.append("profile_public_facts_missing")

    website = (
        await session.execute(select(Website).where(Website.business_id == business_id))
    ).scalars().first()
    if website is None or website.status != "published" or not website.published_version_id:
        reasons.append("website_not_published")

    flags = await _capability_flags(session, business_id)
    return EligibilityResult(
        eligible=len(reasons) == 0,
        reasons=tuple(reasons),
        business=business,
        profile=profile,
        website=website,
        capability_flags=flags,
    )


def serialize_eligibility(result: EligibilityResult) -> dict[str, Any]:
    return {
        "eligible": result.eligible,
        "reasons": list(result.reasons),
        "capability_flags": result.capability_flags or {},
    }


@dataclass(frozen=True)
class LiveEligibility:
    """The subset of eligibility that must hold *now*, not at index time."""

    eligible: bool
    reasons: tuple[str, ...]


async def evaluate_live_eligibility_bulk(
    session: AsyncSession, business_ids: list[uuid.UUID]
) -> dict[uuid.UUID, LiveEligibility]:
    """Re-check the live-state half of eligibility for many businesses at once.

    `evaluate_eligibility` reads four tables per business and needs
    `bind_public_context` before each one, because the policies on
    business_profiles / websites / business_module_states are
    `business_id = current_business_id()`. On a public search that is six round
    trips per result — 243 queries for a page of twenty, which is ten seconds
    before the API has left its own region.

    Splitting the check is what removes that, and the split is not arbitrary.
    Two different kinds of fact are mixed together in `evaluate_eligibility`:

      * Facts that decide whether a business may be *shown at all* — deleted,
        suspended, deactivated, made private. Getting these wrong exposes a
        business that has asked not to be listed, so they are re-read live on
        every request. They all live on `businesses`, whose SELECT policy
        already carries a public arm (`visibility IN ('unlisted','discoverable')
        AND status = 'in_good_standing'`), so one `WHERE id = ANY(...)` reads
        them for the whole page without binding anything.

      * Facts that decide how the card *looks* — the blurb, the published
        website, which capability buttons to offer. Getting these wrong shows a
        stale description or a button that leads nowhere. They are already
        denormalised onto `marketplace_business_projections`, which is what a
        read model is for, and are refreshed by the marketplace.index subscriber.

    So the security-relevant half stays live and the presentational half comes
    from the projection. Nothing new is exposed: this reads `businesses` through
    the arm that already made the Marketplace listing public in the first place.

    A business the policy hides — suspended, deleted, gone private — simply
    returns no row, and is reported ineligible.
    """
    if not business_ids:
        return {}

    result = await session.execute(
        select(
            Business.id,
            Business.state,
            Business.status,
            Business.visibility,
        ).where(Business.id.in_(business_ids), Business.deleted_at.is_(None))
    )
    rows = {row[0]: row for row in result.all()}

    verdicts: dict[uuid.UUID, LiveEligibility] = {}
    for business_id in business_ids:
        row = rows.get(business_id)
        if row is None:
            # Either it does not exist, or RLS withheld it — which is itself the
            # answer, since the public arm only yields in-good-standing rows.
            verdicts[business_id] = LiveEligibility(False, ("business_not_visible",))
            continue

        reasons: list[str] = []
        if row[1] != "active":
            reasons.append("business_not_active")
        if row[2] != "in_good_standing":
            reasons.append("business_status_blocked")
        # `unlisted` passes the RLS arm but must not appear in discovery — an
        # unlisted business is reachable by direct link, not by browsing.
        if row[3] != "discoverable":
            reasons.append("visibility_not_discoverable")

        verdicts[business_id] = LiveEligibility(len(reasons) == 0, tuple(reasons))
    return verdicts
