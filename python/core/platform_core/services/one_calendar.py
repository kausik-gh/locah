"""One calendar (OM-21; MD §22 "Solo professionals … one calendar").

Everything with a time on it for the days ahead, in one list: bookings,
orders wanted for a day, enquiries to follow up, memberships ending and
licences or filings due. Each kind appears only when its tool is on and the
viewer may see it; the ORM location filter applies to bookings and orders.
It reads the records where the work happens and links back to them — it is
not a second schedule.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import Booking, ComplianceItem, CustomerContact, Lead, MembershipEnrolment, SalesOrder

IST = ZoneInfo("Asia/Kolkata")
OPEN_BOOKING = ("pending", "confirmed", "checked_in")
OPEN_ORDER = ("pending", "accepted", "preparing", "ready")


def _day_words(d: date, today: date) -> str:
    if d == today:
        return "Today"
    if d == today + timedelta(days=1):
        return "Tomorrow"
    return d.strftime("%A, %d %b").replace(" 0", " ")


def _clock(at: datetime) -> str:
    return at.astimezone(IST).strftime("%I:%M %p").lstrip("0").replace(":00 ", " ").lower()


async def agenda(session: AsyncSession, business_id: uuid.UUID, *, days: int,
                 can: Callable[[str, str], bool], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(IST).date()
    start = datetime.combine(today, time.min, tzinfo=IST)
    end = start + timedelta(days=days)
    items: list[dict[str, Any]] = []
    names: dict[uuid.UUID, str] = {}

    async def name(cid: uuid.UUID | None) -> str | None:
        if cid is None:
            return None
        if cid not in names:
            c = await session.get(CustomerContact, cid)
            names[cid] = c.display_name if c is not None and c.deleted_at is None else ""
        return names[cid] or None

    if can("bookings.read", "bookings"):
        for b in (await session.execute(select(Booking).where(
                Booking.business_id == business_id, Booking.deleted_at.is_(None), Booking.status.in_(OPEN_BOOKING),
                Booking.starts_at >= start, Booking.starts_at < end).order_by(Booking.starts_at))).scalars():
            who = await name(b.customer_contact_id)
            items.append({"kind": "booking", "at": b.starts_at.isoformat(), "time": _clock(b.starts_at),
                          "title": b.title or "Booking", "who": who,
                          "note": "Waiting for you to confirm" if b.status == "pending" else None,
                          "href": f"/bookings/{b.id}"})
    if can("orders.read", "orders"):
        for o in (await session.execute(select(SalesOrder).where(
                SalesOrder.business_id == business_id, SalesOrder.deleted_at.is_(None),
                SalesOrder.status.in_(OPEN_ORDER), SalesOrder.due_at >= start, SalesOrder.due_at < end)
                .order_by(SalesOrder.due_at))).scalars():
            assert o.due_at is not None
            items.append({"kind": "order", "at": o.due_at.isoformat(), "time": _clock(o.due_at),
                          "title": f"Order {o.order_number} wanted", "who": await name(o.customer_contact_id),
                          "note": None, "href": f"/orders/{o.id}"})
    if can("leads.read", "leads"):
        for lead in (await session.execute(select(Lead).where(
                Lead.business_id == business_id, Lead.deleted_at.is_(None), Lead.status.notin_(("won", "lost")),
                Lead.next_follow_up_at.is_not(None), Lead.next_follow_up_at < end)
                .order_by(Lead.next_follow_up_at))).scalars():
            assert lead.next_follow_up_at is not None
            at = max(lead.next_follow_up_at, start)
            items.append({"kind": "follow_up", "at": at.isoformat(),
                          "time": "Overdue" if lead.next_follow_up_at < start else _clock(lead.next_follow_up_at),
                          "title": "Follow up", "who": lead.display_name, "note": None, "href": f"/leads/{lead.id}"})
    if can("memberships.read", "memberships"):
        for e in (await session.execute(select(MembershipEnrolment).where(
                MembershipEnrolment.business_id == business_id, MembershipEnrolment.deleted_at.is_(None),
                MembershipEnrolment.status == "active", MembershipEnrolment.ends_at >= start,
                MembershipEnrolment.ends_at < end).order_by(MembershipEnrolment.ends_at))).scalars():
            assert e.ends_at is not None
            items.append({"kind": "membership", "at": e.ends_at.isoformat(), "time": "All day",
                          "title": "Membership ends", "who": await name(e.customer_contact_id),
                          "note": "Renews automatically" if e.auto_renew else "Not set to renew",
                          "href": f"/memberships/{e.id}"})
    if can("compliance.read", "compliance"):
        for c in (await session.execute(select(ComplianceItem).where(
                ComplianceItem.business_id == business_id, ComplianceItem.status == "active",
                ComplianceItem.due_on < end.astimezone(IST).date()).order_by(ComplianceItem.due_on))).scalars():
            due = max(c.due_on, today)
            items.append({"kind": "due", "at": datetime.combine(due, time.min, tzinfo=IST).isoformat(),
                          "time": "Overdue" if c.due_on < today else "All day", "title": c.title, "who": None,
                          "note": "Licence or filing due", "href": "/compliance"})
    items.sort(key=lambda x: (x["at"], x["time"] != "Overdue"))
    groups: list[dict[str, Any]] = []
    for it in items:
        d = datetime.fromisoformat(it["at"]).astimezone(IST).date()
        if not groups or groups[-1]["date"] != d.isoformat():
            groups.append({"date": d.isoformat(), "label": _day_words(d, today), "items": []})
        groups[-1]["items"].append(it)
    return {"from": today.isoformat(), "days": days, "days_list": groups, "count": len(items)}
