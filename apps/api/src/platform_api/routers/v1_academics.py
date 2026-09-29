"""Staff Academics API and identity-filtered guardian/student portal."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, get_identity_context, require_business_actor
from platform_core.context import RequestContext
from platform_core.permissions import ACADEMICS_MANAGE, ACADEMICS_READ, ACADEMICS_TEACH
from platform_core.services.academics import AcademicsService

router = APIRouter(prefix="/v1/b/{business_id}/academics", tags=["academics"])
portal_router = APIRouter(prefix="/v1/me/academics", tags=["academics-portal"])


class CourseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)


class BatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_id: UUID
    name: str = Field(min_length=1, max_length=200)
    teacher_member_id: UUID | None = None
    location_id: UUID | None = None
    room: str | None = Field(default=None, max_length=200)
    meeting_url: str | None = Field(default=None, max_length=1000)
    starts_on: date | None = None
    ends_on: date | None = None
    capacity: int | None = Field(default=None, gt=0)


class SessionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    starts_at: datetime
    ends_at: datetime
    topic: str | None = Field(default=None, max_length=300)
    meeting_url: str | None = Field(default=None, max_length=1000)


class EnrolBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_contact_id: UUID
    guardian_contact_id: UUID | None = None
    is_minor: bool = False


class AssessmentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    maximum: Decimal = Field(gt=0)


class ResultBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enrolment_id: UUID
    marks: Decimal = Field(ge=0)
    teacher_note: str | None = Field(default=None, max_length=2000)


class AnnouncementBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)


@router.get("/courses")
async def courses(business_id: UUID,
                  actor: BusinessActorContext = Depends(require_business_actor(ACADEMICS_READ, "academics")),
                  session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    return {"data": await AcademicsService.courses(session, business_id)}


@router.post("/courses")
async def create_course(business_id: UUID, body: CourseBody,
                        actor: BusinessActorContext = Depends(require_business_actor(ACADEMICS_MANAGE, "academics")),
                        session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    row = await AcademicsService.create_course(session, business_id, actor.request.identity_id,
                                                actor.request.correlation_id, body.title, body.description)
    await session.commit()
    return {"data": row}


@router.get("/batches")
async def batches(business_id: UUID, course_id: UUID | None = None,
                  actor: BusinessActorContext = Depends(require_business_actor(ACADEMICS_READ, "academics")),
                  session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    return {"data": await AcademicsService.batches(session, business_id, course_id)}


@router.post("/batches")
async def create_batch(business_id: UUID, body: BatchBody,
                       actor: BusinessActorContext = Depends(require_business_actor(ACADEMICS_MANAGE, "academics")),
                       session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    row = await AcademicsService.create_batch(session, business_id, actor.request.identity_id,
                                               actor.request.correlation_id, body.model_dump())
    await session.commit()
    return {"data": row}


@router.get("/batches/{batch_id}/sessions")
async def sessions(business_id: UUID, batch_id: UUID,
                   actor: BusinessActorContext = Depends(require_business_actor(ACADEMICS_READ, "academics")),
                   session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    return {"data": await AcademicsService.sessions(session, business_id, batch_id)}


@router.post("/batches/{batch_id}/sessions")
async def add_session(business_id: UUID, batch_id: UUID, body: SessionBody,
                      actor: BusinessActorContext = Depends(require_business_actor(ACADEMICS_TEACH, "academics")),
                      session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    row = await AcademicsService.create_session(session, business_id, batch_id,
                                                 actor.request.identity_id, actor.request.correlation_id,
                                                 body.model_dump())
    await session.commit()
    return {"data": row}


@router.get("/batches/{batch_id}/enrolments")
async def enrolments(business_id: UUID, batch_id: UUID,
                     actor: BusinessActorContext = Depends(require_business_actor(ACADEMICS_READ, "academics")),
                     session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    return {"data": await AcademicsService.enrolments(session, business_id, batch_id)}


@router.post("/batches/{batch_id}/enrolments")
async def enrol(business_id: UUID, batch_id: UUID, body: EnrolBody,
                actor: BusinessActorContext = Depends(require_business_actor(ACADEMICS_MANAGE, "academics")),
                session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    row = await AcademicsService.enrol(session, business_id, batch_id,
                                       actor.request.identity_id, actor.request.correlation_id,
                                       body.model_dump())
    await session.commit()
    return {"data": row}


@router.post("/batches/{batch_id}/assessments")
async def assessment(business_id: UUID, batch_id: UUID, body: AssessmentBody,
                     actor: BusinessActorContext = Depends(require_business_actor(ACADEMICS_TEACH, "academics")),
                     session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    row = await AcademicsService.create_assessment(session, business_id, batch_id,
                                                    actor.request.identity_id, actor.request.correlation_id,
                                                    body.title, body.maximum)
    await session.commit()
    return {"data": row}


@router.get("/batches/{batch_id}/assessments")
async def assessments(business_id: UUID, batch_id: UUID,
                      actor: BusinessActorContext = Depends(require_business_actor(ACADEMICS_READ, "academics")),
                      session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    return {"data": await AcademicsService.assessments(session, business_id, batch_id)}


@router.post("/assessments/{assessment_id}/results")
async def result(business_id: UUID, assessment_id: UUID, body: ResultBody,
                 actor: BusinessActorContext = Depends(require_business_actor(ACADEMICS_TEACH, "academics")),
                 session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    row = await AcademicsService.record_result(session, business_id, assessment_id,
                                                body.enrolment_id, body.marks, body.teacher_note,
                                                actor.request.identity_id, actor.request.correlation_id)
    await session.commit()
    return {"data": row}


@router.get("/batches/{batch_id}/announcements")
async def announcements(business_id: UUID, batch_id: UUID,
                        actor: BusinessActorContext = Depends(require_business_actor(ACADEMICS_READ, "academics")),
                        session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    return {"data": await AcademicsService.announcements(session, business_id, batch_id)}


@router.post("/batches/{batch_id}/announcements")
async def announce(business_id: UUID, batch_id: UUID, body: AnnouncementBody,
                   actor: BusinessActorContext = Depends(require_business_actor(ACADEMICS_TEACH, "academics")),
                   session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    row = await AcademicsService.announce(session, business_id, batch_id, body.title, body.body,
                                           actor.request.identity_id, actor.request.correlation_id)
    await session.commit()
    return {"data": row}


@portal_router.get("/{business}")
async def my_academics(business: UUID,
                       ctx: RequestContext = Depends(get_identity_context),
                       session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    # The SECURITY DEFINER function filters by the *bound* identity, not by a
    # caller-supplied student/guardian ID. Never set a business-wide RLS scope.
    await session.execute(text("SELECT set_config('app.current_identity_id', :id, true)"),
                          {"id": str(ctx.identity_id)})
    value = await session.scalar(text("SELECT academics_guardian_portal(:bid)"), {"bid": business})
    return {"data": json.loads(value) if isinstance(value, str) else value or []}
