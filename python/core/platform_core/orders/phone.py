"""A phone order taken by staff (FR-OR-13; Founder: Orders — "Human phone order:
staff creates the same Order using current catalogue, stock, pricing, tax,
delivery and payment rules").

The phone screen prices the basket with the website's own server pricing and
places the order through the website's own path (`place_for_contact`): the
same catalogue check, choices and written messages, stock reservation, the
delivery zone and charge, the pay-on-delivery rule, a dated order's day and
advance, the fulfilment job and payment attempt — with channel "phone" and
the staff member as the actor. Nothing here is a separate order type.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ValidationError
from platform_core.models import Business


def _bad(message: str, fld: str) -> ValidationError:
    return ValidationError(message, details={"field": fld, "errors": [{"field": fld, "message": message}]})


async def price(session: AsyncSession, business: Business, payload: dict[str, Any]) -> dict[str, Any]:
    from platform_core.services.checkout import CheckoutService

    priced: dict[str, Any] = await CheckoutService.price_cart(session, slug=business.slug, payload=payload)
    return priced


async def place(session: AsyncSession, business: Business, *, actor_id: uuid.UUID, correlation_id: str,
                payload: dict[str, Any]) -> dict[str, Any]:
    from platform_core.resolvers.customer_resolver import CustomerResolver
    from platform_core.services.checkout import CheckoutService
    from platform_core.services.customer import CustomerService
    from platform_core.services.messaging import normalise_phone

    who = payload.get("customer") or {}
    if who.get("contact_id"):
        contact = await CustomerResolver.resolve(session, business_id=business.id,
                                                 contact_id=uuid.UUID(str(who["contact_id"])))
    else:
        name = " ".join(str(who.get("name") or "").split())[:120]
        digits = normalise_phone(who.get("phone"))
        if not name:
            raise _bad("Who is ordering? Enter their name", "customer.name")
        if digits is None:
            raise _bad("Enter their phone number so you can reach them", "customer.phone")
        contact = await CustomerService.find_or_create_contact(
            session, business_id=business.id, correlation_id=correlation_id, actor_id=actor_id,
            display_name=name, email=None, phone=f"+{digits}")
    if str(payload.get("payment_method") or "cod") != "cod":
        raise _bad("A phone order is paid at pickup or delivery, or by the advance link", "payment_method")
    placed: dict[str, Any] = await CheckoutService.place_for_contact(
        session, business=business, contact=contact, correlation_id=correlation_id,
        payload={"items": payload.get("items") or [], "fulfilment_mode": payload.get("fulfilment_mode"),
                 "delivery_address": payload.get("delivery_address"), "payment_method": "cod",
                 "due": payload.get("due"), "location_id": payload.get("location_id"), "channel": "phone",
                 "idempotency_key": payload.get("idempotency_key")},
        actor_context="business", actor_id=actor_id)
    return placed
