"""Lead internal notes service (Stage 6)."""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.gates import assert_business_mutable
from platform_core.models import LeadNote
from platform_core.resolvers.lead_resolver import LeadResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService
from platform_core.validation.lead import validate_note_body


class LeadNoteService:
    @staticmethod
    def serialize(note: LeadNote) -> dict[str, Any]:
        return cast(dict[str, Any], LeadResolver.serialize_note(note))

    @staticmethod
    async def list_for_lead(
        session: AsyncSession, *, business_id: uuid.UUID, lead_id: uuid.UUID
    ) -> list[LeadNote]:
        await LeadResolver.resolve(session, business_id=business_id, lead_id=lead_id)
        result = await session.execute(
            select(LeadNote)
            .where(
                LeadNote.business_id == business_id,
                LeadNote.lead_id == lead_id,
                LeadNote.deleted_at.is_(None),
            )
            .order_by(LeadNote.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def create_note(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        lead_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        body: str,
    ) -> LeadNote:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="add lead note")
        await LeadResolver.resolve(session, business_id=business_id, lead_id=lead_id)
        note = LeadNote(
            business_id=business_id,
            lead_id=lead_id,
            body=validate_note_body(body),
            author_identity_id=actor_id,
        )
        session.add(note)
        await session.flush()
        after = LeadNoteService.serialize(note)
        await OutboxService.publish(
            session,
            event_type="lead.note.created",
            payload={
                "business_id": str(business_id),
                "lead_id": str(lead_id),
                "note_id": str(note.id),
                "after": after,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="lead.note.created",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="lead_note",
            resource_id=note.id,
            action="created",
            before_state=None,
            after_state=after,
        )
        return note
