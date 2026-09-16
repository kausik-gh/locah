"""Lead domain service (Stage 6 — Doc 11 §10.2).

Basic enquiry capture, four-state pipeline, follow-up, and Won handoff to a
Business-scoped CustomerContact. No scoring, nurture automation, or proposal
stage — those are deferred per §10.2.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ResourceNotFound
from platform_core.gates import assert_business_mutable
from platform_core.models import Lead, LeadStatusHistory
from platform_core.resolvers.lead_resolver import LeadResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.customer import CustomerService
from platform_core.services.customer_timeline import CustomerTimelineService
from platform_core.services.outbox import OutboxService
from platform_core.validation.lead import (
    STATUS_EVENT_MAP,
    validate_assign_payload,
    validate_create_payload,
    validate_move_stage_payload,
    validate_patch_payload,
)


class LeadService:
    @staticmethod
    def _check_version(lead: Lead, expected_version: int | None) -> None:
        if expected_version is not None and lead.version != expected_version:
            raise ConflictError(
                "Stale lead version",
                details={
                    "expected_version": expected_version,
                    "current_version": lead.version,
                },
            )

    @staticmethod
    async def _publish(
        session: AsyncSession,
        *,
        event_type: str,
        audit_action: str,
        business_id: uuid.UUID,
        lead: Lead,
        actor_id: uuid.UUID,
        correlation_id: str,
        actor_context: str,
        before_state: dict[str, Any] | None,
        after_state: dict[str, Any],
    ) -> None:
        await OutboxService.publish(
            session,
            event_type=event_type,
            payload={
                "business_id": str(business_id),
                "lead_id": str(lead.id),
                "status": lead.status,
                "after": after_state,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type=event_type,
            actor_identity_id=actor_id,
            actor_context=actor_context,
            business_id=business_id,
            resource_type="lead",
            resource_id=lead.id,
            action=audit_action,
            before_state=before_state,
            after_state=after_state,
        )

    @staticmethod
    async def create_lead(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
        actor_context: str = "business",
    ) -> Lead:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="create lead")
        validated = validate_create_payload(payload)

        lead = Lead(
            business_id=business_id,
            display_name=validated["display_name"],
            email=validated["email"],
            phone=validated["phone"],
            message=validated["message"],
            source=validated["source"],
            origin_context=validated["origin_context"],
            offering_id=validated["offering_id"],
            assignee_identity_id=validated["assignee_identity_id"],
            next_follow_up_at=validated["next_follow_up_at"],
            status="new",
            created_by=actor_id,
        )
        session.add(lead)
        await session.flush()

        session.add(
            LeadStatusHistory(
                business_id=business_id,
                lead_id=lead.id,
                from_status=None,
                to_status="new",
                actor_identity_id=actor_id,
                reason="Lead captured",
            )
        )
        await session.flush()

        after = LeadResolver.serialize_lead(lead)
        await LeadService._publish(
            session,
            event_type="lead.created",
            audit_action="create",
            business_id=business_id,
            lead=lead,
            actor_id=actor_id,
            correlation_id=correlation_id,
            actor_context=actor_context,
            before_state=None,
            after_state=after,
        )
        return lead

    @staticmethod
    async def list_leads(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        status: str | None = None,
        assignee_identity_id: uuid.UUID | None = None,
        limit: int = 100,
    ) -> list[Lead]:
        query = select(Lead).where(
            Lead.business_id == business_id, Lead.deleted_at.is_(None)
        )
        if status:
            query = query.where(Lead.status == status)
        if assignee_identity_id:
            query = query.where(Lead.assignee_identity_id == assignee_identity_id)
        query = query.order_by(Lead.updated_at.desc()).limit(min(max(limit, 1), 200))
        return list((await session.execute(query)).scalars().all())

    @staticmethod
    async def pipeline_counts(
        session: AsyncSession, *, business_id: uuid.UUID
    ) -> dict[str, int]:
        rows = await session.execute(
            select(Lead.status, func.count())
            .where(Lead.business_id == business_id, Lead.deleted_at.is_(None))
            .group_by(Lead.status)
        )
        counts = {"new": 0, "contacted": 0, "qualified": 0, "won": 0, "lost": 0}
        for status_value, count in rows.all():
            counts[status_value] = count
        return counts

    @staticmethod
    async def patch_lead(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        lead_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
        expected_version: int | None = None,
    ) -> Lead:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="update lead")
        lead = await LeadResolver.resolve(session, business_id=business_id, lead_id=lead_id)
        LeadService._check_version(lead, expected_version)
        LeadResolver.require_open(lead, action="update lead")
        validated = validate_patch_payload(payload)
        before = LeadResolver.serialize_lead(lead)
        for field, value in validated.items():
            setattr(lead, field, value)
        lead.version += 1
        await session.flush()
        after = LeadResolver.serialize_lead(lead)
        await LeadService._publish(
            session,
            event_type="lead.updated",
            audit_action="update",
            business_id=business_id,
            lead=lead,
            actor_id=actor_id,
            correlation_id=correlation_id,
            actor_context="business",
            before_state=before,
            after_state=after,
        )
        return lead

    @staticmethod
    async def assign_lead(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        lead_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> Lead:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="assign lead")
        lead = await LeadResolver.resolve(session, business_id=business_id, lead_id=lead_id)
        LeadResolver.require_open(lead, action="assign lead")
        validated = validate_assign_payload(payload)
        before = LeadResolver.serialize_lead(lead)
        lead.assignee_identity_id = validated["assignee_identity_id"]
        lead.version += 1
        await session.flush()
        after = LeadResolver.serialize_lead(lead)
        await LeadService._publish(
            session,
            event_type="lead.assigned",
            audit_action="assign",
            business_id=business_id,
            lead=lead,
            actor_id=actor_id,
            correlation_id=correlation_id,
            actor_context="business",
            before_state=before,
            after_state=after,
        )
        return lead

    @staticmethod
    async def move_stage(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        lead_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
        expected_version: int | None = None,
    ) -> Lead:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="move lead stage")
        lead = await LeadResolver.resolve(session, business_id=business_id, lead_id=lead_id)
        LeadService._check_version(lead, expected_version)
        validated = validate_move_stage_payload(payload, current_status=lead.status)
        target = validated["status"]
        reason = validated["reason"]
        from_status = lead.status
        before = LeadResolver.serialize_lead(lead)

        lead.status = target
        lead.version += 1
        if target == "lost":
            lead.lost_reason = reason
        if target == "won":
            # Doc 11 §10.2: on Won, create or link the Business-scoped
            # CustomerContact; the Lead is retained in interaction history.
            contact = await CustomerService.find_or_create_contact(
                session,
                business_id=business_id,
                correlation_id=correlation_id,
                actor_id=actor_id,
                display_name=lead.display_name,
                email=lead.email,
                phone=lead.phone,
            )
            lead.customer_contact_id = contact.id
        await session.flush()

        session.add(
            LeadStatusHistory(
                business_id=business_id,
                lead_id=lead.id,
                from_status=from_status,
                to_status=target,
                actor_identity_id=actor_id,
                reason=reason,
            )
        )
        await session.flush()

        after = LeadResolver.serialize_lead(lead)
        await LeadService._publish(
            session,
            event_type=STATUS_EVENT_MAP.get(target, "lead.stage_changed"),
            audit_action=target,
            business_id=business_id,
            lead=lead,
            actor_id=actor_id,
            correlation_id=correlation_id,
            actor_context="business",
            before_state=before,
            after_state=after,
        )
        if lead.customer_contact_id:
            await CustomerTimelineService.record_entry(
                session,
                business_id=business_id,
                contact_id=lead.customer_contact_id,
                activity_type=f"lead.{target}",
                resource_type="lead",
                resource_id=lead.id,
                summary={"lead_name": lead.display_name, "status": target},
            )
        return lead

    @staticmethod
    async def add_note(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        lead_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        body: str,
    ) -> Any:
        from platform_core.services.lead_note import LeadNoteService

        return await LeadNoteService.create_note(
            session,
            business_id=business_id,
            lead_id=lead_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            body=body,
        )

    @staticmethod
    async def delete_lead(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        lead_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
    ) -> None:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="delete lead")
        lead = await LeadResolver.resolve(session, business_id=business_id, lead_id=lead_id)
        before = LeadResolver.serialize_lead(lead)
        lead.deleted_at = datetime.now(timezone.utc)
        lead.version += 1
        await session.flush()
        await AuditService.record(
            session,
            event_type="lead.deleted",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="lead",
            resource_id=lead.id,
            action="delete",
            before_state=before,
            after_state={"deleted": True},
        )
        await OutboxService.publish(
            session,
            event_type="lead.deleted",
            payload={"business_id": str(business_id), "lead_id": str(lead.id)},
            business_id=business_id,
            correlation_id=correlation_id,
        )
