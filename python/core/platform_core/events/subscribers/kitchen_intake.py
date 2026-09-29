"""Kitchen tickets follow the order. The order never imports the kitchen.

`order.accepted` opens one ticket. A replay of that event does not open another.
`order.updated` adjusts the pass without rewriting lines that have started.
`order.cancelled` and `order.rejected` take the ticket off, or leave a visible
cancel when cooking has already started.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.events.registry import EventContext, subscribe


@subscribe(  # type: ignore[untyped-decorator]
    "kitchen.order_intake",
    "order.accepted",
    "order.updated",
    "order.cancelled",
    "order.rejected",
    description="Open or adjust the kitchen ticket for an order",
)
async def intake_order(session: AsyncSession, event: EventContext) -> None:
    from platform_core.kitchen.intake import OrderIntake

    await OrderIntake.handle(session, event)
