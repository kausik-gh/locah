"""Loyalty earns from a completed sale, through the growth contracts.

The growth lane named its seams (`platform_core.growth.contracts`) and left
calling them to the owner of the final event. A completed order — online or at
the counter, which is an order too — earns points once (key `order:{id}`), and
the customer's first completed sale qualifies a pending referral once. Only for
a business that has Loyalty switched on; a refunded sale earns nothing.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.events.registry import EventContext, subscribe
from platform_core.models import SalesOrder


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "loyalty.earn_on_sale", "order.completed",
    description="A completed sale earns loyalty points once and qualifies a first-purchase referral once",
)
async def earn_on_sale(session: AsyncSession, event: EventContext) -> None:
    from platform_core.events.subscribers.automation_triggers import _module_on
    from platform_core.loyalty.service import LoyaltyPointsService, ReferralService

    business_id = event.require_business_id()
    if not await _module_on(session, business_id, "loyalty"):
        return
    order = await session.get(SalesOrder, event.require_uuid("order_id"))
    if order is None or order.business_id != business_id or order.customer_contact_id is None:
        return
    if order.status != "completed" or order.payment_status == "refunded":
        return
    source_type = "pos" if order.channel == "pos" else "order"
    await LoyaltyPointsService.earn_points(
        session, business_id, order.customer_contact_id,
        order_amount_paise=int(Decimal(str(order.total_amount)) * 100),
        source_type=source_type, source_id=str(order.id), idempotency_key=f"order:{order.id}")
    await ReferralService.qualify_first_purchase(
        session, business_id, order.customer_contact_id, source_type=source_type, source_id=str(order.id))
