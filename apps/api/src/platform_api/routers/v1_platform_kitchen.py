"""Kitchen display API. Preparation only: no prices, no phone numbers, no stock writes."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.authorization.location_scope import scoped_locations
from platform_core.kitchen.service import KitchenService
from platform_core.kitchen.snapshot import STATION_KINDS
from platform_core.permissions import KITCHEN_ADVANCE, KITCHEN_CONFIGURE, KITCHEN_READ

router = APIRouter(prefix="/v1/platform/businesses", tags=["kitchen"])
MODULE = "kitchen"


class StationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=40)
    key: str | None = Field(default=None, max_length=32)
    location_id: UUID | None = None


class RoutesBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offering_id: UUID
    station_ids: list[UUID] = Field(default_factory=list, max_length=8)


class StepBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    station_id: UUID | None = None
    version: int | None = Field(default=None, ge=1)


class PriorityBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: Literal["normal", "rush"]
    version: int | None = Field(default=None, ge=1)


def _meta(actor: BusinessActorContext) -> dict[str, str]:
    return {"correlation_id": actor.request.correlation_id}


def _locations(actor: BusinessActorContext) -> tuple[UUID, ...] | None:
    return scoped_locations(actor.actor_membership)


def _station(station: Any) -> dict[str, Any]:
    return {
        "id": str(station.id),
        "key": station.key,
        "name": station.name,
        "active": station.active,
        "location_id": str(station.location_id) if station.location_id else None,
        "sort_order": station.sort_order,
    }


@router.get("/{business_id}/kitchen/board")
async def kitchen_board(
    business_id: UUID,
    station_id: UUID | None = Query(default=None),
    actor: BusinessActorContext = Depends(require_business_actor(KITCHEN_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await KitchenService.board(
        session,
        business_id=business_id,
        station_id=station_id,
        location_ids=_locations(actor),
    )
    return {"data": data, "meta": _meta(actor)}


@router.get("/{business_id}/kitchen/stations")
async def list_stations(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(KITCHEN_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    stations = await KitchenService.list_stations(
        session, business_id=business_id, location_ids=_locations(actor)
    )
    routes = await KitchenService.routes_for(session, business_id=business_id)
    return {
        "data": {
            "stations": [_station(station) for station in stations],
            "station_kinds": [{"key": key, "name": name} for key, name in STATION_KINDS],
            "routes": [
                {"offering_id": str(offering_id), "station_ids": [str(sid) for sid in station_ids]}
                for offering_id, station_ids in routes.items()
            ],
        },
        "meta": _meta(actor),
    }


@router.post("/{business_id}/kitchen/stations")
async def create_station(
    business_id: UUID,
    body: StationBody,
    actor: BusinessActorContext = Depends(require_business_actor(KITCHEN_CONFIGURE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    station = await KitchenService.create_station(
        session,
        business_id=business_id,
        name=body.name,
        key=body.key,
        location_id=body.location_id,
    )
    await session.commit()
    return {"data": _station(station), "meta": _meta(actor)}


@router.put("/{business_id}/kitchen/routes")
async def set_routes(
    business_id: UUID,
    body: RoutesBody,
    actor: BusinessActorContext = Depends(require_business_actor(KITCHEN_CONFIGURE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    station_ids = await KitchenService.set_routes(
        session,
        business_id=business_id,
        offering_id=body.offering_id,
        station_ids=body.station_ids,
    )
    await session.commit()
    return {
        "data": {"offering_id": str(body.offering_id), "station_ids": [str(sid) for sid in station_ids]},
        "meta": _meta(actor),
    }


async def _step(
    session: AsyncSession,
    actor: BusinessActorContext,
    business_id: UUID,
    ticket_id: UUID,
    step: str,
    body: StepBody,
) -> dict[str, Any]:
    ticket = await KitchenService.advance(
        session,
        business_id=business_id,
        ticket_id=ticket_id,
        step=step,
        station_id=body.station_id,
        location_ids=_locations(actor),
        expected_version=body.version,
    )
    await session.commit()
    return {
        "data": {"id": str(ticket.id), "status": ticket.status, "version": ticket.version, "attention": ticket.attention},
        "meta": _meta(actor),
    }


@router.post("/{business_id}/kitchen/tickets/{ticket_id}/start")
async def start_ticket(
    business_id: UUID,
    ticket_id: UUID,
    body: StepBody | None = None,
    actor: BusinessActorContext = Depends(require_business_actor(KITCHEN_ADVANCE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return await _step(session, actor, business_id, ticket_id, "start", body or StepBody())


@router.post("/{business_id}/kitchen/tickets/{ticket_id}/ready")
async def ready_ticket(
    business_id: UUID,
    ticket_id: UUID,
    body: StepBody | None = None,
    actor: BusinessActorContext = Depends(require_business_actor(KITCHEN_ADVANCE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return await _step(session, actor, business_id, ticket_id, "ready", body or StepBody())


@router.post("/{business_id}/kitchen/tickets/{ticket_id}/serve")
async def serve_ticket(
    business_id: UUID,
    ticket_id: UUID,
    body: StepBody | None = None,
    actor: BusinessActorContext = Depends(require_business_actor(KITCHEN_ADVANCE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return await _step(session, actor, business_id, ticket_id, "serve", body or StepBody())


@router.post("/{business_id}/kitchen/tickets/{ticket_id}/clear")
async def clear_ticket(
    business_id: UUID,
    ticket_id: UUID,
    body: StepBody | None = None,
    actor: BusinessActorContext = Depends(require_business_actor(KITCHEN_ADVANCE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return await _step(session, actor, business_id, ticket_id, "clear", body or StepBody())


@router.post("/{business_id}/kitchen/tickets/{ticket_id}/priority")
async def ticket_priority(
    business_id: UUID,
    ticket_id: UUID,
    body: PriorityBody,
    actor: BusinessActorContext = Depends(require_business_actor(KITCHEN_ADVANCE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    ticket = await KitchenService.set_priority(
        session,
        business_id=business_id,
        ticket_id=ticket_id,
        priority=body.priority,
        location_ids=_locations(actor),
        expected_version=body.version,
    )
    await session.commit()
    return {
        "data": {"id": str(ticket.id), "priority": ticket.priority, "version": ticket.version},
        "meta": _meta(actor),
    }
