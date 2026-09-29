"""Memberships automation (Founder refinement — Memberships §5, §20, §26; Capability Universe §10.4).

The renewal ladder runs on the relationship's cover end:

* T−7, T−2 — WhatsApp renewal reminder with one reusable payment link;
* T0 — "your plan ends today" (autopay only where a provider supports it —
  none is activated, so the owner is told, never pretended to);
* T+1 — the membership moves to grace (or expires when there is none);
* grace end — it expires;
* T+15 — a win-back message, only to customers who opted in to marketing.

Every step recalculates the relationship first: a payment at any point moves
the cover end, which cancels the old ladder and books the next, so a renewed
member is never reminded again. Messages go through Messaging's template
contract with an idempotency key per step — a replayed step sends nothing
twice. Quiet hours are the engine's (business timezone).

Fee plans run their own instalment ladder; session packs listen to bookings.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.automation import StepOutcome, step_handler
from platform_core.automation.engine import DueStep
from platform_core.events.registry import EventContext, subscribe
from platform_core.memberships.models import MembershipInstalment
from platform_core.memberships.service import INSTALMENT_LADDER, RENEWAL_LADDER, MembershipCore
from platform_core.models import Booking, Business, CustomerContact, MembershipEnrolment, MembershipPlan


def _inr(v: Any) -> str:
    return f"₹{float(v or 0):,.2f}".replace(".00", "")


async def _live(session: AsyncSession, business_id: uuid.UUID) -> bool:
    from platform_core.events.subscribers.messaging_notify import _live as messaging_live

    return bool(await messaging_live(session, business_id))


async def _send(session: AsyncSession, business_id: uuid.UUID, contact: CustomerContact | None, key: str,
                params: list[str], idem: str) -> str:
    from platform_core.events.subscribers.messaging_notify import _send as send

    if contact is None:
        return "No customer to message"
    if not await _live(session, business_id):
        return "WhatsApp is not connected, so no message was sent"
    outcome: str = await send(session, business_id, to=contact.phone, key=key, params=params,
                              contact_id=contact.id, idem=idem)
    return outcome


async def _load(session: AsyncSession, step: DueStep) -> tuple[MembershipEnrolment, MembershipPlan] | None:
    enrolment = await session.get(MembershipEnrolment, step.entity_id)
    if enrolment is None or enrolment.business_id != step.business_id or enrolment.deleted_at is not None:
        return None
    plan = await session.get(MembershipPlan, enrolment.plan_id)
    return (enrolment, plan) if plan is not None else None


def _at(step: DueStep) -> datetime:
    """A step runs at or after its due time: judge the membership then, not earlier."""
    due: datetime = step.due_at
    return max(datetime.now(timezone.utc), due)


def _day(moment: datetime | None, zone: str) -> str:
    return moment.astimezone(ZoneInfo(zone)).strftime("%d %b %Y") if moment else ""


async def _renewal_link(session: AsyncSession, enrolment: MembershipEnrolment, plan: MembershipPlan,
                        step: DueStep) -> tuple[str | None, str | None]:
    """One payment link per cover end, reused by every reminder (§5): the
    renewal charge is the next period (created once), the link is sent again."""
    from platform_core.services.payment_collect import PaymentCollectService
    from platform_core.site_urls import business_site_url

    prior = (await session.execute(text(
        "SELECT result->>'link', result->>'request_id' FROM automation_steps WHERE business_id = :b "
        "AND ladder_key = :l AND entity_id = :e AND period_key = :p AND status = 'done' "
        "AND result ? 'link' ORDER BY executed_at DESC LIMIT 1"),
        {"b": str(step.business_id), "l": RENEWAL_LADDER, "e": str(enrolment.id), "p": step.period_key})).first()
    if prior is not None and prior[1]:
        still = (await session.execute(text(
            "SELECT 1 FROM payments_requests WHERE id = CAST(:r AS uuid) AND status = 'open' AND expires_at > now()"),
            {"r": prior[1]})).first()
        if still is not None:
            return str(prior[0]), str(prior[1])
    period = await MembershipCore.renew(session, enrolment, actor_id=None, now=_at(step))
    owing = Decimal(str(period.amount)) - Decimal(str(period.paid_amount))
    if owing <= 0:
        return None, None
    business = await session.get(Business, enrolment.business_id)
    assert business is not None
    req, token = await PaymentCollectService.create_request(
        session, enrolment.business_id, business.primary_owner_identity_id, source_type="membership",
        source_id=enrolment.id, amount=owing, purpose="full", note=f"Renewal — {plan.name}",
        correlation_id=str(uuid.uuid4()))
    return business_site_url(business.slug, f"/pay/{token}"), str(req.id)


@step_handler(RENEWAL_LADDER, "t_minus_7", "t_minus_2", "t0")  # type: ignore[untyped-decorator, unused-ignore]
async def renewal_reminder(session: AsyncSession, step: DueStep) -> StepOutcome:
    loaded = await _load(session, step)
    if loaded is None:
        return StepOutcome("skipped", "This membership no longer exists")
    enrolment, plan = loaded
    st = await MembershipCore.recalculate(session, enrolment, now=_at(step), reason="Renewal reminder")
    if enrolment.status in ("cancelled", "completed"):
        return StepOutcome("skipped", "The membership was cancelled")
    if st.valid_until is None or f"{st.valid_until:%Y%m%d%H%M}" != step.period_key or st.renewed_ahead:
        return StepOutcome("skipped", "Already renewed")
    zone = await MembershipCore.tz(session, enrolment.business_id, enrolment.location_id)
    link, request_id = await _renewal_link(session, enrolment, plan, step)
    if link is None:
        return StepOutcome("skipped", "The next period is already paid")
    business = await session.get(Business, enrolment.business_id)
    contact = await session.get(CustomerContact, enrolment.customer_contact_id)
    sent = await _send(session, enrolment.business_id, contact, "renewal_due",
                       [plan.name, business.display_name if business else "", _day(st.valid_until, zone), link],
                       idem=f"membership:{enrolment.id}:{step.period_key}:{step.step_key}")
    extra = ""
    if step.step_key == "t0" and enrolment.auto_renew:
        extra = " Autopay is not available yet: the payment provider is not activated."
    result = {"link": link, "request_id": request_id, "message": sent}
    if sent == "sent":
        return StepOutcome("done", f"Renewal reminder sent on WhatsApp with a payment link.{extra}", result)
    return StepOutcome("done", f"Renewal link ready; message not sent: {sent}.{extra}", result)


@step_handler(RENEWAL_LADDER, "t_plus_1")  # type: ignore[untyped-decorator, unused-ignore]
async def grace_notice(session: AsyncSession, step: DueStep) -> StepOutcome:
    loaded = await _load(session, step)
    if loaded is None:
        return StepOutcome("skipped", "This membership no longer exists")
    enrolment, plan = loaded
    st = await MembershipCore.recalculate(session, enrolment, now=_at(step), reason="The plan ended without renewal")
    if st.status in ("active", "paused", "cancelled", "completed"):
        return StepOutcome("skipped", "Already renewed" if st.status == "active" else "No longer running")
    zone = await MembershipCore.tz(session, enrolment.business_id, enrolment.location_id)
    business = await session.get(Business, enrolment.business_id)
    contact = await session.get(CustomerContact, enrolment.customer_contact_id)
    link, request_id = await _renewal_link(session, enrolment, plan, step)
    link = link or ""
    if st.status == "grace":
        sent = await _send(session, enrolment.business_id, contact, "membership_grace",
                           [plan.name, business.display_name if business else "", _day(st.valid_until, zone),
                            _day(st.grace_until, zone), link],
                           idem=f"membership:{enrolment.id}:{step.period_key}:grace")
        return StepOutcome("done", f"Moved to grace until {_day(st.grace_until, zone)}; notice {sent}",
                           {"link": link, "request_id": request_id})
    sent = await _send(session, enrolment.business_id, contact, "membership_expired",
                       [plan.name, business.display_name if business else "", link],
                       idem=f"membership:{enrolment.id}:{step.period_key}:expired")
    return StepOutcome("done", f"Expired (no grace period); notice {sent}", {"link": link})


@step_handler(RENEWAL_LADDER, "grace_end")  # type: ignore[untyped-decorator, unused-ignore]
async def grace_ended(session: AsyncSession, step: DueStep) -> StepOutcome:
    loaded = await _load(session, step)
    if loaded is None:
        return StepOutcome("skipped", "This membership no longer exists")
    enrolment, plan = loaded
    st = await MembershipCore.recalculate(session, enrolment, now=_at(step), reason="Grace ended without renewal")
    if st.status != "expired":
        return StepOutcome("skipped", "Already renewed" if st.status == "active" else "Nothing to do")
    await MembershipCore.lapse_unpaid(session, enrolment, now=_at(step))
    business = await session.get(Business, enrolment.business_id)
    contact = await session.get(CustomerContact, enrolment.customer_contact_id)
    if plan.grace_days <= 0:
        return StepOutcome("done", "Expired (the expiry notice went with the day-after step)")
    sent = await _send(session, enrolment.business_id, contact, "membership_expired",
                       [plan.name, business.display_name if business else "",
                        business.slug if business else ""],
                       idem=f"membership:{enrolment.id}:{step.period_key}:expired")
    return StepOutcome("done", f"Expired; notice {sent}")


@step_handler(RENEWAL_LADDER, "t_plus_15")  # type: ignore[untyped-decorator, unused-ignore]
async def winback(session: AsyncSession, step: DueStep) -> StepOutcome:
    """Marketing, so Messaging sends it only to a customer who opted in."""
    loaded = await _load(session, step)
    if loaded is None:
        return StepOutcome("skipped", "This membership no longer exists")
    enrolment, plan = loaded
    st = await MembershipCore.recalculate(session, enrolment, now=_at(step), reason="Win-back check")
    if st.status != "expired":
        return StepOutcome("skipped", "They renewed")
    business = await session.get(Business, enrolment.business_id)
    contact = await session.get(CustomerContact, enrolment.customer_contact_id)
    from platform_core.site_urls import business_site_url

    sent = await _send(session, enrolment.business_id, contact, "membership_winback",
                       [business.display_name if business else "", plan.name,
                        business_site_url(business.slug) if business else ""],
                       idem=f"membership:{enrolment.id}:{step.period_key}:winback")
    return StepOutcome("done", f"Win-back offer: {sent}")


# ---------------------------------------------------------------- fee plans
@step_handler(INSTALMENT_LADDER)  # type: ignore[untyped-decorator, unused-ignore]
async def instalment_reminder(session: AsyncSession, step: DueStep) -> StepOutcome:
    """A fee instalment is coming up, due, or late — to whoever pays (§16).
    An overdue fee is reminded, never used to remove the student."""
    from platform_core.services.payment_collect import PaymentCollectService
    from platform_core.site_urls import business_site_url

    inst = await session.get(MembershipInstalment, step.entity_id)
    if inst is None or inst.business_id != step.business_id:
        return StepOutcome("skipped", "This instalment no longer exists")
    if inst.status in ("paid", "waived", "cancelled"):
        return StepOutcome("skipped", "Paid" if inst.status == "paid" else "No longer due")
    if str(inst.due_on) != step.period_key:
        return StepOutcome("skipped", "The due date changed")
    enrolment = await session.get(MembershipEnrolment, inst.enrolment_id)
    if enrolment is None or enrolment.status in ("cancelled", "completed"):
        return StepOutcome("skipped", "The enrolment ended")
    plan = await session.get(MembershipPlan, enrolment.plan_id)
    business = await session.get(Business, step.business_id)
    assert business is not None and plan is not None
    owing = Decimal(str(inst.amount)) - Decimal(str(inst.paid_amount))
    link = step.context.get("link")
    if not link:
        req, token = await PaymentCollectService.create_request(
            session, step.business_id, business.primary_owner_identity_id, source_type="membership",
            source_id=enrolment.id, amount=owing, purpose="balance", note=f"{plan.name}: {inst.label}",
            correlation_id=str(uuid.uuid4()))
        link = business_site_url(business.slug, f"/pay/{token}")
    payer = await session.get(CustomerContact, enrolment.payer_contact_id or enrolment.customer_contact_id)
    sent = await _send(session, step.business_id, payer, "payment_due",
                       [business.display_name, f"{_inr(owing)} ({inst.label})", link],
                       idem=f"instalment:{inst.id}:{step.step_key}")
    return StepOutcome("done", f"{inst.label} reminder: {sent}", {"link": link})


# ---------------------------------------------------------------- session packs ← bookings (§8)
async def _pack_for(session: AsyncSession, booking: Booking) -> dict[str, Any] | None:
    if booking.customer_contact_id is None or booking.offering_id is None:
        return None
    from platform_core.resolvers.membership_resolver import MembershipResolver

    plan_ids = await MembershipResolver.offering_requires_membership(
        session, business_id=booking.business_id, offering_id=booking.offering_id)
    if not plan_ids:
        return None
    rows = (await session.execute(select(MembershipEnrolment, MembershipPlan).join(
        MembershipPlan, MembershipPlan.id == MembershipEnrolment.plan_id).where(
        MembershipEnrolment.business_id == booking.business_id,
        MembershipEnrolment.customer_contact_id == booking.customer_contact_id,
        MembershipEnrolment.plan_id.in_(plan_ids), MembershipPlan.plan_kind == "session_pack",
        MembershipEnrolment.deleted_at.is_(None)))).all()
    for enrolment, plan in rows:
        return {"enrolment": enrolment, "plan": plan}
    return None


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "memberships.session_pack",
    "booking.created", "booking.confirmed", "booking.completed", "booking.cancelled", "booking.no_show",
    description="A class booked on a session pack uses one session — once — by the plan's rule",
)
async def booking_sessions(session: AsyncSession, event: EventContext) -> None:
    from platform_core.exceptions import ConflictError

    business_id = event.require_business_id()
    booking_id = event.require_uuid("booking_id")
    booking = await session.get(Booking, booking_id)
    if booking is None or booking.business_id != business_id:
        return
    found = await _pack_for(session, booking)
    if found is None:
        return
    enrolment, plan = found["enrolment"], found["plan"]
    key = f"booking:{booking.id}"
    kind = event.event_type
    consume = (plan.consume_on == "booked" and kind in ("booking.created", "booking.confirmed")) or \
        (plan.consume_on == "completed" and kind == "booking.completed") or \
        (kind == "booking.no_show" and plan.no_show_consumes)
    if consume:
        try:
            await MembershipCore.consume_session(session, enrolment, source_type="booking", source_id=booking.id,
                                                 idempotency_key=key, actor_id=None,
                                                 now=min(booking.starts_at, datetime.now(timezone.utc)))
        except ConflictError:
            pass  # no session left: the booking gate refuses new ones; this one is kept as it is
    elif kind == "booking.cancelled" or (kind == "booking.no_show" and not plan.no_show_consumes):
        await MembershipCore.reverse_session(session, business_id, key,
                                             reason="Booking cancelled" if kind == "booking.cancelled"
                                             else "No-show does not count on this plan", actor_id=None)



# ---------------------------------------------------------------- session packs ← attendance check-in (§6, §8)
@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "memberships.checkin_session", "attendance.checked_in",
    description="A check-in on a pack that counts at the door uses one session — once per visit",
)
async def checkin_sessions(session: AsyncSession, event: EventContext) -> None:
    from platform_core.exceptions import ConflictError

    if event.payload.get("context") != "membership_checkin" or not event.payload.get("source_id"):
        return
    business_id = event.require_business_id()
    enrolment = await session.get(MembershipEnrolment, event.require_uuid("source_id"))
    if enrolment is None or enrolment.business_id != business_id:
        return
    plan = await session.get(MembershipPlan, enrolment.plan_id)
    if plan is None or plan.plan_kind != "session_pack" or plan.consume_on != "checkin":
        return
    visit = event.require_uuid("attendance_event_id")
    try:
        await MembershipCore.consume_session(session, enrolment, source_type="checkin", source_id=visit,
                                             idempotency_key=f"checkin:{visit}", actor_id=None)
    except ConflictError:
        pass  # the desk already refused a pack with nothing left; a race keeps the visit as recorded


# ---------------------------------------------------------------- AMC visit ← its job (§9)
@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "memberships.visit_job", "job.created",
    description="Remember which job card is doing a covered visit",
)
async def visit_job(session: AsyncSession, event: EventContext) -> None:
    from platform_core.memberships.models import MembershipServiceVisit

    if event.payload.get("source_type") != "service_contract" or not event.payload.get("source_id"):
        return
    visit = await session.get(MembershipServiceVisit, event.require_uuid("source_id"))
    if visit is None or visit.business_id != event.require_business_id() or visit.job_ref is not None:
        return
    visit.job_ref = event.require_uuid("job_id")
    await session.flush()


# ---------------------------------------------------------------- receipt when a period is paid
@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "memberships.receipt", "membership.period_paid",
    description="Tell the member their payment arrived and how long the plan now runs",
)
async def period_paid(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    enrolment = await session.get(MembershipEnrolment, event.require_uuid("enrolment_id"))
    if enrolment is None or enrolment.business_id != business_id:
        return
    plan = await session.get(MembershipPlan, enrolment.plan_id)
    business = await session.get(Business, business_id)
    if plan is None or business is None or float(plan.price_amount or 0) <= 0:
        return
    st = await MembershipCore.state(session, enrolment, plan)
    zone = await MembershipCore.tz(session, business_id, enrolment.location_id)
    contact = await session.get(CustomerContact, enrolment.customer_contact_id)
    await _send(session, business_id, contact, "membership_renewed",
                [business.display_name, plan.name, _day(st.valid_until, zone)],
                idem=f"membership_paid:{event.payload.get('period_id')}")
