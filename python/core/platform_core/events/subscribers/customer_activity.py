"""My Activity follows the records it describes (Founder §13; MD §7.1).

Orders, bills, quotes, memberships and deliveries publish events; this
subscriber writes the customer's own activity row when the customer is a
LOCAH identity (a linked contact). Guests get nothing here until they sign in
and their verified email links them (services.customer_account). No module
calls My Activity directly — it reacts, like every other consumer.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.events.registry import EventContext, subscribe
from platform_core.models import InvoicingDocument, MembershipEnrolment, Quote, SalesOrder
from platform_core.services.customer_account import CustomerAccountService, contact_identity

ORDER_EVENTS = ("order.created", "order.accepted", "order.preparing", "order.ready", "order.completed",
                "order.cancelled", "order.rejected", "order.updated", "fulfilment.status_changed",
                "fulfilment.delivered", "fulfilment.failed", "payment.completed", "payment.refunded")
BILL_EVENTS = ("invoice.issued", "invoice.cancelled", "invoice.paid", "invoice.payment_recorded")
QUOTE_EVENTS = ("quote.issued", "quote.revised", "quote.accepted", "quote.rejected", "quote.expired",
                "quote.cancelled", "quote.converted")
MEMBERSHIP_EVENTS = ("membership.enrolled", "membership.enrolment.activated", "membership.enrolment.cancelled",
                     "membership.enrolment.completed", "membership.enrolment.expired",
                     "membership.enrolment.paused", "membership.enrolment.updated")


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "customer_activity.orders", *ORDER_EVENTS,
    description="Keep the customer's My Activity in step with their orders and deliveries",
)
async def orders(session: AsyncSession, event: EventContext) -> None:
    order_id = event.payload.get("order_id")
    if not order_id:
        return
    order = await session.get(SalesOrder, event.require_uuid("order_id"))
    if order is None or order.business_id != event.require_business_id():
        return
    identity = await contact_identity(session, order.customer_contact_id)
    if identity is not None:
        await CustomerAccountService.record_order(session, order, identity)


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "customer_activity.bills", *BILL_EVENTS,
    description="Put the customer's bills in their My Activity with a link to open them",
)
async def bills(session: AsyncSession, event: EventContext) -> None:
    doc = await session.get(InvoicingDocument, event.require_uuid("document_id"))
    if doc is None or doc.business_id != event.require_business_id():
        return
    identity = await contact_identity(session, doc.customer_contact_id)
    if identity is not None:
        await CustomerAccountService.record_bill(session, doc, identity)


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "customer_activity.quotes", *QUOTE_EVENTS,
    description="Show quotes sent to the customer in their My Activity",
)
async def quotes(session: AsyncSession, event: EventContext) -> None:
    quote = await session.get(Quote, event.require_uuid("quote_id"))
    if quote is None or quote.business_id != event.require_business_id() or quote.status == "draft":
        return
    identity = await contact_identity(session, quote.customer_contact_id)
    if identity is not None:
        await CustomerAccountService.record_quote(session, quote, identity)


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "customer_activity.memberships", *MEMBERSHIP_EVENTS,
    description="Show the customer's memberships and their state in My Activity",
)
async def memberships(session: AsyncSession, event: EventContext) -> None:
    enrolment = await session.get(MembershipEnrolment, event.require_uuid("enrolment_id"))
    if enrolment is None or enrolment.business_id != event.require_business_id():
        return
    identity = await contact_identity(session, enrolment.customer_contact_id)
    if identity is not None:
        await CustomerAccountService.record_membership(session, enrolment, identity)
