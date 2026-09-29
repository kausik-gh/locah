"""Walk-in queue (Business OS Guide §6.2, Doc 10 QueueEntry, Doc 09 §10.4).

A token is waiting, called, serving, served, or missed. Call next and call
specific take the next waiting token (priority, then arrival). Serve starts
the visit. Complete closes it. Miss marks a no-show. Requeue puts a missed
token back at the end when the lane allows it.

A booked appointment joins the same lane by booking_id. The booking row is
not copied and no second booking is created.

"Your turn soon" publishes queue.turn_soon. Messaging is not called from here.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import (
    ConflictError,
    OutsideAssignmentScope,
    OutsideLocationScope,
    ResourceNotFound,
    ValidationError,
)
from platform_core.models import Booking, QueueEntry, QueueEntryEvent, QueueLane
from platform_core.services.outbox import OutboxService

IST = ZoneInfo("Asia/Kolkata")
OPEN = ("waiting", "called", "serving")
# action -> allowed current statuses, next status, history action, timestamp field
_MOVES: dict[str, tuple[tuple[str, ...], str, str, str | None]] = {
    "call": (("waiting",), "called", "called", "called_at"),
    "serve": (("called",), "serving", "serving", "serving_at"),
    "complete": (("serving",), "served", "served", "closed_at"),
    "miss": (("waiting", "called", "serving"), "missed", "missed", "closed_at"),
}


class QueueService:
    # ---------------------------------------------------------------- scope
    @staticmethod
    def _location_ok(session: AsyncSession, location_id: uuid.UUID | None) -> None:
        from platform_core.authorization.location_scope import current

        scope = current(session)
        if scope and location_id is not None and uuid.UUID(str(location_id)) not in scope:
            raise OutsideLocationScope()

    @staticmethod
    async def _provider_ids(session: AsyncSession) -> set[uuid.UUID] | None:
        """Workforce ids this assignment-scoped caller may operate, or None for no limit."""
        from platform_core.authorization.assignment_scope import current
        from platform_core.models import WorkforceMember

        identity = current(session)
        if identity is None:
            return None
        rows = await session.execute(
            select(WorkforceMember.id).where(WorkforceMember.identity_id == identity)
        )
        return {uuid.UUID(str(row)) for row in rows.scalars().all()}

    @staticmethod
    def _lane_visible(lane: QueueLane, mine: set[uuid.UUID] | None) -> None:
        # A missing row and someone else's row look the same on read.
        if mine is None:
            return
        if lane.provider_id is None or uuid.UUID(str(lane.provider_id)) not in mine:
            raise ResourceNotFound("Queue")

    # ---------------------------------------------------------------- lanes
    @staticmethod
    async def create_lane(
        session: AsyncSession,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        body: dict[str, Any],
    ) -> QueueLane:
        location_id = body["location_id"]
        QueueService._location_ok(session, location_id)
        mine = await QueueService._provider_ids(session)
        provider_id = body.get("provider_id")
        if mine is not None and (provider_id is None or uuid.UUID(str(provider_id)) not in mine):
            raise OutsideAssignmentScope()
        await QueueService._same_business_location(session, business_id, location_id)
        if provider_id is not None:
            await QueueService._same_business_row(
                session, "workforce_members", business_id, provider_id, "provider"
            )
        if body.get("resource_id") is not None:
            await QueueService._same_business_row(
                session, "bookings_resources", business_id, body["resource_id"], "resource"
            )
        lane = QueueLane(
            business_id=business_id,
            location_id=location_id,
            name=body["name"].strip(),
            provider_id=provider_id,
            department=(body.get("department") or None),
            resource_id=body.get("resource_id"),
            allow_requeue=bool(body.get("allow_requeue", True)),
            turn_soon_ahead=int(body.get("turn_soon_ahead", 2)),
            avg_service_minutes=body.get("avg_service_minutes"),
            created_by=actor_id,
        )
        if lane.department:
            lane.department = lane.department.strip()
        session.add(lane)
        await session.flush()
        return lane

    @staticmethod
    async def list_lanes(
        session: AsyncSession, business_id: uuid.UUID, *, location_id: uuid.UUID | None = None,
        department: str | None = None, provider_id: uuid.UUID | None = None,
    ) -> list[QueueLane]:
        mine = await QueueService._provider_ids(session)
        stmt = select(QueueLane).where(
            QueueLane.business_id == business_id, QueueLane.status == "active"
        )
        if location_id is not None:
            stmt = stmt.where(QueueLane.location_id == location_id)
        if department:
            stmt = stmt.where(QueueLane.department == department)
        if provider_id is not None:
            stmt = stmt.where(QueueLane.provider_id == provider_id)
        if mine is not None:
            stmt = stmt.where(QueueLane.provider_id.in_(mine))
        rows = (await session.execute(stmt.order_by(QueueLane.name))).scalars().all()
        return list(rows)

    @staticmethod
    async def get_lane(
        session: AsyncSession, business_id: uuid.UUID, lane_id: uuid.UUID
    ) -> QueueLane:
        lane = await session.get(QueueLane, lane_id)
        if lane is None or lane.business_id != business_id or lane.status != "active":
            raise ResourceNotFound("Queue")
        QueueService._location_ok(session, lane.location_id)
        QueueService._lane_visible(lane, await QueueService._provider_ids(session))
        return lane

    # ---------------------------------------------------------------- issue
    @staticmethod
    async def issue(
        session: AsyncSession,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        body: dict[str, Any],
    ) -> QueueEntry:
        lane = await QueueService.get_lane(session, business_id, body["lane_id"])
        key = (body.get("idempotency_key") or "").strip() or None
        if key:
            existing = (await session.execute(
                select(QueueEntry).where(
                    QueueEntry.business_id == business_id, QueueEntry.idempotency_key == key
                )
            )).scalars().first()
            if existing is not None:
                return existing

        booking_id = body.get("booking_id")
        if booking_id is not None:
            return await QueueService._issue_booking(
                session, business_id, actor_id, lane, booking_id, int(body.get("priority") or 0), key
            )
        label = (body.get("party_label") or "").strip()
        if not label:
            raise ValidationError("Say who the token is for", details={"field": "party_label"})
        contact = body.get("customer_contact_id")
        if contact is not None:
            await QueueService._same_business_row(
                session, "customer_relationships_contacts", business_id, contact, "customer"
            )
        entry = await QueueService._new_entry(
            session, lane, actor_id, source="walk_in", party_label=label,
            customer_contact_id=contact, priority=int(body.get("priority") or 0),
            idempotency_key=key,
        )
        await QueueService._emit_turn_soon(session, lane)
        return entry

    @staticmethod
    async def _issue_booking(
        session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, lane: QueueLane,
        booking_id: uuid.UUID, priority: int, key: str | None,
    ) -> QueueEntry:
        booking = await session.get(Booking, booking_id)
        if booking is None or booking.business_id != business_id or booking.deleted_at is not None:
            raise ResourceNotFound("Booking")
        if booking.location_id != lane.location_id:
            raise ValidationError(
                "That booking is at another location", details={"field": "booking_id"}
            )
        if lane.provider_id is not None and booking.provider_id is not None:
            if uuid.UUID(str(booking.provider_id)) != uuid.UUID(str(lane.provider_id)):
                raise ValidationError(
                    "That booking is with another provider", details={"field": "booking_id"}
                )
        open_row = (await session.execute(
            select(QueueEntry).where(
                QueueEntry.business_id == business_id,
                QueueEntry.booking_id == booking_id,
                QueueEntry.status.in_(OPEN),
            )
        )).scalars().first()
        if open_row is not None:
            return open_row
        entry = await QueueService._new_entry(
            session, lane, actor_id, source="booking", booking_id=booking.id,
            customer_contact_id=booking.customer_contact_id, priority=priority,
            idempotency_key=key,
        )
        await QueueService._emit_turn_soon(session, lane)
        return entry

    @staticmethod
    async def _new_entry(
        session: AsyncSession, lane: QueueLane, actor_id: uuid.UUID, *, source: str,
        party_label: str | None = None, booking_id: uuid.UUID | None = None,
        customer_contact_id: uuid.UUID | None = None, priority: int = 0,
        idempotency_key: str | None = None,
    ) -> QueueEntry:
        today = datetime.now(IST).date()
        number = await QueueService._next_token(session, lane.id, today)
        now = datetime.now(timezone.utc)
        entry = QueueEntry(
            business_id=lane.business_id,
            location_id=lane.location_id,
            lane_id=lane.id,
            token_number=number,
            token_day=today,
            status="waiting",
            source=source,
            booking_id=booking_id,
            customer_contact_id=customer_contact_id,
            party_label=party_label,
            priority=priority,
            provider_id=lane.provider_id,
            issued_at=now,
            idempotency_key=idempotency_key,
            created_by=actor_id,
        )
        session.add(entry)
        await session.flush()
        await QueueService._event(session, entry, "issued", None, "waiting", actor_id)
        return entry

    @staticmethod
    async def _next_token(session: AsyncSession, lane_id: uuid.UUID, today: date) -> int:
        row = (await session.execute(
            text("""
                UPDATE queue_lanes
                   SET token_seq = CASE WHEN token_seq_day = :day THEN token_seq + 1 ELSE 1 END,
                       token_seq_day = :day
                 WHERE id = :id
                RETURNING token_seq
            """),
            {"id": str(lane_id), "day": today},
        )).first()
        if row is None:
            raise ResourceNotFound("Queue")
        return int(row[0])

    # ---------------------------------------------------------------- moves
    @staticmethod
    async def call_next(
        session: AsyncSession, business_id: uuid.UUID, lane_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> QueueEntry:
        lane = await QueueService.get_lane(session, business_id, lane_id)
        waiting = await QueueService._waiting(session, lane.id)
        if not waiting:
            raise ConflictError("Nobody is waiting")
        return await QueueService._move(session, lane, waiting[0], "call", actor_id)

    @staticmethod
    async def act(
        session: AsyncSession, business_id: uuid.UUID, entry_id: uuid.UUID, action: str,
        actor_id: uuid.UUID,
    ) -> QueueEntry:
        entry = await QueueService._entry(session, business_id, entry_id)
        lane = await QueueService.get_lane(session, business_id, entry.lane_id)
        if action == "requeue":
            return await QueueService._requeue(session, lane, entry, actor_id)
        if action not in _MOVES:
            raise ValidationError("Unknown queue action", details={"field": "action"})
        return await QueueService._move(session, lane, entry, action, actor_id)

    @staticmethod
    async def _move(
        session: AsyncSession, lane: QueueLane, entry: QueueEntry, action: str, actor_id: uuid.UUID,
    ) -> QueueEntry:
        allowed, nxt, history, stamp = _MOVES[action]
        if entry.status not in allowed:
            raise ConflictError(
                f"Token {entry.token_number} is {entry.status.replace('_', ' ')}",
                details={"status": entry.status, "action": action},
            )
        previous = entry.status
        entry.status = nxt
        entry.version = (entry.version or 1) + 1
        now = datetime.now(timezone.utc)
        if stamp:
            setattr(entry, stamp, now)
        await session.flush()
        await QueueService._event(session, entry, history, previous, nxt, actor_id)
        await QueueService._emit_turn_soon(session, lane)
        return entry

    @staticmethod
    async def _requeue(
        session: AsyncSession, lane: QueueLane, entry: QueueEntry, actor_id: uuid.UUID,
    ) -> QueueEntry:
        if entry.status != "missed":
            raise ConflictError("Only a missed token can rejoin the queue", details={"status": entry.status})
        if not lane.allow_requeue:
            raise ValidationError("This queue does not put missed tokens back in line")
        previous = entry.status
        now = datetime.now(timezone.utc)
        entry.status = "waiting"
        entry.issued_at = now
        entry.called_at = None
        entry.serving_at = None
        entry.closed_at = None
        entry.requeued_at = now
        entry.turn_soon_emitted_at = None
        entry.visit_cycle = (entry.visit_cycle or 1) + 1
        entry.version = (entry.version or 1) + 1
        await session.flush()
        await QueueService._event(session, entry, "requeued", previous, "waiting", actor_id)
        await QueueService._emit_turn_soon(session, lane)
        return entry

    # ---------------------------------------------------------------- board
    @staticmethod
    async def board(session: AsyncSession, business_id: uuid.UUID, lane_id: uuid.UUID) -> dict[str, Any]:
        lane = await QueueService.get_lane(session, business_id, lane_id)
        rows = list((await session.execute(
            select(QueueEntry).where(QueueEntry.lane_id == lane.id, QueueEntry.business_id == business_id)
        )).scalars().all())
        waiting = sorted(
            (row for row in rows if row.status == "waiting"),
            key=lambda row: (-row.priority, row.issued_at, row.token_number),
        )
        today = datetime.now(IST).date()
        names = await QueueService._labels(session, rows)

        def pack(group: list[QueueEntry], *, ahead_from: list[QueueEntry] | None = None) -> list[dict[str, Any]]:
            packed = []
            for index, row in enumerate(group):
                ahead = index if ahead_from is not None else None
                packed.append(QueueService.serialize(row, lane, names.get(row.id), ahead=ahead))
            return packed

        called = [row for row in rows if row.status == "called"]
        serving = [row for row in rows if row.status == "serving"]
        done = sorted(
            (row for row in rows if row.status in ("served", "missed") and row.token_day == today),
            key=lambda row: row.closed_at or row.issued_at,
            reverse=True,
        )
        return {
            "lane": QueueService.serialize_lane(lane),
            "columns": {
                "waiting": pack(waiting, ahead_from=waiting),
                "called": pack(called),
                "serving": pack(serving),
                "done": pack(done),
            },
        }

    @staticmethod
    async def _waiting(session: AsyncSession, lane_id: uuid.UUID) -> list[QueueEntry]:
        rows = (await session.execute(
            select(QueueEntry)
            .where(QueueEntry.lane_id == lane_id, QueueEntry.status == "waiting")
            .order_by(QueueEntry.priority.desc(), QueueEntry.issued_at, QueueEntry.token_number)
        )).scalars().all()
        return list(rows)

    @staticmethod
    async def _emit_turn_soon(session: AsyncSession, lane: QueueLane) -> None:
        """Tell people near the front once per visit. The event is the Messaging contract."""
        waiting = await QueueService._waiting(session, lane.id)
        limit = lane.turn_soon_ahead
        for index, entry in enumerate(waiting):
            if index > limit or entry.turn_soon_emitted_at is not None:
                continue
            entry.turn_soon_emitted_at = datetime.now(timezone.utc)
            await OutboxService.publish(
                session,
                event_type="queue.turn_soon",
                business_id=lane.business_id,
                payload={
                    "business_id": str(lane.business_id),
                    "entry_id": str(entry.id),
                    "lane_id": str(lane.id),
                    "location_id": str(lane.location_id),
                    "token_number": entry.token_number,
                    "ahead": index,
                    "visit_cycle": entry.visit_cycle,
                    "customer_contact_id": str(entry.customer_contact_id) if entry.customer_contact_id else None,
                    "booking_id": str(entry.booking_id) if entry.booking_id else None,
                    "channel_hint": "whatsapp",
                },
            )

    # ---------------------------------------------------------------- read helpers
    @staticmethod
    async def _entry(session: AsyncSession, business_id: uuid.UUID, entry_id: uuid.UUID) -> QueueEntry:
        entry = await session.get(QueueEntry, entry_id)
        if entry is None or entry.business_id != business_id:
            raise ResourceNotFound("Token")
        return entry

    @staticmethod
    async def _event(
        session: AsyncSession, entry: QueueEntry, action: str, frm: str | None, to: str,
        actor_id: uuid.UUID,
    ) -> None:
        session.add(QueueEntryEvent(
            business_id=entry.business_id, entry_id=entry.id, action=action,
            from_status=frm, to_status=to, actor_identity_id=actor_id,
        ))
        await session.flush()

    @staticmethod
    async def _labels(session: AsyncSession, rows: list[QueueEntry]) -> dict[uuid.UUID, str]:
        """Display names. Booking titles are read, never stored on the token."""
        labels: dict[uuid.UUID, str] = {}
        booking_ids = [row.booking_id for row in rows if row.booking_id]
        titles: dict[uuid.UUID, str] = {}
        if booking_ids:
            found = (await session.execute(
                select(Booking.id, Booking.title).where(Booking.id.in_(booking_ids))
            )).all()
            titles = {row[0]: row[1] for row in found}
        for row in rows:
            if row.party_label:
                labels[row.id] = row.party_label
            elif row.booking_id and row.booking_id in titles:
                labels[row.id] = titles[row.booking_id]
            else:
                labels[row.id] = f"Token {row.token_number}"
        return labels

    @staticmethod
    def serialize(entry: QueueEntry, lane: QueueLane, label: str | None, *, ahead: int | None) -> dict[str, Any]:
        estimate = None
        if ahead is not None and lane.avg_service_minutes:
            estimate = ahead * lane.avg_service_minutes
        return {
            "id": str(entry.id),
            "lane_id": str(entry.lane_id),
            "token_number": entry.token_number,
            "token_day": entry.token_day.isoformat(),
            "status": entry.status,
            "source": entry.source,
            "display_name": label or f"Token {entry.token_number}",
            "booking_id": str(entry.booking_id) if entry.booking_id else None,
            "customer_contact_id": str(entry.customer_contact_id) if entry.customer_contact_id else None,
            "priority": entry.priority,
            "ahead": ahead,
            "estimated_wait_minutes": estimate,
            "provider_id": str(entry.provider_id) if entry.provider_id else None,
            "department": lane.department,
            "location_id": str(entry.location_id),
            "issued_at": entry.issued_at.isoformat(),
            "called_at": entry.called_at.isoformat() if entry.called_at else None,
            "serving_at": entry.serving_at.isoformat() if entry.serving_at else None,
            "closed_at": entry.closed_at.isoformat() if entry.closed_at else None,
        }

    @staticmethod
    def serialize_lane(lane: QueueLane) -> dict[str, Any]:
        return {
            "id": str(lane.id),
            "name": lane.name,
            "location_id": str(lane.location_id),
            "provider_id": str(lane.provider_id) if lane.provider_id else None,
            "department": lane.department,
            "resource_id": str(lane.resource_id) if lane.resource_id else None,
            "allow_requeue": lane.allow_requeue,
            "turn_soon_ahead": lane.turn_soon_ahead,
            "avg_service_minutes": lane.avg_service_minutes,
            "status": lane.status,
        }

    @staticmethod
    async def _same_business_location(
        session: AsyncSession, business_id: uuid.UUID, location_id: uuid.UUID
    ) -> None:
        row = (await session.execute(
            text("SELECT 1 FROM business_locations WHERE id = :id AND business_id = :b AND deleted_at IS NULL"),
            {"id": str(location_id), "b": str(business_id)},
        )).first()
        if row is None:
            raise ValidationError("Unknown location", details={"field": "location_id"})

    @staticmethod
    async def _same_business_row(
        session: AsyncSession, table: str, business_id: uuid.UUID, row_id: uuid.UUID, field: str,
    ) -> None:
        # Table names are fixed by the callers above, never request input.
        row = (await session.execute(
            text(f"SELECT 1 FROM {table} WHERE id = :id AND business_id = :b"),
            {"id": str(row_id), "b": str(business_id)},
        )).first()
        if row is None:
            raise ValidationError(f"Unknown {field}", details={"field": field})
