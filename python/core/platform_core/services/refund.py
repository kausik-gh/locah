"""Refund service (Stage 9)."""

from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ValidationError
from platform_core.gates import assert_business_mutable
from platform_core.models import PaymentAttempt, PaymentRefund
from platform_core.payments.cashfree import CashfreePaymentProvider
from platform_core.resolvers.payment_resolver import PaymentResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService
from platform_core.services.payment_attempt import PaymentAttemptService
from platform_core.validation.payment import REFUNDABLE_STATUSES, validate_refund_payload


class RefundService:
    @staticmethod
    async def _apply_cashfree_result(
        session: AsyncSession,
        *,
        refund: PaymentRefund,
        payment: PaymentAttempt,
        result: dict[str, Any],
        correlation_id: str,
    ) -> None:
        refund = (
            await session.execute(
                select(PaymentRefund).where(
                    PaymentRefund.id == refund.id,
                ).with_for_update().execution_options(populate_existing=True)
            )
        ).scalar_one()
        payment = (
            await session.execute(
                select(PaymentAttempt).where(
                    PaymentAttempt.id == payment.id,
                    PaymentAttempt.business_id == refund.business_id,
                ).with_for_update().execution_options(populate_existing=True)
            )
        ).scalar_one()
        status = str(result.get("refund_status") or "").upper()
        if status == "SUCCESS" and refund.status != "succeeded":
            refund.status = "succeeded"
            payment.refunded_amount = float(
                Decimal(str(payment.refunded_amount)) + Decimal(str(refund.amount))
            )
            payment.status = (
                "refunded"
                if Decimal(str(payment.refunded_amount)) >= Decimal(str(payment.amount))
                else "partially_refunded"
            )
            payment.version += 1
            await PaymentAttemptService._sync_source_payment_status(session, payment)
            await OutboxService.publish(
                session,
                event_type="payment.refunded",
                payload={
                    "business_id": str(payment.business_id),
                    "payment_id": str(payment.id),
                    "refund_id": str(refund.id),
                    "amount": float(refund.amount),
                },
                business_id=payment.business_id,
                correlation_id=correlation_id,
            )
        elif status in {"FAILED", "CANCELLED"} and refund.status == "pending":
            refund.status = "failed"
            refund.failure_reason = f"Cashfree refund {status.lower()}"
        refund.version += 1
        await session.flush()

    @staticmethod
    async def refresh_cashfree_refund(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        payment_id: uuid.UUID,
        refund_id: uuid.UUID,
        correlation_id: str,
    ) -> PaymentRefund:
        refund = (
            (
                await session.execute(
                    select(PaymentRefund).where(
                        PaymentRefund.id == refund_id,
                        PaymentRefund.business_id == business_id,
                        PaymentRefund.payment_attempt_id == payment_id,
                    )
                )
            )
            .scalars()
            .first()
        )
        if refund is None or not refund.provider_reference:
            raise ValidationError("Cashfree refund not found")
        payment = await PaymentResolver.resolve_attempt(
            session, business_id=business_id, payment_id=payment_id
        )
        if payment.provider != "cashfree" or not payment.provider_reference:
            raise ValidationError("Not a Cashfree refund")
        result = await CashfreePaymentProvider.from_environment().fetch_refund(
            payment.provider_reference, refund.provider_reference
        )
        if result.get("refund_id") != refund.provider_reference:
            raise ValidationError("Cashfree refund identity mismatch")
        await RefundService._apply_cashfree_result(
            session,
            refund=refund,
            payment=payment,
            result=result,
            correlation_id=correlation_id,
        )
        return refund

    @staticmethod
    def serialize(refund: PaymentRefund) -> dict[str, Any]:
        return cast(dict[str, Any], PaymentResolver.serialize_refund(refund))

    @staticmethod
    async def list_for_payment(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        payment_id: uuid.UUID,
    ) -> list[PaymentRefund]:
        await PaymentResolver.resolve_attempt(
            session, business_id=business_id, payment_id=payment_id
        )
        result = await session.execute(
            select(PaymentRefund)
            .where(
                PaymentRefund.business_id == business_id,
                PaymentRefund.payment_attempt_id == payment_id,
            )
            .order_by(PaymentRefund.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def create_refund(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        payment_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
        expected_version: int | None = None,
    ) -> tuple[PaymentRefund, PaymentAttempt]:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="refund payment")
        payment = await PaymentResolver.resolve_attempt(
            session, business_id=business_id, payment_id=payment_id
        )
        if payment.provider == "cashfree":
            # Serialize competing refund requests before checking the pending
            # balance; two owners cannot both reserve the same refundable sum.
            payment = (
                await session.execute(
                    select(PaymentAttempt).where(
                        PaymentAttempt.id == payment_id,
                        PaymentAttempt.business_id == business_id,
                    ).with_for_update()
                )
            ).scalar_one()
        idem = str(payload.get("idempotency_key") or "").strip() or None
        if idem:
            prior = (
                (
                    await session.execute(
                        select(PaymentRefund).where(
                            PaymentRefund.business_id == business_id,
                            PaymentRefund.payment_attempt_id == payment_id,
                            PaymentRefund.idempotency_key == idem,
                        )
                    )
                )
                .scalars()
                .first()
            )
            if prior:
                return prior, payment
        if expected_version is not None and payment.version != expected_version:
            raise ConflictError(
                "Stale payment version",
                details={
                    "expected_version": expected_version,
                    "current_version": payment.version,
                },
            )
        if payment.status not in REFUNDABLE_STATUSES:
            raise ConflictError(
                "Payment is not refundable",
                details={"status": payment.status},
            )
        max_refundable = Decimal(str(payment.amount)) - Decimal(str(payment.refunded_amount))
        if payment.provider == "cashfree":
            pending_amount = (
                await session.execute(
                    select(func.coalesce(func.sum(PaymentRefund.amount), 0)).where(
                        PaymentRefund.business_id == business_id,
                        PaymentRefund.payment_attempt_id == payment_id,
                        PaymentRefund.status == "pending",
                    )
                )
            ).scalar_one()
            max_refundable -= Decimal(str(pending_amount))
        validated = validate_refund_payload(payload, max_amount=max_refundable)
        if payment.provider == "cashfree":
            if not payment.provider_reference:
                raise ValidationError("Cashfree order reference is missing")
            meta = payment.provider_metadata or {}
            vendor_id = str(meta.get("vendor_id") or "")
            if not vendor_id:
                raise ValidationError("Cashfree split snapshot is missing")
            gross = Decimal(str(payment.amount))
            business_share = Decimal(str(meta.get("business_amount") or "0"))
            vendor_refund = (validated["amount"] * business_share / gross).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if vendor_refund <= 0:
                raise ValidationError("Refund amount is too small for the vendor split")
            refund = PaymentRefund(
                business_id=business_id,
                payment_attempt_id=payment.id,
                amount=float(validated["amount"]),
                status="pending",
                reason=validated["reason"],
                idempotency_key=idem,
            )
            session.add(refund)
            await session.flush()
            refund.provider_reference = f"LR{refund.id.hex}"
            await OutboxService.publish(
                session,
                event_type="payment.refund_requested",
                payload={
                    "business_id": str(business_id),
                    "payment_id": str(payment.id),
                    "refund_id": str(refund.id),
                    "amount": float(refund.amount),
                },
                business_id=business_id,
                correlation_id=correlation_id,
            )
            await AuditService.record(
                session,
                event_type="payment.refund_requested",
                actor_identity_id=actor_id,
                actor_context="business",
                business_id=business_id,
                resource_type="payment_refund",
                resource_id=refund.id,
                action="requested",
                after_state={"refund": RefundService.serialize(refund)},
            )
            # Durable request/ID before provider call, so retry and refresh use
            # the same Cashfree refund_id after an uncertain network result.
            await session.commit()
            result = await CashfreePaymentProvider.from_environment().create_refund(
                order_id=payment.provider_reference,
                refund_id=refund.provider_reference,
                amount=validated["amount"],
                note=validated["reason"],
                vendor_id=vendor_id,
                vendor_amount=vendor_refund,
            )
            if result.get("refund_id") != refund.provider_reference:
                raise ValidationError("Cashfree refund identity mismatch")
            await RefundService._apply_cashfree_result(
                session,
                refund=refund,
                payment=payment,
                result=result,
                correlation_id=correlation_id,
            )
            return refund, payment
        if payment.payment_method == "online":
            raise ValidationError("Legacy online refunds require provider reconciliation")
        before_payment = PaymentAttemptService.serialize(payment)
        refund = PaymentRefund(
            business_id=business_id,
            payment_attempt_id=payment.id,
            amount=float(validated["amount"]),
            status="succeeded",
            reason=validated["reason"],
        )
        session.add(refund)
        payment.refunded_amount = float(Decimal(str(payment.refunded_amount)) + validated["amount"])
        new_refunded = Decimal(str(payment.refunded_amount))
        if new_refunded >= Decimal(str(payment.amount)):
            payment.status = "refunded"
        else:
            payment.status = "partially_refunded"
        payment.version += 1
        await session.flush()
        await PaymentAttemptService._sync_source_payment_status(session, payment)
        after_payment = PaymentAttemptService.serialize(payment)
        refund_payload = {
            "business_id": str(business_id),
            "payment_id": str(payment.id),
            "refund_id": str(refund.id),
            "amount": float(refund.amount),
            "payment_status": payment.status,
        }
        await OutboxService.publish(
            session,
            event_type="payment.refunded",
            payload=refund_payload,
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="payment.refunded",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="payment_refund",
            resource_id=refund.id,
            action="refunded",
            before_state={"payment": before_payment},
            after_state={"payment": after_payment, "refund": RefundService.serialize(refund)},
        )
        return refund, payment
