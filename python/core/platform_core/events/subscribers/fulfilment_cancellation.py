"""Cancel the fulfilment job behind an order that is no longer going to happen.

Previously a hardcoded branch in the worker's outbox consumer.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.events.registry import EventContext, subscribe


@subscribe(  # type: ignore[untyped-decorator]  # see marketplace_index.py: mypy loses
    # this decorator factory's return type once it wraps an `async def`.
    "fulfilment.order_cancellation",
    "order.cancelled",
    "order.rejected",
    description="Cancel any fulfilment job for a cancelled or rejected order",
)
async def cancel_for_order(session: AsyncSession, event: EventContext) -> None:
    from platform_core.services.fulfilment import FulfilmentService

    await FulfilmentService.cancel_for_order(
        session,
        business_id=event.require_business_id(),
        order_id=event.require_uuid("order_id"),
        correlation_id=event.correlation_id or str(event.event_id),
        reason=str(event.payload.get("reason") or "Order cancelled"),
    )
