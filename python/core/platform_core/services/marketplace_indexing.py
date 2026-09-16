"""Marketplace projection indexing (Doc 12 §14.4–§14.5)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.marketplace.eligibility import evaluate_eligibility
from platform_core.models import (
    BusinessLocation,
    MarketplaceBusinessProjection,
    MarketplaceIndexHealth,
    MarketplaceOfferingProjection,
    Offering,
    OfferingCategory,
)
from platform_core.services.audit import AuditService
from platform_core.services.outbox import OutboxService


class MarketplaceIndexingService:
    @staticmethod
    async def _ensure_health(
        session: AsyncSession, business_id: uuid.UUID
    ) -> MarketplaceIndexHealth:
        result = await session.execute(
            select(MarketplaceIndexHealth).where(
                MarketplaceIndexHealth.business_id == business_id
            )
        )
        health = result.scalars().first()
        if health is None:
            health = MarketplaceIndexHealth(business_id=business_id, last_status="never")
            session.add(health)
            await session.flush()
        return health

    @staticmethod
    async def _primary_location(
        session: AsyncSession, business_id: uuid.UUID
    ) -> BusinessLocation | None:
        result = await session.execute(
            select(BusinessLocation).where(
                BusinessLocation.business_id == business_id,
                BusinessLocation.deleted_at.is_(None),
                BusinessLocation.status == "active",
            ).order_by(BusinessLocation.is_primary.desc(), BusinessLocation.created_at.asc())
        )
        return result.scalars().first()

    @staticmethod
    async def _upsert_offerings(
        session: AsyncSession, *, business_id: uuid.UUID, eligible: bool
    ) -> int:
        await session.execute(
            delete(MarketplaceOfferingProjection).where(
                MarketplaceOfferingProjection.business_id == business_id
            )
        )
        if not eligible:
            return 0
        offerings = (
            await session.execute(
                select(Offering).where(
                    Offering.business_id == business_id,
                    Offering.deleted_at.is_(None),
                    Offering.status == "active",
                    Offering.visibility == "public",
                )
            )
        ).scalars().all()
        count = 0
        for offering in offerings:
            category_name = None
            if offering.category_id:
                cat = (
                    await session.execute(
                        select(OfferingCategory).where(OfferingCategory.id == offering.category_id)
                    )
                ).scalars().first()
                category_name = cat.name if cat else None
            session.add(
                MarketplaceOfferingProjection(
                    id=offering.id,
                    business_id=business_id,
                    offering_type=offering.offering_type,
                    title=offering.title,
                    description=offering.description,
                    price_from=float(offering.price_amount)
                    if offering.price_amount is not None
                    else None,
                    currency=offering.currency,
                    category=category_name,
                    tags=[],
                    location_ids=[],
                    is_active=True,
                    indexed_at=datetime.now(timezone.utc),
                )
            )
            count += 1
        await session.flush()
        return count

    @staticmethod
    async def reindex_business(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        correlation_id: str,
        actor_id: uuid.UUID | None = None,
        trigger: str = "manual",
    ) -> dict[str, Any]:
        health = await MarketplaceIndexingService._ensure_health(session, business_id)
        health.last_attempt_at = datetime.now(timezone.utc)
        eligibility = await evaluate_eligibility(session, business_id)

        try:
            if not eligibility.eligible:
                existing = (
                    await session.execute(
                        select(MarketplaceBusinessProjection).where(
                            MarketplaceBusinessProjection.business_id == business_id
                        )
                    )
                ).scalars().first()
                if existing is not None:
                    await session.delete(existing)
                await MarketplaceIndexingService._upsert_offerings(
                    session, business_id=business_id, eligible=False
                )
                health.last_status = "deindexed"
                health.last_reason = ",".join(eligibility.reasons)
                health.last_error = None
                health.updated_at = datetime.now(timezone.utc)
                await session.flush()
                await OutboxService.publish(
                    session,
                    event_type="marketplace.deindexed",
                    payload={
                        "business_id": str(business_id),
                        "reasons": list(eligibility.reasons),
                        "trigger": trigger,
                    },
                    business_id=business_id,
                    correlation_id=correlation_id,
                )
                return {
                    "status": "deindexed",
                    "reasons": list(eligibility.reasons),
                    "business_id": str(business_id),
                }

            assert eligibility.business is not None
            business = eligibility.business
            profile = eligibility.profile
            location = await MarketplaceIndexingService._primary_location(session, business_id)
            city = None
            if location and isinstance(location.address, dict):
                city = location.address.get("city") or location.address.get("locality")

            projection = (
                await session.execute(
                    select(MarketplaceBusinessProjection).where(
                        MarketplaceBusinessProjection.business_id == business_id
                    )
                )
            ).scalars().first()
            payload = {
                "slug": business.slug,
                "display_name": business.display_name,
                "description": (profile.description if profile else None)
                or (profile.tagline if profile else None),
                "business_type": business.business_type,
                "characteristics": list(business.characteristics or []),
                "primary_category": business.business_type,
                "tags": [business.business_type] if business.business_type else [],
                "primary_location_id": location.id if location else None,
                "city": city,
                "lat": float(location.latitude) if location and location.latitude is not None else None,
                "lng": float(location.longitude)
                if location and location.longitude is not None
                else None,
                "is_discoverable": True,
                "logo_asset_id": profile.logo_asset_id if profile else None,
                "website_status": eligibility.website.status if eligibility.website else None,
                "capability_flags": eligibility.capability_flags or {},
                "indexed_at": datetime.now(timezone.utc),
            }
            if projection is None:
                projection = MarketplaceBusinessProjection(business_id=business_id, **payload)
                session.add(projection)
            else:
                for key, value in payload.items():
                    setattr(projection, key, value)

            offering_count = await MarketplaceIndexingService._upsert_offerings(
                session, business_id=business_id, eligible=True
            )
            health.last_status = "indexed"
            health.last_indexed_at = datetime.now(timezone.utc)
            health.last_reason = None
            health.last_error = None
            health.updated_at = datetime.now(timezone.utc)
            await session.flush()

            await OutboxService.publish(
                session,
                event_type="marketplace.indexed",
                payload={
                    "business_id": str(business_id),
                    "slug": business.slug,
                    "offering_count": offering_count,
                    "trigger": trigger,
                },
                business_id=business_id,
                correlation_id=correlation_id,
            )
            return {
                "status": "indexed",
                "business_id": str(business_id),
                "slug": business.slug,
                "offering_count": offering_count,
            }
        except Exception as exc:  # noqa: BLE001
            health.last_status = "failed"
            health.last_error = str(exc)
            health.updated_at = datetime.now(timezone.utc)
            await session.flush()
            await OutboxService.publish(
                session,
                event_type="marketplace.index_failed",
                payload={
                    "business_id": str(business_id),
                    "error": str(exc),
                    "trigger": trigger,
                },
                business_id=business_id,
                correlation_id=correlation_id,
            )
            if actor_id is not None:
                await AuditService.record(
                    session,
                    event_type="marketplace.index_failed",
                    actor_identity_id=actor_id,
                    actor_context="system",
                    business_id=business_id,
                    resource_type="marketplace_projection",
                    resource_id=business_id,
                    action="index_failed",
                    after_state={"error": str(exc), "trigger": trigger},
                )
            raise

    @staticmethod
    async def reconcile_all(
        session: AsyncSession, *, correlation_id: str, limit: int = 100
    ) -> dict[str, Any]:
        """Periodic reconciliation — catches drift (Doc 11 §17.3 stale-index exit)."""
        from platform_core.models import Business

        businesses = (
            await session.execute(
                select(Business.id)
                .where(Business.deleted_at.is_(None))
                .order_by(Business.updated_at.desc())
                .limit(limit)
            )
        ).all()
        indexed = deindexed = failed = 0
        for (business_id,) in businesses:
            try:
                result = await MarketplaceIndexingService.reindex_business(
                    session,
                    business_id=business_id,
                    correlation_id=correlation_id,
                    trigger="reconciliation",
                )
                if result["status"] == "indexed":
                    indexed += 1
                else:
                    deindexed += 1
            except Exception:  # noqa: BLE001
                failed += 1
        return {"indexed": indexed, "deindexed": deindexed, "failed": failed, "scanned": len(businesses)}

    @staticmethod
    def serialize_health(health: MarketplaceIndexHealth) -> dict[str, Any]:
        return {
            "business_id": str(health.business_id),
            "last_indexed_at": health.last_indexed_at.isoformat()
            if health.last_indexed_at
            else None,
            "last_attempt_at": health.last_attempt_at.isoformat()
            if health.last_attempt_at
            else None,
            "last_status": health.last_status,
            "last_error": health.last_error,
            "last_reason": health.last_reason,
            "discoverability_consented_at": health.discoverability_consented_at.isoformat()
            if health.discoverability_consented_at
            else None,
        }
