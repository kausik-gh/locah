"""Consumer activity projection writer (Doc 12 §5.13).

Stage 5 writes projection rows so Stage 7 My Activity UI has data.
Does NOT build My Activity UI (Doc 11 §17.7).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import ConsumerActivityProjection, CustomerContact


class ConsumerActivityService:
    @staticmethod
    async def record(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        identity_id: uuid.UUID | None,
        activity_type: str,
        resource_type: str,
        resource_id: uuid.UUID,
        summary: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> ConsumerActivityProjection | None:
        if identity_id is None:
            return None
        existing = (
            (
                await session.execute(
                    select(ConsumerActivityProjection).where(
                        ConsumerActivityProjection.identity_id == identity_id,
                        ConsumerActivityProjection.resource_type == resource_type,
                        ConsumerActivityProjection.resource_id == resource_id,
                        ConsumerActivityProjection.activity_type == activity_type,
                    )
                )
            )
            .scalars()
            .first()
        )
        if existing is not None:
            existing.summary = summary or {}
            existing.occurred_at = occurred_at or datetime.now(timezone.utc)
            await session.flush()
            return existing
        row = ConsumerActivityProjection(
            identity_id=identity_id,
            business_id=business_id,
            activity_type=activity_type,
            resource_type=resource_type,
            resource_id=resource_id,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            summary=summary or {},
        )
        session.add(row)
        await session.flush()
        return row

    @staticmethod
    async def record_for_customer_contact(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        customer_contact_id: uuid.UUID | None,
        activity_type: str,
        resource_type: str,
        resource_id: uuid.UUID,
        summary: dict[str, Any] | None = None,
    ) -> ConsumerActivityProjection | None:
        if customer_contact_id is None:
            return None
        contact = (
            (
                await session.execute(
                    select(CustomerContact).where(
                        CustomerContact.id == customer_contact_id,
                        CustomerContact.business_id == business_id,
                    )
                )
            )
            .scalars()
            .first()
        )
        if contact is None or contact.identity_id is None:
            return None
        return await ConsumerActivityService.record(
            session,
            business_id=business_id,
            identity_id=contact.identity_id,
            activity_type=activity_type,
            resource_type=resource_type,
            resource_id=resource_id,
            summary=summary,
        )

    @staticmethod
    def serialize(
        row: ConsumerActivityProjection, *, business_name: str | None = None
    ) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "business_id": str(row.business_id),
            "business_name": business_name,
            "activity_type": row.activity_type,
            "resource_type": row.resource_type,
            "resource_id": str(row.resource_id),
            "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
            "summary": row.summary,
        }

    @staticmethod
    async def list_for_identity(
        session: AsyncSession,
        *,
        identity_id: uuid.UUID,
        resource_type: str | None = None,
        business_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """My Activity feed for one consumer (Doc 09 ACC-011, Doc 11 §17.7).

        Scoped strictly to the calling identity. Business display names are
        attached via a narrow SECURITY DEFINER lookup (resolve_activity_
        business_names) so the consumer surface can name who each activity
        was with, without granting any Business-scoped read.

        This deliberately does NOT join businesses in the projection query:
        consumer_activity_projections' own RLS policy lets the caller read
        their own activity rows (identity_id = current_identity_id())
        regardless of whether they hold a Business membership, but a JOIN
        against businesses runs every row through businesses_api_select too
        — which a consumer (no membership) never satisfies — silently
        dropping rows the caller is otherwise fully entitled to see.

        Only Bookings feed this projection today (BookingService and
        BookingLifecycleService are its only writers), and only for a
        CustomerContact carrying an identity_id — a guest booking writes
        nothing, pending FL-DEC-024 guest-to-authenticated linking.
        """
        stmt = select(ConsumerActivityProjection).where(
            ConsumerActivityProjection.identity_id == identity_id
        )
        if resource_type is not None:
            stmt = stmt.where(ConsumerActivityProjection.resource_type == resource_type)
        if business_id is not None:
            stmt = stmt.where(ConsumerActivityProjection.business_id == business_id)
        stmt = stmt.order_by(ConsumerActivityProjection.occurred_at.desc()).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()

        distinct_business_ids = list({row.business_id for row in rows})
        names: dict[uuid.UUID, str] = {}
        if distinct_business_ids:
            resolved = await session.execute(
                text("SELECT id, display_name FROM resolve_activity_business_names(:ids)"),
                {"ids": distinct_business_ids},
            )
            names = {r.id: r.display_name for r in resolved}

        return [
            ConsumerActivityService.serialize(row, business_name=names.get(row.business_id))
            for row in rows
        ]
