"""Attendance endpoints: presence only, never eligibility or source lifecycle."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.permissions import ATTENDANCE_MANAGE, ATTENDANCE_READ, ATTENDANCE_RECORD
from platform_core.services.attendance import AttendanceService
from platform_core.exceptions import ValidationError
from platform_core.memberships.checkin import MembershipsCheckinEligibility
from platform_core.services.attendance_contracts import MembershipCheckinEligibility

router = APIRouter(prefix="/v1/b/{business_id}/attendance", tags=["attendance"])


def get_membership_eligibility() -> MembershipCheckinEligibility:
    """Memberships decides who may come in; Attendance only records the visit."""
    return MembershipsCheckinEligibility()


class MemberCheckin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # The enrolment itself, or the member's printed code / QR payload.
    enrolment_id: UUID | None = None
    code: str | None = Field(default=None, min_length=4, max_length=64)
    location_id: UUID | None = None
    channel: Literal["manual", "qr"] = "manual"
    idempotency_key: str = Field(min_length=1, max_length=80)


class StaffCheckin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    member_id: UUID
    location_id: UUID
    idempotency_key: str = Field(min_length=1, max_length=80)


class BookingArrival(BaseModel):
    model_config = ConfigDict(extra="forbid")
    booking_id: UUID
    idempotency_key: str = Field(min_length=1, max_length=80)


class SessionAttendance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statuses: dict[UUID, Literal["present", "absent", "late", "excused"]] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=80)


class Checkout(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)


class AcademicCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["present", "absent", "late", "excused"]
    version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


@router.get("/events")
async def events(business_id: UUID, context: str | None = None, today: bool = Query(default=False),
                 actor: BusinessActorContext = Depends(require_business_actor(ATTENDANCE_READ, "attendance")),
                 session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    return {"data": await AttendanceService.list_events(session, business_id=business_id,
                                                         context=context, today=today)}


@router.get("/self")
async def self_options(business_id: UUID,
                       actor: BusinessActorContext = Depends(require_business_actor(ATTENDANCE_READ, "attendance")),
                       session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    return {"data": await AttendanceService.self_options(session, business_id=business_id,
                                                          actor_id=actor.request.identity_id)}


@router.post("/member-checkins")
async def member_checkin(business_id: UUID, body: MemberCheckin,
                         actor: BusinessActorContext = Depends(require_business_actor(ATTENDANCE_RECORD, "attendance")),
                         session: AsyncSession = Depends(get_db_session),
                         eligibility: MembershipCheckinEligibility = Depends(get_membership_eligibility)) -> dict[str, Any]:
    enrolment_id = body.enrolment_id
    if enrolment_id is None:
        if not body.code:
            raise ValidationError("Scan the member's code or choose the membership")
        enrolment_id = await eligibility.resolve(session, business_id, body.code)
    row = await AttendanceService.member_checkin(session, business_id=business_id,
        enrolment_id=enrolment_id, location_id=body.location_id,
        channel=body.channel, idempotency_key=body.idempotency_key,
        actor_id=actor.request.identity_id, correlation_id=actor.request.correlation_id,
        eligibility=eligibility)
    await session.commit()
    return {"data": row}


@router.post("/staff-checkins")
async def staff_checkin(business_id: UUID, body: StaffCheckin,
                        actor: BusinessActorContext = Depends(require_business_actor(ATTENDANCE_RECORD, "attendance")),
                        session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    row = await AttendanceService.staff_checkin(session, business_id=business_id,
        member_id=body.member_id, location_id=body.location_id,
        idempotency_key=body.idempotency_key, actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id)
    await session.commit()
    return {"data": row}


@router.post("/booking-arrivals")
async def booking_arrival(business_id: UUID, body: BookingArrival,
                          actor: BusinessActorContext = Depends(require_business_actor(ATTENDANCE_RECORD, "attendance")),
                          session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    row = await AttendanceService.booking_arrival(session, business_id=business_id,
        booking_id=body.booking_id, idempotency_key=body.idempotency_key,
        actor_id=actor.request.identity_id, correlation_id=actor.request.correlation_id)
    await session.commit()
    return {"data": row}


@router.get("/sessions/{session_id}/roster")
async def roster(business_id: UUID, session_id: UUID,
                 actor: BusinessActorContext = Depends(require_business_actor(ATTENDANCE_READ, "attendance")),
                 session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    return {"data": await AttendanceService.roster(session, business_id=business_id,
                                                    class_session_id=session_id)}


@router.get("/sessions/today")
async def today_sessions(business_id: UUID,
                         actor: BusinessActorContext = Depends(require_business_actor(ATTENDANCE_READ, "attendance")),
                         session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    return {"data": await AttendanceService.today_sessions(session, business_id=business_id)}


@router.post("/sessions/{session_id}/records")
async def record_session(business_id: UUID, session_id: UUID, body: SessionAttendance,
                         actor: BusinessActorContext = Depends(require_business_actor(ATTENDANCE_RECORD, "attendance")),
                         session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    rows = await AttendanceService.record_session(session, business_id=business_id,
        class_session_id=session_id, statuses=body.statuses,
        idempotency_key=body.idempotency_key, actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id)
    await session.commit()
    return {"data": rows}


@router.post("/events/{event_id}/checkout")
async def checkout(business_id: UUID, event_id: UUID, body: Checkout,
                   actor: BusinessActorContext = Depends(require_business_actor(ATTENDANCE_RECORD, "attendance")),
                   session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    row = await AttendanceService.checkout(session, business_id=business_id,
        event_id=event_id, expected_version=body.version,
        actor_id=actor.request.identity_id, correlation_id=actor.request.correlation_id)
    await session.commit()
    return {"data": row}


@router.post("/events/{event_id}/academic-correction")
async def correct_academic(business_id: UUID, event_id: UUID, body: AcademicCorrection,
                           actor: BusinessActorContext = Depends(require_business_actor(ATTENDANCE_MANAGE, "attendance")),
                           session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    row = await AttendanceService.correct_academic(session, business_id=business_id,
        event_id=event_id, status=body.status, expected_version=body.version,
        reason=body.reason, actor_id=actor.request.identity_id)
    await session.commit()
    return {"data": row}
