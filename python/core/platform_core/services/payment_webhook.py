"""Payment webhook service (Stage 9)."""

from __future__ import annotations

import uuid
import hashlib
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ValidationError
from platform_core.logging import get_logger
from platform_core.models import PaymentAttempt, PaymentRefund, PaymentWebhookReceipt
from platform_core.payments.cashfree import CashfreePaymentProvider
from platform_core.payments.provider_adapter import (
    extract_event_id,
    normalize_payment_event,
    parse_webhook_payload,
    verify_webhook_signature,
)
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService
from platform_core.services.payment_attempt import PaymentAttemptService

logger = get_logger("platform_core.payment_webhook")


class PaymentWebhookService:
    @staticmethod
    async def verify_cashfree_order(
        session: AsyncSession,
        *,
        payment: PaymentAttempt,
        correlation_id: str,
    ) -> PaymentAttempt:
        if payment.provider != "cashfree" or not payment.provider_reference:
            raise ValidationError("Not a Cashfree payment")
        provider = CashfreePaymentProvider.from_environment()
        order = await provider.fetch_order(payment.provider_reference)
        successful_payment: dict[str, Any] | None = None
        if order.get("order_status") == "PAID":
            attempts = await provider.fetch_payments(payment.provider_reference)
            successful_payment = next(
                (
                    attempt for attempt in attempts
                    if attempt.get("payment_status") == "SUCCESS"
                    and Decimal(str(attempt.get("payment_amount"))) == Decimal(str(payment.amount))
                ), None,
            )
        payment = (
            await session.execute(
                select(PaymentAttempt).where(
                    PaymentAttempt.id == payment.id,
                    PaymentAttempt.provider == "cashfree",
                ).with_for_update().execution_options(populate_existing=True)
            )
        ).scalar_one()
        if (
            order.get("order_id") != payment.provider_reference
            or str(order.get("order_currency")) != payment.currency
            or Decimal(str(order.get("order_amount"))) != Decimal(str(payment.amount))
        ):
            raise ValidationError("Cashfree order does not match the payment")
        if order.get("order_status") == "PAID" and successful_payment is None:
            raise ValidationError("Cashfree paid order has no matching successful payment")
        if order.get("order_status") == "PAID" and payment.status == "processing":
            assert successful_payment is not None
            metadata = dict(payment.provider_metadata or {})
            metadata["cf_payment_id"] = str(successful_payment.get("cf_payment_id"))
            payment.provider_metadata = metadata
            business = await BusinessService.get_by_id(session, payment.business_id)
            await PaymentAttemptService.apply_status(
                session,
                payment=payment,
                target_status="succeeded",
                correlation_id=correlation_id,
                actor_id=business.primary_owner_identity_id,
            )
        return payment

    @staticmethod
    async def _process_cashfree(
        session: AsyncSession,
        *,
        raw_body: bytes,
        headers: dict[str, str],
        correlation_id: str,
    ) -> dict[str, Any]:
        provider = CashfreePaymentProvider.from_environment()
        if not provider.verify_webhook(
            timestamp=headers.get("x-webhook-timestamp", ""),
            raw_body=raw_body,
            signature=headers.get("x-webhook-signature", ""),
        ):
            raise ValidationError("Invalid Cashfree webhook signature")
        payload = parse_webhook_payload(raw_body)
        event_id = headers.get("x-idempotency-key") or hashlib.sha256(raw_body).hexdigest()
        receipt = (
            (
                await session.execute(
                    select(PaymentWebhookReceipt).where(
                        PaymentWebhookReceipt.provider == "cashfree",
                        PaymentWebhookReceipt.provider_event_id == event_id,
                    )
                )
            )
            .scalars()
            .first()
        )
        if receipt is not None:
            return {"status": "duplicate" if receipt.status == "processed" else "received",
                    "event_id": event_id}
        receipt = PaymentWebhookReceipt(
            provider="cashfree", provider_event_id=event_id,
            raw_payload=payload, status="received",
        )
        session.add(receipt)
        await session.flush()
        # Durable receipt and worker delivery in one transaction. The HTTP
        # handler acknowledges only after its commit; no provider call here.
        await OutboxService.publish(
            session, event_type="payment.webhook_received",
            payload={"receipt_id": str(receipt.id)},
            correlation_id=correlation_id, skip_notifications=True,
        )
        return {"status": "received", "event_id": event_id}

    @staticmethod
    async def process_cashfree_receipt(
        session: AsyncSession, *, receipt_id: uuid.UUID, correlation_id: str,
    ) -> None:
        receipt = (
            await session.execute(
                select(PaymentWebhookReceipt).where(
                    PaymentWebhookReceipt.id == receipt_id,
                    PaymentWebhookReceipt.provider == "cashfree",
                ).with_for_update()
            )
        ).scalars().first()
        if receipt is None:
            raise ValidationError("Cashfree webhook receipt not found")
        if receipt.status == "processed":
            return
        payload = receipt.raw_payload
        event_type = str(payload.get("type") or "")
        order_id = str(((payload.get("data") or {}).get("order") or {}).get("order_id") or "")
        if event_type == "REFUND_STATUS_WEBHOOK":
            from platform_core.services.refund import RefundService

            refund_reference = str(
                ((payload.get("data") or {}).get("refund") or {}).get("refund_id") or ""
            )
            refund = (
                (
                    await session.execute(
                        select(PaymentRefund).where(
                            PaymentRefund.provider_reference == refund_reference
                        )
                    )
                )
                .scalars()
                .first()
            )
            if refund is None:
                raise ValidationError("Cashfree refund not found")
            receipt.payment_attempt_id = refund.payment_attempt_id
            await RefundService.refresh_cashfree_refund(
                session,
                business_id=refund.business_id,
                payment_id=refund.payment_attempt_id,
                refund_id=refund.id,
                correlation_id=correlation_id,
            )
            receipt.status = "processed"
            receipt.processed_at = datetime.now(timezone.utc)
            return
        if event_type not in {
            "PAYMENT_SUCCESS_WEBHOOK",
            "PAYMENT_FAILED_WEBHOOK",
            "PAYMENT_USER_DROPPED_WEBHOOK",
        }:
            receipt.status = "processed"
            receipt.processed_at = datetime.now(timezone.utc)
            return
        payment = (
            (
                await session.execute(
                    select(PaymentAttempt).where(
                        PaymentAttempt.provider == "cashfree",
                        PaymentAttempt.provider_reference == order_id,
                        PaymentAttempt.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .first()
        )
        if payment is None:
            raise ValidationError("Cashfree payment not found")
        receipt.payment_attempt_id = payment.id
        # A failed attempt or dropped checkout does not prove an order will
        # never be paid. Only Cashfree's authoritative PAID state grants value.
        await PaymentWebhookService.verify_cashfree_order(
            session,
            payment=payment,
            correlation_id=correlation_id,
        )
        receipt.status = "processed"
        receipt.processed_at = datetime.now(timezone.utc)

    @staticmethod
    async def process_webhook(
        session: AsyncSession,
        *,
        provider: str,
        raw_body: bytes,
        headers: dict[str, str],
        correlation_id: str,
    ) -> dict[str, Any]:
        if provider == "cashfree":
            return await PaymentWebhookService._process_cashfree(
                session,
                raw_body=raw_body,
                headers=headers,
                correlation_id=correlation_id,
            )
        if not verify_webhook_signature(provider, raw_body, headers):
            # AUD-11: signature rejections are a security event. The redaction
            # processor scrubs any signature/secret values before this ships.
            logger.warning(
                "payment_webhook.signature_rejected",
                provider=provider,
                correlation_id=correlation_id,
                body_bytes=len(raw_body),
            )
            raise ValidationError(
                "Invalid webhook signature",
                details={"provider": provider},
            )
        payload = parse_webhook_payload(raw_body)
        event_id = extract_event_id(provider, payload)
        existing = await session.execute(
            select(PaymentWebhookReceipt).where(
                PaymentWebhookReceipt.provider == provider,
                PaymentWebhookReceipt.provider_event_id == event_id,
            )
        )
        if existing.scalars().first():
            return {"status": "duplicate", "event_id": event_id}

        receipt = PaymentWebhookReceipt(
            provider=provider,
            provider_event_id=event_id,
            raw_payload=payload,
            status="received",
        )
        session.add(receipt)
        await session.flush()

        event = normalize_payment_event(provider, payload)
        payment_id_raw = event.get("payment_id")
        status_raw = event.get("status")
        order_id = event.get("order_id")
        if (not payment_id_raw and not order_id) or not status_raw:
            receipt.status = "failed"
            receipt.failure_reason = "Missing payment_id/order_id or status"
            await session.flush()
            return {"status": "ignored", "event_id": event_id}

        payment: PaymentAttempt | None = None
        if payment_id_raw:
            try:
                payment_uuid = uuid.UUID(str(payment_id_raw))
            except ValueError:
                payment_uuid = None
            if payment_uuid is not None:
                result = await session.execute(
                    select(PaymentAttempt).where(
                        PaymentAttempt.id == payment_uuid,
                        PaymentAttempt.deleted_at.is_(None),
                    )
                )
                payment = result.scalars().first()
        if payment is None and order_id:
            result = await session.execute(
                select(PaymentAttempt).where(
                    PaymentAttempt.provider_reference == str(order_id),
                    PaymentAttempt.deleted_at.is_(None),
                )
            )
            payment = result.scalars().first()
        if payment is None:
            receipt.status = "failed"
            receipt.failure_reason = "Payment not found"
            await session.flush()
            raise ValidationError(
                "Payment not found for webhook",
                details={"event_id": event_id},
            )

        receipt.payment_attempt_id = payment.id
        target_status = str(status_raw).lower()
        if target_status not in {"succeeded", "failed"}:
            receipt.status = "failed"
            receipt.failure_reason = f"Unsupported status: {target_status}"
            await session.flush()
            return {"status": "ignored", "event_id": event_id}

        try:
            business = await BusinessService.get_by_id(session, payment.business_id)
            await PaymentAttemptService.apply_status(
                session,
                payment=payment,
                target_status=target_status,
                correlation_id=correlation_id,
                actor_id=business.primary_owner_identity_id,
                failure_code=event.get("failure_code") or payload.get("failure_code"),
                failure_reason=event.get("failure_reason") or payload.get("failure_reason"),
                provider_reference=event.get("provider_reference")
                or payload.get("provider_reference"),
            )
            receipt.status = "processed"
            receipt.processed_at = datetime.now(timezone.utc)
            if target_status == "failed":
                logger.warning(
                    "payment.failed",
                    provider=provider,
                    payment_id=str(payment.id),
                    business_id=str(payment.business_id),
                    failure_code=payload.get("failure_code"),
                    correlation_id=correlation_id,
                )
        except Exception as exc:
            receipt.status = "failed"
            receipt.failure_reason = str(exc)
            logger.error(
                "payment_webhook.processing_failed",
                provider=provider,
                payment_id=str(payment.id),
                business_id=str(payment.business_id),
                correlation_id=correlation_id,
                exc_info=exc,
            )
            raise

        await OutboxService.publish(
            session,
            event_type="payment.webhook_processed",
            payload={
                "provider": provider,
                "event_id": event_id,
                "payment_id": str(payment.id),
                "business_id": str(payment.business_id),
            },
            business_id=payment.business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="payment.webhook_processed",
            actor_identity_id=business.primary_owner_identity_id,
            actor_context="system",
            business_id=payment.business_id,
            resource_type="payment_webhook",
            resource_id=receipt.id,
            action="processed",
            before_state=None,
            after_state={"event_id": event_id, "payment_id": str(payment.id)},
        )
        return {"status": "processed", "event_id": event_id, "payment_id": str(payment.id)}
