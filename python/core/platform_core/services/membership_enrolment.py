"""Membership enrolment service (Stage 6 kernel, deepened in P2-02).

Enrolling opens a recurring relationship on the engine
(platform_core.memberships.service): its first period — or a fee plan's
instalments — and the first payment. Status is never set by hand except to
cancel: payment, freezes and time decide it (see MembershipCore.recalculate).
The old pause/resume endpoints now freeze and resume with history.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ResourceNotFound
from platform_core.gates import assert_business_accepts_commerce, assert_business_mutable
from platform_core.memberships.service import MembershipCore
from platform_core.models import MembershipEnrolment, MembershipEnrolmentStatusHistory
from platform_core.resolvers.customer_resolver import CustomerResolver
from platform_core.resolvers.membership_resolver import MembershipResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.customer_timeline import CustomerTimelineService
from platform_core.services.outbox import OutboxService
from platform_core.services.payment_attempt import PaymentAttemptService
from platform_core.validation.membership import (
    validate_enrolment_create_payload,
    validate_reason,
)


class MembershipEnrolmentService:
    @staticmethod
    def _check_version(enrolment: MembershipEnrolment, expected_version: int | None) -> None:
        if expected_version is not None and enrolment.version != expected_version:
            raise ConflictError(
                "Stale enrolment version",
                details={"expected_version": expected_version, "current_version": enrolment.version},
            )

    @staticmethod
    async def _publish(
        session: AsyncSession, *, event_type: str, audit_action: str, business_id: uuid.UUID,
        enrolment: MembershipEnrolment, actor_id: uuid.UUID, correlation_id: str,
        before_state: dict[str, Any] | None, after_state: dict[str, Any],
    ) -> None:
        await OutboxService.publish(
            session, event_type=event_type,
            payload={"business_id": str(business_id), "enrolment_id": str(enrolment.id),
                     "plan_id": str(enrolment.plan_id), "status": enrolment.status,
                     "customer_contact_id": str(enrolment.customer_contact_id), "after": after_state},
            business_id=business_id, correlation_id=correlation_id,
        )
        await AuditService.record(
            session, event_type=event_type, actor_identity_id=actor_id, actor_context="business",
            business_id=business_id, resource_type="membership_enrolment", resource_id=enrolment.id,
            action=audit_action, before_state=before_state, after_state=after_state,
        )

    @staticmethod
    async def enrol(
        session: AsyncSession, *, business_id: uuid.UUID, actor_id: uuid.UUID, correlation_id: str,
        payload: dict[str, Any], actor_context: str = "business",
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
            existing = (await session.execute(select(MembershipEnrolment).where(
                MembershipEnrolment.business_id == business_id,
                MembershipEnrolment.idempotency_key == validated["idempotency_key"],
                MembershipEnrolment.deleted_at.is_(None)))).scalars().first()
            if existing:
                return existing

        plan = await MembershipResolver.resolve_plan(session, business_id=business_id, plan_id=validated["plan_id"])
        MembershipResolver.require_plan_enrollable(plan)
        contact = await CustomerResolver.resolve(session, business_id=business_id,
                                                 contact_id=validated["customer_contact_id"])
        if validated["payer_contact_id"]:
            await CustomerResolver.resolve(session, business_id=business_id,
                                           contact_id=validated["payer_contact_id"])
        if validated["location_id"]:
            from platform_core.resolvers.location_resolver import LocationResolver

            await LocationResolver.resolve(session, business_id=business_id, location_id=validated["location_id"])

        starts_at = validated["starts_at"] or datetime.now(timezone.utc)
        ends_at = starts_at + timedelta(days=plan.duration_days) if plan.duration_days else None
        enrolment = MembershipEnrolment(
            business_id=business_id, plan_id=plan.id, customer_contact_id=contact.id,
            identity_id=contact.identity_id, starts_at=starts_at, ends_at=ends_at, status="pending",
            auto_renew=validated["auto_renew"], idempotency_key=validated["idempotency_key"], created_by=actor_id,
            location_id=validated["location_id"], payer_contact_id=validated["payer_contact_id"],
            source_ref_type=validated["source_ref_type"], source_ref_id=validated["source_ref_id"],
            channel=validated["channel"], responsible_identity_id=actor_id,
        )
        session.add(enrolment)
        await session.flush()
        session.add(MembershipEnrolmentStatusHistory(
            business_id=business_id, enrolment_id=enrolment.id, from_status=None, to_status="pending",
            actor_identity_id=actor_id, reason="Enrolment created"))
        await CustomerTimelineService.record_entry(
            session, business_id=business_id, contact_id=contact.id, activity_type="membership.pending",
            resource_type="membership_enrolment", resource_id=enrolment.id,
            summary={"plan_id": str(plan.id), "status": "pending"})
        await MembershipCore.open(session, enrolment, plan, actor_id=actor_id,
                                  instalments=validated["instalments"], delivery=validated["delivery"])

        due = await MembershipCore.due_now(session, enrolment)
        if due > 0:
            payment = await PaymentAttemptService.create_attempt(
                session, business_id=business_id, actor_id=actor_id, correlation_id=correlation_id,
                payload={
                    "source_type": "membership", "source_id": str(enrolment.id), "amount": float(due),
                    "currency": plan.currency, "payment_method": validated["payment_method"],
                    "customer_contact_id": str(enrolment.payer_contact_id or contact.id),
                    "idempotency_key": f"enrol-{validated['idempotency_key']}" if validated["idempotency_key"] else None,
                },
            )
            enrolment.payment_attempt_id = payment.id
        await MembershipCore.recalculate(session, enrolment, actor_id=actor_id, reason="Enrolled",
                                         correlation_id=correlation_id)
        from platform_core.memberships.sweep import ensure_scheduled

        await ensure_scheduled(session)
        after = MembershipResolver.serialize_enrolment(enrolment)
        await MembershipEnrolmentService._publish(
            session, event_type="membership.enrolled", audit_action="enrol", business_id=business_id,
            enrolment=enrolment, actor_id=actor_id, correlation_id=correlation_id, before_state=None,
            after_state=after,
        )
        return enrolment

    @staticmethod
    async def list_enrolments(
        session: AsyncSession, *, business_id: uuid.UUID, plan_id: uuid.UUID | None = None,
        customer_contact_id: uuid.UUID | None = None, status: str | None = None,
    ) -> list[MembershipEnrolment]:
        query = select(MembershipEnrolment).where(MembershipEnrolment.business_id == business_id,
                                                  MembershipEnrolment.deleted_at.is_(None))
        if plan_id:
            query = query.where(MembershipEnrolment.plan_id == plan_id)
        if customer_contact_id:
            query = query.where(MembershipEnrolment.customer_contact_id == customer_contact_id)
        if status:
            query = query.where(MembershipEnrolment.status == status)
        query = query.order_by(MembershipEnrolment.created_at.desc())
        return list((await session.execute(query)).scalars().all())

    @staticmethod
    async def transition(
        session: AsyncSession, *, business_id: uuid.UUID, enrolment_id: uuid.UUID, target_status: str,
        actor_id: uuid.UUID, correlation_id: str, reason: str | None = None, expected_version: int | None = None,
        days: int | None = None, starts_on: date | None = None,
    ) -> MembershipEnrolment:
        """cancel — the owner ends it; paused — a freeze from today (or
        `starts_on`) for `days`; active — resume a running freeze early."""
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="update membership enrolment")
        enrolment = await MembershipCore.get(session, business_id, enrolment_id, lock=True)
        MembershipEnrolmentService._check_version(enrolment, expected_version)
        clean_reason = validate_reason(reason)
        before = MembershipResolver.serialize_enrolment(enrolment)
        zone = await MembershipCore.tz(session, business_id, enrolment.location_id)
        from zoneinfo import ZoneInfo

        today = datetime.now(timezone.utc).astimezone(ZoneInfo(zone)).date()
        if target_status == "cancelled":
            if enrolment.status in ("cancelled", "completed"):
                raise ConflictError("It has already ended")
            if not clean_reason:
                raise ConflictError("A cancellation reason is required")
            await MembershipEnrolmentService._cancel(session, enrolment, actor_id=actor_id, reason=clean_reason)
        elif target_status == "paused":
            plan = await MembershipCore.plan_of(session, enrolment)
            length = days or plan.max_freeze_days or 7
            await MembershipCore.freeze(session, enrolment, starts_on=starts_on or today, days=length,
                                        reason=clean_reason, actor_id=actor_id)
        elif target_status == "active":
            await MembershipEnrolmentService._resume(session, enrolment, today=today, actor_id=actor_id)
        else:
            raise ConflictError("Only cancel, freeze or resume are done by hand; the rest follows payments and dates")
        after = MembershipResolver.serialize_enrolment(enrolment)
        await AuditService.record(
            session, event_type=f"membership.enrolment.{target_status}", actor_identity_id=actor_id,
            actor_context="business", business_id=business_id, resource_type="membership_enrolment",
            resource_id=enrolment.id, action=target_status, before_state=before, after_state=after)
        return enrolment

    @staticmethod
    async def _cancel(session: AsyncSession, enrolment: MembershipEnrolment, *, actor_id: uuid.UUID,
                      reason: str) -> None:
        from platform_core.memberships.models import MembershipDeliveryOverride

        now = datetime.now(timezone.utc)
        enrolment.cancelled_at, enrolment.cancellation_reason = now, reason
        # Charges not yet paid are no longer owed; paid history stays.
        for p in await MembershipCore.periods(session, enrolment.id):
            if p.payment_state == "unpaid":
                p.payment_state = "cancelled"
        for i in await MembershipCore.instalments(session, enrolment.id):
            if i.status == "due":
                i.status = "cancelled"
        await session.execute(update(MembershipDeliveryOverride).where(
            MembershipDeliveryOverride.enrolment_id == enrolment.id,
            MembershipDeliveryOverride.cancelled_at.is_(None)).values(cancelled_at=now))
        before = enrolment.status
        enrolment.status = "cancelled"
        enrolment.version += 1
        session.add(MembershipEnrolmentStatusHistory(
            business_id=enrolment.business_id, enrolment_id=enrolment.id, from_status=before, to_status="cancelled",
            actor_identity_id=actor_id, reason=reason))
        await session.flush()
        await OutboxService.publish(session, event_type="membership.enrolment.cancelled",
                                    business_id=enrolment.business_id,
                                    payload={"business_id": str(enrolment.business_id),
                                             "enrolment_id": str(enrolment.id), "plan_id": str(enrolment.plan_id),
                                             "status": "cancelled", "from": before, "reason": reason,
                                             "customer_contact_id": str(enrolment.customer_contact_id)})
        await CustomerTimelineService.record_entry(
            session, business_id=enrolment.business_id, contact_id=enrolment.customer_contact_id,
            activity_type="membership.cancelled", resource_type="membership_enrolment", resource_id=enrolment.id,
            summary={"plan_id": str(enrolment.plan_id), "status": "cancelled", "reason": reason})
        await MembershipCore.recalculate(session, enrolment, actor_id=actor_id, reason=reason)

    @staticmethod
    async def _resume(session: AsyncSession, enrolment: MembershipEnrolment, *, today: date,
                      actor_id: uuid.UUID) -> None:
        """End a running freeze today: the days not used come off the cover end again."""
        running = next((f for f in await MembershipCore.freezes(session, enrolment.id)
                        if f.status == "confirmed" and f.starts_on <= today <= f.ends_on), None)
        if running is None:
            raise ConflictError("Nothing is frozen right now")
        new_end = today - timedelta(days=1)
        unused = (running.ends_on - new_end).days
        if new_end < running.starts_on:
            running.status, running.cancelled_at = "cancelled", datetime.now(timezone.utc)
        else:
            running.ends_on, running.days = new_end, (new_end - running.starts_on).days + 1
        if running.extends_cover:
            await MembershipCore._shift(session, enrolment, from_day=today, days=-unused)
        await session.flush()
        await MembershipCore.recalculate(session, enrolment, actor_id=actor_id, reason="Resumed early")

    @staticmethod
    async def expire_due(
        session: AsyncSession, *, business_id: uuid.UUID, actor_id: uuid.UUID, correlation_id: str
    ) -> int:
        """Recalculate every running relationship (the sweep does this hourly)."""
        rows = (await session.execute(select(MembershipEnrolment).where(
            MembershipEnrolment.business_id == business_id, MembershipEnrolment.deleted_at.is_(None),
            MembershipEnrolment.status.in_(("pending", "active", "paused", "grace"))))).scalars().all()
        changed = 0
        for enrolment in rows:
            before = enrolment.status
            st = await MembershipCore.recalculate(session, enrolment, actor_id=actor_id, reason="Validity checked",
                                                  correlation_id=correlation_id)
            changed += st.status != before
        return changed
