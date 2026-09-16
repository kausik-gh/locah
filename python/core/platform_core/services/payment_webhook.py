"""Payment webhook service (Stage 9)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ValidationError
from platform_core.logging import get_logger
from platform_core.models import PaymentAttempt, PaymentWebhookReceipt
from platform_core.payments.provider_adapter import (
    extract_event_id,
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
    async def process_webhook(
        session: AsyncSession,
        *,
        provider: str,
        raw_body: bytes,
        headers: dict[str, str],
        correlation_id: str,
    ) -> dict[str, Any]:
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

        payment_id_raw = payload.get("payment_id") or payload.get("payment_attempt_id")
        status_raw = payload.get("status")
        if not payment_id_raw or not status_raw:
            receipt.status = "failed"
            receipt.failure_reason = "Missing payment_id or status"
            await session.flush()
            return {"status": "ignored", "event_id": event_id}

        payment_uuid = uuid.UUID(str(payment_id_raw))
        result = await session.execute(
            select(PaymentAttempt).where(
                PaymentAttempt.id == payment_uuid,
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
                details={"payment_id": str(payment_uuid)},
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
                failure_code=payload.get("failure_code"),
                failure_reason=payload.get("failure_reason"),
                provider_reference=payload.get("provider_reference"),
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
