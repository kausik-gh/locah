"""Recipe/BOM consumption when the kitchen finishes a preparation.

The kitchen never touches stock. It publishes `kitchen.preparation.completed`
with what it cooked; Recipe/BOM (the supply lane's `consume_for_sale`) turns
each cooked line into component movements through Inventory. The key is the
ticket and order line, so one logical preparation consumes once however often
the event is delivered, and the unique key refuses a concurrent second
delivery. A component that would go below zero fails the delivery as a whole
(nothing is half-consumed); it retries and consumes once the stock is right.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.events.registry import EventContext, subscribe
from platform_core.models import Business


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "recipes.kitchen_consumption", "kitchen.preparation.completed",
    description="Cooked lines use their recipe's ingredients from stock — once per preparation",
)
async def consume_cooked(session: AsyncSession, event: EventContext) -> None:
    from platform_core.procurement.service import SupplyService

    business_id = event.require_business_id()
    ticket_id = event.require_uuid("ticket_id")
    location_id = event.require_uuid("location_id")
    owner = (await session.execute(select(Business.primary_owner_identity_id).where(
        Business.id == business_id))).scalar_one_or_none()
    if owner is None:
        return
    for line in event.payload.get("lines") or []:
        quantity = int(line.get("quantity") or 0)
        if quantity <= 0 or not line.get("offering_id"):
            continue
        await SupplyService.consume_for_sale(
            session, business_id, uuid.UUID(str(owner)),
            {"idempotency_key": f"kitchen:{ticket_id}:{line['order_line_id']}",
             "offering_id": line["offering_id"], "quantity": quantity, "location_id": str(location_id)},
            None,
        )
