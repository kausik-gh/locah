"""Domain events → automation ladders (Capability Universe §24.2: modules never
call each other's automations; everything reacts to events).

Each ladder a built module owns is scheduled or cancelled here, and its steps'
work is registered with the engine. Ladders for modules that are not built yet
have no triggers, so they never run.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.automation import AutomationEngine, StepOutcome, step_handler
from platform_core.automation.engine import DueStep
from platform_core.events.registry import EventContext, subscribe


def _ist_day(moment: datetime) -> str:
    return moment.astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat()


async def _module_on(session: AsyncSession, business_id: uuid.UUID, module: str) -> bool:
    row = (await session.execute(
        text("SELECT activation_state FROM business_module_states WHERE business_id = :b AND module_id = :m"),
        {"b": str(business_id), "m": module},
    )).first()
    return row is not None and row[0] in ("enabled", "ready", "active")


# ---------------------------------------------------------------- stock.low (inventory)
@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "automation.stock_low",
    "inventory.stock.low",
    description="Schedule the low-stock alert (at most one per item per day)",
)
async def stock_low(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    if not await _module_on(session, business_id, "inventory"):
        return
    record_id = event.require_uuid("inventory_record_id")
    now = datetime.now(timezone.utc)
    await AutomationEngine.schedule(
        session, business_id, ladder_key="stock.low", entity_id=record_id, anchor=now,
        period_key=_ist_day(now),
        context={"offering_id": event.payload.get("offering_id"), "level": event.payload.get("current_level"),
                 "threshold": event.payload.get("threshold"), "location_id": event.payload.get("location_id")},
        now=now,
    )


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "automation.stock_restored",
    "inventory.stock.replenished",
    description="Cancel a pending low-stock alert once stock is restored",
)
async def stock_restored(session: AsyncSession, event: EventContext) -> None:
    await AutomationEngine.cancel(
        session, event.require_business_id(), ladder_key="stock.low",
        entity_id=event.require_uuid("inventory_record_id"), reason="Stock was restored",
    )


@step_handler("stock.low")  # type: ignore[untyped-decorator, unused-ignore]
async def alert_low_stock(session: AsyncSession, step: DueStep) -> StepOutcome:
    from platform_core.permissions import INVENTORY_READ
    from platform_core.services.notification import NotificationService

    row = (await session.execute(
        text("""
            SELECT r.quantity_on_hand, COALESCE(r.low_stock_threshold, o.low_stock_threshold), o.title
            FROM inventory_records r JOIN offerings_catalog_offerings o ON o.id = r.offering_id
            WHERE r.business_id = :b AND r.id = :id
        """),
        {"b": str(step.business_id), "id": str(step.entity_id)},
    )).first()
    if row is None:
        return StepOutcome("skipped", "The stock item no longer exists")
    level, threshold, title = row
    if threshold is None or level > threshold:
        return StepOutcome("skipped", f"{title}: stock already back above the reorder point")
    await NotificationService.fan_out(
        session, business_id=step.business_id, notification_type="inventory.low_stock",
        title=f"{title} is running low", body=f"{level} left (reorder point {threshold}).",
        required_permission=INVENTORY_READ, severity="warning", resource_type="inventory_record",
        resource_id=step.entity_id, payload={"level": level, "threshold": threshold},
    )
    return StepOutcome("done", f"Told you {title} is low ({level} left)", {"level": level})


# ---------------------------------------------------------------- lead.followup (leads)
@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "automation.lead_followup",
    "lead.created",
    "lead.updated",
    "lead.assigned",
    description="Schedule the follow-up nudge for the lead's follow-up date",
)
async def lead_followup(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    lead_id = event.require_uuid("lead_id")
    after = dict(event.payload.get("after") or {})
    when = after.get("next_follow_up_at")
    if after.get("status") in ("won", "lost"):
        await AutomationEngine.cancel(session, business_id, ladder_key="lead.followup", entity_id=lead_id,
                                      reason=f"Lead {after.get('status')}")
        return
    if not when or not await _module_on(session, business_id, "leads"):
        return
    due = datetime.fromisoformat(str(when))
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    # A new follow-up date replaces the previous one.
    await session.execute(
        text("""UPDATE automation_steps SET status = 'cancelled', outcome = 'Follow-up date changed',
                executed_at = now()
                WHERE business_id = :b AND ladder_key = 'lead.followup' AND entity_id = :e
                  AND status = 'pending' AND period_key <> :p"""),
        {"b": str(business_id), "e": str(lead_id), "p": due.isoformat()},
    )
    await AutomationEngine.schedule(session, business_id, ladder_key="lead.followup", entity_id=lead_id,
                                    anchor=due, period_key=due.isoformat(),
                                    context={"display_name": after.get("display_name")})


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "automation.lead_closed",
    "lead.stage_changed",
    "lead.contacted",
    "lead.qualified",
    "lead.won",
    "lead.lost",
    "lead.deleted",
    description="Stop follow-ups when a lead moves stage or closes (Guide §6)",
)
async def lead_closed(session: AsyncSession, event: EventContext) -> None:
    status = str(event.payload.get("status") or "")
    reason = "Lead deleted" if event.event_type == "lead.deleted" else f"Lead moved to {status or 'another stage'}"
    await AutomationEngine.cancel(session, event.require_business_id(), ladder_key="lead.followup",
                                  entity_id=event.require_uuid("lead_id"), reason=reason)


@step_handler("lead.followup")  # type: ignore[untyped-decorator, unused-ignore]
async def nudge_lead(session: AsyncSession, step: DueStep) -> StepOutcome:
    from platform_core.services.notification import NotificationService

    row = (await session.execute(
        text("""SELECT display_name, status, assignee_identity_id, next_follow_up_at FROM leads_leads
                WHERE business_id = :b AND id = :id AND deleted_at IS NULL"""),
        {"b": str(step.business_id), "id": str(step.entity_id)},
    )).first()
    if row is None:
        return StepOutcome("skipped", "The lead no longer exists")
    name, status, assignee, _ = row
    if status in ("won", "lost"):
        return StepOutcome("skipped", f"{name} is already {status}")
    body = f"Follow up with {name} today."
    if assignee:
        await NotificationService.create(
            session, business_id=step.business_id, recipient_identity_id=assignee,
            notification_type="lead.follow_up_due", title=f"Follow up: {name}", body=body,
            category="operational", severity="info", resource_type="lead", resource_id=step.entity_id,
        )
        who = "the assigned person"
    else:
        from platform_core.permissions import LEADS_READ

        await NotificationService.fan_out(
            session, business_id=step.business_id, notification_type="lead.follow_up_due",
            title=f"Follow up: {name}", body=body, required_permission=LEADS_READ,
            resource_type="lead", resource_id=step.entity_id,
        )
        who = "your team"
    return StepOutcome("done", f"Reminded {who} to follow up with {name}")
