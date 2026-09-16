"""Payment attempt service (Stage 9)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ValidationError
from platform_core.gates import assert_business_accepts_commerce, assert_business_mutable
from platform_core.models import PaymentAttempt
from platform_core.resolvers.booking_resolver import BookingResolver
from platform_core.resolvers.customer_resolver import CustomerResolver
from platform_core.resolvers.order_resolver import OrderResolver
from platform_core.resolvers.payment_resolver import PaymentResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService
from platform_core.validation.payment import assert_transition_allowed, validate_create_payment_payload


class PaymentAttemptService:
    @staticmethod
    def serialize(payment: PaymentAttempt) -> dict[str, Any]:
        return cast(dict[str, Any], PaymentResolver.serialize_attempt(payment))

    @staticmethod
    async def _validate_source(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        source_type: str,
        source_id: uuid.UUID,
        amount: Decimal,
        customer_contact_id: uuid.UUID | None,
    ) -> tuple[str, uuid.UUID | None]:
        if source_type == "order":
            order = await OrderResolver.resolve(
                session, business_id=business_id, order_id=source_id
            )
            if Decimal(str(order.total_amount)) < amount:
                raise ValidationError(
                    "Payment amount exceeds order total",
                    details={"order_total": float(order.total_amount), "amount": float(amount)},
                )
            return order.currency, order.customer_contact_id
        if source_type == "booking":
            booking = await BookingResolver.resolve(
                session, business_id=business_id, booking_id=source_id
            )
            return "INR", booking.customer_contact_id
        if source_type == "membership":
            from platform_core.resolvers.membership_resolver import MembershipResolver

            enrolment = await MembershipResolver.resolve_enrolment(
                session, business_id=business_id, enrolment_id=source_id
            )
            return "INR", enrolment.customer_contact_id
        raise ValidationError("Unsupported payment source")

    @staticmethod
    async def _sync_source_payment_status(
        session: AsyncSession,
        payment: PaymentAttempt,
    ) -> None:
        if payment.source_type == "order":
            order = await OrderResolver.resolve(
                session, business_id=payment.business_id, order_id=payment.source_id
            )
            if payment.status == "succeeded":
                order.payment_status = "paid"
            elif payment.status == "pending_offline":
                order.payment_status = "pending_offline"
            elif payment.status in {"refunded", "partially_refunded"}:
                order.payment_status = "refunded"
            elif payment.status == "failed":
                order.payment_status = "pending"
            order.version += 1
        elif payment.source_type == "booking":
            booking = await BookingResolver.resolve(
                session, business_id=payment.business_id, booking_id=payment.source_id
            )
            if payment.status == "succeeded":
                # Deposit attempts mark deposit_paid; full/remaining mark paid.
                meta = payment.provider_metadata or {}
                if meta.get("purpose") == "deposit" or (
                    booking.deposit_required
                    and float(payment.amount) <= float(booking.deposit_amount or 0)
                    and booking.payment_status != "paid"
                ):
                    booking.payment_status = "deposit_paid"
                else:
                    booking.payment_status = "paid"
            elif payment.status == "pending_offline":
                booking.payment_status = "pending_offline"
            elif payment.status in {"refunded", "partially_refunded"}:
                booking.payment_status = "refunded"
            elif payment.status == "failed":
                booking.payment_status = "pending"
            booking.version += 1
        elif payment.source_type == "membership":
            from platform_core.resolvers.membership_resolver import MembershipResolver

            enrolment = await MembershipResolver.resolve_enrolment(
                session, business_id=payment.business_id, enrolment_id=payment.source_id
            )
            if payment.status == "succeeded":
                enrolment.payment_status = "paid"
            elif payment.status == "pending_offline":
                enrolment.payment_status = "pending_offline"
            elif payment.status in {"refunded", "partially_refunded"}:
                enrolment.payment_status = "refunded"
            elif payment.status == "failed":
                enrolment.payment_status = "pending"
            enrolment.version += 1

    @staticmethod
    async def _publish_status(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        payment: PaymentAttempt,
        actor_id: uuid.UUID | None,
        correlation_id: str,
        event_type: str,
        audit_action: str,
        before_state: dict[str, Any] | None,
        after_state: dict[str, Any],
    ) -> None:
        payload: dict[str, Any] = {
            "business_id": str(business_id),
            "payment_id": str(payment.id),
            "source_type": payment.source_type,
            "source_id": str(payment.source_id),
            "amount": float(payment.amount),
            "status": payment.status,
            "after": after_state,
        }
        await OutboxService.publish(
            session,
            event_type=event_type,
            payload=payload,
            business_id=business_id,
            correlation_id=correlation_id,
        )
        if actor_id is not None:
            await AuditService.record(
                session,
                event_type=event_type,
                actor_identity_id=actor_id,
                actor_context="business",
                business_id=business_id,
                resource_type="payment",
                resource_id=payment.id,
                action=audit_action,
                before_state=before_state,
                after_state=after_state,
            )

    @staticmethod
    async def list_for_business(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        status: str | None = None,
        source_type: str | None = None,
        source_id: uuid.UUID | None = None,
    ) -> list[PaymentAttempt]:
        query = select(PaymentAttempt).where(
            PaymentAttempt.business_id == business_id,
            PaymentAttempt.deleted_at.is_(None),
        )
        if status:
            query = query.where(PaymentAttempt.status == status)
        if source_type:
            query = query.where(PaymentAttempt.source_type == source_type)
        if source_id:
            query = query.where(PaymentAttempt.source_id == source_id)
        query = query.order_by(PaymentAttempt.created_at.desc())
        return list((await session.execute(query)).scalars().all())

    @staticmethod
    async def create_attempt(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> PaymentAttempt:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="create payment")
        # Doc 04 §6.1: a suspended Business cannot receive orders. Standing
        # (`status`) is a separate axis from lifecycle (`state`) — both apply.
        assert_business_accepts_commerce(business.status, action="create payment")
        validated = validate_create_payment_payload(payload)

        if validated["idempotency_key"]:
            existing = await session.execute(
                select(PaymentAttempt).where(
                    PaymentAttempt.business_id == business_id,
                    PaymentAttempt.idempotency_key == validated["idempotency_key"],
                    PaymentAttempt.deleted_at.is_(None),
                )
            )
            found = existing.scalars().first()
            if found:
                return found

        currency, source_customer_id = await PaymentAttemptService._validate_source(
            session,
            business_id=business_id,
            source_type=validated["source_type"],
            source_id=validated["source_id"],
            amount=validated["amount"],
            customer_contact_id=validated["customer_contact_id"],
        )
        customer_id = validated["customer_contact_id"] or source_customer_id
        if customer_id:
            await CustomerResolver.resolve(
                session, business_id=business_id, contact_id=customer_id
            )

        if validated["payment_method"] == "online":
            initial_status = "processing"
        else:
            initial_status = "pending_offline"

        payment = PaymentAttempt(
            business_id=business_id,
            customer_contact_id=customer_id,
            source_type=validated["source_type"],
            source_id=validated["source_id"],
            amount=float(validated["amount"]),
            currency=validated.get("currency") or currency,
            payment_method=validated["payment_method"],
            status=initial_status,
            provider="stub",
            idempotency_key=validated["idempotency_key"],
        )
        session.add(payment)
        await session.flush()
        await PaymentAttemptService._sync_source_payment_status(session, payment)
        after = PaymentAttemptService.serialize(payment)
        await PaymentAttemptService._publish_status(
            session,
            business_id=business_id,
            payment=payment,
            actor_id=actor_id,
            correlation_id=correlation_id,
            event_type="payment.initiated",
            audit_action="initiated",
            before_state=None,
            after_state=after,
        )
        return payment

    @staticmethod
    async def apply_status(
        session: AsyncSession,
        *,
        payment: PaymentAttempt,
        target_status: str,
        correlation_id: str,
        actor_id: uuid.UUID | None = None,
        failure_code: str | None = None,
        failure_reason: str | None = None,
        provider_reference: str | None = None,
    ) -> PaymentAttempt:
        assert_transition_allowed(payment.status, target_status, action="update payment status")
        before = PaymentAttemptService.serialize(payment)
        payment.status = target_status
        if failure_code:
            payment.failure_code = failure_code
        if failure_reason:
            payment.failure_reason = failure_reason
        if provider_reference:
            payment.provider_reference = provider_reference
        payment.version += 1
        await session.flush()
        await PaymentAttemptService._sync_source_payment_status(session, payment)
        after = PaymentAttemptService.serialize(payment)
        event_map = {
            "succeeded": "payment.completed",
            "failed": "payment.failed",
            "pending_offline": "payment.initiated",
        }
        event_type = event_map.get(target_status, "payment.updated")
        await PaymentAttemptService._publish_status(
            session,
            business_id=payment.business_id,
            payment=payment,
            actor_id=actor_id,
            correlation_id=correlation_id,
            event_type=event_type,
            audit_action=target_status,
            before_state=before,
            after_state=after,
        )
        return payment

    @staticmethod
    async def record_offline_settlement(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        payment_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        expected_version: int | None = None,
    ) -> PaymentAttempt:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="record payment settlement")
        payment = await PaymentResolver.resolve_attempt(
            session, business_id=business_id, payment_id=payment_id
        )
        if expected_version is not None and payment.version != expected_version:
            raise ConflictError(
                "Stale payment version",
                details={
                    "expected_version": expected_version,
                    "current_version": payment.version,
                },
            )
        if payment.status != "pending_offline":
            raise ValidationError(
                "Only offline payments awaiting settlement can be recorded",
                details={"status": payment.status},
            )
        return await PaymentAttemptService.apply_status(
            session,
            payment=payment,
            target_status="succeeded",
            correlation_id=correlation_id,
            actor_id=actor_id,
        )

    @staticmethod
    async def export_payments(
        session: AsyncSession,
        business_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        payments = await PaymentAttemptService.list_for_business(session, business_id)
        return [PaymentAttemptService.serialize(p) for p in payments]
