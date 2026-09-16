"""Lead lookup resolver (Stage 6)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ResourceNotFound, ResourceStateDenied
from platform_core.models import Lead, LeadNote, LeadStatusHistory
from platform_core.validation.lead import TERMINAL_STATUSES


class LeadResolver:
    @staticmethod
    async def resolve(
        session: AsyncSession, *, business_id: uuid.UUID, lead_id: uuid.UUID
    ) -> Lead:
        result = await session.execute(
            select(Lead).where(
                Lead.id == lead_id,
                Lead.business_id == business_id,
                Lead.deleted_at.is_(None),
            )
        )
        lead = result.scalars().first()
        if lead is None:
            raise ResourceNotFound("Lead")
        return lead

    @staticmethod
    def require_open(lead: Lead, *, action: str = "update") -> None:
        if lead.status == "won":
            raise ResourceStateDenied(
                "lead",
                lead.status,
                action=action,
                allowed_states=sorted(
                    {"new", "contacted", "qualified", "lost"} - TERMINAL_STATUSES
                    | {"lost"}
                ),
            )

    @staticmethod
    async def load_status_history(
        session: AsyncSession, *, lead_id: uuid.UUID
    ) -> list[LeadStatusHistory]:
        result = await session.execute(
            select(LeadStatusHistory)
            .where(LeadStatusHistory.lead_id == lead_id)
            .order_by(LeadStatusHistory.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def load_notes(session: AsyncSession, *, lead_id: uuid.UUID) -> list[LeadNote]:
        result = await session.execute(
            select(LeadNote)
            .where(LeadNote.lead_id == lead_id, LeadNote.deleted_at.is_(None))
            .order_by(LeadNote.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    def serialize_lead(lead: Lead) -> dict[str, Any]:
        return {
            "id": str(lead.id),
            "business_id": str(lead.business_id),
            "display_name": lead.display_name,
            "email": lead.email,
            "phone": lead.phone,
            "message": lead.message,
            "source": lead.source,
            "origin_context": lead.origin_context or {},
            "offering_id": str(lead.offering_id) if lead.offering_id else None,
            "status": lead.status,
            "lost_reason": lead.lost_reason,
            "assignee_identity_id": (
                str(lead.assignee_identity_id) if lead.assignee_identity_id else None
            ),
            "next_follow_up_at": (
                lead.next_follow_up_at.isoformat() if lead.next_follow_up_at else None
            ),
            "customer_contact_id": (
                str(lead.customer_contact_id) if lead.customer_contact_id else None
            ),
            "version": lead.version,
            "created_at": lead.created_at.isoformat(),
            "updated_at": lead.updated_at.isoformat(),
        }

    @staticmethod
    def serialize_status_event(event: LeadStatusHistory) -> dict[str, Any]:
        return {
            "id": str(event.id),
            "from_status": event.from_status,
            "to_status": event.to_status,
            "actor_identity_id": (
                str(event.actor_identity_id) if event.actor_identity_id else None
            ),
            "reason": event.reason,
            "created_at": event.created_at.isoformat(),
        }

    @staticmethod
    def serialize_note(note: LeadNote) -> dict[str, Any]:
        return {
            "id": str(note.id),
            "lead_id": str(note.lead_id),
            "body": note.body,
            "author_identity_id": str(note.author_identity_id),
            "version": note.version,
            "created_at": note.created_at.isoformat(),
            "updated_at": note.updated_at.isoformat(),
        }
