"""Shared tasks, checklist items, and repeatable operational lists."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.permissions import TASKS_COMPLETE, TASKS_MANAGE, TASKS_READ
from platform_core.services.tasks import TaskService
from platform_core.tasks.compliance_hook import create_task_for_compliance_due

router = APIRouter(prefix="/v1/platform/businesses", tags=["tasks"])
MODULE = "tasks"

Related = Literal[
    "business", "customer", "project", "job", "booking", "order",
    "compliance_item", "location", "staff_assignment",
]


class CreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    due_at: datetime | None = None
    assignee_member_id: UUID | None = None
    location_id: UUID | None = None
    related_type: Related
    related_id: UUID


class AssignBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignee_member_id: UUID | None = None


class ItemBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=200)
    required: bool = True
    photo_required: bool = False


class CheckBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    done: bool = True
    proof_media_id: UUID | None = None


class TemplateItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=200)
    required: bool = True
    photo_required: bool = False


class TemplateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    kind: Literal["opening", "closing", "handover", "prep", "custom"] = "custom"
    location_id: UUID | None = None
    items: list[TemplateItem] = Field(min_length=1)


class SpawnBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    occurrence_key: str = Field(min_length=1, max_length=80)
    title: str | None = Field(default=None, max_length=160)
    due_at: datetime | None = None
    assignee_member_id: UUID | None = None
    location_id: UUID | None = None
    related_type: Related | None = None
    related_id: UUID | None = None
    priority: Literal["low", "normal", "high", "urgent"] = "normal"


class ComplianceTaskBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: UUID


def _meta(actor: BusinessActorContext) -> dict[str, str]:
    return {"correlation_id": actor.request.correlation_id}


async def _one(session: AsyncSession, task: Any) -> dict[str, Any]:
    return TaskService.serialize(task, await TaskService.items(session, task))


@router.get("/{business_id}/tasks")
async def list_tasks(
    business_id: UUID,
    view: Literal["mine", "due_today", "overdue", "unassigned", "completed", "open"] = Query(default="open"),
    actor: BusinessActorContext = Depends(require_business_actor(TASKS_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    rows = await TaskService.list_tasks(
        session, business_id, view=view, actor_id=actor.request.identity_id,
    )
    return {"data": {"tasks": [TaskService.serialize(row) for row in rows], "view": view}, "meta": _meta(actor)}


@router.post("/{business_id}/tasks")
async def create_task(
    business_id: UUID, body: CreateBody,
    actor: BusinessActorContext = Depends(require_business_actor(TASKS_MANAGE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    task = await TaskService.create(session, business_id, actor.request.identity_id, body.model_dump())
    data = await _one(session, task)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/tasks/from-compliance")
async def from_compliance(
    business_id: UUID, body: ComplianceTaskBody,
    actor: BusinessActorContext = Depends(require_business_actor(TASKS_MANAGE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    task = await create_task_for_compliance_due(
        session, business_id=business_id, item_id=body.item_id, actor_identity_id=actor.request.identity_id,
    )
    if task is None:
        from platform_core.exceptions import ValidationError

        raise ValidationError("That licence or filing is not active, or Tasks is switched off")
    data = await _one(session, task)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.get("/{business_id}/tasks/{task_id}")
async def get_task(
    business_id: UUID, task_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(TASKS_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    task = await TaskService.get(session, business_id, task_id)
    history = await TaskService.history(session, task)
    data = await _one(session, task)
    data["history"] = [
        {"action": row.action, "from_status": row.from_status, "to_status": row.to_status,
         "note": row.note, "at": row.created_at.isoformat()}
        for row in history
    ]
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/tasks/{task_id}/assign")
async def assign(
    business_id: UUID, task_id: UUID, body: AssignBody,
    actor: BusinessActorContext = Depends(require_business_actor(TASKS_MANAGE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    task = await TaskService.assign(
        session, business_id, task_id, body.assignee_member_id, actor.request.identity_id,
    )
    data = await _one(session, task)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/tasks/{task_id}/start")
async def start(
    business_id: UUID, task_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(TASKS_COMPLETE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    task = await TaskService.start(session, business_id, task_id, actor.request.identity_id)
    data = await _one(session, task)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/tasks/{task_id}/complete")
async def complete(
    business_id: UUID, task_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(TASKS_COMPLETE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    task = await TaskService.complete(session, business_id, task_id, actor.request.identity_id)
    data = await _one(session, task)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/tasks/{task_id}/items")
async def add_item(
    business_id: UUID, task_id: UUID, body: ItemBody,
    actor: BusinessActorContext = Depends(require_business_actor(TASKS_MANAGE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await TaskService.add_item(session, business_id, task_id, body.model_dump(), actor.request.identity_id)
    task = await TaskService.get(session, business_id, task_id)
    data = await _one(session, task)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/tasks/{task_id}/items/{item_id}/check")
async def check_item(
    business_id: UUID, task_id: UUID, item_id: UUID, body: CheckBody,
    actor: BusinessActorContext = Depends(require_business_actor(TASKS_COMPLETE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await TaskService.check_item(
        session, business_id, task_id, item_id, actor.request.identity_id,
        done=body.done, proof_media_id=body.proof_media_id,
    )
    task = await TaskService.get(session, business_id, task_id)
    data = await _one(session, task)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/tasks/templates")
async def create_template(
    business_id: UUID, body: TemplateBody,
    actor: BusinessActorContext = Depends(require_business_actor(TASKS_MANAGE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    template = await TaskService.create_template(
        session, business_id, actor.request.identity_id, body.model_dump(),
    )
    await session.commit()
    return {"data": {"id": str(template.id), "name": template.name, "kind": template.kind}, "meta": _meta(actor)}


@router.post("/{business_id}/tasks/templates/{template_id}/spawn")
async def spawn(
    business_id: UUID, template_id: UUID, body: SpawnBody,
    actor: BusinessActorContext = Depends(require_business_actor(TASKS_MANAGE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    task = await TaskService.spawn(
        session, business_id, template_id, actor.request.identity_id, body.model_dump(),
    )
    data = await _one(session, task)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}
