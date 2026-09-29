"""Business-authoritative job-card endpoints (P5)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.jobs.service import JobService
from platform_core.permissions import JOBS_ASSIGN, JOBS_COMPLETE, JOBS_CREATE, JOBS_READ, JOBS_USE_PARTS

router = APIRouter(prefix="/v1/b/{business_id}/jobs", tags=["jobs"])


class CreateJob(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_contact_id: UUID
    title: str = Field(min_length=1, max_length=200)
    problem: str | None = Field(default=None, max_length=4000)
    location_id: UUID | None = None
    project_id: UUID | None = None
    source_quote_id: UUID | None = None
    source_type: str = "manual"
    source_id: UUID | None = None
    asset_description: str | None = Field(default=None, max_length=300)
    asset_serial: str | None = Field(default=None, max_length=100)
    priority: str = "normal"
    scheduled_at: str | None = None
    assigned_member_id: UUID | None = None


class AssignJob(BaseModel):
    model_config = ConfigDict(extra="forbid")
    member_id: UUID


class MoveJob(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    version: int = Field(ge=1)
    work_performed: str | None = Field(default=None, max_length=6000)
    completion_note: str | None = Field(default=None, max_length=2000)
    approval_note: str | None = Field(default=None, max_length=2000)


class ConsumePart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inventory_record_id: UUID
    quantity: int = Field(gt=0)
    serials: list[str] = Field(default_factory=list)
    idempotency_key: str = Field(min_length=1, max_length=100)


class ReturnPart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity: int = Field(gt=0)
    idempotency_key: str = Field(min_length=1, max_length=40)


@router.get("")
async def list_jobs(business_id: UUID, status: str | None = None,
                    customer_contact_id: UUID | None = None, project_id: UUID | None = None,
                    actor: BusinessActorContext = Depends(require_business_actor(JOBS_READ, "jobs")),
                    session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    rows = await JobService.list_jobs(session, business_id, status=status,
                                 customer_contact_id=customer_contact_id, project_id=project_id)
    return {"data": rows, "meta": {"correlation_id": actor.request.correlation_id}}


@router.post("")
async def create_job(business_id: UUID, body: CreateJob,
                     actor: BusinessActorContext = Depends(require_business_actor(JOBS_CREATE, "jobs")),
                     session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    job = await JobService.create(session, business_id, actor.request.identity_id,
                                  actor.request.correlation_id, body.model_dump(mode="python"))
    await session.commit()
    return {"data": await JobService.detail(session, business_id, job.id)}


@router.get("/{job_id}")
async def get_job(business_id: UUID, job_id: UUID,
                  actor: BusinessActorContext = Depends(require_business_actor(JOBS_READ, "jobs")),
                  session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    return {"data": await JobService.detail(session, business_id, job_id),
            "meta": {"correlation_id": actor.request.correlation_id}}


@router.post("/{job_id}/assign")
async def assign_job(business_id: UUID, job_id: UUID, body: AssignJob,
                     actor: BusinessActorContext = Depends(require_business_actor(JOBS_ASSIGN, "jobs")),
                     session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    await JobService.assign(session, business_id, job_id, body.member_id,
                            actor.request.identity_id, actor.request.correlation_id)
    await session.commit()
    return {"data": await JobService.detail(session, business_id, job_id)}


@router.post("/{job_id}/move")
async def move_job(business_id: UUID, job_id: UUID, body: MoveJob,
                   actor: BusinessActorContext = Depends(require_business_actor(JOBS_COMPLETE, "jobs")),
                   session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    await JobService.transition(session, business_id, job_id, body.status, body.work_performed,
                                body.completion_note, body.approval_note, body.version,
                                actor.request.identity_id, actor.request.correlation_id)
    await session.commit()
    return {"data": await JobService.detail(session, business_id, job_id)}


@router.post("/{job_id}/parts")
async def consume_job_part(business_id: UUID, job_id: UUID, body: ConsumePart,
                           actor: BusinessActorContext = Depends(require_business_actor(JOBS_USE_PARTS, "jobs")),
                           session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    part = await JobService.consume_part(session, business_id, job_id, body.inventory_record_id,
                                         body.quantity, body.serials, body.idempotency_key,
                                         actor.request.identity_id, actor.request.correlation_id)
    await session.commit()
    return {"data": {"id": str(part.id), "inventory_movement_id": str(part.inventory_movement_id)}}


@router.get("/{job_id}/parts/stock")
async def job_part_stock(business_id: UUID, job_id: UUID,
                         actor: BusinessActorContext = Depends(require_business_actor(JOBS_USE_PARTS, "jobs")),
                         session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    """The parts this person may use on this job: a technician sees the job's own
    location and their vans, not the whole stock book."""
    return {"data": await JobService.part_stock(session, business_id, job_id)}


@router.post("/{job_id}/parts/{part_id}/return")
async def return_job_part(business_id: UUID, job_id: UUID, part_id: UUID, body: ReturnPart,
                          actor: BusinessActorContext = Depends(require_business_actor(JOBS_USE_PARTS, "jobs")),
                          session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    back = await JobService.return_part(session, business_id, job_id, part_id, body.quantity,
                                        body.idempotency_key, actor.request.identity_id,
                                        actor.request.correlation_id)
    await session.commit()
    return {"data": back}
