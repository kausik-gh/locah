"""The owner's pre-order day (P1-10D2; Founder: Orders — "Operational UI must
distinguish prepare now, today, tomorrow, future preorder, overdue"; MD §21.1
"daily production list", "batch cooking list").

Reads the one order table by *when each order is wanted*: the board groups
open dated orders into overdue · prepare now · today · tomorrow · later, and
the production list adds up what has to be made for one day (item and
choices), with each written message beside the order it belongs to.
"""

from __future__ import annotations

import re
import uuid
from collections import OrderedDict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import (
    BusinessLocation,
    CustomerContact,
    FulfilmentJob,
    OrderLineItem,
    PaymentAttempt,
    SalesOrder,
)
from platform_core.orders.preorder import OPEN_STATUSES, bucket, day_label, when_words, zone_of

BUCKETS = (("overdue", "Overdue"), ("now", "Prepare now"), ("today", "Today"), ("tomorrow", "Tomorrow"),
           ("later", "Later"))
PAID = ("succeeded", "partially_refunded", "refunded")


async def _zone(session: AsyncSession, business_id: uuid.UUID) -> Any:
    location = (await session.execute(select(BusinessLocation).where(
        BusinessLocation.business_id == business_id, BusinessLocation.status == "active")
        .order_by(BusinessLocation.is_primary.desc(), BusinessLocation.created_at).limit(1))).scalars().first()
    return zone_of(location)


async def _paid(session: AsyncSession, business_id: uuid.UUID, ids: list[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
    if not ids:
        return {}
    rows = (await session.execute(select(
        PaymentAttempt.source_id,
        func.coalesce(func.sum(PaymentAttempt.amount - func.coalesce(PaymentAttempt.refunded_amount, 0)), 0))
        .where(PaymentAttempt.business_id == business_id, PaymentAttempt.source_type == "order",
               PaymentAttempt.source_id.in_(ids), PaymentAttempt.deleted_at.is_(None),
               PaymentAttempt.status.in_(PAID)).group_by(PaymentAttempt.source_id))).all()
    return {r[0]: Decimal(str(r[1])) for r in rows}


def _item(line: OrderLineItem) -> dict[str, Any]:
    opts = line.options or {}
    return {"title": line.title, "quantity": line.quantity, "notes": dict(opts.get("notes") or {}),
            "choices": {k: list(v) for k, v in (opts.get("choices") or {}).items()}}


async def board(session: AsyncSession, business_id: uuid.UUID, *, now: datetime | None = None,
                location_ids: list[uuid.UUID] | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    zone = await _zone(session, business_id)
    q = select(SalesOrder).where(SalesOrder.business_id == business_id, SalesOrder.deleted_at.is_(None),
                                 SalesOrder.due_at.is_not(None), SalesOrder.status.in_(OPEN_STATUSES))
    if location_ids is not None:
        q = q.where(SalesOrder.location_id.in_(location_ids))
    orders = list((await session.execute(q.order_by(SalesOrder.due_at))).scalars())
    ids = [o.id for o in orders]
    lines: dict[uuid.UUID, list[OrderLineItem]] = {}
    if ids:
        for ln in (await session.execute(select(OrderLineItem).where(OrderLineItem.order_id.in_(ids))
                                         .order_by(OrderLineItem.sort_order))).scalars():
            if ln.title != "Delivery fee":
                lines.setdefault(ln.order_id, []).append(ln)
    contacts = {c.id: c for c in (await session.execute(select(CustomerContact).where(
        CustomerContact.id.in_([o.customer_contact_id for o in orders if o.customer_contact_id])))).scalars()} \
        if orders else {}
    modes = {r[0]: r[1] for r in (await session.execute(select(FulfilmentJob.order_id, FulfilmentJob.mode).where(
        FulfilmentJob.business_id == business_id, FulfilmentJob.order_id.in_(ids))))} if ids else {}
    paid = await _paid(session, business_id, ids)
    from platform_core.stages.engine import StageEngine

    stages = await StageEngine.get(session, business_id, "orders")
    groups: dict[str, list[dict[str, Any]]] = OrderedDict((k, []) for k, _ in BUCKETS)
    for o in orders:
        assert o.due_at is not None
        b = bucket(o.due_at, o.status, now, zone)
        if b not in groups:
            continue
        contact = contacts.get(o.customer_contact_id) if o.customer_contact_id else None
        got = paid.get(o.id, Decimal("0"))
        advance = Decimal(str(o.advance_amount)) if o.advance_amount is not None else None
        groups[b].append({
            "id": str(o.id), "order_number": o.order_number, "status": o.status, "channel": o.channel,
            # The business's own step inside the status ("Packed"), when the order is at one.
            "stage": step.label if (step := stages.effective(o.stage, o.status)).custom else None,
            "due_at": o.due_at.isoformat(), "due_words": when_words(o.due_at, zone, now.astimezone(zone).date()),
            "customer": contact.display_name if contact else None, "mode": modes.get(o.id),
            "total": float(o.total_amount), "paid": float(got),
            "advance": float(advance) if advance is not None else None,
            "advance_state": None if advance is None else ("paid" if got >= advance else "awaited"),
            "items": [_item(ln) for ln in lines.get(o.id, [])],
        })
    from platform_core.models import Offering

    items = int((await session.execute(select(func.count()).select_from(Offering).where(
        Offering.business_id == business_id, Offering.deleted_at.is_(None), Offering.status == "active",
        Offering.preorder.is_not(None)))).scalar() or 0)
    today = now.astimezone(zone).date()
    return {"buckets": [{"key": k, "label": label, "orders": groups[k]} for k, label in BUCKETS],
            "count": sum(len(v) for v in groups.values()), "preorder_items": items,
            "today": today.isoformat(), "tomorrow": (today + timedelta(days=1)).isoformat()}


async def production(session: AsyncSession, business_id: uuid.UUID, day: date, *,
                     location_ids: list[uuid.UUID] | None = None) -> dict[str, Any]:
    """Everything to make for ``day``: each item with its choices added up, and
    the written messages listed with their order (a bakery's production list,
    a home kitchen's batch list)."""
    zone = await _zone(session, business_id)
    start = datetime.combine(day, time.min, tzinfo=zone)
    q = (select(OrderLineItem, SalesOrder).join(SalesOrder, SalesOrder.id == OrderLineItem.order_id)
         .where(SalesOrder.business_id == business_id, SalesOrder.deleted_at.is_(None),
                SalesOrder.status.in_(OPEN_STATUSES), SalesOrder.due_at >= start,
                SalesOrder.due_at < start + timedelta(days=1), OrderLineItem.title != "Delivery fee")
         .order_by(SalesOrder.due_at, OrderLineItem.sort_order))
    if location_ids is not None:
        q = q.where(SalesOrder.location_id.in_(location_ids))
    rows: dict[str, dict[str, Any]] = OrderedDict()
    orders: set[uuid.UUID] = set()
    for line, order in (await session.execute(q)).all():
        orders.add(order.id)
        opts = line.options or {}
        # The item with its choices (flavour, weight, cut); written messages are listed apart.
        name = re.sub(r"\s(?:·|—)\s“[^”]*”", "", line.title).strip()
        row = rows.setdefault(name, {"item": name, "quantity": 0, "orders": [], "notes": []})
        row["quantity"] += line.quantity
        row["orders"].append(order.order_number)
        for label, text in (opts.get("notes") or {}).items():
            row["notes"].append({"order_number": order.order_number, "label": label, "text": text,
                                 # the page is already that day: just the time it is wanted
                                 "due_words": _clock(order.due_at, zone) if order.due_at else None})
    today = datetime.now(timezone.utc).astimezone(zone).date()
    return {"date": day.isoformat(), "label": day_label(day, today), "orders": len(orders),
            "items": list(rows.values())}


def _clock(due: datetime, zone: Any) -> str:
    return due.astimezone(zone).strftime("%I:%M %p").lstrip("0").replace(":00 ", " ").lower()
