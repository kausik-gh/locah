"""Shared presence records. Source domains own eligibility and occurrence truth."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.authorization.assignment_scope import current as assigned_identity
from platform_core.authorization.location_scope import current as allowed_locations
from platform_core.exceptions import (ConflictError, OutsideAssignmentScope,
                                      OutsideLocationScope, ResourceNotFound, ValidationError)
from platform_core.models import (Booking, BusinessLocation, CustomerContact,
                                  WorkforceLocationAssignment, WorkforceMember)
from platform_core.services.audit import AuditService
from platform_core.services.outbox import OutboxService
from platform_core.services.attendance_contracts import (MembershipCheckinEligibility,
                                                          UnconnectedMembershipEligibility)

ACADEMIC_STATUSES = frozenset({"present", "absent", "late", "excused"})
CONTEXTS = frozenset({"membership_checkin", "academic_session", "staff_site", "booking_arrival"})
IST = ZoneInfo("Asia/Kolkata")


def _view(row: Any) -> dict[str, Any]:
    return {key: str(value) if isinstance(value, uuid.UUID) else
            value.isoformat() if isinstance(value, datetime) else value
            for key, value in dict(row).items()}


def _key(value: str) -> str:
    key = value.strip()
    if not key or len(key) > 80:
        raise ValidationError("Supply a request key of at most 80 characters")
    return key


def _location(session: AsyncSession, location_id: uuid.UUID | None) -> None:
    allowed = allowed_locations(session)
    if allowed is not None and location_id is not None and location_id not in allowed:
        raise OutsideLocationScope()


async def _lock(session: AsyncSession, business_id: uuid.UUID, key: str) -> None:
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key), 5300)"),
                          {"key": f"{business_id}:{key}"})


async def _event(session: AsyncSession, *, business_id: uuid.UUID, actor_id: uuid.UUID,
                 correlation_id: str, kind: str, event_id: uuid.UUID,
                 context: str, status: str, source_id: str | None = None) -> None:
    # source_id is the owning domain's occurrence (a membership enrolment, an
    # academic session, a booking), so a subscriber never reads attendance rows.
    await OutboxService.publish(session, event_type=kind, business_id=business_id,
                                correlation_id=correlation_id,
                                payload={"attendance_event_id": str(event_id), "context": context,
                                         "status": status, "source_id": source_id})
    await AuditService.record(session, event_type=kind, actor_identity_id=actor_id,
                              actor_context="business", business_id=business_id,
                              resource_type="attendance_event", resource_id=event_id,
                              action=kind, after_state={"context": context, "status": status})


@dataclass(frozen=True)
class AcademicSession:
    id: uuid.UUID
    batch_id: uuid.UUID
    teacher_member_id: uuid.UUID | None
    location_id: uuid.UUID | None
    students: tuple[tuple[uuid.UUID, str], ...]


class AcademicAttendanceSource:
    """Read-only adapter to P5 Academics, once its branch is integrated."""

    @staticmethod
    async def resolve(session: AsyncSession, business_id: uuid.UUID,
                      session_id: uuid.UUID) -> AcademicSession:
        if not await session.scalar(text("SELECT to_regclass('public.academics_sessions') IS NOT NULL")):
            raise ConflictError("Academics sessions are not installed yet")
        row = (await session.execute(text("""SELECT s.id,s.batch_id,
                COALESCE(s.teacher_member_id,b.teacher_member_id) AS teacher_member_id,
                s.location_id,s.status FROM academics_sessions s
                JOIN academics_batches b ON b.id=s.batch_id AND b.business_id=:bid
                WHERE s.id=:sid AND s.business_id=:bid"""),
                {"sid": session_id, "bid": business_id})).mappings().one_or_none()
        if row is None:
            raise ResourceNotFound("Class session")
        if row["status"] != "scheduled":
            raise ConflictError("Attendance can be recorded only for a scheduled class")
        teacher = row["teacher_member_id"]
        scoped = assigned_identity(session)
        if scoped is not None:
            member = (await session.execute(select(WorkforceMember.identity_id).where(
                WorkforceMember.id == teacher, WorkforceMember.business_id == business_id))).scalar_one_or_none()
            if member != scoped:
                raise OutsideAssignmentScope()
        _location(session, row["location_id"])
        students = (await session.execute(text("""SELECT e.student_contact_id,c.display_name
            FROM academics_enrolments e
            JOIN customer_relationships_contacts c ON c.id=e.student_contact_id AND c.business_id=:bid
            WHERE e.business_id=:bid AND e.batch_id=:batch AND e.status='active'
              AND c.deleted_at IS NULL ORDER BY c.display_name,e.student_contact_id"""),
            {"bid": business_id, "batch": row["batch_id"]})).all()
        return AcademicSession(row["id"], row["batch_id"], teacher,
                               row["location_id"], tuple((sid, name) for sid, name in students))


class AttendanceService:
    @staticmethod
    async def self_options(session: AsyncSession, *, business_id: uuid.UUID,
                           actor_id: uuid.UUID) -> dict[str, Any]:
        member = (await session.execute(select(WorkforceMember.id, WorkforceMember.display_name).where(
            WorkforceMember.business_id == business_id,
            WorkforceMember.identity_id == actor_id,
            WorkforceMember.status == "active", WorkforceMember.deleted_at.is_(None)))).first()
        query = select(BusinessLocation.id, BusinessLocation.name).where(
            BusinessLocation.business_id == business_id,
            BusinessLocation.deleted_at.is_(None))
        locs = allowed_locations(session)
        if locs is not None:
            query = query.where(BusinessLocation.id.in_(locs))
        locations = (await session.execute(query.order_by(BusinessLocation.name))).all()
        return {"member": {"id": str(member[0]), "name": member[1]} if member else None,
                "locations": [{"id": str(loc_id), "name": name} for loc_id, name in locations]}

    @staticmethod
    async def today_sessions(session: AsyncSession, *, business_id: uuid.UUID) -> list[dict[str, Any]]:
        if not await session.scalar(text("SELECT to_regclass('public.academics_sessions') IS NOT NULL")):
            return []
        clauses = ["s.business_id=:bid", "s.status='scheduled'",
                   "(s.starts_at AT TIME ZONE 'Asia/Kolkata')::date=CAST(:day AS date)"]
        values: dict[str, Any] = {"bid": business_id, "day": datetime.now(IST).date().isoformat()}
        scoped = assigned_identity(session)
        if scoped is not None:
            clauses.append("COALESCE(s.teacher_member_id,b.teacher_member_id) IN "
                           "(SELECT id FROM workforce_members WHERE business_id=:bid AND identity_id=:identity)")
            values["identity"] = scoped
        locs = allowed_locations(session)
        if locs is not None:
            clauses.append("(s.location_id IS NULL OR s.location_id = ANY(:locations))")
            values["locations"] = list(locs)
        rows = (await session.execute(text("""SELECT s.id,s.batch_id,s.topic,s.starts_at,s.ends_at,
            b.name AS batch_name FROM academics_sessions s
            JOIN academics_batches b ON b.id=s.batch_id AND b.business_id=:bid WHERE """ +
            " AND ".join(clauses) + " ORDER BY s.starts_at LIMIT 100"), values)).mappings().all()
        return [_view(row) for row in rows]

    @staticmethod
    async def _by_key(session: AsyncSession, business_id: uuid.UUID, key: str) -> dict[str, Any] | None:
        row = (await session.execute(text("""SELECT * FROM attendance_events
            WHERE business_id=:bid AND idempotency_key=:key"""),
            {"bid": business_id, "key": key})).mappings().one_or_none()
        return _view(row) if row else None

    @staticmethod
    async def _insert(session: AsyncSession, *, business_id: uuid.UUID, context: str,
                      source_id: uuid.UUID, subject_contact_id: uuid.UUID | None,
                      subject_member_id: uuid.UUID | None, location_id: uuid.UUID | None,
                      assigned_member_id: uuid.UUID | None, status: str, channel: str,
                      key: str, actor_id: uuid.UUID, metadata: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        row = (await session.execute(text("""INSERT INTO attendance_events
            (business_id,context,source_id,subject_contact_id,subject_member_id,location_id,
             assigned_member_id,status,channel,idempotency_key,checked_in_at,
             recorded_by_identity_id,verification_metadata)
            VALUES (:bid,:context,:source,:contact,:member,:location,:assignee,:status,:channel,
                    :key,:checked_in,:actor,CAST(:metadata AS jsonb)) RETURNING *"""),
            {"bid": business_id, "context": context, "source": source_id,
             "contact": subject_contact_id, "member": subject_member_id,
             "location": location_id, "assignee": assigned_member_id,
             "status": status, "channel": channel, "key": key,
             "checked_in": now if status in {"checked_in", "present", "late"} else None,
             "actor": actor_id, "metadata": json.dumps(metadata)})).mappings().one()
        return _view(row)

    @staticmethod
    async def member_checkin(session: AsyncSession, *, business_id: uuid.UUID,
                             enrolment_id: uuid.UUID, location_id: uuid.UUID | None,
                             channel: str, idempotency_key: str, actor_id: uuid.UUID,
                             correlation_id: str,
                             eligibility: MembershipCheckinEligibility | None = None) -> dict[str, Any]:
        if channel not in {"manual", "qr"}:
            raise ValidationError("Use manual or QR check-in")
        if assigned_identity(session) is not None:
            raise OutsideAssignmentScope()
        _location(session, location_id)
        if location_id is not None:
            location = (await session.execute(select(BusinessLocation.id).where(
                BusinessLocation.id == location_id,
                BusinessLocation.business_id == business_id,
                BusinessLocation.deleted_at.is_(None)))).scalar_one_or_none()
            if location is None:
                raise ResourceNotFound("Location")
        key = _key(idempotency_key)
        await _lock(session, business_id, key)
        previous = await AttendanceService._by_key(session, business_id, key)
        if previous:
            if (previous["context"] != "membership_checkin" or previous["source_id"] != str(enrolment_id)
                    or previous["location_id"] != (str(location_id) if location_id else None)
                    or previous["channel"] != channel):
                raise ConflictError("Request key was used for a different check-in")
            return previous
        decision = await (eligibility or UnconnectedMembershipEligibility()).decide(
            session, business_id, enrolment_id)
        if decision.enrolment_id != enrolment_id or decision.state not in {"allowed", "warning", "denied"}:
            raise ConflictError("Membership eligibility response did not match this request")
        if decision.state == "denied":
            raise ConflictError(decision.reason or "Member is not eligible to check in")
        contact = (await session.execute(select(CustomerContact.id).where(
            CustomerContact.id == decision.customer_contact_id,
            CustomerContact.business_id == business_id,
            CustomerContact.deleted_at.is_(None)).execution_options(skip_assignment_scope=True))).scalar_one_or_none()
        if contact is None:
            raise ResourceNotFound("Member contact")
        record = await AttendanceService._insert(session, business_id=business_id,
            context="membership_checkin", source_id=enrolment_id,
            subject_contact_id=decision.customer_contact_id, subject_member_id=None,
            location_id=location_id, assigned_member_id=None, status="checked_in",
            channel=channel, key=key, actor_id=actor_id,
            metadata={"eligibility_state": decision.state})
        await _event(session, business_id=business_id, actor_id=actor_id,
                     correlation_id=correlation_id, kind="attendance.checked_in",
                     event_id=uuid.UUID(record["id"]), context=record["context"], status=record["status"],
                     source_id=record.get("source_id"))
        return record

    @staticmethod
    async def staff_checkin(session: AsyncSession, *, business_id: uuid.UUID,
                            member_id: uuid.UUID, location_id: uuid.UUID,
                            idempotency_key: str, actor_id: uuid.UUID,
                            correlation_id: str) -> dict[str, Any]:
        _location(session, location_id)
        member = (await session.execute(select(WorkforceMember).where(
            WorkforceMember.id == member_id, WorkforceMember.business_id == business_id,
            WorkforceMember.status == "active", WorkforceMember.deleted_at.is_(None)))).scalar_one_or_none()
        if member is None:
            raise ResourceNotFound("Workforce member")
        if assigned_identity(session) is not None and member.identity_id != actor_id:
            raise OutsideAssignmentScope()
        location = (await session.execute(select(BusinessLocation.id).where(
            BusinessLocation.id == location_id,
            BusinessLocation.business_id == business_id,
            BusinessLocation.deleted_at.is_(None)))).scalar_one_or_none()
        if location is None:
            raise ResourceNotFound("Location")
        assignments = (await session.execute(select(WorkforceLocationAssignment.location_id).where(
            WorkforceLocationAssignment.business_id == business_id,
            WorkforceLocationAssignment.member_id == member_id))).scalars().all()
        if assignments and location_id not in assignments:
            raise OutsideLocationScope()
        key = _key(idempotency_key)
        await _lock(session, business_id, key)
        previous = await AttendanceService._by_key(session, business_id, key)
        if previous:
            if previous["context"] != "staff_site" or previous["subject_member_id"] != str(member_id) or previous["source_id"] != str(location_id):
                raise ConflictError("Request key was used for another person's site check-in")
            return previous
        record = await AttendanceService._insert(session, business_id=business_id,
            context="staff_site", source_id=location_id, subject_contact_id=None,
            subject_member_id=member_id, location_id=location_id,
            assigned_member_id=member_id, status="checked_in", channel="manual",
            key=key, actor_id=actor_id, metadata={"geo_verification": "not_requested"})
        await _event(session, business_id=business_id, actor_id=actor_id,
                     correlation_id=correlation_id, kind="attendance.checked_in",
                     event_id=uuid.UUID(record["id"]), context=record["context"], status=record["status"],
                     source_id=record.get("source_id"))
        return record

    @staticmethod
    async def booking_arrival(session: AsyncSession, *, business_id: uuid.UUID,
                              booking_id: uuid.UUID, idempotency_key: str,
                              actor_id: uuid.UUID, correlation_id: str) -> dict[str, Any]:
        """Physical arrival only; Bookings retains the reservation state."""
        key = _key(idempotency_key)
        await _lock(session, business_id, f"booking:{booking_id}")
        previous = await AttendanceService._by_key(session, business_id, key)
        if previous and (previous["context"] != "booking_arrival" or previous["source_id"] != str(booking_id)):
            raise ConflictError("Request key was used for a different arrival")
        booking = (await session.execute(select(Booking).where(
            Booking.id == booking_id, Booking.business_id == business_id,
            Booking.deleted_at.is_(None)))).scalar_one_or_none()
        if booking is None:
            raise ResourceNotFound("Booking")
        if booking.status != "confirmed" or booking.customer_contact_id is None:
            raise ConflictError("Only a confirmed customer booking can record arrival")
        _location(session, booking.location_id)
        if previous:
            return previous
        existing = (await session.execute(text("""SELECT * FROM attendance_events
            WHERE business_id=:bid AND context='booking_arrival' AND source_id=:source"""),
            {"bid": business_id, "source": booking_id})).mappings().one_or_none()
        if existing:
            return _view(existing)
        record = await AttendanceService._insert(session, business_id=business_id,
            context="booking_arrival", source_id=booking_id,
            subject_contact_id=booking.customer_contact_id, subject_member_id=None,
            location_id=booking.location_id, assigned_member_id=booking.provider_id,
            status="checked_in", channel="manual", key=key, actor_id=actor_id,
            metadata={"booking_state": "confirmed"})
        await _event(session, business_id=business_id, actor_id=actor_id,
                     correlation_id=correlation_id, kind="attendance.checked_in",
                     event_id=uuid.UUID(record["id"]), context=record["context"], status=record["status"],
                     source_id=record.get("source_id"))
        return record

    @staticmethod
    async def roster(session: AsyncSession, *, business_id: uuid.UUID,
                     class_session_id: uuid.UUID,
                     source: AcademicAttendanceSource | None = None) -> dict[str, Any]:
        occurrence = await (source or AcademicAttendanceSource()).resolve(session, business_id, class_session_id)
        rows = (await session.execute(text("""SELECT id,subject_contact_id,status,version
            FROM attendance_events WHERE business_id=:bid AND context='academic_session' AND source_id=:sid"""),
            {"bid": business_id, "sid": class_session_id})).all()
        recorded = {sid: (event_id, status, version) for event_id, sid, status, version in rows}
        return {"session_id": str(class_session_id), "batch_id": str(occurrence.batch_id),
                "students": [{"contact_id": str(sid), "name": name,
                              "status": recorded[sid][1] if sid in recorded else "present",
                              "saved": sid in recorded,
                              "event_id": str(recorded[sid][0]) if sid in recorded else None,
                              "version": recorded[sid][2] if sid in recorded else None}
                             for sid, name in occurrence.students]}

    @staticmethod
    async def record_session(session: AsyncSession, *, business_id: uuid.UUID,
                             class_session_id: uuid.UUID, statuses: dict[uuid.UUID, str],
                             idempotency_key: str, actor_id: uuid.UUID,
                             correlation_id: str,
                             source: AcademicAttendanceSource | None = None) -> list[dict[str, Any]]:
        key = _key(idempotency_key)
        await _lock(session, business_id, f"academic:{class_session_id}")
        occurrence = await (source or AcademicAttendanceSource()).resolve(session, business_id, class_session_id)
        students = {sid for sid, _ in occurrence.students}
        if not students:
            raise ConflictError("There are no active students in this class")
        if not set(statuses).issubset(students):
            raise ValidationError("Attendance includes a student outside this class")
        if any(status not in ACADEMIC_STATUSES for status in statuses.values()):
            raise ValidationError("Unknown academic attendance status")
        result: list[dict[str, Any]] = []
        created: list[dict[str, Any]] = []
        for sid, _ in occurrence.students:
            status = statuses.get(sid, "present")
            existing = (await session.execute(text("""SELECT * FROM attendance_events
                WHERE business_id=:bid AND context='academic_session' AND source_id=:session
                  AND subject_contact_id=:student FOR UPDATE"""),
                {"bid": business_id, "session": class_session_id,
                 "student": sid})).mappings().one_or_none()
            if existing:
                if existing["status"] != status:
                    raise ConflictError("Attendance was already saved; use a correction to change a status")
                result.append(_view(existing))
                continue
            record = await AttendanceService._insert(session, business_id=business_id,
                context="academic_session", source_id=class_session_id,
                subject_contact_id=sid, subject_member_id=None,
                location_id=occurrence.location_id, assigned_member_id=occurrence.teacher_member_id,
                status=status, channel="manual", key=f"{key}:{sid}", actor_id=actor_id,
                metadata={"batch_id": str(occurrence.batch_id)})
            result.append(record)
            created.append(record)
        if created:
            await _event(session, business_id=business_id, actor_id=actor_id,
                         correlation_id=correlation_id, kind="attendance.session_recorded",
                         event_id=uuid.UUID(created[0]["id"]), context="academic_session", status="recorded")
        return result

    @staticmethod
    async def list_events(session: AsyncSession, *, business_id: uuid.UUID,
                          context: str | None = None, today: bool = False) -> list[dict[str, Any]]:
        if context and context not in CONTEXTS:
            raise ValidationError("Unknown attendance context")
        clauses = ["business_id=:bid"]
        values: dict[str, Any] = {"bid": business_id}
        if context:
            clauses.append("context=:context")
            values["context"] = context
        if today:
            start = datetime.now(IST).date().isoformat()
            clauses.append("(recorded_at AT TIME ZONE 'Asia/Kolkata')::date = CAST(:day AS date)")
            values["day"] = start
        scoped = assigned_identity(session)
        if scoped is not None:
            clauses.append("assigned_member_id IN (SELECT id FROM workforce_members WHERE business_id=:bid AND identity_id=:identity)")
            values["identity"] = scoped
        locs = allowed_locations(session)
        if locs is not None:
            clauses.append("(location_id IS NULL OR location_id = ANY(:locations))")
            values["locations"] = list(locs)
        rows = (await session.execute(text("SELECT * FROM attendance_events WHERE " +
            " AND ".join(clauses) + " ORDER BY recorded_at DESC LIMIT 100"), values)).mappings().all()
        return [_view(row) for row in rows]

    @staticmethod
    async def checkout(session: AsyncSession, *, business_id: uuid.UUID,
                       event_id: uuid.UUID, expected_version: int, actor_id: uuid.UUID,
                       correlation_id: str) -> dict[str, Any]:
        row = (await session.execute(text("""SELECT * FROM attendance_events
            WHERE id=:id AND business_id=:bid FOR UPDATE"""),
            {"id": event_id, "bid": business_id})).mappings().one_or_none()
        if row is None:
            raise ResourceNotFound("Attendance event")
        _location(session, row["location_id"])
        scoped = assigned_identity(session)
        if scoped is not None:
            member = (await session.execute(select(WorkforceMember.identity_id).where(
                WorkforceMember.id == row["subject_member_id"],
                WorkforceMember.business_id == business_id))).scalar_one_or_none()
            if row["context"] != "staff_site" or member != scoped:
                raise OutsideAssignmentScope()
        if row["version"] != expected_version:
            raise ConflictError("Attendance changed; reload before checking out")
        if row["status"] != "checked_in":
            raise ValidationError("Only an open check-in can be checked out")
        updated = (await session.execute(text("""UPDATE attendance_events
            SET status='checked_out',checked_out_at=GREATEST(clock_timestamp(),checked_in_at),
                updated_at=clock_timestamp(),version=version+1
            WHERE id=:id AND business_id=:bid RETURNING *"""),
            {"id": event_id, "bid": business_id})).mappings().one()
        result = _view(updated)
        await _event(session, business_id=business_id, actor_id=actor_id,
                     correlation_id=correlation_id, kind="attendance.checked_out",
                     event_id=event_id, context=row["context"], status="checked_out")
        return result

    @staticmethod
    async def correct_academic(session: AsyncSession, *, business_id: uuid.UUID,
                               event_id: uuid.UUID, status: str, expected_version: int,
                               reason: str, actor_id: uuid.UUID) -> dict[str, Any]:
        if assigned_identity(session) is not None:
            raise OutsideAssignmentScope()
        if status not in ACADEMIC_STATUSES:
            raise ValidationError("Unknown academic attendance status")
        note = reason.strip()
        if not note or len(note) > 1000:
            raise ValidationError("A short correction reason is required")
        row = (await session.execute(text("""SELECT * FROM attendance_events
            WHERE id=:id AND business_id=:bid FOR UPDATE"""),
            {"id": event_id, "bid": business_id})).mappings().one_or_none()
        if row is None:
            raise ResourceNotFound("Attendance event")
        if row["context"] != "academic_session":
            raise ValidationError("Only class attendance has an academic status")
        _location(session, row["location_id"])
        if row["version"] != expected_version:
            raise ConflictError("Attendance changed; reload before correcting")
        if row["status"] == status:
            return _view(row)
        updated = (await session.execute(text("""UPDATE attendance_events
            SET status=:status,checked_in_at=CASE WHEN :status IN ('present','late')
                THEN COALESCE(checked_in_at,now()) ELSE NULL END,
                version=version+1,updated_at=now()
            WHERE id=:id AND business_id=:bid RETURNING *"""),
            {"id": event_id, "bid": business_id, "status": status})).mappings().one()
        await AuditService.record(session, event_type="attendance.status.corrected",
            actor_identity_id=actor_id, actor_context="business", business_id=business_id,
            resource_type="attendance_event", resource_id=event_id, action="correct",
            before_state={"status": row["status"]}, after_state={"status": status}, reason=note)
        return _view(updated)
