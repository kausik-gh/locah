"""Stations, the pass, and moving a ticket from new to served.

Actions here change preparation only. They never write the sales order and
they never call inventory.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.kitchen.models import (
    KitchenLineEvent,
    KitchenStation,
    KitchenStationRoute,
    KitchenTicket,
    KitchenTicketLine,
)
from platform_core.kitchen.snapshot import (
    STATION_KINDS,
    VISIBLE_EVENT_KINDS,
    channel_words,
    mode_words,
)
from platform_core.services.outbox import OutboxService

# The event the recipe/BOM lane must subscribe to. See the kitchen handoff.
PREPARATION_COMPLETED = "kitchen.preparation.completed"

_STEP = {"start": "preparing", "ready": "ready", "serve": "completed"}
_FROM = {"start": "new", "ready": "preparing", "serve": "ready"}


def _bad(message: str, field: str = "kitchen") -> ValidationError:
    return ValidationError(message, details={"field": field, "errors": [{"field": field, "message": message}]})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def slug_key(name: str) -> str:
    """A station key from a name the business typed. Not a restaurant preset."""
    key = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")[:32]
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,31}", key or ""):
        raise _bad("Use a station name of at least two letters", "name")
    return key


class KitchenService:
    # ---------------------------------------------------------------- stations

    @staticmethod
    async def list_stations(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        location_ids: tuple[uuid.UUID, ...] | None = None,
    ) -> list[KitchenStation]:
        query = select(KitchenStation).where(KitchenStation.business_id == business_id)
        if location_ids is not None:
            query = query.where(
                (KitchenStation.location_id.is_(None)) | (KitchenStation.location_id.in_(location_ids))
            )
        rows = await session.execute(query.order_by(KitchenStation.sort_order, KitchenStation.name))
        return list(rows.scalars().all())

    @staticmethod
    async def create_station(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        name: str | None = None,
        key: str | None = None,
        location_id: uuid.UUID | None = None,
    ) -> KitchenStation:
        known = {k: label for k, label in STATION_KINDS}
        if key:
            station_key = key.strip().lower()
            if station_key not in known and not re.fullmatch(r"[a-z][a-z0-9_]{1,31}", station_key):
                raise _bad("Unknown station", "key")
            station_name = (name or known.get(station_key) or station_key).strip()[:40]
        else:
            station_name = (name or "").strip()[:40]
            if not station_name:
                raise _bad("Name the station", "name")
            station_key = slug_key(station_name)
        existing = await session.scalar(
            select(KitchenStation).where(
                KitchenStation.business_id == business_id,
                KitchenStation.key == station_key,
            )
        )
        if existing is not None:
            if not existing.active:
                existing.active = True
                existing.name = station_name
                existing.updated_at = _now()
                await session.flush()
            return existing
        count = await session.scalar(
            select(func.count()).select_from(KitchenStation).where(KitchenStation.business_id == business_id)
        )
        station = KitchenStation(
            business_id=business_id,
            location_id=location_id,
            key=station_key,
            name=station_name,
            sort_order=int(count or 0),
        )
        session.add(station)
        await session.flush()
        return station

    @staticmethod
    async def set_routes(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        offering_id: uuid.UUID,
        station_ids: list[uuid.UUID],
    ) -> list[uuid.UUID]:
        """Replace the stations that cook this offering. Empty means unrouted."""
        from platform_core.models import Offering

        offering = await session.scalar(
            select(Offering).where(Offering.business_id == business_id, Offering.id == offering_id)
        )
        if offering is None:
            raise ResourceNotFound("Offering")
        unique_ids = list(dict.fromkeys(station_ids))
        if unique_ids:
            found = list(
                (
                    await session.scalars(
                        select(KitchenStation.id).where(
                            KitchenStation.business_id == business_id,
                            KitchenStation.id.in_(unique_ids),
                            KitchenStation.active.is_(True),
                        )
                    )
                ).all()
            )
            if len(found) != len(unique_ids):
                raise _bad("Choose stations that belong to this business", "station_ids")
        await session.execute(
            delete(KitchenStationRoute).where(
                KitchenStationRoute.business_id == business_id,
                KitchenStationRoute.offering_id == offering_id,
            )
        )
        for station_id in unique_ids:
            session.add(
                KitchenStationRoute(
                    business_id=business_id,
                    offering_id=offering_id,
                    station_id=station_id,
                )
            )
        await session.flush()
        return unique_ids

    @staticmethod
    async def routes_for(
        session: AsyncSession, *, business_id: uuid.UUID
    ) -> dict[uuid.UUID, list[uuid.UUID]]:
        rows = (
            await session.execute(
                select(KitchenStationRoute.offering_id, KitchenStationRoute.station_id).where(
                    KitchenStationRoute.business_id == business_id
                )
            )
        ).all()
        grouped: dict[uuid.UUID, list[uuid.UUID]] = {}
        for offering_id, station_id in rows:
            grouped.setdefault(offering_id, []).append(station_id)
        return grouped

    @staticmethod
    async def ensure_general(session: AsyncSession, *, business_id: uuid.UUID) -> KitchenStation:
        """The fallback station. Created the first time a prepared item has nowhere to go."""
        existing = await session.scalar(
            select(KitchenStation).where(
                KitchenStation.business_id == business_id,
                KitchenStation.key == "general",
            )
        )
        if existing is not None:
            if not existing.active:
                existing.active = True
            return existing
        try:
            async with session.begin_nested():
                station = KitchenStation(
                    business_id=business_id,
                    location_id=None,
                    key="general",
                    name="General",
                    sort_order=0,
                )
                session.add(station)
                await session.flush()
                return station
        except IntegrityError:
            found = await session.scalar(
                select(KitchenStation).where(
                    KitchenStation.business_id == business_id,
                    KitchenStation.key == "general",
                )
            )
            if found is None:
                raise
            return found

    # ---------------------------------------------------------------- pass

    @staticmethod
    async def get_ticket(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        ticket_id: uuid.UUID,
        location_ids: tuple[uuid.UUID, ...] | None = None,
    ) -> KitchenTicket:
        ticket = await session.scalar(
            select(KitchenTicket).where(
                KitchenTicket.business_id == business_id,
                KitchenTicket.id == ticket_id,
            )
        )
        if ticket is None or (location_ids is not None and ticket.location_id not in location_ids):
            raise ResourceNotFound("Kitchen ticket")
        return ticket

    @staticmethod
    async def lines_of(session: AsyncSession, ticket_id: uuid.UUID) -> list[KitchenTicketLine]:
        rows = await session.scalars(
            select(KitchenTicketLine)
            .where(KitchenTicketLine.ticket_id == ticket_id)
            .order_by(KitchenTicketLine.entered_at, KitchenTicketLine.title)
        )
        return list(rows.all())

    @staticmethod
    async def board(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        station_id: uuid.UUID | None = None,
        location_ids: tuple[uuid.UUID, ...] | None = None,
    ) -> dict[str, Any]:
        """New, Preparing, Ready. Completed tickets leave the pass.

        With a station selected, a ticket sits in the column for that station's
        own lines, so the grill can be ready while the fryer is still on new.
        """
        stations = await KitchenService.list_stations(
            session, business_id=business_id, location_ids=location_ids
        )
        active_stations = [s for s in stations if s.active]
        if station_id is not None and all(s.id != station_id for s in active_stations):
            raise ResourceNotFound("Station")

        query = select(KitchenTicket).where(
            KitchenTicket.business_id == business_id,
            KitchenTicket.status.in_(("new", "preparing", "ready")),
        )
        if location_ids is not None:
            query = query.where(KitchenTicket.location_id.in_(location_ids))
        tickets = list(
            (await session.scalars(query.order_by(KitchenTicket.priority.desc(), KitchenTicket.entered_at))).all()
        )
        # Rush sorts first because 'rush' > 'normal'. Then oldest first within that,
        # which the query's second key does not guarantee across the priority split.
        tickets.sort(key=lambda t: (0 if t.priority == "rush" else 1, t.entered_at))

        ticket_ids = [t.id for t in tickets]
        lines: list[KitchenTicketLine] = []
        events: list[KitchenLineEvent] = []
        if ticket_ids:
            lines = list(
                (
                    await session.scalars(
                        select(KitchenTicketLine).where(KitchenTicketLine.ticket_id.in_(ticket_ids))
                    )
                ).all()
            )
            events = list(
                (
                    await session.scalars(
                        select(KitchenLineEvent).where(
                            KitchenLineEvent.ticket_id.in_(ticket_ids),
                            KitchenLineEvent.kind.in_(VISIBLE_EVENT_KINDS),
                        )
                    )
                ).all()
            )
        names = {s.id: s.name for s in stations}
        by_ticket: dict[uuid.UUID, list[KitchenTicketLine]] = {}
        for line in lines:
            by_ticket.setdefault(line.ticket_id, []).append(line)
        events_by: dict[uuid.UUID, list[KitchenLineEvent]] = {}
        for event in events:
            events_by.setdefault(event.ticket_id, []).append(event)

        columns: dict[str, list[dict[str, Any]]] = {"new": [], "preparing": [], "ready": []}
        now = _now()
        for ticket in tickets:
            own = by_ticket.get(ticket.id, [])
            if station_id is not None:
                own = [line for line in own if line.station_id == station_id]
                if not own:
                    continue
            column = _column_for(own)
            if column is None:
                continue
            columns[column].append(_card(ticket, own, events_by.get(ticket.id, []), names, now))

        return {
            "now": now.isoformat(),
            "station_id": str(station_id) if station_id else None,
            "stations": [
                {"id": str(s.id), "key": s.key, "name": s.name, "location_id": str(s.location_id) if s.location_id else None}
                for s in active_stations
            ],
            "station_kinds": [{"key": key, "name": label} for key, label in STATION_KINDS],
            "columns": columns,
        }

    @staticmethod
    async def set_priority(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        ticket_id: uuid.UUID,
        priority: str,
        location_ids: tuple[uuid.UUID, ...] | None = None,
        expected_version: int | None = None,
    ) -> KitchenTicket:
        if priority not in {"normal", "rush"}:
            raise _bad("Priority is normal or rush", "priority")
        ticket = await KitchenService.get_ticket(
            session, business_id=business_id, ticket_id=ticket_id, location_ids=location_ids
        )
        _check_version(ticket, expected_version)
        ticket.priority = priority
        ticket.version += 1
        ticket.updated_at = _now()
        await session.flush()
        return ticket

    @staticmethod
    async def advance(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        ticket_id: uuid.UUID,
        step: str,
        station_id: uuid.UUID | None = None,
        location_ids: tuple[uuid.UUID, ...] | None = None,
        expected_version: int | None = None,
    ) -> KitchenTicket:
        """new → preparing → ready → completed (served), for one station or the whole ticket."""
        if step not in _STEP and step != "clear":
            raise _bad("Unknown step", "step")
        ticket = await KitchenService.get_ticket(
            session, business_id=business_id, ticket_id=ticket_id, location_ids=location_ids
        )
        _check_version(ticket, expected_version)
        if ticket.status in {"completed", "cancelled"} and ticket.attention is None:
            raise ConflictError("This ticket has left the pass")
        lines = await KitchenService.lines_of(session, ticket.id)
        scoped = [line for line in lines if station_id is None or line.station_id == station_id]
        if station_id is not None and not scoped:
            raise ResourceNotFound("Station")
        if step == "clear":
            # The cook has seen the cancel. Status, quantity and timestamps of the
            # cooked line are not rewritten; it simply leaves the active pass.
            moved = [line for line in scoped if line.attention == "cancel" and line.prep_status != "cancelled"]
            if not moved:
                raise ConflictError("Nothing on this ticket was cancelled")
            for line in moved:
                line.prep_status = "cancelled"
            if not any(line.attention == "cancel" and line.prep_status != "cancelled" for line in lines):
                ticket.attention = None
            await _rollup(session, ticket, lines, _now())
            await session.flush()
            return ticket
        target = _STEP[step]
        source = _FROM[step]
        moved = [line for line in scoped if line.prep_status == source and line.attention is None]
        if not moved:
            raise ConflictError(_nothing_to_do(step))
        moment = _now()
        for line in moved:
            line.prep_status = target
            if step == "start":
                line.started_at = moment
            elif step == "ready":
                line.ready_at = moment
            else:
                line.completed_at = moment
        await _rollup(session, ticket, lines, moment)
        await session.flush()
        return ticket

    @staticmethod
    async def publish_preparation_completed(
        session: AsyncSession,
        *,
        ticket: KitchenTicket,
        lines: list[KitchenTicketLine],
    ) -> None:
        """Tell Recipe/BOM that this preparation is finished. Does not touch stock.

        Payload contract (stable for the supply lane):

            business_id, location_id, order_id, ticket_id, ticket_number,
            completed_at,
            lines: [{ order_line_id, offering_id, variant_id, quantity, modifiers }]

        Quantity is what the kitchen cooked, including lines added after the
        order grew. Lines the kitchen was told to cancel are omitted.
        """
        if ticket.consumption_published:
            return
        cooked = [
            line
            for line in lines
            if line.prep_status == "completed" and line.attention is None
        ]
        payload = {
            "business_id": str(ticket.business_id),
            "location_id": str(ticket.location_id),
            "order_id": str(ticket.order_id),
            "ticket_id": str(ticket.id),
            "ticket_number": ticket.ticket_number,
            "completed_at": (ticket.completed_at or _now()).isoformat(),
            "lines": [
                {
                    "order_line_id": str(line.order_line_id),
                    "offering_id": str(line.offering_id),
                    "variant_id": str(line.variant_id) if line.variant_id else None,
                    "quantity": line.quantity,
                    "modifiers": line.modifiers or {},
                }
                for line in cooked
            ],
        }
        await OutboxService.publish(
            session,
            event_type=PREPARATION_COMPLETED,
            business_id=ticket.business_id,
            payload=payload,
            skip_notifications=True,
        )
        ticket.consumption_published = True


def _check_version(ticket: KitchenTicket, expected: int | None) -> None:
    if expected is not None and ticket.version != expected:
        raise ConflictError("This ticket changed — refresh the pass")


def _nothing_to_do(step: str) -> str:
    if step == "start":
        return "Nothing on this ticket is waiting to start"
    if step == "ready":
        return "Start it before marking it ready"
    return "Mark it ready before serving"


def _column_for(lines: list[KitchenTicketLine]) -> str | None:
    """Where this station's lines sit. Cancelled-only lines leave the pass."""
    active = [line for line in lines if line.prep_status != "cancelled"]
    if not active:
        return None
    statuses = {line.prep_status for line in active}
    if statuses <= {"completed"}:
        return None
    if statuses <= {"ready", "completed"}:
        return "ready"
    if statuses <= {"new"}:
        return "new"
    return "preparing"


def _card(
    ticket: KitchenTicket,
    lines: list[KitchenTicketLine],
    events: list[KitchenLineEvent],
    station_names: dict[uuid.UUID, str],
    now: datetime,
) -> dict[str, Any]:
    """A pass card. No prices, no phone numbers, no customer name."""
    anchor = ticket.entered_at
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    elapsed = max(0, int((now - anchor).total_seconds()))
    visible = sorted(events, key=lambda event: event.created_at)
    return {
        "id": str(ticket.id),
        "ticket_number": ticket.ticket_number,
        "order_id": str(ticket.order_id),
        "channel": ticket.channel,
        "channel_label": channel_words(ticket.channel),
        "service_mode": ticket.service_mode,
        "service_mode_label": mode_words(ticket.service_mode),
        "service_label": ticket.service_label,
        "priority": ticket.priority,
        "status": ticket.status,
        "attention": ticket.attention,
        "notes": ticket.notes,
        "entered_at": ticket.entered_at.isoformat(),
        "started_at": ticket.started_at.isoformat() if ticket.started_at else None,
        "elapsed_seconds": elapsed,
        "version": ticket.version,
        "lines": [
            {
                "id": str(line.id),
                "title": line.title,
                "quantity": line.quantity,
                "modifiers": list(line.modifier_lines or []),
                "station_id": str(line.station_id),
                "station_name": station_names.get(line.station_id, ""),
                "prep_status": line.prep_status,
                "origin": line.origin,
                "attention": line.attention,
            }
            for line in lines
            if line.prep_status != "cancelled" or line.attention
        ],
        "events": [
            {"kind": event.kind, "summary": event.summary, "at": event.created_at.isoformat()}
            for event in visible
        ],
    }


async def _rollup(
    session: AsyncSession,
    ticket: KitchenTicket,
    lines: list[KitchenTicketLine],
    moment: datetime,
) -> None:
    """Ticket status follows every station, then the served ticket tells Recipe/BOM."""
    active = [line for line in lines if line.prep_status != "cancelled"]
    previous = ticket.status
    if not active:
        ticket.status = "cancelled"
    else:
        statuses = {line.prep_status for line in active}
        if statuses <= {"completed"}:
            ticket.status = "completed"
            ticket.completed_at = ticket.completed_at or moment
        elif statuses <= {"ready", "completed"}:
            ticket.status = "ready"
            ticket.ready_at = ticket.ready_at or moment
        elif statuses <= {"new"}:
            ticket.status = "new"
        else:
            ticket.status = "preparing"
            ticket.started_at = ticket.started_at or moment
    ticket.version += 1
    ticket.updated_at = moment
    if ticket.status == "preparing" and previous == "new":
        await OutboxService.publish(
            session,
            event_type="kitchen.ticket.started",
            business_id=ticket.business_id,
            payload=_ticket_payload(ticket),
            skip_notifications=True,
        )
    if ticket.status == "ready" and previous != "ready":
        await OutboxService.publish(
            session,
            event_type="kitchen.ticket.ready",
            business_id=ticket.business_id,
            payload=_ticket_payload(ticket),
            skip_notifications=True,
        )
    if ticket.status == "completed" and previous != "completed":
        await KitchenService.publish_preparation_completed(session, ticket=ticket, lines=lines)


def _ticket_payload(ticket: KitchenTicket) -> dict[str, Any]:
    return {
        "business_id": str(ticket.business_id),
        "location_id": str(ticket.location_id),
        "order_id": str(ticket.order_id),
        "ticket_id": str(ticket.id),
        "ticket_number": ticket.ticket_number,
        "status": ticket.status,
    }


async def allocate_ticket_number(session: AsyncSession, business_id: uuid.UUID) -> str:
    """KOT-0001, KOT-0002, … per business. Not an order number."""
    row = await session.execute(
        text(
            """
            INSERT INTO kitchen_counters (business_id, next_number)
            VALUES (:business_id, 2)
            ON CONFLICT (business_id)
            DO UPDATE SET next_number = kitchen_counters.next_number + 1
            RETURNING next_number - 1 AS n
            """
        ),
        {"business_id": business_id},
    )
    number = int(row.scalar_one())
    return f"KOT-{number:04d}"
