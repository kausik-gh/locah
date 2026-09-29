"""Walk-in queue board: issue a token, call, serve, miss, requeue."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.permissions import QUEUE_CONFIGURE, QUEUE_OPERATE, QUEUE_READ
from platform_core.services.queue import QueueService

router = APIRouter(prefix="/v1/platform/businesses", tags=["queue"])
MODULE = "queue-operations"


class LaneBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID
    name: str = Field(min_length=1, max_length=80)
    provider_id: UUID | None = None
    department: str | None = Field(default=None, max_length=80)
    resource_id: UUID | None = None
    allow_requeue: bool = True
    turn_soon_ahead: int = Field(default=2, ge=0, le=50)
    avg_service_minutes: int | None = Field(default=None, ge=1, le=480)


class IssueBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lane_id: UUID
    party_label: str | None = Field(default=None, max_length=80)
    customer_contact_id: UUID | None = None
    booking_id: UUID | None = None
    priority: int = Field(default=0, ge=0, le=9)
    idempotency_key: str | None = Field(default=None, max_length=80)


def _meta(actor: BusinessActorContext) -> dict[str, str]:
    return {"correlation_id": actor.request.correlation_id}


@router.get("/{business_id}/queue/lanes")
async def list_lanes(
    business_id: UUID,
    location_id: UUID | None = None,
    department: str | None = None,
    provider_id: UUID | None = None,
    actor: BusinessActorContext = Depends(require_business_actor(QUEUE_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    lanes = await QueueService.list_lanes(
        session, business_id, location_id=location_id, department=department, provider_id=provider_id,
    )
    return {"data": {"lanes": [QueueService.serialize_lane(lane) for lane in lanes]}, "meta": _meta(actor)}


@router.post("/{business_id}/queue/lanes")
async def create_lane(
    business_id: UUID, body: LaneBody,
    actor: BusinessActorContext = Depends(require_business_actor(QUEUE_CONFIGURE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    lane = await QueueService.create_lane(
        session, business_id, actor.request.identity_id, body.model_dump(),
    )
    data = QueueService.serialize_lane(lane)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.get("/{business_id}/queue/lanes/{lane_id}")
async def board(
    business_id: UUID, lane_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(QUEUE_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await QueueService.board(session, business_id, lane_id)
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/queue/entries")
async def issue(
    business_id: UUID, body: IssueBody,
    actor: BusinessActorContext = Depends(require_business_actor(QUEUE_OPERATE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    entry = await QueueService.issue(session, business_id, actor.request.identity_id, body.model_dump())
    lane = await QueueService.get_lane(session, business_id, entry.lane_id)
    names = await QueueService._labels(session, [entry])
    data = QueueService.serialize(entry, lane, names.get(entry.id), ahead=None)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/queue/lanes/{lane_id}/call-next")
async def call_next(
    business_id: UUID, lane_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(QUEUE_OPERATE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    entry = await QueueService.call_next(session, business_id, lane_id, actor.request.identity_id)
    lane = await QueueService.get_lane(session, business_id, lane_id)
    names = await QueueService._labels(session, [entry])
    data = QueueService.serialize(entry, lane, names.get(entry.id), ahead=None)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/queue/entries/{entry_id}/{action}")
async def act(
    business_id: UUID, entry_id: UUID,
    action: Literal["call", "serve", "complete", "miss", "requeue"],
    actor: BusinessActorContext = Depends(require_business_actor(QUEUE_OPERATE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    entry = await QueueService.act(session, business_id, entry_id, action, actor.request.identity_id)
    lane = await QueueService.get_lane(session, business_id, entry.lane_id)
    names = await QueueService._labels(session, [entry])
    data = QueueService.serialize(entry, lane, names.get(entry.id), ahead=None)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}
