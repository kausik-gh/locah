import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.logging import get_logger
from platform_worker.claiming import claim_outbox_batch

logger = get_logger("platform_worker.outbox")

KNOWN_HANDLERS = {
    "business.created",
    "membership.created",
    "membership.updated",
    "membership.suspended",
    "membership.reactivated",
    "membership.removed",
    "ownership.transferred",
    "invitation.created",
    "invitation.resent",
    "invitation.accepted",
    "invitation.declined",
    "invitation.revoked",
    "invitation.expired",
    "business.settings.updated",
    "business.profile.updated",
    "business.branding.updated",
    "business.preferences.updated",
    "business_type.changed",
    "configuration.resolved",
    "configuration.profile.updated",
    "entitlement.updated",
    "module.disabled",
    "feature.enabled",
    "feature.disabled",
    "business.override.updated",
    "permission.override.created",
    "permission.override.removed",
    "authorization.snapshot.updated",
    "role.changed",
    "location.created",
    "location.updated",
    "location.archived",
    "employee.created",
    "employee.updated",
    "employee.deactivated",
    "employee.assigned",
    "employee.unassigned",
    "employee.transferred",
    "customer.created",
    "customer.updated",
    "customer.blocked",
    "customer.archived",
    "customer.restored",
    "customer.tagged",
    "customer.note.created",
    "product_category.created",
    "product_category.updated",
    "product_category.archived",
    "offering.created",
    "offering.updated",
    "offering.archived",
    "offering.restored",
    "offering.variant.created",
    "inventory.stock.updated",
    "inventory.stock.low",
    "inventory.stock.zero",
    "inventory.stock.replenished",
    "inventory.adjusted",
    "inventory.opening_stock.set",
    "order.created",
    "order.updated",
    "order.accepted",
    "order.preparing",
    "order.ready",
    "order.completed",
    "order.cancelled",
    "order.rejected",
    "order.note.created",
    "booking.created",
    "booking.updated",
    "booking.confirmed",
    "booking.rejected",
    "booking.checked_in",
    "booking.completed",
    "booking.cancelled",
    "booking.rescheduled",
    "booking.no_show",
    "booking.note.created",
    "booking.deposit_collected",
    "booking.policy_updated",
    "workforce.member_created",
    "workforce.member_updated",
    "workforce.location_assigned",
    "workforce.location_unassigned",
    "workforce.service_associated",
    "workforce.availability_updated",
    "payment.initiated",
    "payment.completed",
    "payment.failed",
    "payment.refunded",
    "payment.webhook_processed",
    "payment.merchant.updated",
    "payment.updated",
    "website.draft_generated",
    "website.published",
    "website.generation_failed",
    "business.visibility.changed",
    "business.suspended",
    "marketplace.indexed",
    "marketplace.index_failed",
    "marketplace.deindexed",
    "marketplace.reindex_triggered",
    "fulfilment.job_created",
    "fulfilment.status_changed",
    "fulfilment.failed",
    "fulfilment.delivered",
    "fulfilment.zone_configured",
    "fulfilment.settings_updated",
    "business.initialized",
    "business.context_switched",
    "permission.granted",
    "module.enabled",
    "module.deactivated",
    # Stage 6 — Leads
    "lead.created",
    "lead.updated",
    "lead.assigned",
    "lead.deleted",
    "lead.stage_changed",
    "lead.contacted",
    "lead.qualified",
    "lead.won",
    "lead.lost",
    "lead.note.created",
    # Stage 6 — Memberships
    "membership.plan.created",
    "membership.plan.updated",
    "membership.plan.archived",
    "membership.enrolled",
    "membership.enrolment.updated",
    "membership.enrolment.activated",
    "membership.enrolment.paused",
    "membership.enrolment.expired",
    "membership.enrolment.cancelled",
    "membership.enrolment.completed",
}

# Events that trigger Marketplace projection re-index (Doc 12 §14.5).
MARKETPLACE_INDEX_TRIGGERS = {
    "website.published",
    "business.profile.updated",
    "business.visibility.changed",
    "business.suspended",
    "offering.created",
    "offering.updated",
    "offering.archived",
    "offering.restored",
    "location.updated",
    "location.created",
    "location.archived",
}


async def _mark_completed(session: AsyncSession, event_id: str) -> None:
    await session.execute(
        text("""
            UPDATE platform_outbox_events
            SET status = 'completed', processed_at = now(), leased_until = NULL, leased_by = NULL
            WHERE id = :id
        """),
        {"id": event_id},
    )


async def _mark_retry(session: AsyncSession, event_id: str, attempt_count: int, error: str) -> None:
    backoff = min(2**attempt_count * 30, 3600)
    await session.execute(
        text("""
            UPDATE platform_outbox_events
            SET status = 'failed',
                attempt_count = :attempt_count,
                next_attempt_at = now() + make_interval(secs => :backoff),
                last_error = :error,
                leased_until = NULL,
                leased_by = NULL
            WHERE id = :id
        """),
        {"id": event_id, "attempt_count": attempt_count, "backoff": backoff, "error": error},
    )


async def _mark_dead_letter(session: AsyncSession, event: dict[str, Any], error: str) -> None:
    await session.execute(
        text("""
            UPDATE platform_outbox_events SET status = 'dead_letter', last_error = :error WHERE id = :id
        """),
        {"id": event["id"], "error": error},
    )
    payload = event["payload"]
    if isinstance(payload, dict):
        payload = json.dumps(payload)
    await session.execute(
        text("""
            INSERT INTO platform_dead_letter_events
                (source_table, source_id, event_type, payload, final_error, attempt_count)
            VALUES ('platform_outbox_events', :id, :event_type, CAST(:payload AS jsonb), :error, :attempt_count)
        """),
        {
            "id": event["id"],
            "event_type": event["event_type"],
            "payload": payload,
            "error": error,
            "attempt_count": event["attempt_count"],
        },
    )


async def _dispatch_order_cancelled_fulfilment(
    session: AsyncSession, event: dict[str, Any]
) -> None:
    from uuid import UUID

    from platform_core.services.fulfilment import FulfilmentService

    payload = event.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)
    business_id = payload.get("business_id") or event.get("business_id")
    order_id = payload.get("order_id")
    if not business_id or not order_id:
        return
    await FulfilmentService.cancel_for_order(
        session,
        business_id=UUID(str(business_id)),
        order_id=UUID(str(order_id)),
        correlation_id=str(event.get("correlation_id") or event.get("id")),
        reason=str(payload.get("reason") or "Order cancelled"),
    )


async def _dispatch_marketplace_index(session: AsyncSession, event: dict[str, Any]) -> None:
    from uuid import UUID

    from platform_core.services.marketplace_indexing import MarketplaceIndexingService

    payload = event.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)
    business_id = payload.get("business_id") or event.get("business_id")
    if not business_id:
        return
    await MarketplaceIndexingService.reindex_business(
        session,
        business_id=UUID(str(business_id)),
        correlation_id=str(event.get("correlation_id") or event.get("id")),
        trigger=str(event.get("event_type") or "outbox"),
    )


async def poll_and_dispatch_outbox(session: AsyncSession, worker_id: str) -> int:
    events = await claim_outbox_batch(session, worker_id)
    if not events:
        return 0

    processed = 0
    for event in events:
        event_type = event.get("event_type", "")
        try:
            if event_type not in KNOWN_HANDLERS:
                raise ValueError(f"No handler for event type: {event_type}")
            if event_type in MARKETPLACE_INDEX_TRIGGERS:
                await _dispatch_marketplace_index(session, dict(event))
            if event_type in {"order.cancelled", "order.rejected"}:
                await _dispatch_order_cancelled_fulfilment(session, dict(event))
            await _mark_completed(session, str(event["id"]))
            processed += 1
        except Exception as exc:
            attempt = int(event.get("attempt_count", 0)) + 1
            max_attempts = int(event.get("max_attempts", 5))
            if attempt >= max_attempts:
                logger.error(
                    "outbox.dead_letter",
                    event_id=str(event["id"]),
                    event_type=event_type,
                    business_id=str(event.get("business_id") or ""),
                    attempt=attempt,
                    error=str(exc),
                )
                await _mark_dead_letter(session, event, str(exc))
            else:
                logger.warning(
                    "outbox.retry_scheduled",
                    event_id=str(event["id"]),
                    event_type=event_type,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    error=str(exc),
                )
                await _mark_retry(session, str(event["id"]), attempt, str(exc))
    await session.commit()
    return processed
