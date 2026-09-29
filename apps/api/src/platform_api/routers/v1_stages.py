"""Stages (P2-01; Capability Universe §24 #10): a business's own steps inside
the statuses of orders, enquiries and projects, and moving a record along them."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import (
    BusinessActorContext,
    assert_entitled,
    assert_module_operational,
    require_business_actor,
    require_business_member,
)
from platform_core.exceptions import PermissionDenied, ResourceNotFound
from platform_core.permissions import (
    LEADS_READ,
    ORDERS_READ,
    PROJECTS_READ,
    SETTINGS_UPDATE,
)
from platform_core.stages.engine import ENTITIES, MODULE, StageEngine

router = APIRouter(prefix="/v1/b", tags=["stages"])

_READ = {"orders": ORDERS_READ, "leads": LEADS_READ, "projects": PROJECTS_READ}


class StageRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str | None = Field(default=None, max_length=40)
    label: str = Field(min_length=1, max_length=60)
    status: str = Field(min_length=1, max_length=30)
    needs_note: bool = False
    custom: bool | None = None


class StageSetBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stages: list[StageRow] = Field(min_length=1, max_length=40)


class MoveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to: str = Field(min_length=1, max_length=40)
    note: str | None = Field(default=None, max_length=500)
    version: int | None = None


def _gate(actor: BusinessActorContext, entity: str, permission: str | None = None) -> None:
    if entity not in ENTITIES:
        raise ResourceNotFound("Stage set")
    assert_entitled(actor.request, MODULE[entity])
    assert_module_operational(actor.request, MODULE[entity])
    needed = permission or _READ[entity]
    if needed not in actor.request.effective_permissions:
        raise PermissionDenied(needed)


@router.get("/{business_id}/stages/{entity}")
async def get_stage_set(
    business_id: UUID, entity: str,
    actor: BusinessActorContext = Depends(require_business_member()),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """The stages in flow order and the moves open from each."""
    _gate(actor, entity)
    sset = await StageEngine.get(session, business_id, entity)
    return {"data": sset.view(), "meta": {"correlation_id": actor.request.correlation_id}}


@router.put("/{business_id}/stages/{entity}")
async def save_stage_set(
    business_id: UUID, entity: str, body: StageSetBody,
    actor: BusinessActorContext = Depends(require_business_actor(SETTINGS_UPDATE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Rename stages and add, reorder or remove the business's own steps inside open statuses."""
    _gate(actor, entity, SETTINGS_UPDATE)
    sset = await StageEngine.save(session, business_id, entity, [r.model_dump() for r in body.stages],
                                  actor_id=actor.request.identity_id, correlation_id=actor.request.correlation_id)
    await session.commit()
    return {"data": sset.view(), "meta": {"correlation_id": actor.request.correlation_id}}


@router.get("/{business_id}/stages/{entity}/{record_id}")
async def record_stage(
    business_id: UUID, entity: str, record_id: UUID,
    actor: BusinessActorContext = Depends(require_business_member()),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Where one record is, the moves open from there, and its stage history."""
    _gate(actor, entity)
    data = await StageEngine.where(session, business_id, entity, record_id)
    data["history"] = await StageEngine.history(session, business_id, entity, record_id)
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.post("/{business_id}/stages/{entity}/{record_id}/move")
async def move_record(
    business_id: UUID, entity: str, record_id: UUID, body: MoveBody,
    actor: BusinessActorContext = Depends(require_business_member()),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Move a record to a stage — a step within its status, or on to a status the module allows next."""
    _gate(actor, entity)
    data = await StageEngine.move(
        session, business_id=business_id, entity=entity, record_id=record_id, to=body.to, note=body.note,
        actor_id=actor.request.identity_id, permissions=frozenset(actor.request.effective_permissions),
        correlation_id=actor.request.correlation_id, version=body.version)
    await session.commit()
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}
