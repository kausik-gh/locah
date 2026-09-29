"""Shared tasks and checklists (Business OS Guide §6.2 `tasks`).

One task record can point at a business, customer, project, job, booking,
order, compliance item, location, or staff assignment. Checklist items live
on that task. Repeatable opening/closing lists are templates that spawn a
task; they are not a second engine.

Assignment scope is the existing P2-01 contract: a member limited to their
assignments sees tasks whose assignee_member_id is their workforce record.
"""

from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import (
    ConflictError,
    OutsideAssignmentScope,
    OutsideLocationScope,
    ResourceNotFound,
    ValidationError,
)
from platform_core.models import (
    TaskChecklistItem,
    TaskChecklistTemplate,
    TaskChecklistTemplateItem,
    TaskHistory,
    WorkTask,
)
from platform_core.services.outbox import OutboxService

IST = ZoneInfo("Asia/Kolkata")
OPEN = ("open", "in_progress")
RELATED_TABLES = {
    "customer": "customer_relationships_contacts",
    "project": "projects_projects",
    "booking": "bookings_bookings",
    "order": "orders_orders",
    "compliance_item": "compliance_items",
    "location": "business_locations",
    "staff_assignment": "workforce_members",
}
# Jobs are owned by another lane. The id is stored; existence is checked when that table exists.
VIEWS = ("mine", "due_today", "overdue", "unassigned", "completed", "open")


class TaskService:
    # ---------------------------------------------------------------- scope
    @staticmethod
    def _location_ok(session: AsyncSession, location_id: uuid.UUID | None) -> None:
        from platform_core.authorization.location_scope import current

        scope = current(session)
        if scope and location_id is not None and uuid.UUID(str(location_id)) not in scope:
            raise OutsideLocationScope()

    @staticmethod
    async def _mine(session: AsyncSession) -> set[uuid.UUID] | None:
        from platform_core.authorization.assignment_scope import current
        from platform_core.models import WorkforceMember

        identity = current(session)
        if identity is None:
            return None
        rows = await session.execute(
            select(WorkforceMember.id).where(WorkforceMember.identity_id == identity)
        )
        return {uuid.UUID(str(row)) for row in rows.scalars().all()}

    @staticmethod
    async def _actor_member_ids(session: AsyncSession, business_id: uuid.UUID, identity_id: uuid.UUID) -> set[uuid.UUID]:
        from platform_core.models import WorkforceMember

        rows = await session.execute(
            select(WorkforceMember.id).where(
                WorkforceMember.identity_id == identity_id,
                WorkforceMember.business_id == business_id,
            )
        )
        return {uuid.UUID(str(row)) for row in rows.scalars().all()}

    @staticmethod
    def _assignee_ok(mine: set[uuid.UUID] | None, assignee: uuid.UUID | None, *, writing: bool) -> None:
        if mine is None:
            return
        if assignee is None or uuid.UUID(str(assignee)) not in mine:
            if writing:
                raise OutsideAssignmentScope()
            raise ResourceNotFound("Task")

    # ---------------------------------------------------------------- create
    @staticmethod
    async def create(
        session: AsyncSession,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        body: dict[str, Any],
        *,
        occurrence_key: str | None = None,
        template_id: uuid.UUID | None = None,
    ) -> WorkTask:
        related_type = body["related_type"]
        related_id = body["related_id"]
        await TaskService._related_exists(session, business_id, related_type, related_id)
        location_id = body.get("location_id")
        TaskService._location_ok(session, location_id)
        if location_id is not None:
            await TaskService._row(session, "business_locations", business_id, location_id, "location_id")
        assignee = body.get("assignee_member_id")
        mine = await TaskService._mine(session)
        if mine is not None:
            TaskService._assignee_ok(mine, assignee, writing=True)
        if assignee is not None:
            await TaskService._row(session, "workforce_members", business_id, assignee, "assignee_member_id")
        if occurrence_key:
            existing = (await session.execute(
                select(WorkTask).where(
                    WorkTask.business_id == business_id,
                    WorkTask.occurrence_key == occurrence_key,
                    WorkTask.status != "cancelled",
                )
            )).scalars().first()
            if existing is not None:
                return existing
        task = WorkTask(
            business_id=business_id,
            location_id=location_id,
            title=body["title"].strip(),
            description=(body.get("description") or None),
            status="open",
            priority=body.get("priority") or "normal",
            due_at=body.get("due_at"),
            assignee_member_id=assignee,
            related_type=related_type,
            related_id=related_id,
            occurrence_key=occurrence_key,
            template_id=template_id,
            created_by=actor_id,
        )
        session.add(task)
        await session.flush()
        await TaskService._history(session, task, "created", None, "open", actor_id, None)
        await TaskService._publish(session, "task.created", task, actor_id)
        if assignee is not None:
            await TaskService._publish_assigned(session, task, None, actor_id)
        return task

    @staticmethod
    async def list_tasks(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        view: str,
        actor_id: uuid.UUID,
        now: datetime | None = None,
    ) -> list[WorkTask]:
        if view not in VIEWS:
            raise ValidationError("Unknown task view", details={"field": "view"})
        moment = now or datetime.now(timezone.utc)
        start, end = _ist_day_bounds(moment)
        stmt = select(WorkTask).where(WorkTask.business_id == business_id)
        mine = await TaskService._mine(session)
        if mine is not None:
            stmt = stmt.where(WorkTask.assignee_member_id.in_(mine))
        if view == "mine":
            own = await TaskService._actor_member_ids(session, business_id, actor_id)
            stmt = stmt.where(WorkTask.assignee_member_id.in_(own), WorkTask.status.in_(OPEN))
        elif view == "due_today":
            stmt = stmt.where(WorkTask.status.in_(OPEN), WorkTask.due_at >= start, WorkTask.due_at < end)
        elif view == "overdue":
            stmt = stmt.where(WorkTask.status.in_(OPEN), WorkTask.due_at < start)
        elif view == "unassigned":
            stmt = stmt.where(WorkTask.status.in_(OPEN), WorkTask.assignee_member_id.is_(None))
        elif view == "completed":
            stmt = stmt.where(WorkTask.status == "completed")
        else:
            stmt = stmt.where(WorkTask.status.in_(OPEN))
        rows = (await session.execute(stmt.order_by(WorkTask.due_at.asc().nulls_last(), WorkTask.created_at))).scalars().all()
        return list(rows)

    @staticmethod
    async def get(session: AsyncSession, business_id: uuid.UUID, task_id: uuid.UUID) -> WorkTask:
        task = await session.get(WorkTask, task_id)
        if task is None or task.business_id != business_id:
            raise ResourceNotFound("Task")
        TaskService._location_ok(session, task.location_id)
        TaskService._assignee_ok(await TaskService._mine(session), task.assignee_member_id, writing=False)
        return task

    # ---------------------------------------------------------------- changes
    @staticmethod
    async def assign(
        session: AsyncSession, business_id: uuid.UUID, task_id: uuid.UUID,
        assignee: uuid.UUID | None, actor_id: uuid.UUID,
    ) -> WorkTask:
        task = await TaskService.get(session, business_id, task_id)
        if task.status in ("completed", "cancelled"):
            raise ConflictError("That task is already closed")
        mine = await TaskService._mine(session)
        TaskService._assignee_ok(mine, assignee, writing=True)
        if assignee is not None:
            await TaskService._row(session, "workforce_members", business_id, assignee, "assignee_member_id")
        previous = task.assignee_member_id
        if previous == assignee:
            return task
        task.assignee_member_id = assignee
        task.version = (task.version or 1) + 1
        await session.flush()
        note = str(assignee) if assignee else "unassigned"
        await TaskService._history(session, task, "assigned", task.status, task.status, actor_id, note)
        await TaskService._publish_assigned(session, task, previous, actor_id)
        return task

    @staticmethod
    async def start(
        session: AsyncSession, business_id: uuid.UUID, task_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> WorkTask:
        task = await TaskService.get(session, business_id, task_id)
        if task.status != "open":
            raise ConflictError("Only an open task can be started", details={"status": task.status})
        task.status = "in_progress"
        task.version = (task.version or 1) + 1
        await session.flush()
        await TaskService._history(session, task, "started", "open", "in_progress", actor_id, None)
        return task

    @staticmethod
    async def complete(
        session: AsyncSession, business_id: uuid.UUID, task_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> WorkTask:
        task = await TaskService.get(session, business_id, task_id)
        if task.status not in OPEN:
            raise ConflictError("That task is already closed", details={"status": task.status})
        items = await TaskService.items(session, task)
        pending = [item.label for item in items if item.required and item.done_at is None]
        if pending:
            raise ConflictError(
                "Finish the required checklist first",
                details={"pending": pending},
            )
        previous = task.status
        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc)
        task.completed_by = actor_id
        task.version = (task.version or 1) + 1
        await session.flush()
        await TaskService._history(session, task, "completed", previous, "completed", actor_id, None)
        await TaskService._publish(session, "task.completed", task, actor_id)
        return task

    @staticmethod
    async def cancel(
        session: AsyncSession, business_id: uuid.UUID, task_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> WorkTask:
        task = await TaskService.get(session, business_id, task_id)
        if task.status == "completed":
            raise ConflictError("A completed task stays completed")
        if task.status == "cancelled":
            return task
        previous = task.status
        task.status = "cancelled"
        task.version = (task.version or 1) + 1
        await session.flush()
        await TaskService._history(session, task, "cancelled", previous, "cancelled", actor_id, None)
        return task

    # ---------------------------------------------------------------- checklist
    @staticmethod
    async def add_item(
        session: AsyncSession, business_id: uuid.UUID, task_id: uuid.UUID, body: dict[str, Any],
        actor_id: uuid.UUID,
    ) -> TaskChecklistItem:
        task = await TaskService.get(session, business_id, task_id)
        if task.status not in OPEN:
            raise ConflictError("That task is already closed")
        position = (await session.execute(
            text("SELECT COALESCE(MAX(position), -1) + 1 FROM tasks_checklist_items WHERE task_id = :id"),
            {"id": str(task.id)},
        )).scalar_one()
        item = TaskChecklistItem(
            business_id=business_id,
            task_id=task.id,
            position=int(position),
            label=body["label"].strip(),
            required=bool(body.get("required", True)),
            photo_required=bool(body.get("photo_required", False)),
        )
        session.add(item)
        await session.flush()
        await TaskService._history(session, task, "checklist", task.status, task.status, actor_id, item.label)
        return item

    @staticmethod
    async def check_item(
        session: AsyncSession, business_id: uuid.UUID, task_id: uuid.UUID, item_id: uuid.UUID,
        actor_id: uuid.UUID, *, done: bool, proof_media_id: uuid.UUID | None,
    ) -> TaskChecklistItem:
        task = await TaskService.get(session, business_id, task_id)
        if task.status not in OPEN:
            raise ConflictError("That task is already closed")
        item = await session.get(TaskChecklistItem, item_id)
        if item is None or item.task_id != task.id or item.business_id != business_id:
            raise ResourceNotFound("Checklist item")
        if done:
            if item.photo_required and proof_media_id is None and item.proof_media_id is None:
                raise ValidationError(
                    "This step needs a photo", details={"field": "proof_media_id"}
                )
            if proof_media_id is not None:
                await TaskService._row(session, "media_assets", business_id, proof_media_id, "proof_media_id")
                item.proof_media_id = proof_media_id
            item.done_at = datetime.now(timezone.utc)
            item.done_by = actor_id
        else:
            item.done_at = None
            item.done_by = None
        await session.flush()
        note = f"{'done' if done else 'undone'}: {item.label}"
        await TaskService._history(session, task, "checklist", task.status, task.status, actor_id, note)
        return item

    @staticmethod
    async def items(session: AsyncSession, task: WorkTask) -> list[TaskChecklistItem]:
        rows = (await session.execute(
            select(TaskChecklistItem)
            .where(TaskChecklistItem.task_id == task.id)
            .order_by(TaskChecklistItem.position)
        )).scalars().all()
        return list(rows)

    @staticmethod
    async def history(session: AsyncSession, task: WorkTask) -> list[TaskHistory]:
        rows = (await session.execute(
            select(TaskHistory).where(TaskHistory.task_id == task.id).order_by(TaskHistory.created_at.desc())
        )).scalars().all()
        return list(rows)

    # ---------------------------------------------------------------- templates
    @staticmethod
    async def create_template(
        session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, body: dict[str, Any],
    ) -> TaskChecklistTemplate:
        location_id = body.get("location_id")
        TaskService._location_ok(session, location_id)
        template = TaskChecklistTemplate(
            business_id=business_id,
            location_id=location_id,
            name=body["name"].strip(),
            kind=body.get("kind") or "custom",
            created_by=actor_id,
        )
        session.add(template)
        await session.flush()
        for index, item in enumerate(body.get("items") or []):
            session.add(TaskChecklistTemplateItem(
                business_id=business_id,
                template_id=template.id,
                position=index,
                label=item["label"].strip(),
                required=bool(item.get("required", True)),
                photo_required=bool(item.get("photo_required", False)),
            ))
        await session.flush()
        return template

    @staticmethod
    async def spawn(
        session: AsyncSession, business_id: uuid.UUID, template_id: uuid.UUID, actor_id: uuid.UUID,
        body: dict[str, Any],
    ) -> WorkTask:
        template = await session.get(TaskChecklistTemplate, template_id)
        if template is None or template.business_id != business_id or template.status != "active":
            raise ResourceNotFound("Checklist")
        occurrence = f"template:{template.id}:{body['occurrence_key'].strip()}"
        existing = (await session.execute(
            select(WorkTask).where(
                WorkTask.business_id == business_id,
                WorkTask.occurrence_key == occurrence,
                WorkTask.status != "cancelled",
            )
        )).scalars().first()
        if existing is not None:
            return existing
        task = await TaskService.create(
            session, business_id, actor_id,
            {
                "title": body.get("title") or template.name,
                "description": body.get("description"),
                "priority": body.get("priority") or "normal",
                "due_at": body.get("due_at"),
                "assignee_member_id": body.get("assignee_member_id"),
                "location_id": body.get("location_id") or template.location_id,
                "related_type": body.get("related_type") or "business",
                "related_id": body.get("related_id") or business_id,
            },
            occurrence_key=occurrence,
            template_id=template.id,
        )
        # create() may have returned the existing row from a race; only copy items onto a new task.
        already = await TaskService.items(session, task)
        if already:
            return task
        copies = (await session.execute(
            select(TaskChecklistTemplateItem)
            .where(TaskChecklistTemplateItem.template_id == template.id)
            .order_by(TaskChecklistTemplateItem.position)
        )).scalars().all()
        for item in copies:
            session.add(TaskChecklistItem(
                business_id=business_id,
                task_id=task.id,
                position=item.position,
                label=item.label,
                required=item.required,
                photo_required=item.photo_required,
            ))
        await session.flush()
        return task

    # ---------------------------------------------------------------- events
    @staticmethod
    async def _publish(session: AsyncSession, event_type: str, task: WorkTask, actor_id: uuid.UUID) -> None:
        await OutboxService.publish(
            session, event_type=event_type, business_id=task.business_id,
            payload=_payload(task, actor_id),
        )

    @staticmethod
    async def _publish_assigned(
        session: AsyncSession, task: WorkTask, previous: uuid.UUID | None, actor_id: uuid.UUID,
    ) -> None:
        identity = None
        if task.assignee_member_id is not None:
            identity = (await session.execute(
                text("SELECT identity_id FROM workforce_members WHERE id = :id AND business_id = :b"),
                {"id": str(task.assignee_member_id), "b": str(task.business_id)},
            )).scalar()
        payload = _payload(task, actor_id)
        payload["previous_assignee_member_id"] = str(previous) if previous else None
        payload["assignee_identity_id"] = str(identity) if identity else None
        await OutboxService.publish(
            session, event_type="task.assigned", business_id=task.business_id, payload=payload,
        )

    @staticmethod
    async def _history(
        session: AsyncSession, task: WorkTask, action: str, frm: str | None, to: str | None,
        actor_id: uuid.UUID, note: str | None,
    ) -> None:
        session.add(TaskHistory(
            business_id=task.business_id, task_id=task.id, action=action,
            from_status=frm, to_status=to, note=note, actor_identity_id=actor_id,
        ))
        await session.flush()

    @staticmethod
    async def _related_exists(
        session: AsyncSession, business_id: uuid.UUID, related_type: str, related_id: uuid.UUID,
    ) -> None:
        if related_type == "business":
            if related_id != business_id:
                raise ValidationError("A business task points at this business", details={"field": "related_id"})
            return
        if related_type == "job":
            # Jobs ship on another lane. Keep the reference; do not invent a job table.
            return
        table = RELATED_TABLES.get(related_type)
        if table is None:
            raise ValidationError("Unknown related record", details={"field": "related_type"})
        await TaskService._row(session, table, business_id, related_id, "related_id")

    @staticmethod
    async def _row(
        session: AsyncSession, table: str, business_id: uuid.UUID, row_id: uuid.UUID, field: str,
    ) -> None:
        row = (await session.execute(
            text(f"SELECT 1 FROM {table} WHERE id = :id AND business_id = :b"),
            {"id": str(row_id), "b": str(business_id)},
        )).first()
        if row is None:
            raise ValidationError("That record is not in this business", details={"field": field})

    @staticmethod
    def serialize(task: WorkTask, items: list[TaskChecklistItem] | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": str(task.id),
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "priority": task.priority,
            "due_at": task.due_at.isoformat() if task.due_at else None,
            "assignee_member_id": str(task.assignee_member_id) if task.assignee_member_id else None,
            "location_id": str(task.location_id) if task.location_id else None,
            "related_type": task.related_type,
            "related_id": str(task.related_id),
            "occurrence_key": task.occurrence_key,
            "template_id": str(task.template_id) if task.template_id else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "created_at": task.created_at.isoformat(),
        }
        if items is not None:
            data["checklist"] = [
                {
                    "id": str(item.id),
                    "position": item.position,
                    "label": item.label,
                    "required": item.required,
                    "photo_required": item.photo_required,
                    "done": item.done_at is not None,
                    "done_at": item.done_at.isoformat() if item.done_at else None,
                    "proof_media_id": str(item.proof_media_id) if item.proof_media_id else None,
                }
                for item in items
            ]
        return data


def _payload(task: WorkTask, actor_id: uuid.UUID) -> dict[str, Any]:
    return {
        "business_id": str(task.business_id),
        "task_id": str(task.id),
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "due_at": task.due_at.isoformat() if task.due_at else None,
        "assignee_member_id": str(task.assignee_member_id) if task.assignee_member_id else None,
        "location_id": str(task.location_id) if task.location_id else None,
        "related_type": task.related_type,
        "related_id": str(task.related_id),
        "actor_identity_id": str(actor_id),
    }


def _ist_day_bounds(moment: datetime) -> tuple[datetime, datetime]:
    local = moment.astimezone(IST)
    start = datetime.combine(local.date(), time.min, IST).astimezone(timezone.utc)
    return start, start + timedelta(days=1)
