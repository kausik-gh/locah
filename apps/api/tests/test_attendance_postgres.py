"""Attendance acceptance against a disposable LOCAL PostgreSQL database.

The caller supplies a database with main migrations applied. Each case creates
its own data in a transaction and rolls it back, including Academics fixtures
until the separate P5 branch is merged. Hosted URLs are deliberately refused.
"""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from platform_core.authorization.assignment_scope import bind as bind_assignment
from platform_core.authorization.location_scope import bind as bind_locations
from platform_core.exceptions import ConflictError, OutsideAssignmentScope, ResourceNotFound
from platform_core.services.attendance import AttendanceService
from platform_core.services.attendance_contracts import MembershipCheckinDecision
from platform_api.main import app
from platform_api.routers.v1_attendance import StaffCheckin


def _url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        pytest.fail("Attendance PostgreSQL tests require a disposable local DATABASE_URL")
    if urlparse(url.replace("postgresql+asyncpg://", "postgresql://")).hostname not in {"localhost", "127.0.0.1"}:
        pytest.fail("Attendance tests refuse a non-local PostgreSQL host")
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


async def _identity(session: AsyncSession, label: str) -> uuid.UUID:
    value = uuid.uuid4()
    await session.execute(text("INSERT INTO auth.users (id,email) VALUES (:id,:email)"),
                          {"id": value, "email": f"{label}-{value}@example.test"})
    return value


async def _business(session: AsyncSession, owner: uuid.UUID) -> uuid.UUID:
    value = uuid.uuid4()
    await session.execute(text("""INSERT INTO businesses
        (id,slug,display_name,primary_owner_identity_id,state)
        VALUES (:id,:slug,'Attendance fixture',:owner,'active')"""),
        {"id": value, "slug": f"attendance-{value.hex}", "owner": owner})
    return value


async def _location(session: AsyncSession, business_id: uuid.UUID) -> uuid.UUID:
    value = uuid.uuid4()
    await session.execute(text("""INSERT INTO business_locations
        (id,business_id,name) VALUES (:id,:bid,'Site X')"""), {"id": value, "bid": business_id})
    return value


async def _contact(session: AsyncSession, business_id: uuid.UUID, name: str,
                   identity: uuid.UUID | None = None) -> uuid.UUID:
    value = uuid.uuid4()
    await session.execute(text("""INSERT INTO customer_relationships_contacts
        (id,business_id,identity_id,display_name) VALUES (:id,:bid,:identity,:name)"""),
        {"id": value, "bid": business_id, "identity": identity, "name": name})
    return value


async def _member(session: AsyncSession, business_id: uuid.UUID,
                  identity: uuid.UUID, name: str) -> uuid.UUID:
    value = uuid.uuid4()
    await session.execute(text("""INSERT INTO workforce_members
        (id,business_id,identity_id,display_name) VALUES (:id,:bid,:identity,:name)"""),
        {"id": value, "bid": business_id, "identity": identity, "name": name})
    return value


async def _role(session: AsyncSession, business_id: uuid.UUID, identity: uuid.UUID,
                assignee: uuid.UUID | None = None) -> None:
    await session.execute(text("SET LOCAL ROLE platform_api"))
    for setting, value in (("app.current_business_id", business_id),
                           ("app.current_identity_id", identity),
                           ("app.current_assignee", assignee or "")):
        await session.execute(text("SELECT set_config(:name,:value,true)"),
                              {"name": setting, "value": str(value)})
    bind_assignment(session, assignee)
    bind_locations(session, None)


@asynccontextmanager
async def _case() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(_url(), poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()


class Eligibility:
    def __init__(self, contact_id: uuid.UUID, state: str) -> None:
        self.contact_id = contact_id
        self.state = state

    async def decide(self, session: AsyncSession, business_id: uuid.UUID,
                     enrolment_id: uuid.UUID) -> MembershipCheckinDecision:
        return MembershipCheckinDecision(enrolment_id, self.contact_id, self.state)  # type: ignore[arg-type]


def test_attendance_api_requires_authentication_and_rejects_geo_claims() -> None:
    business = uuid.uuid4()
    client = TestClient(app)
    assert client.get(f"/v1/b/{business}/attendance/events").status_code == 401
    with pytest.raises(PydanticValidationError):
        StaffCheckin.model_validate({"member_id": str(uuid.uuid4()),
            "location_id": str(uuid.uuid4()), "idempotency_key": "x", "geo_verified": True})


@pytest.mark.asyncio
async def test_member_checkin_allowed_replay_denied_and_tenant_rls() -> None:
    async with _case() as session:
        owner = await _identity(session, "owner")
        business = await _business(session, owner)
        other = await _business(session, owner)
        location = await _location(session, business)
        member = await _contact(session, business, "Member")
        await _role(session, business, owner)
        enrolment = uuid.uuid4()
        args: dict[str, Any] = dict(business_id=business, enrolment_id=enrolment,
            location_id=location, channel="qr", idempotency_key="member-scan-1",
            actor_id=owner, correlation_id=str(uuid.uuid4()))
        first = await AttendanceService.member_checkin(session, **args,
                                                        eligibility=Eligibility(member, "allowed"))
        assert await session.scalar(text("SELECT has_table_privilege('authenticated','attendance_events','SELECT')")) is False
        again = await AttendanceService.member_checkin(session, **args,
                                                        eligibility=Eligibility(member, "denied"))
        assert again["id"] == first["id"]
        assert first["verification_metadata"]["eligibility_state"] == "allowed"
        with pytest.raises(ConflictError):
            await AttendanceService.member_checkin(session, **{**args, "idempotency_key": "denied-scan"},
                                                    eligibility=Eligibility(member, "denied"))
        assert await session.scalar(text("SELECT count(*) FROM attendance_events WHERE business_id=:bid"),
                                    {"bid": business}) == 1
        await session.execute(text("SELECT set_config('app.current_business_id',:bid,true)"),
                              {"bid": str(other)})
        assert await session.scalar(text("SELECT count(*) FROM attendance_events")) == 0


@pytest.mark.asyncio
async def test_staff_presence_is_own_scope_and_never_claims_geo_proof() -> None:
    async with _case() as session:
        owner, staff_a, staff_b = [await _identity(session, label) for label in ("owner", "A", "B")]
        business = await _business(session, owner)
        location = await _location(session, business)
        a = await _member(session, business, staff_a, "Staff A")
        b = await _member(session, business, staff_b, "Staff B")
        await _role(session, business, staff_a, staff_a)
        row = await AttendanceService.staff_checkin(session, business_id=business,
            member_id=a, location_id=location, idempotency_key="site-1",
            actor_id=staff_a, correlation_id=str(uuid.uuid4()))
        assert row["geo_verified"] is False
        assert row["verification_metadata"]["geo_verification"] == "not_requested"
        await session.execute(text("SELECT set_config('app.current_identity_id',:id,true)"),
                              {"id": str(staff_b)})
        await session.execute(text("SELECT set_config('app.current_assignee',:id,true)"),
                              {"id": str(staff_b)})
        bind_assignment(session, staff_b)
        with pytest.raises(OutsideAssignmentScope):
            await AttendanceService.staff_checkin(session, business_id=business,
                member_id=a, location_id=location, idempotency_key="site-2",
                actor_id=staff_b, correlation_id=str(uuid.uuid4()))
        assert await session.scalar(text("SELECT count(*) FROM attendance_events")) == 0
        own = await AttendanceService.staff_checkin(session, business_id=business,
            member_id=b, location_id=location, idempotency_key="site-b",
            actor_id=staff_b, correlation_id=str(uuid.uuid4()))
        with pytest.raises(ResourceNotFound):
            await AttendanceService.checkout(session, business_id=business,
                event_id=uuid.UUID(row["id"]), expected_version=1,
                actor_id=staff_b, correlation_id=str(uuid.uuid4()))
        checked_out = await AttendanceService.checkout(session, business_id=business,
            event_id=uuid.UUID(own["id"]), expected_version=1,
            actor_id=staff_b, correlation_id=str(uuid.uuid4()))
        assert checked_out["status"] == "checked_out"


@pytest.mark.asyncio
async def test_booking_arrival_records_presence_without_changing_booking() -> None:
    async with _case() as session:
        owner = await _identity(session, "booking-owner")
        business = await _business(session, owner)
        location = await _location(session, business)
        contact = await _contact(session, business, "Guest")
        booking = uuid.uuid4()
        now = datetime.now(timezone.utc)
        await session.execute(text("""INSERT INTO bookings_bookings
            (id,business_id,location_id,customer_contact_id,booking_number,
             reservation_mode,status,title,starts_at,ends_at)
            VALUES (:id,:bid,:location,:contact,:number,'appointment','confirmed',
                    'Test appointment',:start,:end)"""),
            {"id": booking, "bid": business, "location": location, "contact": contact,
             "number": f"TEST-{booking.hex}", "start": now, "end": now + timedelta(hours=1)})
        await _role(session, business, owner)
        args: dict[str, Any] = dict(business_id=business, booking_id=booking,
            idempotency_key="arrival-1", actor_id=owner, correlation_id=str(uuid.uuid4()))
        first = await AttendanceService.booking_arrival(session, **args)
        again = await AttendanceService.booking_arrival(session, **{**args, "idempotency_key": "arrival-2"})
        assert first["id"] == again["id"]
        assert first["subject_contact_id"] == str(contact)
        assert await session.scalar(text("SELECT count(*) FROM attendance_events WHERE business_id=:bid"),
                                    {"bid": business}) == 1
        assert await session.scalar(text("SELECT status FROM bookings_bookings WHERE id=:id"),
                                    {"id": booking}) == "confirmed"


@pytest.mark.asyncio
async def test_class_roster_defaults_present_and_replay_is_single_occurrence() -> None:
    async with _case() as session:
        owner, teacher, unrelated, guardian = [await _identity(session, label)
                                               for label in ("owner", "teacher", "unrelated", "guardian")]
        business = await _business(session, owner)
        location = await _location(session, business)
        teacher_member = await _member(session, business, teacher, "Teacher")
        await _member(session, business, unrelated, "Other teacher")
        asha = await _contact(session, business, "Asha")
        bharat = await _contact(session, business, "Bharat")
        await _contact(session, business, "Asha's guardian", guardian)
        # Until the separate P5 branch lands, transactional fixtures reproduce
        # its read contract. Once merged, the same case uses its real tables.
        academics_installed = bool(await session.scalar(text(
            "SELECT to_regclass('public.academics_sessions') IS NOT NULL")))
        if not academics_installed:
            await session.execute(text("""CREATE TABLE public.academics_batches
                (id uuid PRIMARY KEY,business_id uuid,teacher_member_id uuid)"""))
            await session.execute(text("""CREATE TABLE public.academics_sessions
                (id uuid PRIMARY KEY,business_id uuid,batch_id uuid,teacher_member_id uuid,
                 location_id uuid,status text,topic text,starts_at timestamptz,ends_at timestamptz)"""))
            await session.execute(text("""CREATE TABLE public.academics_enrolments
                (id uuid PRIMARY KEY,business_id uuid,batch_id uuid,student_contact_id uuid,status text)"""))
            await session.execute(text("""GRANT SELECT ON public.academics_batches,
                public.academics_sessions,public.academics_enrolments TO platform_api"""))
        batch, occurrence = uuid.uuid4(), uuid.uuid4()
        now = datetime.now(timezone.utc)
        if academics_installed:
            course = uuid.uuid4()
            await session.execute(text("""INSERT INTO academics_courses (id,business_id,title)
                VALUES (:id,:bid,'Physics')"""), {"id": course, "bid": business})
            await session.execute(text("""INSERT INTO academics_batches
                (id,business_id,course_id,name,teacher_member_id)
                VALUES (:id,:bid,:course,'Class A',:teacher)"""),
                {"id": batch, "bid": business, "course": course, "teacher": teacher_member})
        else:
            await session.execute(text("""INSERT INTO academics_batches VALUES (:id,:bid,:teacher)"""),
                                  {"id": batch, "bid": business, "teacher": teacher_member})
        await session.execute(text("""INSERT INTO academics_sessions
            (id,business_id,batch_id,teacher_member_id,location_id,status,topic,starts_at,ends_at)
            VALUES (:id,:bid,:batch,:teacher,:loc,'scheduled','Physics',:start,:end)"""),
            {"id": occurrence, "bid": business, "batch": batch, "teacher": teacher_member,
             "loc": location, "start": now, "end": now + timedelta(hours=1)})
        for student in (asha, bharat):
            await session.execute(text("""INSERT INTO academics_enrolments
                (id,business_id,batch_id,student_contact_id,status) VALUES
                (:id,:bid,:batch,:student,'active')"""),
                {"id": uuid.uuid4(), "bid": business, "batch": batch, "student": student})
        await _role(session, business, teacher, teacher)
        roster = await AttendanceService.roster(session, business_id=business,
                                                class_session_id=occurrence)
        assert [student["name"] for student in roster["students"]] == ["Asha", "Bharat"]
        assert all(student["status"] == "present" for student in roster["students"])
        args: dict[str, Any] = dict(business_id=business, class_session_id=occurrence,
            statuses={bharat: "absent"}, idempotency_key="class-save-1",
            actor_id=teacher, correlation_id=str(uuid.uuid4()))
        first = await AttendanceService.record_session(session, **args)
        second = await AttendanceService.record_session(session, **args)
        assert [row["id"] for row in second] == [row["id"] for row in first]
        assert {row["subject_contact_id"]: row["status"] for row in first} == {
            str(asha): "present", str(bharat): "absent"}
        assert await session.scalar(text("SELECT count(*) FROM attendance_events")) == 2
        await session.execute(text("SELECT set_config('app.current_assignee',:id,true)"),
                              {"id": str(unrelated)})
        bind_assignment(session, unrelated)
        # With the real Academics tables, their restrictive RLS hides another
        # teacher's class entirely (not found); the stub tables only reach the
        # service's own scope check. Either way the roster is refused.
        with pytest.raises(ResourceNotFound if academics_installed else OutsideAssignmentScope):
            await AttendanceService.roster(session, business_id=business,
                                            class_session_id=occurrence)
        # No customer-facing attendance route exists: guardians cannot obtain
        # another student's record merely by knowing an event or session ID.
