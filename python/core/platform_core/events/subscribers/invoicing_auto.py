"""Website and WhatsApp orders get their bill automatically (Capability
Universe §14: one billing engine for every bill), at the moment the owner
chose in Settings → Tax & invoicing: when the order is accepted or when it is
completed. "Only when I issue it myself" leaves it to staff.

A bill that cannot be issued (no register at that location, a missing GST
rate) is never guessed around: nothing is issued and the people who issue
bills are told why, in plain words.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.events.registry import EventContext, subscribe
from platform_core.exceptions import PlatformError

_TRIGGER = {"order.accepted": "order_accepted", "order.completed": "order_completed"}


async def _module_on(session: AsyncSession, business_id: uuid.UUID) -> bool:
    row = (await session.execute(
        text("SELECT activation_state FROM business_module_states WHERE business_id = :b AND module_id = 'invoicing'"),
        {"b": str(business_id)},
    )).first()
    return row is not None and row[0] in ("enabled", "ready", "active")


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "invoicing.auto_bill",
    "order.accepted",
    "order.completed",
    description="Issue the order's bill when the owner chose this moment (§14)",
)
async def auto_bill(session: AsyncSession, event: EventContext) -> None:
    from platform_core.models import Business, InvoicingTaxProfile
    from platform_core.permissions import INVOICES_ISSUE
    from platform_core.services.invoicing import InvoiceService
    from platform_core.services.notification import NotificationService

    business_id = event.require_business_id()
    order_id = event.require_uuid("order_id")
    if not await _module_on(session, business_id):
        return
    profile = await session.get(InvoicingTaxProfile, business_id)
    if profile is None or profile.issue_on != _TRIGGER.get(event.event_type):
        return
    business = await session.get(Business, business_id)
    if business is None:
        return
    number = event.payload.get("order_number") or ""
    try:
        async with session.begin_nested():
            doc = await InvoiceService.from_order(session, business_id, order_id, business.primary_owner_identity_id,
                                                  actor_context="system")
    except PlatformError as exc:
        detail = getattr(exc, "detail", None)
        message = detail.get("message") if isinstance(detail, dict) else str(detail or exc)
        await NotificationService.fan_out(
            session, business_id=business_id, notification_type="invoicing.bill_blocked",
            title=f"Order {number} could not be billed", body=str(message),
            required_permission=INVOICES_ISSUE, severity="warning", resource_type="order", resource_id=order_id,
            payload={"order_id": str(order_id)},
        )
        return
    del doc
