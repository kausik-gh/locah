"""Membership enrolment service (Stage 6 — Doc 11 §9.5).

Enrolment/purchase, validity window, manual lifecycle (activate/pause/resume/
cancel), and expiry reconciliation. Fixed-duration only; automatic renewal is
deferred pending FL-DEC-005.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ResourceNotFound
from platform_core.gates import assert_business_accepts_commerce, assert_business_mutable
from platform_core.models import MembershipEnrolment, MembershipEnrolmentStatusHistory
from platform_core.resolvers.customer_resolver import CustomerResolver
from platform_core.resolvers.membership_resolver import MembershipResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.customer_timeline import CustomerTimelineService
from platform_core.services.outbox import OutboxService
from platform_core.services.payment_attempt import PaymentAttemptService
from platform_core.validation.membership import (
    ENROLMENT_STATUS_EVENT_MAP,
    assert_enrolment_transition_allowed,
    validate_enrolment_create_payload,
    validate_reason,
)


class MembershipEnrolmentService:
    @staticmethod
    def _check_version(enrolment: MembershipEnrolment, expected_version: int | None) -> None:
        if expected_version is not None and enrolment.version != expected_version:
            raise ConflictError(
                "Stale enrolment version",
                details={
                    "expected_version": expected_version,
                    "current_version": enrolment.version,
                },
            )

    @staticmethod
    async def _publish(
        session: AsyncSession,
        *,
        event_type: str,
        audit_action: str,
        business_id: uuid.UUID,
        enrolment: MembershipEnrolment,
        actor_id: uuid.UUID,
        correlation_id: str,
        before_state: dict[str, Any] | None,
        after_state: dict[str, Any],
    ) -> None:
        await OutboxService.publish(
            session,
            event_type=event_type,
            payload={
                "business_id": str(business_id),
                "enrolment_id": str(enrolment.id),
                "plan_id": str(enrolment.plan_id),
                "status": enrolment.status,
                "after": after_state,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type=event_type,
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="membership_enrolment",
            resource_id=enrolment.id,
            action=audit_action,
            before_state=before_state,
            after_state=after_state,
        )

    @staticmethod
    async def _record_transition(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        enrolment: MembershipEnrolment,
        from_status: str,
        to_status: str,
        actor_id: uuid.UUID,
        reason: str | None,
    ) -> None:
        session.add(
            MembershipEnrolmentStatusHistory(
                business_id=business_id,
                enrolment_id=enrolment.id,
                from_status=from_status,
                to_status=to_status,
                actor_identity_id=actor_id,
                reason=reason,
            )
        )
        await session.flush()
        contact = await CustomerResolver.resolve(
            session, business_id=business_id, contact_id=enrolment.customer_contact_id
        )
        await CustomerTimelineService.record_entry(
            session,
            business_id=business_id,
            contact_id=contact.id,
            activity_type=f"membership.{to_status}",
            resource_type="membership_enrolment",
            resource_id=enrolment.id,
            summary={"plan_id": str(enrolment.plan_id), "status": to_status},
        )

    @staticmethod
    async def enrol(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
        actor_context: str = "business",
    ) -> MembershipEnrolment:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="create membership enrolment")
        # Doc 04 §6.1: a suspended Business cannot receive orders. Standing
        # (`status`) is a separate axis from lifecycle (`state`) — both apply.
        assert_business_accepts_commerce(business.status, action="create membership enrolment")
        validated = validate_enrolment_create_payload(payload)

        if validated["idempotency_key"]:
            existing = (
                await session.execute(
                    select(MembershipEnrolment).where(
                        MembershipEnrolment.business_id == business_id,
                        MembershipEnrolment.idempotency_key == validated["idempotency_key"],
                        MembershipEnrolment.deleted_at.is_(None),
                    )
                )
            ).scalars().first()
            if existing:
                return existing

        plan = await MembershipResolver.resolve_plan(
            session, business_id=business_id, plan_id=validated["plan_id"]
        )
        MembershipResolver.require_plan_enrollable(plan)
        contact = await CustomerResolver.resolve(
            session, business_id=business_id, contact_id=validated["customer_contact_id"]
        )

        starts_at = validated["starts_at"] or datetime.now(timezone.utc)
        ends_at = (
            starts_at + timedelta(days=plan.duration_days) if plan.duration_days else None
        )

        enrolment = MembershipEnrolment(
            business_id=business_id,
            plan_id=plan.id,
            customer_contact_id=contact.id,
            identity_id=contact.identity_id,
            starts_at=starts_at,
            ends_at=ends_at,
            status="pending",
            auto_renew=validated["auto_renew"],
            idempotency_key=validated["idempotency_key"],
            created_by=actor_id,
        )
        session.add(enrolment)
        await session.flush()
        await MembershipEnrolmentService._record_transition(
            session,
            business_id=business_id,
            enrolment=enrolment,
            from_status="",
            to_status="pending",
            actor_id=actor_id,
            reason="Enrolment created",
        )

        # Payment linkage (payments module). Free plans (price 0) activate directly.
        if float(plan.price_amount) > 0:
            payment = await PaymentAttemptService.create_attempt(
                session,
                business_id=business_id,
                actor_id=actor_id,
                correlation_id=correlation_id,
                payload={
                    "source_type": "membership",
                    "source_id": str(enrolment.id),
                    "amount": float(plan.price_amount),
                    "currency": plan.currency,
                    "payment_method": validated["payment_method"],
                    "customer_contact_id": str(contact.id),
                    "idempotency_key": (
                        f"enrol-{validated['idempotency_key']}"
                        if validated["idempotency_key"]
                        else None
                    ),
                },
            )
            enrolment.payment_attempt_id = payment.id
            if payment.status == "succeeded":
                await MembershipEnrolmentService._activate(
                    session,
                    business_id=business_id,
                    enrolment=enrolment,
                    actor_id=actor_id,
                    correlation_id=correlation_id,
                    reason="Payment succeeded",
                )
            await session.flush()
        else:
            await MembershipEnrolmentService._activate(
                session,
                business_id=business_id,
                enrolment=enrolment,
                actor_id=actor_id,
                correlation_id=correlation_id,
                reason="Free plan",
            )

        after = MembershipResolver.serialize_enrolment(enrolment)
        await MembershipEnrolmentService._publish(
            session,
            event_type="membership.enrolled",
            audit_action="enrol",
            business_id=business_id,
            enrolment=enrolment,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=None,
            after_state=after,
        )
        return enrolment

    @staticmethod
    async def _activate(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        enrolment: MembershipEnrolment,
        actor_id: uuid.UUID,
        correlation_id: str,
        reason: str,
    ) -> None:
        from_status = enrolment.status
        assert_enrolment_transition_allowed(from_status, "active", action="activate enrolment")
        enrolment.status = "active"
        enrolment.version += 1
        await session.flush()
        await MembershipEnrolmentService._record_transition(
            session,
            business_id=business_id,
            enrolment=enrolment,
            from_status=from_status,
            to_status="active",
            actor_id=actor_id,
            reason=reason,
        )

    @staticmethod
    async def list_enrolments(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        plan_id: uuid.UUID | None = None,
        customer_contact_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[MembershipEnrolment]:
        query = select(MembershipEnrolment).where(
            MembershipEnrolment.business_id == business_id,
            MembershipEnrolment.deleted_at.is_(None),
        )
        if plan_id:
            query = query.where(MembershipEnrolment.plan_id == plan_id)
        if customer_contact_id:
            query = query.where(
                MembershipEnrolment.customer_contact_id == customer_contact_id
            )
        if status:
            query = query.where(MembershipEnrolment.status == status)
        query = query.order_by(MembershipEnrolment.created_at.desc())
        return list((await session.execute(query)).scalars().all())

    @staticmethod
    async def transition(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        enrolment_id: uuid.UUID,
        target_status: str,
        actor_id: uuid.UUID,
        correlation_id: str,
        reason: str | None = None,
        expected_version: int | None = None,
    ) -> MembershipEnrolment:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="update membership enrolment")
        enrolment = await MembershipResolver.resolve_enrolment(
            session, business_id=business_id, enrolment_id=enrolment_id
        )
        MembershipEnrolmentService._check_version(enrolment, expected_version)
        from_status = enrolment.status
        assert_enrolment_transition_allowed(from_status, target_status)
        clean_reason = validate_reason(reason)
        if target_status == "cancelled" and not clean_reason:
            raise ConflictError("A cancellation reason is required")

        before = MembershipResolver.serialize_enrolment(enrolment)
        now = datetime.now(timezone.utc)
        enrolment.status = target_status
        enrolment.version += 1
        if target_status == "paused":
            enrolment.paused_at = now
        elif target_status == "cancelled":
            enrolment.cancelled_at = now
            enrolment.cancellation_reason = clean_reason
        await session.flush()
        await MembershipEnrolmentService._record_transition(
            session,
            business_id=business_id,
            enrolment=enrolment,
            from_status=from_status,
            to_status=target_status,
            actor_id=actor_id,
            reason=clean_reason,
        )
        after = MembershipResolver.serialize_enrolment(enrolment)
        await MembershipEnrolmentService._publish(
            session,
            event_type=ENROLMENT_STATUS_EVENT_MAP.get(
                target_status, "membership.enrolment.updated"
            ),
            audit_action=target_status,
            business_id=business_id,
            enrolment=enrolment,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state=after,
        )
        return enrolment

    @staticmethod
    async def expire_due(
        session: AsyncSession, *, business_id: uuid.UUID, actor_id: uuid.UUID, correlation_id: str
    ) -> int:
        """Reconcile active enrolments past their validity window. Called by the
        scheduler lane (`membership.renewal_reminder` / expiry sweep)."""
        now = datetime.now(timezone.utc)
        rows = (
            await session.execute(
                select(MembershipEnrolment).where(
                    MembershipEnrolment.business_id == business_id,
                    MembershipEnrolment.status == "active",
                    MembershipEnrolment.ends_at.is_not(None),
                    MembershipEnrolment.ends_at < now,
                    MembershipEnrolment.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        for enrolment in rows:
            await MembershipEnrolmentService.transition(
                session,
                business_id=business_id,
                enrolment_id=enrolment.id,
                target_status="expired",
                actor_id=actor_id,
                correlation_id=correlation_id,
                reason="Validity window elapsed",
            )
        return len(rows)
