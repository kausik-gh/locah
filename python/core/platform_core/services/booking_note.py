"""Booking internal notes service (Stage 7)."""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.gates import assert_business_mutable
from platform_core.models import BookingNote
from platform_core.resolvers.booking_resolver import BookingResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService
from platform_core.validation.booking import validate_note_body


class BookingNoteService:
    @staticmethod
    def serialize(note: BookingNote) -> dict[str, Any]:
        return cast(dict[str, Any], BookingResolver.serialize_note(note))

    @staticmethod
    async def list_for_booking(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        booking_id: uuid.UUID,
    ) -> list[BookingNote]:
        await BookingResolver.resolve(session, business_id=business_id, booking_id=booking_id)
        result = await session.execute(
            select(BookingNote)
            .where(
                BookingNote.business_id == business_id,
                BookingNote.booking_id == booking_id,
                BookingNote.deleted_at.is_(None),
            )
            .order_by(BookingNote.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def create_note(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        booking_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        body: str,
    ) -> BookingNote:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="add booking note")
        await BookingResolver.resolve(session, business_id=business_id, booking_id=booking_id)
        normalized = validate_note_body(body)
        note = BookingNote(
            business_id=business_id,
            booking_id=booking_id,
            body=normalized,
            author_identity_id=actor_id,
        )
        session.add(note)
        await session.flush()
        after = BookingNoteService.serialize(note)
        await OutboxService.publish(
            session,
            event_type="booking.note.created",
            payload={
                "business_id": str(business_id),
                "booking_id": str(booking_id),
                "note_id": str(note.id),
                "after": after,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="booking.note.created",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="booking_note",
            resource_id=note.id,
            action="created",
            before_state=None,
            after_state=after,
        )
        return note
