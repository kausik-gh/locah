"""Marketplace presence opt-in (Doc 04 / Doc 11 §13.3 — never auto-opt-in)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ValidationError
from platform_core.gates import assert_business_mutable
from platform_core.marketplace.eligibility import evaluate_eligibility, serialize_eligibility
from platform_core.models import MarketplaceIndexHealth
from platform_core.services.audit import AuditService
from platform_core.services.marketplace_indexing import MarketplaceIndexingService
from platform_core.services.outbox import OutboxService


class MarketplacePresenceService:
    @staticmethod
    def _business_service():
        from platform_core.services.business import BusinessService

        return BusinessService

    @staticmethod
    async def get_settings(
        session: AsyncSession, *, business_id: uuid.UUID
    ) -> dict[str, Any]:
        BusinessService = MarketplacePresenceService._business_service()
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            from platform_core.exceptions import ResourceNotFound

            raise ResourceNotFound("Business")
        eligibility = await evaluate_eligibility(session, business_id)
        health = (
            await session.execute(
                select(MarketplaceIndexHealth).where(
                    MarketplaceIndexHealth.business_id == business_id
                )
            )
        ).scalars().first()
        return {
            "visibility": business.visibility,
            "state": business.state,
            "eligibility": serialize_eligibility(eligibility),
            "consent": {
                "consented_at": health.discoverability_consented_at.isoformat()
                if health and health.discoverability_consented_at
                else None,
            },
            "index_health": MarketplaceIndexingService.serialize_health(health)
            if health
            else None,
            "discoverability_means": [
                "Your Business may appear in Marketplace search results",
                "Public profile facts and published Website are used for the listing",
                "Only capability-backed actions are shown to consumers",
                "You can return to unlisted or private at any time",
            ],
        }

    @staticmethod
    async def opt_in_discoverable(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        confirmed: bool,
    ) -> dict[str, Any]:
        if not confirmed:
            raise ValidationError(
                "Explicit confirmation is required to become discoverable",
                details={"field": "confirmed"},
            )
        BusinessService = MarketplacePresenceService._business_service()
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            from platform_core.exceptions import ResourceNotFound

            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="marketplace_opt_in")

        before_visibility = business.visibility
        # Going live on Marketplace activates the Business lifecycle when still draft/onboarding.
        if business.state in {"draft", "onboarding"}:
            business.state = "active"
        business.visibility = "discoverable"
        business.version += 1

        health = await MarketplaceIndexingService._ensure_health(session, business_id)
        health.discoverability_consented_at = datetime.now(timezone.utc)
        health.consented_by = actor_id
        health.updated_at = datetime.now(timezone.utc)
        await session.flush()

        await OutboxService.publish(
            session,
            event_type="business.visibility.changed",
            payload={
                "business_id": str(business_id),
                "before": before_visibility,
                "after": "discoverable",
                "consented": True,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="business.visibility.changed",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="business",
            resource_id=business_id,
            action="opt_in_discoverable",
            before_state={"visibility": before_visibility},
            after_state={"visibility": "discoverable", "state": business.state},
        )

        index_result = await MarketplaceIndexingService.reindex_business(
            session,
            business_id=business_id,
            correlation_id=correlation_id,
            actor_id=actor_id,
            trigger="opt_in",
        )
        settings = await MarketplacePresenceService.get_settings(
            session, business_id=business_id
        )
        settings["index_result"] = index_result
        return settings

    @staticmethod
    async def set_visibility(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        visibility: str,
    ) -> dict[str, Any]:
        if visibility not in {"private", "unlisted", "discoverable"}:
            raise ValidationError("Unsupported visibility")
        if visibility == "discoverable":
            raise ValidationError(
                "Use the discoverability opt-in consent flow to become discoverable",
                details={"use": "POST .../marketplace/opt-in"},
            )
        BusinessService = MarketplacePresenceService._business_service()
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            from platform_core.exceptions import ResourceNotFound

            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="update_visibility")
        before = business.visibility
        if before == visibility:
            return await MarketplacePresenceService.get_settings(
                session, business_id=business_id
            )
        business.visibility = visibility
        business.version += 1
        await session.flush()
        await OutboxService.publish(
            session,
            event_type="business.visibility.changed",
            payload={
                "business_id": str(business_id),
                "before": before,
                "after": visibility,
                "consented": False,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="business.visibility.changed",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="business",
            resource_id=business_id,
            action="visibility_changed",
            before_state={"visibility": before},
            after_state={"visibility": visibility},
        )
        await MarketplaceIndexingService.reindex_business(
            session,
            business_id=business_id,
            correlation_id=correlation_id,
            actor_id=actor_id,
            trigger="visibility_changed",
        )
        return await MarketplacePresenceService.get_settings(
            session, business_id=business_id
        )
