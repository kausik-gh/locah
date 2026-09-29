"""P5 teaching structure. Fees belong to Memberships; attendance belongs to Attendance."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.authorization.assignment_scope import current as assigned_identity
from platform_core.authorization.location_scope import current as allowed_locations
from platform_core.exceptions import ConflictError, OutsideAssignmentScope, OutsideLocationScope, ResourceNotFound, ValidationError
from platform_core.models import CustomerContact
from platform_core.resolvers.customer_resolver import CustomerResolver
from platform_core.services.audit import AuditService
from platform_core.services.outbox import OutboxService
from platform_core.services.business import BusinessService
from platform_core.gates import assert_business_mutable


def _view(row: Any) -> dict[str, Any]:
    return {key: str(value) if isinstance(value, (uuid.UUID, Decimal)) else
            value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in dict(row).items()}


def _word(value: Any, name: str, limit: int = 200) -> str:
    cleaned = str(value or "").strip()
    if not cleaned or len(cleaned) > limit:
        raise ValidationError(f"Enter {name} (up to {limit} characters)")
    return cleaned


def _safe_url(value: Any) -> str | None:
    if not value:
        return None
    url = str(value).strip()
    if not url.startswith("https://") or len(url) > 1000:
        raise ValidationError("Online class links must use HTTPS")
    return url


async def _mutable(session: AsyncSession, business_id: uuid.UUID) -> None:
    business = await BusinessService.get_by_id(session, business_id)
    if business is None:
        raise ResourceNotFound("Business")
    assert_business_mutable(business.state, action="change academics")


async def _one(session: AsyncSession, sql: str, values: dict[str, Any], name: str) -> dict[str, Any]:
    row = (await session.execute(text(sql), values)).mappings().one_or_none()
    if row is None:
        raise ResourceNotFound(name)
    return _view(row)


async def _event(session: AsyncSession, *, business_id: uuid.UUID, actor_id: uuid.UUID,
                 correlation_id: str, event: str, resource: str, resource_id: uuid.UUID) -> None:
    await OutboxService.publish(session, event_type=event, business_id=business_id,
                                correlation_id=correlation_id, payload={"id": str(resource_id)})
    await AuditService.record(session, event_type=event, actor_identity_id=actor_id,
                              actor_context="business", business_id=business_id,
                              resource_type=resource, resource_id=resource_id, action=event)


class AcademicsService:
    @staticmethod
    async def _batch(session: AsyncSession, business_id: uuid.UUID, batch_id: uuid.UUID,
                     *, writing: bool, lock: bool = False) -> dict[str, Any]:
        row = await _one(session, "SELECT * FROM academics_batches WHERE id=:id AND business_id=:bid" +
                         (" FOR UPDATE" if lock else ""), {"id": batch_id, "bid": business_id}, "Batch")
        locs = allowed_locations(session)
        if locs and row["location_id"] is not None and uuid.UUID(row["location_id"]) not in locs:
            raise OutsideLocationScope()
        identity = assigned_identity(session)
        if identity:
            member = (await session.execute(text("SELECT identity_id FROM workforce_members WHERE id=:mid AND business_id=:bid"),
                {"mid": row["teacher_member_id"], "bid": business_id})).scalar_one_or_none()
            if member != identity:
                # As Tasks does, and as RLS already answers: another teacher's
                # batch does not exist for a read; changing it is refused.
                if writing:
                    raise OutsideAssignmentScope()
                raise ResourceNotFound("Batch")
        return row

    @staticmethod
    async def courses(session: AsyncSession, business_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (await session.execute(text("SELECT * FROM academics_courses WHERE business_id=:bid ORDER BY created_at DESC"),
                                      {"bid": business_id})).mappings().all()
        return [_view(row) for row in rows]

    @staticmethod
    async def create_course(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
                            correlation_id: str, title: str, description: str | None) -> dict[str, Any]:
        await _mutable(session, business_id)
        if assigned_identity(session):
            raise OutsideAssignmentScope()
        row = await _one(session, """INSERT INTO academics_courses (business_id,title,description)
            VALUES (:bid,:title,:description) RETURNING *""",
            {"bid": business_id, "title": _word(title, "course name"),
             "description": description.strip()[:4000] if description else None}, "Course")
        await _event(session, business_id=business_id, actor_id=actor_id, correlation_id=correlation_id,
                     event="academics.course.created", resource="academic_course", resource_id=uuid.UUID(row["id"]))
        return row

    @staticmethod
    async def batches(session: AsyncSession, business_id: uuid.UUID, course_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
        sql = "SELECT b.* FROM academics_batches b WHERE b.business_id=:bid"
        args: dict[str, Any] = {"bid": business_id}
        if course_id is not None:
            sql += " AND b.course_id=:course_id"
            args["course_id"] = course_id
        identity = assigned_identity(session)
        if identity:
            sql += " AND b.teacher_member_id IN (SELECT id FROM workforce_members WHERE business_id=:bid AND identity_id=:identity)"
            args["identity"] = identity
        locs = allowed_locations(session)
        if locs:
            sql += " AND (b.location_id IS NULL OR b.location_id = ANY(:locations))"
            args["locations"] = list(locs)
        rows = (await session.execute(text(sql + " ORDER BY b.created_at DESC"), args)).mappings().all()
        return [_view(row) for row in rows]

    @staticmethod
    async def create_batch(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
                           correlation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        await _mutable(session, business_id)
        if assigned_identity(session):
            raise OutsideAssignmentScope()
        course_id = payload["course_id"]
        await _one(session, "SELECT id FROM academics_courses WHERE id=:id AND business_id=:bid AND status<>'archived'",
                   {"id": course_id, "bid": business_id}, "Active course")
        teacher = payload.get("teacher_member_id")
        if teacher:
            await _one(session, "SELECT id FROM workforce_members WHERE id=:id AND business_id=:bid AND status='active' AND deleted_at IS NULL",
                       {"id": teacher, "bid": business_id}, "Teacher")
        location = payload.get("location_id")
        if location:
            await _one(session, "SELECT id FROM business_locations WHERE id=:id AND business_id=:bid AND deleted_at IS NULL",
                       {"id": location, "bid": business_id}, "Location")
            locs = allowed_locations(session)
            if locs and location not in locs:
                raise OutsideLocationScope()
        row = await _one(session, """INSERT INTO academics_batches
            (business_id,course_id,name,teacher_member_id,location_id,room,meeting_url,starts_on,ends_on,capacity)
            VALUES (:bid,:course_id,:name,:teacher,:location,:room,:url,:starts,:ends,:capacity) RETURNING *""",
            {"bid": business_id, "course_id": course_id, "name": _word(payload["name"], "batch name"),
             "teacher": teacher, "location": location, "room": payload.get("room"),
             "url": _safe_url(payload.get("meeting_url")), "starts": payload.get("starts_on"),
             "ends": payload.get("ends_on"), "capacity": payload.get("capacity")}, "Batch")
        await _event(session, business_id=business_id, actor_id=actor_id, correlation_id=correlation_id,
                     event="academics.batch.created", resource="academic_batch", resource_id=uuid.UUID(row["id"]))
        return row

    @staticmethod
    async def sessions(session: AsyncSession, business_id: uuid.UUID, batch_id: uuid.UUID) -> list[dict[str, Any]]:
        await AcademicsService._batch(session, business_id, batch_id, writing=False)
        rows = (await session.execute(text("SELECT * FROM academics_sessions WHERE business_id=:bid AND batch_id=:batch ORDER BY starts_at"),
                                      {"bid": business_id, "batch": batch_id})).mappings().all()
        return [_view(row) for row in rows]

    @staticmethod
    async def create_session(session: AsyncSession, business_id: uuid.UUID, batch_id: uuid.UUID,
                             actor_id: uuid.UUID, correlation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        await _mutable(session, business_id)
        batch = await AcademicsService._batch(session, business_id, batch_id, writing=True)
        if batch["status"] in {"completed", "cancelled"}:
            raise ConflictError("This batch is closed")
        starts = payload["starts_at"]
        ends = payload["ends_at"]
        if starts.tzinfo is None or ends.tzinfo is None or ends <= starts:
            raise ValidationError("Class needs valid start and end times with a timezone")
        teacher = uuid.UUID(batch["teacher_member_id"]) if batch["teacher_member_id"] else None
        room = batch["room"]
        # Lock every constrained resource in stable order. Two different teachers
        # sharing a room must not pass the overlap check concurrently.
        keys = [f"{business_id}:batch:{batch_id}"]
        if teacher:
            keys.append(f"{business_id}:teacher:{teacher}")
        if room:
            keys.append(f"{business_id}:room:{batch['location_id']}:{room}")
        for key in sorted(keys):
            await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key), 5200)"), {"key": key})
        clash = (await session.execute(text("""SELECT id FROM academics_sessions
            WHERE business_id=CAST(:bid AS uuid) AND status='scheduled' AND starts_at<:ends AND ends_at>:starts
              AND (batch_id=CAST(:batch AS uuid)
                OR (CAST(:teacher AS uuid) IS NOT NULL AND teacher_member_id=CAST(:teacher AS uuid))
                OR (CAST(:room AS text) IS NOT NULL AND room=CAST(:room AS text)
                    AND location_id IS NOT DISTINCT FROM CAST(:location AS uuid)))
            LIMIT 1"""), {"bid": str(business_id), "starts": starts, "ends": ends,
                           "batch": str(batch_id), "teacher": str(teacher) if teacher else None,
                           "room": room, "location": batch["location_id"]})).first()
        if clash:
            raise ConflictError("Teacher or room already has a class at that time")
        row = await _one(session, """INSERT INTO academics_sessions
            (business_id,batch_id,teacher_member_id,location_id,room,topic,starts_at,ends_at,meeting_url)
            VALUES (:bid,:batch,:teacher,:location,:room,:topic,:starts,:ends,:url) RETURNING *""",
            {"bid": business_id, "batch": batch_id, "teacher": teacher,
             "location": batch["location_id"], "room": room, "topic": payload.get("topic"),
             "starts": starts, "ends": ends, "url": _safe_url(payload.get("meeting_url")) or batch["meeting_url"]}, "Class")
        await _event(session, business_id=business_id, actor_id=actor_id, correlation_id=correlation_id,
                     event="academics.session.scheduled", resource="academic_session", resource_id=uuid.UUID(row["id"]))
        return row

    @staticmethod
    async def enrol(session: AsyncSession, business_id: uuid.UUID, batch_id: uuid.UUID,
                    actor_id: uuid.UUID, correlation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        await _mutable(session, business_id)
        batch = await AcademicsService._batch(session, business_id, batch_id, writing=True, lock=True)
        if batch["status"] in {"completed", "cancelled"}:
            raise ConflictError("This batch is closed")
        student = await CustomerResolver.resolve(session, business_id=business_id,
                                                 contact_id=payload["student_contact_id"])
        guardian_id = payload.get("guardian_contact_id")
        guardian: CustomerContact | None = None
        if guardian_id:
            guardian = await CustomerResolver.resolve(session, business_id=business_id, contact_id=guardian_id)
            if guardian.id == student.id:
                raise ValidationError("Student and guardian must be different contacts")
        if payload.get("is_minor") and guardian is None:
            raise ValidationError("A guardian contact is required for a minor")
        existing = (await session.execute(text("""SELECT * FROM academics_enrolments WHERE
            business_id=:bid AND batch_id=:batch AND student_contact_id=:student"""),
            {"bid": business_id, "batch": batch_id, "student": student.id})).mappings().one_or_none()
        if existing:
            if (existing["status"] == "active" and existing["guardian_contact_id"] ==
                    (guardian.id if guardian else None) and existing["is_minor"] == bool(payload.get("is_minor"))):
                return _view(existing)
            raise ConflictError("This student already has an enrolment in the batch")
        if batch["capacity"]:
            count = (await session.execute(text("""SELECT count(*) FROM academics_enrolments
                WHERE business_id=:bid AND batch_id=:batch AND status='active'"""),
                {"bid": business_id, "batch": batch_id})).scalar_one()
            if count >= batch["capacity"]:
                raise ConflictError("The batch is full")
        row = await _one(session, """INSERT INTO academics_enrolments
            (business_id,batch_id,student_contact_id,guardian_contact_id,is_minor)
            VALUES (:bid,:batch,:student,:guardian,:minor) RETURNING *""",
            {"bid": business_id, "batch": batch_id, "student": student.id,
             "guardian": guardian.id if guardian else None, "minor": bool(payload.get("is_minor"))}, "Enrolment")
        await _event(session, business_id=business_id, actor_id=actor_id, correlation_id=correlation_id,
                     event="academics.student.enrolled", resource="academic_enrolment", resource_id=uuid.UUID(row["id"]))
        return row

    @staticmethod
    async def enrolments(session: AsyncSession, business_id: uuid.UUID, batch_id: uuid.UUID) -> list[dict[str, Any]]:
        await AcademicsService._batch(session, business_id, batch_id, writing=False)
        rows = (await session.execute(text("""SELECT e.*, s.display_name AS student_name,
            g.display_name AS guardian_name FROM academics_enrolments e
            JOIN customer_relationships_contacts s ON s.id=e.student_contact_id
            LEFT JOIN customer_relationships_contacts g ON g.id=e.guardian_contact_id
            WHERE e.business_id=:bid AND e.batch_id=:batch ORDER BY e.enrolled_at"""),
            {"bid": business_id, "batch": batch_id})).mappings().all()
        return [_view(row) for row in rows]

    @staticmethod
    async def create_assessment(session: AsyncSession, business_id: uuid.UUID, batch_id: uuid.UUID,
                                actor_id: uuid.UUID, correlation_id: str,
                                title: str, maximum: Decimal) -> dict[str, Any]:
        await _mutable(session, business_id)
        await AcademicsService._batch(session, business_id, batch_id, writing=True)
        if maximum <= 0:
            raise ValidationError("Maximum marks must be positive")
        row = await _one(session, """INSERT INTO academics_assessments (business_id,batch_id,title,maximum)
            VALUES (:bid,:batch,:title,:maximum) RETURNING *""",
            {"bid": business_id, "batch": batch_id, "title": _word(title, "assessment title"),
             "maximum": maximum}, "Assessment")
        await _event(session, business_id=business_id, actor_id=actor_id, correlation_id=correlation_id,
                     event="academics.assessment.created", resource="academic_assessment", resource_id=uuid.UUID(row["id"]))
        return row

    @staticmethod
    async def assessments(session: AsyncSession, business_id: uuid.UUID,
                          batch_id: uuid.UUID) -> list[dict[str, Any]]:
        await AcademicsService._batch(session, business_id, batch_id, writing=False)
        rows = (await session.execute(text("""SELECT a.*, r.id AS result_id,
            r.enrolment_id, r.marks, r.teacher_note FROM academics_assessments a
            LEFT JOIN academics_results r ON r.assessment_id=a.id AND r.business_id=:bid
            WHERE a.business_id=:bid AND a.batch_id=:batch ORDER BY a.created_at DESC"""),
            {"bid": business_id, "batch": batch_id})).mappings().all()
        return [_view(row) for row in rows]

    @staticmethod
    async def announcements(session: AsyncSession, business_id: uuid.UUID,
                            batch_id: uuid.UUID) -> list[dict[str, Any]]:
        await AcademicsService._batch(session, business_id, batch_id, writing=False)
        rows = (await session.execute(text("""SELECT * FROM academics_announcements
            WHERE business_id=:bid AND batch_id=:batch ORDER BY created_at DESC LIMIT 50"""),
            {"bid": business_id, "batch": batch_id})).mappings().all()
        return [_view(row) for row in rows]

    @staticmethod
    async def announce(session: AsyncSession, business_id: uuid.UUID, batch_id: uuid.UUID,
                       title: str, body: str, actor_id: uuid.UUID,
                       correlation_id: str) -> dict[str, Any]:
        await _mutable(session, business_id)
        await AcademicsService._batch(session, business_id, batch_id, writing=True)
        row = await _one(session, """INSERT INTO academics_announcements
            (business_id,batch_id,title,body,created_by)
            VALUES (:bid,:batch,:title,:body,:actor) RETURNING *""",
            {"bid": business_id, "batch": batch_id, "title": _word(title, "notice title"),
             "body": _word(body, "notice", 4000), "actor": actor_id}, "Notice")
        await _event(session, business_id=business_id, actor_id=actor_id, correlation_id=correlation_id,
                     event="academics.announcement.created", resource="academic_announcement",
                     resource_id=uuid.UUID(row["id"]))
        return row

    @staticmethod
    async def record_result(session: AsyncSession, business_id: uuid.UUID, assessment_id: uuid.UUID,
                            enrolment_id: uuid.UUID, marks: Decimal, teacher_note: str | None,
                            actor_id: uuid.UUID, correlation_id: str) -> dict[str, Any]:
        await _mutable(session, business_id)
        assessment = await _one(session, "SELECT * FROM academics_assessments WHERE id=:id AND business_id=:bid",
                                {"id": assessment_id, "bid": business_id}, "Assessment")
        await AcademicsService._batch(session, business_id, uuid.UUID(assessment["batch_id"]), writing=True)
        await _one(session, "SELECT id FROM academics_enrolments WHERE id=:id AND business_id=:bid AND batch_id=:batch",
                   {"id": enrolment_id, "bid": business_id, "batch": uuid.UUID(assessment["batch_id"])}, "Enrolment")
        if marks < 0 or marks > Decimal(assessment["maximum"]):
            raise ValidationError("Marks must be between zero and the assessment maximum")
        row = await _one(session, """INSERT INTO academics_results
            (business_id,assessment_id,enrolment_id,marks,teacher_note)
            VALUES (:bid,:assessment,:enrolment,:marks,:note)
            ON CONFLICT (assessment_id,enrolment_id) DO UPDATE SET marks=EXCLUDED.marks,
                teacher_note=EXCLUDED.teacher_note,updated_at=now() RETURNING *""",
            {"bid": business_id, "assessment": assessment_id, "enrolment": enrolment_id,
             "marks": marks, "note": teacher_note.strip()[:2000] if teacher_note else None}, "Result")
        await _event(session, business_id=business_id, actor_id=actor_id, correlation_id=correlation_id,
                     event="academics.result.recorded", resource="academic_result", resource_id=uuid.UUID(row["id"]))
        return row
