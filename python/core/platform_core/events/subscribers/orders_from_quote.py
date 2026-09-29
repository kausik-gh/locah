"""Orders takes an accepted quote handed to it (locah.quote.conversion.v1).

The order is the sale at the prices the customer accepted: each locked line is
carried at its agreed pre-tax unit price ((subtotal − discount) ÷ quantity),
one order per quote (idempotency key `quote:{id}`). An order line is a
catalogue item in whole units; a quote with a free-text or fractional line
cannot become an order and is refused for good with that reason (hand it to a
project or an invoice instead) — nothing is guessed.

The token the customer accepted (the quote's deposit) becomes this order's
advance. Payments then asks for it against the order, the real transaction —
the Money panel defaults to it and a payment link carries it — so the quote's
payment handoff lands in the one payment system, never a second one.
"""

from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.events.registry import EventContext, PermanentEventError, subscribe
from platform_core.models import Business, BusinessLocation


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "orders.from_quote", "quote.conversion_requested",
    description="An accepted quote handed to Orders becomes one order at the accepted prices",
)
async def order_from_quote(session: AsyncSession, event: EventContext) -> None:
    if event.payload.get("target") != "order":
        return
    from platform_core.services.order import OrderService

    business_id = event.require_business_id()
    items = []
    for line in event.payload.get("lines") or []:
        quantity = Decimal(str(line.get("quantity") or 0))
        if not line.get("offering_id") or quantity <= 0 or quantity != quantity.to_integral_value():
            raise PermanentEventError(
                f"Quote line '{line.get('title')}' is not a catalogue item in whole units; "
                "hand this quote to a project or an invoice instead")
        agreed = (Decimal(str(line["line_subtotal"])) - Decimal(str(line.get("line_discount") or 0))) / quantity
        items.append({"offering_id": line["offering_id"], "quantity": int(quantity),
                      "unit_price": str(agreed.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))})
    if not items:
        raise PermanentEventError("The quote has no lines to order")
    owner = (await session.execute(select(Business.primary_owner_identity_id).where(
        Business.id == business_id))).scalar_one()
    location = (await session.execute(select(BusinessLocation.id).where(
        BusinessLocation.business_id == business_id, BusinessLocation.is_primary.is_(True),
        BusinessLocation.deleted_at.is_(None)))).scalars().first()
    order = await OrderService.create_order(
        session, business_id=business_id, actor_id=uuid.UUID(str(owner)),
        correlation_id=event.correlation_id or str(event.event_id),
        payload={"location_id": str(location) if location else None,
                 "customer_contact_id": event.payload.get("customer_contact_id"),
                 "channel": "workspace",
                 "internal_reference": f"Quote {event.payload.get('quote_number')} r{event.payload.get('revision')}",
                 "idempotency_key": f"quote:{event.payload['quote_id']}",
                 "items": items},
        actor_context="system")
    token = Decimal(str(event.payload.get("token_amount") or 0))
    if token > 0:
        ask = min(token, Decimal(str(order.total_amount)))
        if Decimal(str(order.advance_amount or 0)) < ask:
            order.advance_amount = float(ask)
            await session.flush()
