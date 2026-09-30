"""Notification routing to WhatsApp (Capability Universe §12.4 templates,
§12.5, §26.3 P1-07 "owner connects a number and receives order notifications").

Events from the modules become WhatsApp messages from the business's number:

* to the customer, the moment something happens to their order or booking
  (the owner switches each in WhatsApp settings), and on the timed ladders the
  owner switches in Automations — out for delivery, booking reminders, and
  payment reminders for bills and khata;
* to team members who asked for WhatsApp alerts (new orders, bookings,
  enquiries, chats waiting, khata over a limit).

Nothing here runs without a connected number; nothing is sent twice for the
same event (idempotency keys); a message LOCAH may not send is recorded with
the reason, never forced.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.automation import AutomationEngine, StepOutcome, step_handler
from platform_core.automation.engine import DueStep
from platform_core.events.registry import EventContext, subscribe
from platform_core.models import (
    Booking,
    Business,
    CustomerContact,
    FulfilmentJob,
    InvoicingDocument,
    Lead,
    LedgerAccount,
    LedgerEntry,
    MessagingConversation,
    SalesOrder,
)
from platform_core.services.messaging import MessagingService, NotSent
from platform_core.site_urls import business_site_url

IST = ZoneInfo("Asia/Kolkata")


def _inr(v: Any) -> str:
    return f"₹{float(v or 0):,.2f}"


def _when(moment: datetime) -> str:
    local = moment.astimezone(IST)
    return local.strftime("%a %d %b, %I:%M %p").replace(" 0", " ").replace("AM", "am").replace("PM", "pm")


def _ten_am(day: date) -> datetime:
    return datetime.combine(day, time(10, 0), IST)


async def _live(session: AsyncSession, business_id: uuid.UUID) -> bool:
    """The messaging module is on and a number is connected."""
    from platform_core.events.subscribers.automation_triggers import _module_on

    channel = await MessagingService.channel(session, business_id)
    return channel is not None and channel.status == "connected" and await _module_on(session, business_id, "messaging")


async def _business(session: AsyncSession, business_id: uuid.UUID) -> Business:
    b = await session.get(Business, business_id)
    assert b is not None
    return b


async def _contact(session: AsyncSession, contact_id: Any) -> CustomerContact | None:
    if not contact_id:
        return None
    return await session.get(CustomerContact, uuid.UUID(str(contact_id)))


async def _send(session: AsyncSession, business_id: uuid.UUID, *, to: str | None, key: str, params: list[str],
                contact_id: Any = None, idem: str) -> str:
    """Send, and say what happened in owner words."""
    if not to:
        return "No phone number for this customer"
    try:
        msg = await MessagingService.send_template(
            session, business_id, to=to, key=key, params=params, idempotency_key=idem,
            contact_id=uuid.UUID(str(contact_id)) if contact_id else None)
    except NotSent as exc:
        return str(exc)
    return "sent" if msg.status == "sent" else f"Not sent: {msg.error or msg.status}"


async def _update_on(session: AsyncSession, business_id: uuid.UUID, key: str) -> bool:
    return bool(MessagingService.update_on(await MessagingService.settings(session, business_id), key))


# ---------------------------------------------------------------- orders
@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "messaging.order_created", "order.created",
    description="Tell the customer their order arrived; alert team members who asked on WhatsApp",
)
async def order_created(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    if not await _live(session, business_id):
        return
    order_id = event.require_uuid("order_id")
    p = event.payload
    business = await _business(session, business_id)
    contact = await _contact(session, p.get("customer_contact_id"))
    name = contact.display_name if contact else "a customer"
    if contact and await _update_on(session, business_id, "order_received"):
        await _send(session, business_id, to=contact.phone, key="order_received", contact_id=contact.id,
                    params=[contact.display_name, business.display_name, str(p.get("order_number")),
                            _inr(p.get("total_amount"))], idem=f"order_received:{order_id}")
    await MessagingService.alert_staff(
        session, business_id, "order.new",
        f"New order {p.get('order_number')} for {_inr(p.get('total_amount'))} from {name}", key=str(order_id))


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "messaging.order_accepted", "order.accepted",
    description="Tell the customer their order is confirmed",
)
async def order_accepted(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    if not await _live(session, business_id) or not await _update_on(session, business_id, "order_confirmed"):
        return
    p = event.payload
    contact = await _contact(session, p.get("customer_contact_id"))
    if contact is None:
        return
    business = await _business(session, business_id)
    await _send(session, business_id, to=contact.phone, key="order_confirmed", contact_id=contact.id,
                params=[str(p.get("order_number")), business.display_name, _inr(p.get("total_amount"))],
                idem=f"order_confirmed:{p.get('order_id')}")


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "messaging.order_on_its_way", "fulfilment.status_changed",
    description="Schedule the out-for-delivery message (Automations › Order updates)",
)
async def order_on_its_way(session: AsyncSession, event: EventContext) -> None:
    if event.payload.get("to") != "out_for_delivery":
        return
    business_id = event.require_business_id()
    now = datetime.now(timezone.utc)
    await AutomationEngine.schedule(session, business_id, ladder_key="order.tracking",
                                    entity_id=event.require_uuid("order_id"), anchor=now,
                                    period_key=str(event.payload.get("job_id")), context={}, now=now)


@step_handler("order.tracking")  # type: ignore[untyped-decorator, unused-ignore]
async def send_tracking(session: AsyncSession, step: DueStep) -> StepOutcome:
    order = await session.get(SalesOrder, step.entity_id)
    job = (await session.execute(select(FulfilmentJob).where(
        FulfilmentJob.business_id == step.business_id, FulfilmentJob.order_id == step.entity_id))).scalars().first()
    if order is None or job is None:
        return StepOutcome("skipped", "The order no longer exists")
    if job.status != "out_for_delivery":
        return StepOutcome("skipped", f"Order {order.order_number} is no longer on its way ({job.status})")
    contact = await _contact(session, order.customer_contact_id)
    business = await _business(session, step.business_id)
    link = business_site_url(business.slug, f"/track/{order.id}?token={job.tracking_token}")
    said = await _send(session, step.business_id, to=contact.phone if contact else None, key="order_out_for_delivery",
                       contact_id=contact.id if contact else None,
                       params=[order.order_number, business.display_name, link], idem=f"ladder:{step.id}")
    return StepOutcome("done" if said == "sent" else "skipped",
                       f"Tracking link for {order.order_number} sent on WhatsApp" if said == "sent" else said)


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "messaging.order_delivered", "fulfilment.delivered",
    description="Tell the customer their order was delivered",
)
async def order_delivered(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    await AutomationEngine.cancel(session, business_id, ladder_key="order.tracking",
                                  entity_id=event.require_uuid("order_id"), reason="Delivered")
    if not await _live(session, business_id) or not await _update_on(session, business_id, "order_delivered"):
        return
    order = await session.get(SalesOrder, event.require_uuid("order_id"))
    contact = await _contact(session, order.customer_contact_id if order else None)
    if order is None or contact is None:
        return
    business = await _business(session, business_id)
    await _send(session, business_id, to=contact.phone, key="order_delivered", contact_id=contact.id,
                params=[order.order_number, business.display_name], idem=f"order_delivered:{order.id}")


# ---------------------------------------------------------------- bookings
@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "messaging.booking_created", "booking.created",
    description="Alert team members who asked for new bookings on WhatsApp",
)
async def booking_created(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    if not await _live(session, business_id):
        return
    booking = await session.get(Booking, event.require_uuid("booking_id"))
    if booking is None:
        return
    await MessagingService.alert_staff(
        session, business_id, "booking.new",
        f"New booking {booking.booking_number}: {booking.title} on {_when(booking.starts_at)}", key=str(booking.id))


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "messaging.booking_confirmed", "booking.confirmed",
    description="Confirm the booking to the customer and schedule its reminders",
)
async def booking_confirmed(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    booking = await session.get(Booking, event.require_uuid("booking_id"))
    if booking is None:
        return
    now = datetime.now(timezone.utc)
    await AutomationEngine.schedule(session, business_id, ladder_key="booking.reminder", entity_id=booking.id,
                                    anchor=booking.starts_at, period_key=booking.starts_at.isoformat(),
                                    context={}, now=now)
    if not await _live(session, business_id) or not await _update_on(session, business_id, "booking_confirmed"):
        return
    contact = await _contact(session, booking.customer_contact_id)
    if contact is None:
        return
    business = await _business(session, business_id)
    await _send(session, business_id, to=contact.phone, key="booking_confirmed", contact_id=contact.id,
                params=[business.display_name, _when(booking.starts_at), booking.title],
                idem=f"booking_confirmed:{booking.id}:{booking.starts_at.isoformat()}")


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "messaging.booking_moved", "booking.cancelled", "booking.rescheduled", "booking.rejected",
    description="Stop reminders for a booking that was cancelled or moved (a moved one is re-confirmed)",
)
async def booking_moved(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    booking_id = event.require_uuid("booking_id")
    await AutomationEngine.cancel(session, business_id, ladder_key="booking.reminder", entity_id=booking_id,
                                  reason="The booking was cancelled or moved")
    booking = await session.get(Booking, booking_id)
    if event.event_type == "booking.rescheduled" and booking is not None and booking.status == "confirmed":
        await AutomationEngine.schedule(session, business_id, ladder_key="booking.reminder", entity_id=booking.id,
                                        anchor=booking.starts_at, period_key=booking.starts_at.isoformat(),
                                        context={}, now=datetime.now(timezone.utc))


@step_handler("booking.reminder")  # type: ignore[untyped-decorator, unused-ignore]
async def remind_booking(session: AsyncSession, step: DueStep) -> StepOutcome:
    booking = await session.get(Booking, step.entity_id)
    if booking is None or booking.status != "confirmed":
        return StepOutcome("skipped", "The booking is no longer confirmed")
    if booking.starts_at.isoformat() != step.period_key:
        return StepOutcome("skipped", "The booking was moved")
    contact = await _contact(session, booking.customer_contact_id)
    business = await _business(session, step.business_id)
    said = await _send(session, step.business_id, to=contact.phone if contact else None, key="booking_reminder",
                       contact_id=contact.id if contact else None,
                       params=[business.display_name, _when(booking.starts_at), booking.title], idem=f"ladder:{step.id}")
    return StepOutcome("done" if said == "sent" else "skipped",
                       f"Reminder for {booking.booking_number} sent on WhatsApp" if said == "sent" else said)


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "messaging.booking_no_show", "booking.no_show",
    description="Schedule the “we missed you” follow-up for a no-show (owner switch in Automations)",
)
async def booking_no_show(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    booking_id = event.require_uuid("booking_id")
    await AutomationEngine.schedule(session, business_id, ladder_key="booking.no_show", entity_id=booking_id,
                                    anchor=datetime.now(timezone.utc), period_key=str(booking_id))


@step_handler("booking.no_show")  # type: ignore[untyped-decorator, unused-ignore]
async def follow_up_no_show(session: AsyncSession, step: DueStep) -> StepOutcome:
    booking = await session.get(Booking, step.entity_id)
    if booking is None or booking.status != "no_show":
        return StepOutcome("skipped", "The booking is no longer a no-show")
    contact = await _contact(session, booking.customer_contact_id)
    business = await _business(session, step.business_id)
    said = await _send(session, step.business_id, to=contact.phone if contact else None, key="booking_missed",
                       contact_id=contact.id if contact else None,
                       params=[business.display_name, booking.title, _when(booking.starts_at),
                               business_site_url(business.slug, "/book")],
                       idem=f"booking_missed:{booking.id}")
    return StepOutcome("done" if said == "sent" else "skipped",
                       f"“We missed you” for {booking.booking_number} sent on WhatsApp" if said == "sent" else said)


# ---------------------------------------------------------------- quotes
@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "messaging.quote_acceptance_code", "quote.acceptance_code_issued",
    description="Send the customer the code that accepts their quote — the only place the code goes",
)
async def quote_acceptance_code(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    if not await _live(session, business_id):
        return
    p = event.payload
    contact = await _contact(session, p.get("customer_contact_id"))
    if contact is None:
        return
    await _send(session, business_id, to=contact.phone, key="quote_acceptance_code", contact_id=contact.id,
                params=[str(p.get("code"))],
                idem=f"quote_code:{event.event_id}")


# ---------------------------------------------------------------- walk-in queue
@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "messaging.queue_turn_soon", "queue.turn_soon",
    description="Tell the customer on WhatsApp that their turn is near — once per token visit",
)
async def queue_turn_soon(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    if not await _live(session, business_id) or not await _update_on(session, business_id, "queue_turn_soon"):
        return
    p = event.payload
    contact = await _contact(session, p.get("customer_contact_id"))
    if contact is None:
        return  # a walk-in without a number is called at the desk
    business = await _business(session, business_id)
    await _send(session, business_id, to=contact.phone, key="queue_turn_soon", contact_id=contact.id,
                params=[business.display_name, str(p.get("token_number")), str(p.get("ahead"))],
                idem=f"queue:{p.get('entry_id')}:{p.get('visit_cycle')}")


# ---------------------------------------------------------------- enquiries, khata alerts
@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "messaging.lead_created", "lead.created",
    description="Alert team members who asked for new enquiries on WhatsApp",
)
async def lead_created(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    if not await _live(session, business_id):
        return
    lead = await session.get(Lead, event.require_uuid("lead_id"))
    who = lead.display_name if lead and lead.display_name else "someone"
    await MessagingService.alert_staff(session, business_id, "lead.new", f"New enquiry from {who}",
                                       key=str(event.payload.get("lead_id")))


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "messaging.khata_over_limit", "ledger.limit.overridden",
    description="Alert whoever manages the khata when credit was allowed over a limit",
)
async def khata_over_limit(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    if not await _live(session, business_id):
        return
    acct = await session.get(LedgerAccount, event.require_uuid("account_id"))
    if acct is None:
        return
    await MessagingService.alert_staff(
        session, business_id, "khata.over_limit",
        f"{acct.display_name} was given {_inr(event.payload.get('amount'))} over their khata limit; "
        f"they owe {_inr(event.payload.get('balance_after'))}", key=str(event.payload.get("entry_id")))


# ---------------------------------------------------------------- payment reminders (bills)
@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "messaging.bill_reminders", "invoice.issued", "invoice.paid", "invoice.cancelled",
    description="Schedule payment reminders for a bill with a due date; stop them when paid or cancelled",
)
async def bill_reminders(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    doc_id = event.require_uuid("document_id")
    if event.event_type != "invoice.issued":
        await AutomationEngine.cancel(session, business_id, ladder_key="invoice.overdue", entity_id=doc_id,
                                      reason="Paid" if event.event_type == "invoice.paid" else "Bill cancelled")
        return
    doc = await session.get(InvoicingDocument, doc_id)
    if doc is None or doc.due_date is None or doc.on_account or doc.doc_kind not in ("tax_invoice", "bill_of_supply", "bill"):
        return  # a khata bill is reminded through the khata, not twice
    await AutomationEngine.schedule(session, business_id, ladder_key="invoice.overdue", entity_id=doc.id,
                                    anchor=_ten_am(doc.due_date), period_key=doc.due_date.isoformat(), context={},
                                    now=datetime.now(timezone.utc))


@step_handler("invoice.overdue")  # type: ignore[untyped-decorator, unused-ignore]
async def remind_bill(session: AsyncSession, step: DueStep) -> StepOutcome:
    from platform_core.services.invoicing import InvoiceService, share_token

    doc = await session.get(InvoicingDocument, step.entity_id)
    if doc is None or doc.status != "issued":
        return StepOutcome("skipped", "The bill was cancelled")
    view = await InvoiceService._money_view(session, doc)
    if view["outstanding"] <= 0:
        return StepOutcome("skipped", f"Bill {doc.number} is paid")
    business = await _business(session, step.business_id)
    contact = await _contact(session, doc.customer_contact_id)
    phone = (doc.buyer or {}).get("phone") or (contact.phone if contact else None)
    link = business_site_url(business.slug, f"/bill/{share_token(step.business_id, doc.id)}")
    said = await _send(session, step.business_id, to=phone, key="payment_due", contact_id=doc.customer_contact_id,
                       params=[business.display_name, _inr(view["outstanding"]), link], idem=f"ladder:{step.id}")
    if step.step_key == "plus_15":
        from platform_core.permissions import INVOICES_READ
        from platform_core.services.notification import NotificationService

        await NotificationService.fan_out(
            session, business_id=step.business_id, notification_type="invoicing.bill_long_overdue",
            title=f"Bill {doc.number} is 15 days late", body=f"{_inr(view['outstanding'])} still unpaid.",
            required_permission=INVOICES_READ, severity="warning", resource_type="invoice", resource_id=doc.id)
    return StepOutcome("done" if said == "sent" else "skipped",
                       f"Payment reminder for {doc.number} ({_inr(view['outstanding'])}) sent on WhatsApp"
                       if said == "sent" else said)


# ---------------------------------------------------------------- khata reminders
@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "messaging.khata_reminders", "ledger.entry.posted",
    description="Schedule khata reminders from the day credit falls due",
)
async def khata_reminders(session: AsyncSession, event: EventContext) -> None:
    p = event.payload
    if p.get("party_type") != "customer" or float(p.get("amount") or 0) <= 0:
        return
    business_id = event.require_business_id()
    entry = await session.get(LedgerEntry, event.require_uuid("entry_id"))
    acct = await session.get(LedgerAccount, event.require_uuid("account_id"))
    if entry is None or acct is None:
        return
    due = entry.due_date or (entry.entry_date + timedelta(days=acct.credit_days) if acct.credit_days is not None
                             else None)
    if due is None:
        return
    await AutomationEngine.schedule(session, business_id, ladder_key="ledger.statement", entity_id=acct.id,
                                    anchor=_ten_am(due), period_key=due.isoformat(), context={},
                                    now=datetime.now(timezone.utc))


@step_handler("ledger.statement")  # type: ignore[untyped-decorator, unused-ignore]
async def remind_khata(session: AsyncSession, step: DueStep) -> StepOutcome:
    from platform_core.services.invoicing_setup import local_today
    from platform_core.services.ledger import LedgerService, age

    acct = await session.get(LedgerAccount, step.entity_id)
    if acct is None or acct.status != "active":
        return StepOutcome("skipped", "The khata is closed")
    # What has fallen due by the step's own day (a reminder on the due date
    # counts what is due that day), never judged by when the worker ran.
    as_of = max(local_today(), step.due_at.astimezone(IST).date())
    ageing = age(await LedgerService.entries(session, acct.id), as_of + timedelta(days=1), acct.credit_days)
    if ageing.overdue <= 0:
        return StepOutcome("skipped", f"{acct.display_name} has nothing due")
    share = await LedgerService.share(session, step.business_id, acct.id)
    business = await _business(session, step.business_id)
    link = business_site_url(business.slug, f"/khata/{share['token']}")
    said = await _send(session, step.business_id, to=acct.phone, key="payment_due",
                       contact_id=acct.customer_contact_id,
                       params=[business.display_name, _inr(ageing.overdue), link],
                       idem=f"ladder:{step.id}")
    return StepOutcome("done" if said == "sent" else "skipped",
                       f"Khata reminder to {acct.display_name} ({_inr(ageing.overdue)} past due) sent on WhatsApp"
                       if said == "sent" else said)


# ---------------------------------------------------------------- chats waiting
@step_handler("chat.waiting")  # type: ignore[untyped-decorator, unused-ignore]
async def chat_waiting(session: AsyncSession, step: DueStep) -> StepOutcome:
    from platform_core.permissions import MESSAGING_REPLY
    from platform_core.services.notification import NotificationService

    conv = await session.get(MessagingConversation, step.entity_id)
    if conv is None or conv.state != "open" or not conv.needs_person or conv.waiting_since is None:
        return StepOutcome("skipped", "Someone replied")
    minutes = int((datetime.now(timezone.utc) - conv.waiting_since).total_seconds() // 60)
    who = conv.profile_name or f"+{conv.wa_id}"
    await NotificationService.fan_out(
        session, business_id=step.business_id, notification_type="messaging.waiting",
        title=f"{who} is waiting for a reply on WhatsApp", body=f"Waiting {minutes} minutes.",
        required_permission=MESSAGING_REPLY, severity="warning", resource_type="messaging_conversation",
        resource_id=conv.id)
    sent = await MessagingService.alert_staff(session, step.business_id, "chat.waiting",
                                              f"{who} has waited {minutes} minutes for a reply on WhatsApp",
                                              key=f"{conv.id}:{step.period_key}")
    return StepOutcome("done", f"Told your team {who} is waiting" + (f" ({sent} on WhatsApp)" if sent else ""))

