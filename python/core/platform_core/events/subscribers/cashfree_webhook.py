"""Process verified, durably recorded Cashfree events in the worker."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.events.registry import EventContext, subscribe
from platform_core.services.payment_webhook import PaymentWebhookService


@subscribe(
    "cashfree.webhook",
    "payment.webhook_received",
    description="Re-verify Cashfree order/refund and apply the resulting state",
    max_attempts=12,
)
async def process_cashfree_webhook(session: AsyncSession, event: EventContext) -> None:
    await PaymentWebhookService.process_cashfree_receipt(
        session,
        receipt_id=event.require_uuid("receipt_id"),
        correlation_id=event.correlation_id or str(event.event_id),
    )
