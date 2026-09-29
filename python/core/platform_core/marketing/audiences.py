"""Marketing Audience resolution (MK-01; MD §18.2).

Consumes existing customer segments (P1-10E2) and consent store (P1-02).
Shows counts: estimated count, eligible count, consented count, excluded count.
Privacy protection: Marketers cannot export raw phone numbers.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.customers.segments import evaluate
from platform_core.exceptions import ResourceNotFound
from platform_core.models import CustomerSegment
from platform_core.services.consent import ConsentService


class MarketingAudienceService:
    @staticmethod
    async def resolve_segment_audience(
        session: AsyncSession,
        business_id: uuid.UUID,
        segment_id: uuid.UUID,
        *,
        channel: str = "whatsapp",
    ) -> dict[str, Any]:
        """Resolves audience counts from an existing segment with consent checking."""
        seg = (
            await session.execute(
                select(CustomerSegment).where(
                    CustomerSegment.business_id == business_id,
                    CustomerSegment.id == segment_id,
                    CustomerSegment.archived_at.is_(None),
                )
            )
        ).scalars().first()
        if seg is None:
            raise ResourceNotFound("Customer Segment")

        # Evaluate segment rules
        result = await evaluate(session, business_id, seg.rules, limit=0)
        total_count = result["count"]
        consented_count = result["whatsapp_offers"] if channel == "whatsapp" else total_count
        excluded_no_consent = max(0, total_count - consented_count)

        return {
            "segment_id": str(seg.id),
            "segment_name": seg.name,
            "channel": channel,
            "total_count": total_count,
            "consented_count": consented_count,
            "excluded_no_consent_count": excluded_no_consent,
        }

    @staticmethod
    async def get_consented_contacts_for_broadcast(
        session: AsyncSession,
        business_id: uuid.UUID,
        segment_id: uuid.UUID,
        channel: str = "whatsapp",
    ) -> list[dict[str, Any]]:
        """Returns eligible, consented contacts strictly for internal broadcast dispatch.

        Never exposed as raw public export.
        """
        seg = (
            await session.execute(
                select(CustomerSegment).where(
                    CustomerSegment.business_id == business_id,
                    CustomerSegment.id == segment_id,
                    CustomerSegment.archived_at.is_(None),
                )
            )
        ).scalars().first()
        if seg is None:
            raise ResourceNotFound("Customer Segment")

        # Get matching members
        result = await evaluate(session, business_id, seg.rules, limit=10000)
        members = result["members"]

        consented_recipients: list[dict[str, Any]] = []
        for m in members:
            contact_id = uuid.UUID(m["id"])
            has_consent = await ConsentService.has(
                session,
                business_id,
                contact_id,
                purpose="marketing",
                channel=channel,
            )
            if has_consent and m.get("phone"):
                consented_recipients.append(
                    {
                        "contact_id": contact_id,
                        "display_name": m["display_name"],
                        "phone": m["phone"],
                    }
                )

        return consented_recipients
