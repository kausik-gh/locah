"""Order internal notes service (Stage 6)."""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.gates import assert_business_mutable
from platform_core.models import OrderNote
from platform_core.resolvers.order_resolver import OrderResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService
from platform_core.validation.order import validate_note_body


class OrderNoteService:
    @staticmethod
    def serialize(note: OrderNote) -> dict[str, Any]:
        return cast(dict[str, Any], OrderResolver.serialize_note(note))

    @staticmethod
    async def list_for_order(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        order_id: uuid.UUID,
    ) -> list[OrderNote]:
        await OrderResolver.resolve(session, business_id=business_id, order_id=order_id)
        result = await session.execute(
            select(OrderNote)
            .where(
                OrderNote.business_id == business_id,
                OrderNote.order_id == order_id,
                OrderNote.deleted_at.is_(None),
            )
            .order_by(OrderNote.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def create_note(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        order_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        body: str,
    ) -> OrderNote:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="add order note")
        await OrderResolver.resolve(session, business_id=business_id, order_id=order_id)
        normalized = validate_note_body(body)
        note = OrderNote(
            business_id=business_id,
            order_id=order_id,
            body=normalized,
            author_identity_id=actor_id,
        )
        session.add(note)
        await session.flush()
        after = OrderNoteService.serialize(note)
        await OutboxService.publish(
            session,
            event_type="order.note.created",
            payload={
                "business_id": str(business_id),
                "order_id": str(order_id),
                "note_id": str(note.id),
                "after": after,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="order.note.created",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="order_note",
            resource_id=note.id,
            action="created",
            before_state=None,
            after_state=after,
        )
        return note
