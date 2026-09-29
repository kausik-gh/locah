"""Task events: schedule the due moment, notify the assignee once, cancel on completion.

Handlers claim a receipt first so a redelivery does not schedule or notify twice.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.automation import AutomationEngine
from platform_core.automation.engine import DueStep, StepOutcome, step_handler
from platform_core.events.registry import EventContext, subscribe
from platform_core.services.notification import NotificationService
from platform_core.services.outbox import OutboxService


async def _claim(session: AsyncSession, business_id: object, subscriber: str, key: str) -> bool:
    row = (await session.execute(
        text("""
            INSERT INTO tasks_handler_receipts (business_id, subscriber_id, idempotency_key)
            VALUES (:b, :s, :k)
            ON CONFLICT DO NOTHING
            RETURNING idempotency_key
        """),
        {"b": str(business_id), "s": subscriber, "k": key},
    )).first()
    return row is not None


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "tasks.created",
    "task.created",
    description="Schedule task.due for the task's due time",
)
async def on_created(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    task_id = event.require_uuid("task_id")
    due = event.payload.get("due_at")
    if not due:
        return
    if not await _claim(session, business_id, "tasks.created", f"{task_id}:{due}"):
        return
    when = datetime.fromisoformat(str(due))
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    await AutomationEngine.schedule(
        session, business_id, ladder_key="task.due", entity_id=task_id, anchor=when,
        period_key=when.isoformat(), context={"title": event.payload.get("title")},
        now=datetime.now(timezone.utc),
    )


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "tasks.assigned",
    "task.assigned",
    description="Tell the assignee once that a task is theirs",
)
async def on_assigned(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    task_id = event.require_uuid("task_id")
    assignee = event.payload.get("assignee_member_id") or ""
    if not await _claim(session, business_id, "tasks.assigned", f"{task_id}:{assignee}"):
        return
    identity = event.payload.get("assignee_identity_id")
    if not identity:
        return
    from uuid import UUID

    await NotificationService.create(
        session,
        business_id=business_id,
        recipient_identity_id=UUID(str(identity)),
        notification_type="task.assigned",
        title=f"Task: {event.payload.get('title') or 'New task'}",
        body="This is assigned to you.",
        resource_type="task",
        resource_id=task_id,
        location_id=UUID(str(event.payload["location_id"])) if event.payload.get("location_id") else None,
    )


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "tasks.completed",
    "task.completed",
    description="Stop the due reminder once the task is completed",
)
async def on_completed(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    task_id = event.require_uuid("task_id")
    if not await _claim(session, business_id, "tasks.completed", str(task_id)):
        return
    await AutomationEngine.cancel(
        session, business_id, ladder_key="task.due", entity_id=task_id, reason="Task completed",
    )


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "tasks.due",
    "task.due",
    description="Accept task.due once; other lanes may also subscribe",
)
async def on_due(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    task_id = event.require_uuid("task_id")
    due = event.payload.get("due_at") or ""
    await _claim(session, business_id, "tasks.due", f"{task_id}:{due}")


@step_handler("task.due")  # type: ignore[untyped-decorator, unused-ignore]
async def fire_due(session: AsyncSession, step: DueStep) -> StepOutcome:
    """Publish task.due when the due time arrives. One publish per task and due time."""
    row = (await session.execute(
        text("""
            SELECT title, status, due_at, assignee_member_id, location_id, related_type, related_id
              FROM tasks_tasks WHERE id = :id AND business_id = :b
        """),
        {"id": str(step.entity_id), "b": str(step.business_id)},
    )).first()
    if row is None:
        return StepOutcome("skipped", "The task no longer exists")
    title, status, due_at, assignee, location_id, related_type, related_id = row
    if status not in ("open", "in_progress"):
        return StepOutcome("skipped", "The task is already closed")
    if due_at is None:
        return StepOutcome("skipped", "The due time changed")
    expected = datetime.fromisoformat(step.period_key)
    if expected.tzinfo is None:
        expected = expected.replace(tzinfo=timezone.utc)
    if abs((due_at - expected).total_seconds()) > 1:
        return StepOutcome("skipped", "The due time changed")
    key = f"{step.entity_id}:{step.period_key}"
    if not await _claim(session, step.business_id, "tasks.due.step", key):
        return StepOutcome("done", "Already signalled")
    await OutboxService.publish(
        session,
        event_type="task.due",
        business_id=step.business_id,
        payload={
            "business_id": str(step.business_id),
            "task_id": str(step.entity_id),
            "title": title,
            "status": status,
            "due_at": due_at.isoformat(),
            "assignee_member_id": str(assignee) if assignee else None,
            "location_id": str(location_id) if location_id else None,
            "related_type": related_type,
            "related_id": str(related_id),
        },
    )
    return StepOutcome("done", f"Task due: {title}")
