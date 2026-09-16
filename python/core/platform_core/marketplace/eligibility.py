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
