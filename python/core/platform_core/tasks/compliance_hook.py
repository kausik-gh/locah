"""Compliance due → one Task.

Compliance already reminds the owner (compliance.due ladder) and does not
create a task. This function is the hook. It does not change Compliance
tables or the reminder step.

Claude integration: at the end of `remind` in
`platform_core.events.subscribers.compliance_due`, call:

    from platform_core.tasks.compliance_hook import create_task_for_compliance_due
    await create_task_for_compliance_due(
        session, business_id=step.business_id, item_id=step.entity_id,
    )

The first reminder for a due date creates the task. Later steps of the same
ladder return that same task. Renewing or changing the date changes the key,
so the next reminder opens a new task. Requires the `tasks` module to be on.
"""

from __future__ import annotations

import uuid
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import ComplianceItem, WorkTask
from platform_core.services.tasks import TaskService

IST = ZoneInfo("Asia/Kolkata")


async def create_task_for_compliance_due(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    item_id: uuid.UUID,
    actor_identity_id: uuid.UUID | None = None,
) -> WorkTask | None:
    """Create the open task for this licence or filing date, or return the one already open."""
    row = (await session.execute(
        text("""
            SELECT activation_state FROM business_module_states
             WHERE business_id = :b AND module_id = 'tasks'
        """),
        {"b": str(business_id)},
    )).first()
    if row is None or row[0] not in ("enabled", "ready", "active"):
        return None
    item = await session.get(ComplianceItem, item_id)
    if item is None or item.business_id != business_id or item.status != "active":
        return None
    actor = actor_identity_id or item.created_by
    if actor is None:
        actor = (await session.execute(
            text("SELECT primary_owner_identity_id FROM businesses WHERE id = :b"),
            {"b": str(business_id)},
        )).scalar_one()
    due_at = datetime.combine(item.due_on, time(9, 0), IST).astimezone(timezone.utc)
    words = "Renew" if item.item_type == "licence" else "File"
    return await TaskService.create(
        session,
        business_id,
        actor,
        {
            "title": f"{words}: {item.title}",
            "description": (
                f"Due {item.due_on.isoformat()}. "
                "The date was entered by your team. LOCAH does not decide which licence or filing you need."
            ),
            "priority": "high",
            "due_at": due_at,
            "location_id": item.location_id,
            "related_type": "compliance_item",
            "related_id": item.id,
        },
        occurrence_key=f"compliance:{item.id}:{item.due_on.isoformat()}",
    )
