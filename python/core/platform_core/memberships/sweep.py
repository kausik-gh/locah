"""The scheduled lifecycle check (Founder refinement — Memberships §4).

Events recalculate a relationship the moment something happens; this sweep
catches what time alone changes — a plan that ended overnight, a freeze that
started today, a grace period that ran out — and does the day's work:

* recalculates every running relationship of every business with Memberships on;
* after each subscription's cutoff, turns tomorrow's deliveries into orders;
* asks Jobs for AMC visits falling due within a week (an event, once per visit);
* on the 1st, bills last month's postpaid deliveries onto the khata.

It runs hourly (the worker books the next run), which is enough for things
that change by the day and cutoffs set to the minute of an hour; every step is
idempotent, so running it twice changes nothing.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.memberships.models import MembershipServiceVisit
from platform_core.memberships.service import MembershipCore
from platform_core.models import Business, MembershipEnrolment, MembershipPlan
from platform_core.services.outbox import OutboxService

RECURRENCE_KEY = "memberships.sweep"
VISIT_LEAD_DAYS = 7


async def ensure_scheduled(session: AsyncSession, *, minutes: int = 60) -> bool:
    """Book the next sweep unless one is already waiting (one chain however many workers)."""
    pending = (await session.execute(text(
        "SELECT 1 FROM platform_scheduled_jobs WHERE recurrence_key = :k AND status = 'pending' LIMIT 1"),
        {"k": RECURRENCE_KEY})).first()
    if pending is not None:
        return False
    await session.execute(text(
        "INSERT INTO platform_scheduled_jobs (schedule_type, payload, run_at, recurrence_key) "
        "VALUES ('memberships.sweep', CAST(:p AS jsonb), now() + make_interval(mins => :m), :k)"),
        {"p": '{"recurring": true}', "m": max(1, int(minutes)), "k": RECURRENCE_KEY})
    return True


async def businesses_with_memberships(session: AsyncSession) -> list[uuid.UUID]:
    rows = (await session.execute(text(
        "SELECT DISTINCT business_id FROM business_module_states WHERE module_id = 'memberships' "
        "AND activation_state IN ('enabled', 'ready', 'active')"))).all()
    return [uuid.UUID(str(r[0])) for r in rows]


async def sweep_business(session: AsyncSession, business_id: uuid.UUID, *, now: datetime | None = None) -> dict[str, Any]:
    """One business's day. The caller binds the tenant (RLS) before calling."""
    from platform_core.memberships.subscriptions import SubscriptionService

    moment = now or datetime.now(timezone.utc)
    zone = ZoneInfo(await MembershipCore.tz(session, business_id))
    today = moment.astimezone(zone).date()
    business = await session.get(Business, business_id)
    assert business is not None
    owner = business.primary_owner_identity_id
    out: dict[str, Any] = {"recalculated": 0, "changed": 0, "deliveries": None, "visits_due": 0, "billed": None}

    rows = (await session.execute(select(MembershipEnrolment).where(
        MembershipEnrolment.business_id == business_id, MembershipEnrolment.deleted_at.is_(None),
        MembershipEnrolment.status.in_(("pending", "active", "paused", "grace", "expired"))))).scalars().all()
    for enrolment in rows:
        before = enrolment.status
        st = await MembershipCore.recalculate(session, enrolment, now=moment, reason="Daily check")
        out["recalculated"] += 1
        if st.status != before:
            out["changed"] += 1
        if st.status == "expired" and before != "expired":
            await MembershipCore.lapse_unpaid(session, enrolment, now=moment)

    # Tomorrow's deliveries, once the earliest subscription cutoff for tomorrow has passed.
    cutoffs = [str((e.delivery or {}).get("cutoff") or "21:00") for e in rows if e.delivery]
    if cutoffs:
        earliest = min(time(int(c.split(":")[0]), int(c.split(":")[1])) for c in cutoffs)
        if moment >= datetime.combine(today, earliest, zone):
            out["deliveries"] = await SubscriptionService.generate_day(
                session, business_id, today + timedelta(days=1), actor_id=owner, correlation_id=str(uuid.uuid4()))

    # AMC visits falling due within a week: ask Jobs, once per visit.
    visits = (await session.execute(select(MembershipServiceVisit).where(
        MembershipServiceVisit.business_id == business_id, MembershipServiceVisit.status == "scheduled",
        MembershipServiceVisit.due_on <= today + timedelta(days=VISIT_LEAD_DAYS)).with_for_update())).scalars().all()
    for visit in visits:
        contract = await session.get(MembershipEnrolment, visit.enrolment_id)
        if contract is None or contract.status not in ("active", "grace"):
            continue
        plan = await session.get(MembershipPlan, contract.plan_id)
        visit.status, visit.requested_at = "requested", moment
        await OutboxService.publish(session, event_type="membership.service_visit_due", business_id=business_id,
                                    payload={"visit_id": str(visit.id), "enrolment_id": str(contract.id),
                                             "due_on": str(visit.due_on), "seq": visit.seq,
                                             "customer_contact_id": str(contract.customer_contact_id),
                                             "plan_name": plan.name if plan else None,
                                             "asset_ref": str(contract.source_ref_id)
                                             if contract.source_ref_type == "customer_asset" else None})
        out["visits_due"] += 1

    # The 1st of the month: last month's postpaid deliveries go on the khata.
    if today.day == 1:
        out["billed"] = await SubscriptionService.bill_postpaid(session, business_id, today - timedelta(days=1),
                                                                actor_id=owner)
    await session.flush()
    return out


async def sweep_all(session: AsyncSession, *, now: datetime | None = None) -> dict[str, Any]:
    """Every business with Memberships on, each in its own tenant binding and transaction."""
    from platform_core.context_resolver import bind_public_context

    done: dict[str, Any] = {}
    for business_id in await businesses_with_memberships(session):
        await bind_public_context(session, business_id)
        try:
            done[str(business_id)] = await sweep_business(session, business_id, now=now)
            await session.commit()
        except Exception as exc:  # noqa: BLE001 — one business's failure must not stop the others
            await session.rollback()
            done[str(business_id)] = {"error": str(exc)[:300]}
    return done


def today_in(zone: str, now: datetime | None = None) -> date:
    return (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(zone)).date()
