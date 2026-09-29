"""Dated pre-orders (P1-10D2 — MD §6.1, §21.1; Business OS Guide p.22;
Founder refinement — Orders & Customer Transactions, "Pre-orders").

A bakery's custom cake, a sweet shop's festival box, a home kitchen's batch
or a butcher's Sunday order is wanted *for a day*. The owner sets, per item:

* whether it **needs** a date (made to order) or **may** take one;
* how much notice it needs (``lead_hours``) and an optional next-day
  ``cutoff`` ("order by 6 pm for tomorrow");
* the ``ready_times`` a customer can pick, how far ahead (``max_days``), an
  optional festival ``window`` (order until …, ready between … and …) and a
  ``daily_limit`` (how many the kitchen can make for one day);
* the ``advance`` it asks (a % of the line or a fixed amount per piece) and
  until when the customer may cancel (``cancel_hours`` before it is due).

The server decides — for the website, WhatsApp and a phone order alike, in
this one place — which dates are open, whether a chosen date is allowed, the
advance, and the terms the customer confirms. The order keeps a snapshot of
those terms, so a later change to the rules never rewrites an order already
taken. The owner then works the orders by *when they are wanted*: overdue,
prepare now, today, tomorrow, later — and a production list for a day.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ValidationError
from platform_core.models import BusinessLocation, Offering, OrderLineItem, SalesOrder

MODES = ("required", "optional")
DEFAULT_READY = ("17:00",)
OPEN_STATUSES = ("pending", "accepted", "preparing", "ready")
# "Prepare now": due within this many hours (and not ready yet).
PREPARE_NOW_HOURS = 3


def _bad(fld: str, message: str) -> ValidationError:
    return ValidationError(message, details={"field": fld, "errors": [{"field": fld, "message": message}]})


def _time(value: Any, fld: str) -> time:
    try:
        return time.fromisoformat(str(value).strip()[:5])
    except ValueError:
        raise _bad(fld, "Times are written like 17:00") from None


def _date(value: Any, fld: str) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise _bad(fld, "Dates are written like 2026-10-04") from None


def _int(value: Any, fld: str, low: int, high: int, default: int | None) -> int | None:
    if value in (None, ""):
        return default
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise _bad(fld, "Enter a whole number") from None
    if not low <= n <= high:
        raise _bad(fld, f"Between {low} and {high}")
    return n


# ---------------------------------------------------------------- the owner's rules
def clean_rules(flow: str, raw: Any) -> dict[str, Any] | None:
    """Validate an offering's pre-order rules; None switches ordering ahead off."""
    if raw in (None, "", {}) or (isinstance(raw, dict) and raw.get("mode") in (None, "", "none")):
        return None
    if flow != "cart":
        raise _bad("preorder", "Only items customers put in a basket can be ordered ahead")
    if not isinstance(raw, dict):
        raise _bad("preorder", "Pre-order rules must be a set of fields")
    mode = str(raw.get("mode"))
    if mode not in MODES:
        raise _bad("preorder.mode", "Choose whether it needs a date or may take one")
    cutoff = _time(raw["cutoff"], "preorder.cutoff") if raw.get("cutoff") else None
    times = raw.get("ready_times") or list(DEFAULT_READY)
    if not isinstance(times, list) or not 1 <= len(times) <= 8:
        raise _bad("preorder.ready_times", "Give between one and eight ready times")
    ready = sorted({_time(t, "preorder.ready_times").strftime("%H:%M") for t in times})
    window_raw = raw.get("window") or {}
    window = {k: _date(window_raw.get(k), f"preorder.window.{k}") for k in ("order_until", "ready_from", "ready_until")}
    if window["ready_from"] and window["ready_until"] and window["ready_from"] > window["ready_until"]:
        raise _bad("preorder.window", "The window ends before it starts")
    if window["order_until"] and window["ready_until"] and window["order_until"] > window["ready_until"]:
        raise _bad("preorder.window", "Orders cannot close after the last ready day")
    advance = None
    adv = raw.get("advance") or {}
    if adv.get("type") not in (None, "", "none"):
        if adv.get("type") not in ("percent", "fixed"):
            raise _bad("preorder.advance", "The advance is a percentage or a fixed amount")
        try:
            value = Decimal(str(adv.get("value"))).quantize(Decimal("0.01"))
        except InvalidOperation:
            raise _bad("preorder.advance", "Enter the advance as a number") from None
        if value <= 0 or (adv["type"] == "percent" and value > 100) or value > Decimal("10000000"):
            raise _bad("preorder.advance", "Enter a percentage up to 100, or an amount above ₹0")
        advance = {"type": adv["type"], "value": str(value)}
    return {
        "mode": mode,
        "lead_hours": _int(raw.get("lead_hours"), "preorder.lead_hours", 0, 720, 24),
        "cutoff": cutoff.strftime("%H:%M") if cutoff else None,
        "ready_times": ready,
        "max_days": _int(raw.get("max_days"), "preorder.max_days", 1, 180, 30),
        "window": {k: v.isoformat() if v else None for k, v in window.items()},
        "daily_limit": _int(raw.get("daily_limit"), "preorder.daily_limit", 1, 10000, None),
        "advance": advance,
        "cancel_hours": _int(raw.get("cancel_hours"), "preorder.cancel_hours", 0, 720, None),
    }


@dataclass(frozen=True)
class Rules:
    mode: str
    lead_hours: int
    cutoff: time | None
    ready_times: tuple[time, ...]
    max_days: int
    order_until: date | None
    ready_from: date | None
    ready_until: date | None
    daily_limit: int | None
    advance: dict[str, str] | None
    cancel_hours: int | None

    @staticmethod
    def of(raw: dict[str, Any] | None) -> Rules | None:
        if not raw or raw.get("mode") not in MODES:
            return None
        w = raw.get("window") or {}
        return Rules(
            mode=str(raw["mode"]), lead_hours=int(raw.get("lead_hours") or 0),
            cutoff=time.fromisoformat(raw["cutoff"]) if raw.get("cutoff") else None,
            ready_times=tuple(time.fromisoformat(t) for t in (raw.get("ready_times") or DEFAULT_READY)),
            max_days=int(raw.get("max_days") or 30),
            order_until=date.fromisoformat(w["order_until"]) if w.get("order_until") else None,
            ready_from=date.fromisoformat(w["ready_from"]) if w.get("ready_from") else None,
            ready_until=date.fromisoformat(w["ready_until"]) if w.get("ready_until") else None,
            daily_limit=int(raw["daily_limit"]) if raw.get("daily_limit") else None,
            advance=raw.get("advance"), cancel_hours=raw.get("cancel_hours"))


def zone_of(location: BusinessLocation | None) -> ZoneInfo:
    try:
        return ZoneInfo((location.timezone if location else None) or "Asia/Kolkata")
    except Exception:  # noqa: BLE001 — a bad stored zone falls back to India
        return ZoneInfo("Asia/Kolkata")


def _open_on(location: BusinessLocation | None, day: date) -> bool:
    """Opening hours saved as {"mon": [["09:00", "18:00"]], ...}; no hours saved = open every day."""
    hours = (location.hours if location else None) or {}
    if not hours:
        return True
    return bool(hours.get(day.strftime("%a").lower()[:3]))


def advance_for(rules: Rules, quantity: int, line_total: Decimal) -> Decimal:
    if not rules.advance:
        return Decimal("0")
    value = Decimal(rules.advance["value"])
    if rules.advance["type"] == "percent":
        raw = line_total * value / Decimal(100)
    else:
        raw = value * quantity
    return min(raw, line_total).quantize(Decimal("1"), ROUND_CEILING)


def day_label(day: date, today: date) -> str:
    if day == today:
        return "Today"
    if day == today + timedelta(days=1):
        return "Tomorrow"
    return f"{day.strftime('%a')} {day.day} {day.strftime('%b')}"


def when_words(due: datetime, zone: ZoneInfo, today: date | None = None) -> str:
    local = due.astimezone(zone)
    today = today or datetime.now(timezone.utc).astimezone(zone).date()
    hour = local.strftime("%I:%M %p").lstrip("0").replace(":00 ", " ").lower()
    return f"{day_label(local.date(), today)}, {hour}"


# ---------------------------------------------------------------- one line, one plan
@dataclass
class Line:
    offering: Offering
    rules: Rules | None
    quantity: int
    line_total: Decimal


@dataclass
class Plan:
    needed: bool = False
    offered: bool = False
    earliest: datetime | None = None
    latest: datetime | None = None
    dates: list[dict[str, Any]] = field(default_factory=list)
    due_at: datetime | None = None
    advance: Decimal = Decimal("0")
    terms: dict[str, Any] = field(default_factory=dict)

    def public(self, zone: ZoneInfo) -> dict[str, Any]:
        return {
            "needed": self.needed, "offered": self.offered,
            "earliest": self.earliest.isoformat() if self.earliest else None,
            "earliest_words": when_words(self.earliest, zone) if self.earliest else None,
            "dates": self.dates, "advance": float(self.advance),
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "due_words": when_words(self.due_at, zone) if self.due_at else None,
            "cancel_hours": self.terms.get("cancel_hours"),
        }


async def _booked(session: AsyncSession, business_id: Any, offering_id: Any, day: date, zone: ZoneInfo,
                  exclude: Any = None) -> int:
    """How many of this item are already promised for that day."""
    start = datetime.combine(day, time.min, tzinfo=zone)
    q = (select(func.coalesce(func.sum(OrderLineItem.quantity), 0))
         .join(SalesOrder, SalesOrder.id == OrderLineItem.order_id)
         .where(SalesOrder.business_id == business_id, OrderLineItem.offering_id == offering_id,
                SalesOrder.deleted_at.is_(None), SalesOrder.status.notin_(("cancelled", "rejected")),
                SalesOrder.due_at >= start, SalesOrder.due_at < start + timedelta(days=1)))
    if exclude is not None:
        q = q.where(SalesOrder.id != exclude)
    return int((await session.execute(q)).scalar() or 0)


def _day_allowed(rules: list[Rules], day: date, today: date, now_local: datetime) -> bool:
    for r in rules:
        if r.cutoff is not None:
            first = today + timedelta(days=1 if now_local.time() < r.cutoff else 2)
            if day < first:
                return False
        if day > today + timedelta(days=r.max_days):
            return False
        if r.ready_from and day < r.ready_from:
            return False
        if r.ready_until and day > r.ready_until:
            return False
        if r.order_until and today > r.order_until:
            return False
    return True


async def plan(session: AsyncSession, *, business_id: Any, location: BusinessLocation | None, lines: list[Line],
               requested: datetime | None = None, now: datetime | None = None, days: int = 14,
               exclude_order: Any = None, require: bool = True) -> Plan:
    """Which dates are open, whether ``requested`` is allowed (raises when not),
    the advance and the terms — the same answer for every channel."""
    zone = zone_of(location)
    now = now or datetime.now(timezone.utc)
    now_local = now.astimezone(zone)
    today = now_local.date()
    ruled = [ln for ln in lines if ln.rules is not None]
    rules = [ln.rules for ln in ruled if ln.rules is not None]
    out = Plan(needed=any(r.mode == "required" for r in rules), offered=bool(rules))
    if not rules and requested is None:
        return out
    lead = max((r.lead_hours for r in rules), default=0)
    earliest_at = now + timedelta(hours=lead)
    times = sorted(set.intersection(*[set(r.ready_times) for r in rules])) if rules else [time(17, 0)]
    if not times:  # items with no ready time in common: the most restrictive item's times
        times = sorted(max(rules, key=lambda r: r.lead_hours).ready_times)
    horizon = min((r.max_days for r in rules), default=30)
    limited = [ln for ln in ruled if ln.rules is not None and ln.rules.daily_limit]

    async def full(day: date) -> bool:
        for ln in limited:
            assert ln.rules is not None and ln.rules.daily_limit is not None
            if await _booked(session, business_id, ln.offering.id, day, zone, exclude_order) + ln.quantity > ln.rules.daily_limit:
                return True
        return False

    for d in range(0, horizon + 1):
        day = today + timedelta(days=d)
        if not _day_allowed(rules, day, today, now_local) or not _open_on(location, day):
            continue
        slots = [t for t in times if datetime.combine(day, t, tzinfo=zone) >= earliest_at]
        if not slots:
            continue
        is_full = await full(day)
        if out.earliest is None and not is_full:
            out.earliest = datetime.combine(day, slots[0], tzinfo=zone)
        if len(out.dates) < days:
            out.dates.append({"date": day.isoformat(), "label": day_label(day, today),
                              "times": [t.strftime("%H:%M") for t in slots], "full": is_full})
    if out.dates:
        last = out.dates[-1]
        out.latest = datetime.combine(date.fromisoformat(last["date"]), time.fromisoformat(last["times"][-1]),
                                      tzinfo=zone)

    advance = sum((advance_for(ln.rules, ln.quantity, ln.line_total) for ln in ruled if ln.rules), Decimal("0"))
    cancel = max((r.cancel_hours for r in rules if r.cancel_hours is not None), default=None)
    out.terms = {"lead_hours": lead, "cancel_hours": cancel, "advance": str(advance),
                 "items": [{"offering_id": str(ln.offering.id), "title": ln.offering.title,
                            "rules": ln.offering.preorder} for ln in ruled]}
    out.advance = advance

    if requested is None:
        if out.needed and require:
            raise _bad("due", "Choose the day you need it" + (
                f" — the earliest is {when_words(out.earliest, zone, today)}" if out.earliest else ""))
        return out

    due = requested if requested.tzinfo else requested.replace(tzinfo=zone)
    local = due.astimezone(zone)
    if due < now:
        raise _bad("due", "That time has already passed")
    if rules:
        if due < earliest_at:
            raise _bad("due", f"This needs {lead} hours' notice — the earliest is "
                              f"{when_words(out.earliest, zone, today) if out.earliest else 'not available'}")
        if not _day_allowed(rules, local.date(), today, now_local):
            raise _bad("due", "That day is not open for these items" + (
                f" — the earliest is {when_words(out.earliest, zone, today)}" if out.earliest else ""))
        if not _open_on(location, local.date()):
            raise _bad("due", "The business is closed that day")
        if local.time().replace(second=0, microsecond=0) not in times:
            raise _bad("due", "Choose one of the ready times: " + ", ".join(t.strftime("%H:%M") for t in times))
        for ln in limited:
            assert ln.rules is not None and ln.rules.daily_limit is not None
            # One count at a time per item and day, so two orders never both take the last one.
            key = zlib.crc32(f"{business_id}:{ln.offering.id}:{local.date()}".encode())
            await session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": key})
            taken = await _booked(session, business_id, ln.offering.id, local.date(), zone, exclude_order)
            if taken + ln.quantity > ln.rules.daily_limit:
                left = max(0, ln.rules.daily_limit - taken)
                raise _bad("due", f"{ln.offering.title}: {day_label(local.date(), today)} is full"
                                  + (f" (only {left} left)" if left else "") + " — choose another day")
    out.due_at = due
    out.terms["due_at"] = due.isoformat()
    return out


async def lines_for(session: AsyncSession, business_id: Any, raw: list[tuple[Any, int, Decimal]]) -> list[Line]:
    """(offering_id, quantity, line_total) → Lines with each offering's rules."""
    ids = list({oid for oid, _, _ in raw})
    offerings = {o.id: o for o in (await session.execute(select(Offering).where(
        Offering.business_id == business_id, Offering.id.in_(ids)))).scalars()} if ids else {}
    out = []
    for oid, qty, total in raw:
        o = offerings.get(oid)
        if o is None:
            continue
        out.append(Line(o, Rules.of(o.preorder), int(qty), Decimal(str(total))))
    return out


def parse_requested(raw: Any, zone: ZoneInfo) -> datetime | None:
    """``{"date": "2026-10-04", "time": "17:00"}`` or an ISO datetime."""
    if raw in (None, "", {}):
        return None
    try:
        if isinstance(raw, dict):
            day = date.fromisoformat(str(raw.get("date"))[:10])
            at = time.fromisoformat(str(raw.get("time") or "17:00")[:5])
            return datetime.combine(day, at, tzinfo=zone)
        value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return value if value.tzinfo else value.replace(tzinfo=zone)
    except ValueError:
        raise _bad("due", "Choose a day and a time") from None


# ---------------------------------------------------------------- the owner's day
def bucket(due: datetime | None, status: str, now: datetime, zone: ZoneInfo) -> str:
    """overdue · now (prepare now) · today · tomorrow · later — or none (not dated)."""
    if due is None:
        return "none"
    if due < now and status not in ("completed", "cancelled", "rejected"):
        return "overdue"
    local, today = due.astimezone(zone).date(), now.astimezone(zone).date()
    if status in ("pending", "accepted") and due - now <= timedelta(hours=PREPARE_NOW_HOURS):
        return "now"
    if local == today:
        return "today"
    if local == today + timedelta(days=1):
        return "tomorrow"
    return "later"
