"""Owner-entered compliance dates schedule permission-gated reminders."""

from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.automation import AutomationEngine, StepOutcome, step_handler
from platform_core.automation.engine import DueStep
from platform_core.events.registry import EventContext, subscribe
from platform_core.events.subscribers.automation_triggers import _module_on
from platform_core.models import ComplianceItem
from platform_core.permissions import COMPLIANCE_READ
from platform_core.services.notification import NotificationService

IST = ZoneInfo("Asia/Kolkata")


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "compliance.reminders",
    "compliance.item.created", "compliance.item.updated", "compliance.item.renewed",
    "compliance.item.filed", "compliance.item.archived",
    description="Reschedule reminders when an owner changes a licence or filing date",
)
async def reschedule(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    item_id = event.require_uuid("item_id")
    await AutomationEngine.cancel(session, business_id, ladder_key="compliance.due",
                                  entity_id=item_id, reason="Licence or filing changed")
    if not await _module_on(session, business_id, "compliance"):
        return
    item = await session.get(ComplianceItem, item_id)
    if item is None or item.business_id != business_id or item.status != "active":
        return
    anchor = datetime.combine(item.due_on, time(9, 0), IST).astimezone(timezone.utc)
    await AutomationEngine.schedule(session, business_id, ladder_key="compliance.due", entity_id=item.id,
                                    anchor=anchor, period_key=item.due_on.isoformat(),
                                    context={"item_type": item.item_type}, now=datetime.now(timezone.utc))


@step_handler("compliance.due")  # type: ignore[untyped-decorator, unused-ignore]
async def remind(session: AsyncSession, step: DueStep) -> StepOutcome:
    item = await session.get(ComplianceItem, step.entity_id)
    if item is None or item.business_id != step.business_id or item.status != "active":
        return StepOutcome("skipped", "This licence or filing is no longer active")
    if item.due_on.isoformat() != step.period_key:
        return StepOutcome("skipped", "The due date was changed")
    if not await _module_on(session, step.business_id, "compliance"):
        return StepOutcome("skipped", "Licences & deadlines is switched off")
    words = "expires" if item.item_type == "licence" else "is due"
    await NotificationService.fan_out(
        session, business_id=step.business_id, notification_type="compliance.due",
        title=f"{item.title} {words} on {item.due_on:%d %b %Y}",
        body="Check the date and record renewal or filing when done. Dates come from your team, not LOCAH.",
        required_permission=COMPLIANCE_READ, severity="warning", resource_type="compliance_item",
        resource_id=item.id, location_id=item.location_id,
    )
    # The shared Tasks engine owns the follow-up: the first reminder for this
    # due date opens one task, later steps return that same task, a new date a
    # new one (occurrence key). Nothing happens when Tasks is switched off.
    from platform_core.tasks.compliance_hook import create_task_for_compliance_due

    task = await create_task_for_compliance_due(session, business_id=step.business_id, item_id=item.id)
    also = " and opened a task" if task is not None else ""
    return StepOutcome("done", f"Reminded your team about {item.title} ({item.due_on.isoformat()}){also}")
