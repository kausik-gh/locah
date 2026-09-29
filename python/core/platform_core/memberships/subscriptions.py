"""Recurring deliveries (Founder refinement — Memberships §9–§15).

The subscription is the schedule; Orders owns each day's order. At the
business's cutoff (9 pm by default) tomorrow is decided — running
subscriptions, minus pauses, minus skips, with one-day quantity changes — and
each delivery becomes a real order (channel `subscription`) that Kitchen,
Inventory and Dispatch act on like any other. The owner never recreates them.

Money is never counted twice: a generated order carries the goods and the
quantities at zero value ("covered by subscription"). A prepaid subscriber
already paid for the period; a postpaid one is billed on the khata at month
end for what was actually delivered — skipped days are never charged.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ValidationError
from platform_core.memberships.lifecycle import paused_on
from platform_core.memberships.models import MembershipDelivery, MembershipDeliveryOverride, MembershipFreeze
from platform_core.memberships.service import MembershipCore
from platform_core.models import MembershipEnrolment, MembershipPlan, Offering
from platform_core.services.outbox import OutboxService


def _err(field: str, message: str) -> ValidationError:
    return ValidationError(message, details={"errors": [{"field": field, "message": message}], "field": field})


@dataclass(frozen=True)
class Occurrence:
    enrolment_id: uuid.UUID
    on_date: date
    slot: str
    quantity: Decimal
    status: str  # deliver | skipped | paused | not_covered
    why: str


def _hm(value: str) -> time:
    hh, mm = (int(x) for x in value.split(":"))
    return time(hh, mm)


def decide_day(delivery: dict[str, Any], *, on_date: date, overrides: list[MembershipDeliveryOverride],
               freezes: list[MembershipFreeze], covered: bool, enrolment_id: uuid.UUID) -> Occurrence | None:
    """Pure: what happens for one subscriber on one day. None = not a delivery day."""
    if on_date.weekday() not in delivery.get("days", list(range(7))):
        return None
    slot = str(delivery.get("slot") or "")
    usual = Decimal(str(delivery.get("quantity") or 1))
    live = [o for o in overrides if o.cancelled_at is None and o.on_date == on_date and o.slot == slot]
    pause = paused_on([_fz(f) for f in freezes], on_date)
    if pause is not None:
        return Occurrence(enrolment_id, on_date, slot, Decimal("0"), "paused", "Paused")
    if any(o.kind == "skip" for o in live):
        return Occurrence(enrolment_id, on_date, slot, Decimal("0"), "skipped", "Skipped by the customer")
    if not covered:
        return Occurrence(enrolment_id, on_date, slot, Decimal("0"), "not_covered", "Not paid for this day")
    qty = next((Decimal(str(o.quantity)) for o in live if o.kind == "quantity"), usual)
    return Occurrence(enrolment_id, on_date, slot, qty, "deliver", "Delivering")


def _fz(f: MembershipFreeze) -> Any:
    from platform_core.memberships.lifecycle import FreezeRow

    return FreezeRow(f.starts_on, f.ends_on, f.kind, f.status)


class SubscriptionService:
    # ------------------------------------------------------------------ the customer's changes (§11–§12)
    @staticmethod
    async def _cutoff_passed(session: AsyncSession, enrolment: MembershipEnrolment, on_date: date,
                             now: datetime | None) -> bool:
        zone = ZoneInfo(await MembershipCore.tz(session, enrolment.business_id, enrolment.location_id))
        cutoff = _hm(str((enrolment.delivery or {}).get("cutoff") or "21:00"))
        deadline = datetime.combine(on_date - timedelta(days=1), cutoff, zone)
        return (now or datetime.now(timezone.utc)) >= deadline

    @staticmethod
    async def _generated(session: AsyncSession, enrolment_id: uuid.UUID, on_date: date, slot: str) -> bool:
        return (await session.execute(select(MembershipDelivery.id).where(
            MembershipDelivery.enrolment_id == enrolment_id, MembershipDelivery.on_date == on_date,
            MembershipDelivery.slot == slot))).first() is not None

    @staticmethod
    async def change_day(session: AsyncSession, enrolment: MembershipEnrolment, *, on_date: date,
                         kind: str, quantity: Any = None, actor_id: uuid.UUID | None, channel: str,
                         now: datetime | None = None) -> MembershipDeliveryOverride | None:
        """Skip one day, or change its quantity for that day only (the usual
        schedule is untouched). After the cutoff the day is already decided:
        the business's policy is shown instead of a silent change."""
        plan = await MembershipCore.plan_of(session, enrolment)
        if plan.plan_kind != "recurring_delivery" or not enrolment.delivery:
            raise ConflictError("This is not a delivery subscription")
        if enrolment.status in ("cancelled", "expired", "completed"):
            raise ConflictError("This subscription is not running")
        if kind not in ("skip", "quantity", "restore"):
            raise _err("kind", "Skip, change quantity or restore")
        slot = str(enrolment.delivery.get("slot") or "")
        if await SubscriptionService._cutoff_passed(session, enrolment, on_date, now) or \
                await SubscriptionService._generated(session, enrolment.id, on_date, slot):
            raise ConflictError(
                f"Tomorrow's deliveries were finalised at {enrolment.delivery.get('cutoff', '21:00')}. "
                "Call or message the business to change this one.", details={"code": "after_cutoff"})
        live = (await session.execute(select(MembershipDeliveryOverride).where(
            MembershipDeliveryOverride.enrolment_id == enrolment.id, MembershipDeliveryOverride.on_date == on_date,
            MembershipDeliveryOverride.slot == slot, MembershipDeliveryOverride.cancelled_at.is_(None))
            .with_for_update())).scalars().first()
        if live is not None:
            live.cancelled_at = datetime.now(timezone.utc)
            await session.flush()
        row = None
        if kind != "restore":
            qty = None
            if kind == "quantity":
                qty = Decimal(str(quantity or 0))
                if qty <= 0 or qty != qty.to_integral_value():
                    raise _err("quantity", "Quantity is a whole number of the item")
            row = MembershipDeliveryOverride(business_id=enrolment.business_id, enrolment_id=enrolment.id,
                                             on_date=on_date, slot=slot, kind=kind, quantity=qty, channel=channel,
                                             created_by=actor_id)
            session.add(row)
            await session.flush()
        await OutboxService.publish(session, event_type="membership.delivery_changed",
                                    business_id=enrolment.business_id,
                                    payload={"enrolment_id": str(enrolment.id), "on_date": str(on_date),
                                             "kind": kind, "quantity": str(quantity) if quantity else None,
                                             "channel": channel})
        return row

    @staticmethod
    async def change_future(session: AsyncSession, enrolment: MembershipEnrolment, *, quantity: Any = None,
                            days: list[int] | None = None, actor_id: uuid.UUID | None) -> dict[str, Any]:
        """'Change future deliveries': the usual quantity or delivery days, from the next open day on."""
        from platform_core.services.audit import AuditService

        if not enrolment.delivery:
            raise ConflictError("This is not a delivery subscription")
        before = dict(enrolment.delivery)
        new = dict(enrolment.delivery)
        if quantity is not None:
            q = Decimal(str(quantity))
            if q <= 0 or q != q.to_integral_value():
                raise _err("quantity", "Quantity is a whole number of the item")
            new["quantity"] = str(int(q))
        if days is not None:
            clean = sorted({int(d) for d in days if 0 <= int(d) <= 6})
            if not clean:
                raise _err("days", "Choose at least one delivery day")
            new["days"] = clean
        enrolment.delivery = new
        enrolment.version += 1
        await session.flush()
        if actor_id is not None:
            await AuditService.record(session, event_type="membership.delivery_changed", actor_identity_id=actor_id,
                                      actor_context="business", action="change_future",
                                      business_id=enrolment.business_id, resource_type="membership_enrolment",
                                      resource_id=enrolment.id, before_state=before, after_state=new)
        return new

    # ------------------------------------------------------------------ tomorrow's demand (§10)
    @staticmethod
    async def plan_day(session: AsyncSession, business_id: uuid.UUID, on_date: date) -> list[Occurrence]:
        """Every running subscription's answer for `on_date` — the board's count
        and the generator's input are the same list."""
        rows = (await session.execute(select(MembershipEnrolment, MembershipPlan).join(
            MembershipPlan, MembershipPlan.id == MembershipEnrolment.plan_id).where(
            MembershipEnrolment.business_id == business_id, MembershipEnrolment.deleted_at.is_(None),
            MembershipPlan.plan_kind == "recurring_delivery",
            MembershipEnrolment.status.in_(("active", "paused", "grace", "pending"))))).all()
        out: list[Occurrence] = []
        for enrolment, plan in rows:
            if not enrolment.delivery:
                continue
            zone = ZoneInfo(await MembershipCore.tz(session, business_id, enrolment.location_id))
            day_start = datetime.combine(on_date, time(0, 0), zone)
            if enrolment.starts_at > day_start + timedelta(days=1) or (
                    enrolment.ends_at is not None and plan.billing_timing == "postpaid" and enrolment.ends_at <= day_start):
                continue
            if plan.billing_timing == "postpaid":
                covered = enrolment.status != "pending"
            else:
                covered = any(p.payment_state in ("paid", "waived") and p.starts_at <= day_start + timedelta(hours=12)
                              < p.ends_at for p in await MembershipCore.periods(session, enrolment.id))
            overrides = list((await session.execute(select(MembershipDeliveryOverride).where(
                MembershipDeliveryOverride.enrolment_id == enrolment.id,
                MembershipDeliveryOverride.on_date == on_date))).scalars())
            occ = decide_day(enrolment.delivery, on_date=on_date, overrides=overrides,
                             freezes=await MembershipCore.freezes(session, enrolment.id), covered=covered,
                             enrolment_id=enrolment.id)
            if occ is not None:
                out.append(occ)
        return out

    @staticmethod
    async def generate_day(session: AsyncSession, business_id: uuid.UUID, on_date: date, *,
                           actor_id: uuid.UUID, correlation_id: str) -> dict[str, Any]:
        """Turn one day's demand into orders — once. Re-running finds each
        occurrence already recorded and creates nothing new."""
        from platform_core.models import Business
        from platform_core.services.fulfilment import FulfilmentService
        from platform_core.services.order import OrderService
        from platform_core.services.order_lifecycle import OrderLifecycleService

        business = await session.get(Business, business_id)
        assert business is not None
        created = skipped = already = 0
        per_item: dict[str, Decimal] = {}
        for occ in await SubscriptionService.plan_day(session, business_id, on_date):
            if await SubscriptionService._generated(session, occ.enrolment_id, occ.on_date, occ.slot):
                already += 1
                continue
            enrolment = await MembershipCore.get(session, business_id, occ.enrolment_id)
            delivery = enrolment.delivery or {}
            offering = await session.get(Offering, uuid.UUID(str(delivery["offering_id"])))
            unit = Decimal(str(offering.price_amount or 0)) if offering is not None else Decimal("0")
            row = MembershipDelivery(business_id=business_id, enrolment_id=occ.enrolment_id, on_date=occ.on_date,
                                     slot=occ.slot, quantity=occ.quantity,
                                     status="ordered" if occ.status == "deliver" else occ.status,
                                     unit_price=unit, amount=(unit * occ.quantity).quantize(Decimal("0.01")))
            session.add(row)
            await session.flush()
            if occ.status != "deliver" or offering is None:
                skipped += 1
                continue
            location_id = enrolment.location_id or await SubscriptionService._primary_location(session, business_id)
            zone = ZoneInfo(await MembershipCore.tz(session, business_id, location_id))
            window = str(delivery.get("window") or "")
            due_time = _hm(window.split("-")[0]) if "-" in window and ":" in window else time(9, 0)
            order = await OrderService.create_order(
                session, business_id=business_id, actor_id=actor_id, correlation_id=correlation_id,
                actor_context="system",
                payload={"channel": "subscription", "location_id": str(location_id),
                         "customer_contact_id": str(enrolment.customer_contact_id), "payment_method": "pay_later",
                         "idempotency_key": f"subscription:{occ.enrolment_id}:{occ.on_date}:{occ.slot}",
                         "internal_reference": f"Subscription {occ.on_date:%d %b}"
                                               + (f" · {occ.slot}" if occ.slot else ""),
                         # The goods are covered: prepaid by the period, or billed on the
                         # khata at month end — the order carries the quantity, not the money.
                         "items": [{"offering_id": str(offering.id), "unit_price": 0,
                                    "quantity": int(occ.quantity)}],
                         "due_at": datetime.combine(occ.on_date, due_time, zone).isoformat()})
            row.order_id = order.id
            await OrderLifecycleService.transition_status(
                session, business_id=business_id, order_id=order.id, actor_id=actor_id,
                correlation_id=correlation_id, payload={"status": "accepted", "reason": "Subscription delivery"})
            mode = str(delivery.get("mode") or "delivery")
            try:
                await FulfilmentService.create_job_for_order(
                    session, business_id=business_id, order=order, actor_id=actor_id, correlation_id=correlation_id,
                    mode=mode, delivery_address=delivery.get("address") if mode == "delivery" else None)
            except Exception:  # noqa: BLE001 — no fulfilment module: the order still stands
                pass
            per_item[offering.title] = per_item.get(offering.title, Decimal("0")) + occ.quantity
            created += 1
        await session.flush()
        if created or skipped:
            await OutboxService.publish(session, event_type="membership.deliveries_generated", business_id=business_id,
                                        payload={"on_date": str(on_date), "orders": created, "not_delivered": skipped,
                                                 "items": {k: str(v) for k, v in per_item.items()}},
                                        correlation_id=correlation_id)
        return {"on_date": str(on_date), "orders": created, "not_delivered": skipped, "already": already,
                "items": {k: float(v) for k, v in per_item.items()}}

    @staticmethod
    async def _primary_location(session: AsyncSession, business_id: uuid.UUID) -> uuid.UUID:
        from platform_core.models import BusinessLocation

        loc = (await session.execute(select(BusinessLocation.id).where(
            BusinessLocation.business_id == business_id).order_by(BusinessLocation.is_primary.desc()).limit(1))).scalar()
        if loc is None:
            raise ConflictError("The business has no location to deliver from")
        return uuid.UUID(str(loc))

    @staticmethod
    async def board(session: AsyncSession, business_id: uuid.UUID, on_date: date) -> dict[str, Any]:
        """Tomorrow's quantity, skipped, paused (§14): the milkman's and the
        tiffin kitchen's first question, answered from the same plan the
        generator uses."""
        occs = await SubscriptionService.plan_day(session, business_id, on_date)
        by_slot: dict[str, dict[str, Any]] = {}
        for o in occs:
            s = by_slot.setdefault(o.slot or "Delivery", {"deliver": 0, "quantity": Decimal("0"), "skipped": 0,
                                                          "paused": 0, "not_covered": 0})
            if o.status == "deliver":
                s["deliver"] += 1
                s["quantity"] += o.quantity
            else:
                s[o.status] += 1
        generated = (await session.execute(select(MembershipDelivery).where(
            MembershipDelivery.business_id == business_id, MembershipDelivery.on_date == on_date))).scalars().all()
        return {"on_date": str(on_date), "generated": bool(generated),
                "slots": {k: {**v, "quantity": float(v["quantity"])} for k, v in by_slot.items()},
                "subscribers": [{"enrolment_id": str(o.enrolment_id), "slot": o.slot, "quantity": float(o.quantity),
                                 "status": o.status, "why": o.why} for o in occs]}

    # ------------------------------------------------------------------ postpaid month-end bill (§13)
    @staticmethod
    async def bill_postpaid(session: AsyncSession, business_id: uuid.UUID, month: date, *,
                            actor_id: uuid.UUID) -> dict[str, Any]:
        """Actual deliveries of the month go on each postpaid subscriber's
        khata as one entry — skipped and paused days cost nothing. Running it
        twice bills nothing twice (one idempotency key per subscriber and month)."""
        from platform_core.services.ledger import LedgerService

        first = month.replace(day=1)
        nxt = (first + timedelta(days=32)).replace(day=1)
        rows = (await session.execute(select(MembershipDelivery, MembershipEnrolment).join(
            MembershipEnrolment, MembershipEnrolment.id == MembershipDelivery.enrolment_id).join(
            MembershipPlan, MembershipPlan.id == MembershipEnrolment.plan_id).where(
            MembershipDelivery.business_id == business_id, MembershipDelivery.status == "ordered",
            MembershipDelivery.on_date >= first, MembershipDelivery.on_date < nxt,
            MembershipDelivery.ledger_entry_id.is_(None), MembershipPlan.billing_timing == "postpaid"))).all()
        per: dict[uuid.UUID, list[MembershipDelivery]] = {}
        who: dict[uuid.UUID, MembershipEnrolment] = {}
        for d, e in rows:
            per.setdefault(e.id, []).append(d)
            who[e.id] = e
        billed = []
        for enrolment_id, deliveries in per.items():
            enrolment = who[enrolment_id]
            total = sum((Decimal(str(d.amount or 0)) for d in deliveries), Decimal("0"))
            if total <= 0:
                continue
            acct = await LedgerService.for_customer(session, business_id, enrolment.customer_contact_id, actor_id)
            assert acct is not None
            entry = await LedgerService.post(
                session, business_id, acct.id, kind="credit_sale", amount=total, actor_id=actor_id,
                reference=f"Subscription {first:%b %Y}", note=f"{len(deliveries)} deliveries",
                idempotency_key=f"subbill:{enrolment_id}:{first:%Y-%m}")
            for d in deliveries:
                d.ledger_entry_id = entry.id
            billed.append({"enrolment_id": str(enrolment_id), "deliveries": len(deliveries), "amount": float(total)})
        await session.flush()
        return {"month": f"{first:%Y-%m}", "billed": billed}
