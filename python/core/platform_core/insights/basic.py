"""Basic insights from real data only (IS-01; MD §26.3 P1-10, §228 "Dashboards
computed from real data only"; First Launch §12.1 "Core Workspace Insights").

Four numbers for a period — sales, orders, bookings, money received — each
counted from the records behind it, within the viewer's permissions and
location scope (the ORM location filter runs on the order, booking and bill
queries), each linking to the page where the work happens. A tool that is
not switched on is named as such, never shown as a zero; a tool the viewer
may not see says so. Trends, comparisons and cohorts are the later Analytics
module (First Launch §12.2) and are not computed here.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import Booking, InvoicingDocument, SalesOrder

IST = ZoneInfo("Asia/Kolkata")
PERIODS = {"today": "Today", "7d": "Last 7 days", "month": "This month"}
ENDED_ORDER = ("cancelled", "rejected")
SALE_KINDS = ("tax_invoice", "bill_of_supply", "bill")
CHANNEL_WORDS = {"web": "Website", "whatsapp": "WhatsApp", "pos": "Counter", "phone": "Phone",
                 "workspace": "Entered by team", "marketplace": "Marketplace"}


def rupees(amount: Decimal | float | int | None) -> str:
    """Whole rupees with Indian digit grouping (₹1,23,456)."""
    digits = str(int(Decimal(str(amount or 0)).quantize(Decimal("1"))))
    neg = digits.startswith("-")
    digits = digits.lstrip("-")
    head, tail = digits[:-3], digits[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return ("-" if neg else "") + "₹" + ",".join([g for g in [head, *groups] if g] + [tail])


def window(period: str, now: datetime) -> tuple[date, date]:
    """First day and the day after the last, in India time."""
    today = now.astimezone(IST).date()
    if period == "7d":
        return today - timedelta(days=6), today + timedelta(days=1)
    if period == "month":
        return today.replace(day=1), today + timedelta(days=1)
    return today, today + timedelta(days=1)


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


class _Card:
    @staticmethod
    def off(key: str, title: str, reason: str, href: str, state: str) -> dict[str, Any]:
        return {"key": key, "title": title, "state": state, "value": None, "note": reason, "detail": [],
                "href": href}


async def summary(session: AsyncSession, business_id: uuid.UUID, *, period: str,
                  can: Callable[[str, str], bool], has: Callable[[str], bool], business_wide: bool,
                  now: datetime | None = None) -> dict[str, Any]:
    """``can(perm, module)``: permitted and switched on; ``has(module)``: switched on;
    ``business_wide``: the viewer sees every location (money received is
    counted business-wide, so a location-scoped viewer is not shown it)."""
    if period not in PERIODS:
        period = "today"
    now = now or datetime.now(timezone.utc)
    first, until = window(period, now)
    start = datetime.combine(first, time.min, tzinfo=IST)
    end = datetime.combine(until, time.min, tzinfo=IST)
    cards: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []

    def gate(key: str, title: str, perm: str, module: str, href: str, tool: str) -> bool:
        if not has(module):
            missing.append({"key": key, "title": title, "tool": tool})
            return False
        if not can(perm, module):
            cards.append(_Card.off(key, title, f"Your role does not include {tool.lower()}.", href, "no_permission"))
            return False
        return True

    # ---------------------------------------------------------------- sales (issued bills)
    if gate("sales", "Sales", "invoices.read", "invoicing", "/invoices", "Bills & invoices"):
        rows = (await session.execute(
            select(InvoicingDocument.doc_kind, InvoicingDocument.source, func.count(),
                   func.coalesce(func.sum(InvoicingDocument.grand_total), 0))
            .where(InvoicingDocument.business_id == business_id, InvoicingDocument.status == "issued",
                   InvoicingDocument.issue_date >= first, InvoicingDocument.issue_date < until,
                   InvoicingDocument.doc_kind.in_((*SALE_KINDS, "credit_note")))
            .group_by(InvoicingDocument.doc_kind, InvoicingDocument.source))).all()
        billed = sum((Decimal(str(r[3])) for r in rows if r[0] in SALE_KINDS), Decimal(0))
        count = sum(int(r[2]) for r in rows if r[0] in SALE_KINDS)
        counter = sum((Decimal(str(r[3])) for r in rows if r[0] in SALE_KINDS and r[1] == "pos"), Decimal(0))
        credited = sum((Decimal(str(r[3])) for r in rows if r[0] == "credit_note"), Decimal(0))
        detail = []
        if count:
            if counter and billed - counter:  # the split only says something when there are both
                detail.append({"label": "At the counter", "value": rupees(counter)})
                detail.append({"label": "Other bills", "value": rupees(billed - counter)})
            elif counter:
                detail.append({"label": "All at the counter", "value": rupees(counter)})
            if credited:
                detail.append({"label": "Credit notes (returns)", "value": rupees(-credited)})
        cards.append({"key": "sales", "title": "Sales", "state": "ok" if count else "no_data",
                      "value": rupees(billed - credited) if count else None,
                      "note": _plural(count, "bill") if count else "No bills issued in this period.",
                      "detail": detail, "href": "/invoices", "go": "Open bills"})

    # ---------------------------------------------------------------- orders
    if gate("orders", "Orders", "orders.read", "orders", "/orders", "Orders"):
        rows = (await session.execute(
            select(SalesOrder.channel, SalesOrder.status, func.count(),
                   func.coalesce(func.sum(SalesOrder.total_amount), 0))
            .where(SalesOrder.business_id == business_id, SalesOrder.deleted_at.is_(None),
                   SalesOrder.created_at >= start, SalesOrder.created_at < end)
            .group_by(SalesOrder.channel, SalesOrder.status))).all()
        live = [r for r in rows if r[1] not in ENDED_ORDER]
        n = sum(int(r[2]) for r in live)
        value = sum((Decimal(str(r[3])) for r in live), Decimal(0))
        cancelled = sum(int(r[2]) for r in rows if r[1] in ENDED_ORDER)
        by_channel: dict[str, int] = {}
        for r in live:
            by_channel[r[0]] = by_channel.get(r[0], 0) + int(r[2])
        detail = [{"label": CHANNEL_WORDS.get(c, c.title()), "value": _plural(k, "order")}
                  for c, k in sorted(by_channel.items(), key=lambda x: -x[1])]
        if cancelled:
            detail.append({"label": "Cancelled or declined", "value": _plural(cancelled, "order")})
        cards.append({"key": "orders", "title": "Orders", "state": "ok" if n or cancelled else "no_data",
                      "value": rupees(value) if n else None,
                      "note": _plural(n, "order") if n or cancelled else "No orders placed in this period.",
                      "detail": detail, "href": "/orders", "go": "Open orders"})

    # ---------------------------------------------------------------- bookings
    if gate("bookings", "Bookings", "bookings.read", "bookings", "/bookings", "Bookings"):
        rows = (await session.execute(
            select(Booking.status, func.count())
            .where(Booking.business_id == business_id, Booking.deleted_at.is_(None),
                   Booking.starts_at >= start, Booking.starts_at < end)
            .group_by(Booking.status))).all()
        by = {r[0]: int(r[1]) for r in rows}
        held = sum(v for s, v in by.items() if s not in ("cancelled", "rejected", "no_show"))
        detail = []
        if by.get("completed") or by.get("checked_in"):
            detail.append({"label": "Came in", "value": str(by.get("completed", 0) + by.get("checked_in", 0))})
        if by.get("pending"):
            detail.append({"label": "Waiting for you to confirm", "value": str(by["pending"])})
        if by.get("no_show"):
            detail.append({"label": "Did not come", "value": str(by["no_show"])})
        if by.get("cancelled") or by.get("rejected"):
            detail.append({"label": "Cancelled or declined",
                           "value": str(by.get("cancelled", 0) + by.get("rejected", 0))})
        cards.append({"key": "bookings", "title": "Bookings", "state": "ok" if by else "no_data",
                      "value": str(held) if by else None,
                      "note": _plural(held, "booking") + " in this period" if by else "No bookings in this period.",
                      "detail": detail, "href": "/bookings", "go": "Open bookings"})

    # ---------------------------------------------------------------- money received
    if gate("collections", "Money received", "payments.read", "payments", "/payments", "Payments"):
        if not business_wide:
            cards.append(_Card.off("collections", "Money received",
                                   "Money received is counted for the whole business, so it is shown to people "
                                   "who see every location.", "/payments", "whole_business_only"))
        else:
            from platform_core.services.payment_collect import PaymentCollectService

            got = await PaymentCollectService.received(session, business_id, first, until)
            detail = [{"label": label, "value": rupees(got[k])} for k, label in (
                ("bills_and_counter", "Bills and the counter"), ("links_and_recorded", "Orders, bookings and plans"),
                ("khata", "Khata payments")) if got[k]]
            cards.append({"key": "collections", "title": "Money received",
                          "state": "ok" if got["total"] else "no_data",
                          "value": rupees(got["total"]) if got["total"] else None,
                          "note": "Verified payments only" if got["total"] else "No money received in this period.",
                          "detail": detail, "href": "/payments", "go": "Open payments"})

    return {
        "period": {"key": period, "label": PERIODS[period], "from": first.isoformat(),
                   "to": (until - timedelta(days=1)).isoformat()},
        "periods": [{"key": k, "label": v} for k, v in PERIODS.items()],
        "cards": cards,
        "not_switched_on": missing,
    }
