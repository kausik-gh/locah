"""Customer timeline projection service (Stage 4 foundation)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import CustomerTimelineEntry
from platform_core.resolvers.customer_resolver import CustomerResolver


class CustomerTimelineService:
    @staticmethod
    async def list_for_contact(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        contact_id: uuid.UUID,
        limit: int = 50,
    ) -> list[CustomerTimelineEntry]:
        await CustomerResolver.resolve(
            session, business_id=business_id, contact_id=contact_id
        )
        capped = min(max(limit, 1), 100)
        result = await session.execute(
            select(CustomerTimelineEntry)
            .where(
                CustomerTimelineEntry.business_id == business_id,
                CustomerTimelineEntry.contact_id == contact_id,
            )
            .order_by(CustomerTimelineEntry.occurred_at.desc())
            .limit(capped)
        )
        return list(result.scalars().all())

    @staticmethod
    async def record_entry(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        contact_id: uuid.UUID,
        activity_type: str,
        summary: dict[str, Any],
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        occurred_at: datetime | None = None,
        source_event_id: uuid.UUID | None = None,
    ) -> CustomerTimelineEntry:
        if source_event_id is not None:
            existing = await session.execute(
                select(CustomerTimelineEntry).where(
                    CustomerTimelineEntry.business_id == business_id,
                    CustomerTimelineEntry.source_event_id == source_event_id,
                )
            )
            found = existing.scalars().first()
            if found is not None:
                return found

        entry = CustomerTimelineEntry(
            business_id=business_id,
            contact_id=contact_id,
            activity_type=activity_type,
            resource_type=resource_type,
            resource_id=resource_id,
            location_id=location_id,
            summary=summary,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            source_event_id=source_event_id,
        )
        session.add(entry)
        await session.flush()
        return entry
