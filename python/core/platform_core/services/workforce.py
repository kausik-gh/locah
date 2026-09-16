"""Workforce module — operational providers (Doc 10 §4.8, Doc 11 §10.5).

identity_id linkage is optional and NEVER grants Workspace access.
"""

from __future__ import annotations

import uuid
from datetime import datetime, time, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ModuleNotActive, ResourceNotFound, ValidationError
from platform_core.gates import assert_business_mutable
from platform_core.models import (
    BusinessModuleState,
    Offering,
    WorkforceAvailability,
    WorkforceLocationAssignment,
    WorkforceMember,
    WorkforceServiceAssociation,
)
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService

ACTIVE_MODULE_STATES = frozenset({"enabled", "ready", "active"})


class WorkforceService:
    @staticmethod
    async def assert_module_active(session: AsyncSession, business_id: uuid.UUID) -> None:
        state = (
            await session.execute(
                select(BusinessModuleState).where(
                    BusinessModuleState.business_id == business_id,
                    BusinessModuleState.module_id == "workforce",
                )
            )
        ).scalars().first()
        if state is None or state.activation_state not in ACTIVE_MODULE_STATES:
            raise ModuleNotActive("workforce")

    @staticmethod
    def serialize_member(member: WorkforceMember) -> dict[str, Any]:
        return {
            "id": str(member.id),
            "business_id": str(member.business_id),
            "display_name": member.display_name,
            "email": member.email,
            "phone": member.phone,
            "designation": member.designation,
            "identity_id": str(member.identity_id) if member.identity_id else None,
            "status": member.status,
            "notes": member.notes,
            "version": member.version,
            # Explicit: linkage is not a membership grant
            "grants_workspace_access": False,
        }

    @staticmethod
    async def list_members(
        session: AsyncSession, business_id: uuid.UUID, *, status: str | None = None
    ) -> list[WorkforceMember]:
        query = select(WorkforceMember).where(
            WorkforceMember.business_id == business_id,
            WorkforceMember.deleted_at.is_(None),
        )
        if status:
            query = query.where(WorkforceMember.status == status)
        query = query.order_by(WorkforceMember.display_name.asc())
        return list((await session.execute(query)).scalars().all())

    @staticmethod
    async def get_member(
        session: AsyncSession, *, business_id: uuid.UUID, member_id: uuid.UUID
    ) -> WorkforceMember:
        member = (
            await session.execute(
                select(WorkforceMember).where(
                    WorkforceMember.business_id == business_id,
                    WorkforceMember.id == member_id,
                    WorkforceMember.deleted_at.is_(None),
                )
            )
        ).scalars().first()
        if member is None:
            raise ResourceNotFound("WorkforceMember")
        return member

    @staticmethod
    async def create_member(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> WorkforceMember:
        await WorkforceService.assert_module_active(session, business_id)
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="create_workforce_member")
        name = str(payload.get("display_name") or "").strip()
        if not name:
            raise ValidationError("display_name is required")
        identity_id = payload.get("identity_id")
        member = WorkforceMember(
            business_id=business_id,
            display_name=name,
            email=(str(payload["email"]).strip() if payload.get("email") else None),
            phone=(str(payload["phone"]).strip() if payload.get("phone") else None),
            designation=(str(payload["designation"]).strip() if payload.get("designation") else None),
            identity_id=uuid.UUID(str(identity_id)) if identity_id else None,
            status=str(payload.get("status") or "active"),
            notes=payload.get("notes"),
        )
        session.add(member)
        await session.flush()
        after = WorkforceService.serialize_member(member)
        await AuditService.record(
            session,
            event_type="workforce.member_created",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="workforce_member",
            resource_id=member.id,
            action="created",
            after_state=after,
        )
        await OutboxService.publish(
            session,
            event_type="workforce.member_created",
            payload={"business_id": str(business_id), "member": after},
            business_id=business_id,
            correlation_id=correlation_id,
        )
        return member

    @staticmethod
    async def update_member(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        member_id: uuid.UUID,
        actor_id: uuid.UUID,
        payload: dict[str, Any],
    ) -> WorkforceMember:
        await WorkforceService.assert_module_active(session, business_id)
        member = await WorkforceService.get_member(
            session, business_id=business_id, member_id=member_id
        )
        before = WorkforceService.serialize_member(member)
        for key in ("display_name", "email", "phone", "designation", "notes", "status"):
            if key in payload and payload[key] is not None:
                setattr(member, key, payload[key])
        if "identity_id" in payload:
            raw = payload["identity_id"]
            member.identity_id = uuid.UUID(str(raw)) if raw else None
        member.version += 1
        member.updated_at = datetime.now(timezone.utc)
        await session.flush()
        after = WorkforceService.serialize_member(member)
        await AuditService.record(
            session,
            event_type="workforce.member_updated",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="workforce_member",
            resource_id=member.id,
            action="updated",
            before_state=before,
            after_state=after,
        )
        return member

    @staticmethod
    async def deactivate_member(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        member_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> WorkforceMember:
        return await WorkforceService.update_member(
            session,
            business_id=business_id,
            member_id=member_id,
            actor_id=actor_id,
            payload={"status": "inactive"},
        )

    @staticmethod
    async def assign_location(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        member_id: uuid.UUID,
        location_id: uuid.UUID,
        actor_id: uuid.UUID,
        is_primary: bool = False,
    ) -> WorkforceLocationAssignment:
        await WorkforceService.get_member(session, business_id=business_id, member_id=member_id)
        existing = (
            await session.execute(
                select(WorkforceLocationAssignment).where(
                    WorkforceLocationAssignment.member_id == member_id,
                    WorkforceLocationAssignment.location_id == location_id,
                )
            )
        ).scalars().first()
        if existing:
            return existing
        row = WorkforceLocationAssignment(
            business_id=business_id,
            member_id=member_id,
            location_id=location_id,
            is_primary=is_primary,
            assigned_by=actor_id,
        )
        session.add(row)
        await session.flush()
        await AuditService.record(
            session,
            event_type="workforce.location_assigned",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="workforce_member",
            resource_id=member_id,
            action="location_assigned",
            after_state={"location_id": str(location_id), "is_primary": is_primary},
        )
        return row

    @staticmethod
    async def unassign_location(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        member_id: uuid.UUID,
        location_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        row = (
            await session.execute(
                select(WorkforceLocationAssignment).where(
                    WorkforceLocationAssignment.business_id == business_id,
                    WorkforceLocationAssignment.member_id == member_id,
                    WorkforceLocationAssignment.location_id == location_id,
                )
            )
        ).scalars().first()
        if row is None:
            raise ResourceNotFound("WorkforceLocationAssignment")
        await session.delete(row)
        await session.flush()
        await AuditService.record(
            session,
            event_type="workforce.location_unassigned",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="workforce_member",
            resource_id=member_id,
            action="location_unassigned",
            after_state={"location_id": str(location_id)},
        )

    @staticmethod
    async def list_locations(
        session: AsyncSession, *, business_id: uuid.UUID, member_id: uuid.UUID
    ) -> list[WorkforceLocationAssignment]:
        return list(
            (
                await session.execute(
                    select(WorkforceLocationAssignment).where(
                        WorkforceLocationAssignment.business_id == business_id,
                        WorkforceLocationAssignment.member_id == member_id,
                    )
                )
            ).scalars().all()
        )

    @staticmethod
    async def associate_service(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        member_id: uuid.UUID,
        offering_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> WorkforceServiceAssociation:
        await WorkforceService.get_member(session, business_id=business_id, member_id=member_id)
        offering = (
            await session.execute(
                select(Offering).where(
                    Offering.id == offering_id,
                    Offering.business_id == business_id,
                    Offering.deleted_at.is_(None),
                )
            )
        ).scalars().first()
        if offering is None:
            raise ResourceNotFound("Offering")
        existing = (
            await session.execute(
                select(WorkforceServiceAssociation).where(
                    WorkforceServiceAssociation.member_id == member_id,
                    WorkforceServiceAssociation.offering_id == offering_id,
                )
            )
        ).scalars().first()
        if existing:
            return existing
        row = WorkforceServiceAssociation(
            business_id=business_id,
            member_id=member_id,
            offering_id=offering_id,
            created_by=actor_id,
        )
        session.add(row)
        await session.flush()
        await AuditService.record(
            session,
            event_type="workforce.service_associated",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="workforce_member",
            resource_id=member_id,
            action="service_associated",
            after_state={"offering_id": str(offering_id)},
        )
        return row

    @staticmethod
    async def list_services(
        session: AsyncSession, *, business_id: uuid.UUID, member_id: uuid.UUID
    ) -> list[WorkforceServiceAssociation]:
        return list(
            (
                await session.execute(
                    select(WorkforceServiceAssociation).where(
                        WorkforceServiceAssociation.business_id == business_id,
                        WorkforceServiceAssociation.member_id == member_id,
                    )
                )
            ).scalars().all()
        )

    @staticmethod
    async def set_availability(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        member_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> WorkforceAvailability:
        await WorkforceService.get_member(session, business_id=business_id, member_id=member_id)
        start = payload.get("start_time")
        end = payload.get("end_time")
        if isinstance(start, str):
            parts = [int(p) for p in start.split(":")[:2]]
            start = time(parts[0], parts[1])
        if isinstance(end, str):
            parts = [int(p) for p in end.split(":")[:2]]
            end = time(parts[0], parts[1])
        row = WorkforceAvailability(
            business_id=business_id,
            member_id=member_id,
            location_id=payload.get("location_id"),
            weekday=payload.get("weekday"),
            exception_date=payload.get("exception_date"),
            start_time=start,
            end_time=end,
            is_available=bool(payload.get("is_available", True)),
        )
        session.add(row)
        await session.flush()
        await OutboxService.publish(
            session,
            event_type="workforce.availability_updated",
            payload={
                "business_id": str(business_id),
                "member_id": str(member_id),
                "availability_id": str(row.id),
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="workforce.availability_updated",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="workforce_member",
            resource_id=member_id,
            action="availability_updated",
            after_state={"availability_id": str(row.id)},
        )
        return row

    @staticmethod
    async def list_availability(
        session: AsyncSession, *, business_id: uuid.UUID, member_id: uuid.UUID
    ) -> list[WorkforceAvailability]:
        return list(
            (
                await session.execute(
                    select(WorkforceAvailability).where(
                        WorkforceAvailability.business_id == business_id,
                        WorkforceAvailability.member_id == member_id,
                    )
                )
            ).scalars().all()
        )

    @staticmethod
    async def assert_provider_eligible(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        provider_id: uuid.UUID,
        location_id: uuid.UUID,
        offering_id: uuid.UUID | None,
    ) -> WorkforceMember:
        member = await WorkforceService.get_member(
            session, business_id=business_id, member_id=provider_id
        )
        if member.status != "active":
            raise ValidationError(
                "Provider is not active",
                details={"provider_id": str(provider_id)},
            )
        assignment = (
            await session.execute(
                select(WorkforceLocationAssignment.id).where(
                    WorkforceLocationAssignment.business_id == business_id,
                    WorkforceLocationAssignment.member_id == provider_id,
                    WorkforceLocationAssignment.location_id == location_id,
                )
            )
        ).scalars().first()
        if assignment is None:
            raise ValidationError(
                "Provider is not assigned to this location",
                details={"provider_id": str(provider_id), "location_id": str(location_id)},
            )
        if offering_id is not None:
            assoc = (
                await session.execute(
                    select(WorkforceServiceAssociation.id).where(
                        WorkforceServiceAssociation.business_id == business_id,
                        WorkforceServiceAssociation.member_id == provider_id,
                        WorkforceServiceAssociation.offering_id == offering_id,
                    )
                )
            ).scalars().first()
            if assoc is None:
                raise ValidationError(
                    "Provider is not associated with this service",
                    details={"provider_id": str(provider_id), "offering_id": str(offering_id)},
                )
        return member
