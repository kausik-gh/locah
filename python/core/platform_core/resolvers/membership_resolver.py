"""Membership plan / enrolment lookup resolver (Stage 6)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ResourceNotFound, ResourceStateDenied
from platform_core.models import (
    MembershipEnrolment,
    MembershipEnrolmentStatusHistory,
    MembershipPlan,
    MembershipPlanOfferingAccess,
)


class MembershipResolver:
    @staticmethod
    async def resolve_plan(
        session: AsyncSession, *, business_id: uuid.UUID, plan_id: uuid.UUID
    ) -> MembershipPlan:
        result = await session.execute(
            select(MembershipPlan).where(
                MembershipPlan.id == plan_id,
                MembershipPlan.business_id == business_id,
                MembershipPlan.deleted_at.is_(None),
            )
        )
        plan = result.scalars().first()
        if plan is None:
            raise ResourceNotFound("Membership plan")
        return plan

    @staticmethod
    def require_plan_operable(plan: MembershipPlan, *, action: str = "update") -> None:
        if plan.status == "archived":
            raise ResourceStateDenied(
                "membership_plan",
                plan.status,
                action=action,
                allowed_states=["draft", "active"],
            )

    @staticmethod
    def require_plan_enrollable(plan: MembershipPlan) -> None:
        if plan.status != "active":
            raise ResourceStateDenied(
                "membership_plan",
                plan.status,
                action="enrol",
                allowed_states=["active"],
            )

    @staticmethod
    async def resolve_enrolment(
        session: AsyncSession, *, business_id: uuid.UUID, enrolment_id: uuid.UUID
    ) -> MembershipEnrolment:
        result = await session.execute(
            select(MembershipEnrolment).where(
                MembershipEnrolment.id == enrolment_id,
                MembershipEnrolment.business_id == business_id,
                MembershipEnrolment.deleted_at.is_(None),
            )
        )
        enrolment = result.scalars().first()
        if enrolment is None:
            raise ResourceNotFound("Membership enrolment")
        return enrolment

    @staticmethod
    async def load_plan_offering_access(
        session: AsyncSession, *, business_id: uuid.UUID, plan_id: uuid.UUID
    ) -> list[MembershipPlanOfferingAccess]:
        result = await session.execute(
            select(MembershipPlanOfferingAccess).where(
                MembershipPlanOfferingAccess.business_id == business_id,
                MembershipPlanOfferingAccess.plan_id == plan_id,
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def offering_requires_membership(
        session: AsyncSession, *, business_id: uuid.UUID, offering_id: uuid.UUID
    ) -> list[uuid.UUID]:
        """Plan ids that gate booking of `offering_id`. Empty ⇒ no membership gate
        (the Stage 5 capacity-only path is unchanged)."""
        result = await session.execute(
            select(MembershipPlanOfferingAccess.plan_id).where(
                MembershipPlanOfferingAccess.business_id == business_id,
                MembershipPlanOfferingAccess.offering_id == offering_id,
            )
        )
        return [row[0] for row in result.all()]

    @staticmethod
    async def has_active_enrolment(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        customer_contact_id: uuid.UUID,
        plan_ids: list[uuid.UUID],
    ) -> bool:
        if not plan_ids:
            return False
        result = await session.execute(
            select(MembershipEnrolment.id).where(
                MembershipEnrolment.business_id == business_id,
                MembershipEnrolment.customer_contact_id == customer_contact_id,
                MembershipEnrolment.plan_id.in_(plan_ids),
                MembershipEnrolment.status == "active",
                MembershipEnrolment.deleted_at.is_(None),
            )
        )
        return result.scalars().first() is not None

    @staticmethod
    async def load_enrolment_status_history(
        session: AsyncSession, *, enrolment_id: uuid.UUID
    ) -> list[MembershipEnrolmentStatusHistory]:
        result = await session.execute(
            select(MembershipEnrolmentStatusHistory)
            .where(MembershipEnrolmentStatusHistory.enrolment_id == enrolment_id)
            .order_by(MembershipEnrolmentStatusHistory.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    def serialize_plan(
        plan: MembershipPlan, *, offering_access: list[uuid.UUID] | None = None
    ) -> dict[str, Any]:
        return {
            "id": str(plan.id),
            "business_id": str(plan.business_id),
            "name": plan.name,
            "description": plan.description,
            "offering_id": str(plan.offering_id) if plan.offering_id else None,
            "price_amount": float(plan.price_amount),
            "currency": plan.currency,
            "billing_model": plan.billing_model,
            "duration_days": plan.duration_days,
            "status": plan.status,
            "visibility": plan.visibility,
            "offering_access": [str(o) for o in (offering_access or [])],
            # P2-02: the kind and its rules.
            "plan_kind": plan.plan_kind,
            "kind_label": _kind_label(plan.plan_kind),
            "grace_days": plan.grace_days,
            "grace_allows_entry": plan.grace_allows_entry,
            "freeze_allowed": plan.freeze_allowed,
            "max_freeze_days": plan.max_freeze_days,
            "sessions_included": plan.sessions_included,
            "consume_on": plan.consume_on,
            "no_show_consumes": plan.no_show_consumes,
            "delivery": plan.delivery,
            "billing_timing": plan.billing_timing,
            "instalment_template": plan.instalment_template,
            "visits_included": plan.visits_included,
            "visit_every_days": plan.visit_every_days,
            "version": plan.version,
            "created_at": plan.created_at.isoformat(),
            "updated_at": plan.updated_at.isoformat(),
        }

    @staticmethod
    def serialize_enrolment(enrolment: MembershipEnrolment) -> dict[str, Any]:
        return {
            "id": str(enrolment.id),
            "business_id": str(enrolment.business_id),
            "plan_id": str(enrolment.plan_id),
            "customer_contact_id": str(enrolment.customer_contact_id),
            "identity_id": str(enrolment.identity_id) if enrolment.identity_id else None,
            "starts_at": enrolment.starts_at.isoformat(),
            "ends_at": enrolment.ends_at.isoformat() if enrolment.ends_at else None,
            "status": enrolment.status,
            "payment_attempt_id": (
                str(enrolment.payment_attempt_id) if enrolment.payment_attempt_id else None
            ),
            "payment_status": enrolment.payment_status,
            "auto_renew": enrolment.auto_renew,
            "cancellation_reason": enrolment.cancellation_reason,
            "valid_until": enrolment.valid_until.isoformat() if enrolment.valid_until else None,
            "grace_until": enrolment.grace_until.isoformat() if enrolment.grace_until else None,
            "next_due_on": enrolment.next_due_on.isoformat() if enrolment.next_due_on else None,
            "checkin_code": enrolment.checkin_code,
            "location_id": str(enrolment.location_id) if enrolment.location_id else None,
            "payer_contact_id": str(enrolment.payer_contact_id) if enrolment.payer_contact_id else None,
            "source_ref_type": enrolment.source_ref_type,
            "source_ref_id": str(enrolment.source_ref_id) if enrolment.source_ref_id else None,
            "delivery": enrolment.delivery,
            "channel": enrolment.channel,
            "version": enrolment.version,
            "created_at": enrolment.created_at.isoformat(),
            "updated_at": enrolment.updated_at.isoformat(),
        }

    @staticmethod
    def serialize_status_event(event: MembershipEnrolmentStatusHistory) -> dict[str, Any]:
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


def _kind_label(kind: str) -> str:
    from platform_core.memberships.words import words

    return str(words(kind)["kind_label"])
