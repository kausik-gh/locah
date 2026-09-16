"""Customer notes service (Stage 4)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ResourceNotFound
from platform_core.gates import assert_business_mutable
from platform_core.models import CustomerNote
from platform_core.resolvers.customer_resolver import CustomerResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService
from platform_core.validation.customer import validate_note_body


class CustomerNoteService:
    @staticmethod
    async def list_for_contact(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        contact_id: uuid.UUID,
    ) -> list[CustomerNote]:
        await CustomerResolver.resolve(
            session, business_id=business_id, contact_id=contact_id
        )
        result = await session.execute(
            select(CustomerNote).where(
                CustomerNote.business_id == business_id,
                CustomerNote.contact_id == contact_id,
                CustomerNote.deleted_at.is_(None),
            )
            .order_by(CustomerNote.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def create_note(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        contact_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        body: str,
    ) -> CustomerNote:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="create_customer_note")

        contact = await CustomerResolver.resolve_operable(
            session, business_id=business_id, contact_id=contact_id, action="add_note"
        )
        validated_body = validate_note_body(body)

        note = CustomerNote(
            business_id=business_id,
            contact_id=contact.id,
            body=validated_body,
            author_identity_id=actor_id,
        )
        session.add(note)
        await session.flush()

        after = CustomerResolver.serialize_note(note)
        await OutboxService.publish(
            session,
            event_type="customer.note.created",
            payload={
                "business_id": str(business_id),
                "customer_id": str(contact.id),
                "note_id": str(note.id),
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="customer.note.created",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="customer_note",
            resource_id=note.id,
            action="create",
            after_state=after,
        )
        return note
