"""Dispatch APIs — execution of a delivery or pickup after the order exists."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.dispatch.service import DispatchService
from platform_core.permissions import DISPATCH_ASSIGN, DISPATCH_READ, DISPATCH_UPDATE_STATUS

router = APIRouter(prefix="/v1/b", tags=["dispatch"])


class Dropoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line: str | None = None
    area: str | None = None
    city: str | None = None
    postal_code: str | None = None
    lat: float | None = None
    lng: float | None = None


class JobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: UUID
    kind: str | None = None
    location_id: UUID | None = None
    dropoff: Dropoff | None = None
    planned_at: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=200)


class AssignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: UUID
    planned_at: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=200)


class StatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    proof_note: str | None = None
    reason: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=200)


def _can_assign(actor: BusinessActorContext) -> bool:
    return actor.request.has_permission(DISPATCH_ASSIGN)


@router.post("/{business_id}/dispatch/jobs")
async def create_job(
    business_id: UUID,
    body: JobCreateRequest,
    actor: BusinessActorContext = Depends(require_business_actor(DISPATCH_ASSIGN, "dispatch")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    job = await DispatchService.create_job(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(mode="json"),
    )
    # Serialize before commit: the tenant GUC is local to this transaction.
    data = await DispatchService.serialize_one(session, job, privileged=True)
    await session.commit()
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.get("/{business_id}/dispatch/board")
async def board(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(DISPATCH_READ, "dispatch")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    columns = await DispatchService.board(session, business_id)
    return {"data": {"columns": columns}, "meta": {"correlation_id": actor.request.correlation_id}}


@router.get("/{business_id}/dispatch/mine")
async def mine(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(DISPATCH_READ, "dispatch")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await DispatchService.mine(session, business_id)
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.get("/{business_id}/dispatch/jobs/{job_id}")
async def get_job(
    business_id: UUID,
    job_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(DISPATCH_READ, "dispatch")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    job = await DispatchService.get_job(session, business_id=business_id, job_id=job_id)
    return {
        "data": await DispatchService.serialize_one(session, job, privileged=_can_assign(actor)),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/dispatch/jobs/{job_id}/assign")
async def assign_job(
    business_id: UUID,
    job_id: UUID,
    body: AssignRequest,
    actor: BusinessActorContext = Depends(require_business_actor(DISPATCH_ASSIGN, "dispatch")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    payload = body.model_dump(mode="json")
    payload["status"] = "assigned"
    job = await DispatchService.transition(
        session,
        business_id=business_id,
        job_id=job_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=payload,
    )
    data = await DispatchService.serialize_one(session, job, privileged=True)
    await session.commit()
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.post("/{business_id}/dispatch/jobs/{job_id}/status")
async def update_status(
    business_id: UUID,
    job_id: UUID,
    body: StatusRequest,
    actor: BusinessActorContext = Depends(require_business_actor(DISPATCH_UPDATE_STATUS, "dispatch")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    job = await DispatchService.transition(
        session,
        business_id=business_id,
        job_id=job_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(mode="json"),
    )
    data = await DispatchService.serialize_one(session, job, privileged=_can_assign(actor))
    await session.commit()
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}
