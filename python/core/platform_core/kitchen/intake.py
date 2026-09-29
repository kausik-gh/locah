"""Open and adjust a kitchen ticket from an order event.

The order service does not know the kitchen exists. This module reads the
order through its resolver and the fulfilment job's mode, then writes only
kitchen tables. Replaying the same outbox event is a no-op: `kitchen_intakes`
is keyed by the event id, and a ticket is unique per order.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.events.registry import EventContext
from platform_core.kitchen.models import KitchenLineEvent, KitchenTicket, KitchenTicketLine
from platform_core.kitchen.service import KitchenService, allocate_ticket_number
from platform_core.kitchen.snapshot import (
    OPEN_ORDER_STATUSES,
    PREPARED_KINDS,
    modifier_snapshot,
    modifiers_match,
    service_snapshot,
)
from platform_core.services.outbox import OutboxService

_DELIVERY_FEE = "Delivery fee"


class OrderIntake:
    @staticmethod
    async def handle(session: AsyncSession, event: EventContext) -> None:
        business_id = event.require_business_id()
        order_id = event.require_uuid("order_id")
        if not await _module_on(session, business_id):
            return
        claimed = await session.execute(
            text(
                """
                INSERT INTO kitchen_intakes (event_id, business_id, order_id, action)
                VALUES (:event_id, :business_id, :order_id, :action)
                ON CONFLICT (event_id) DO NOTHING
                RETURNING event_id
                """
            ),
            {
                "event_id": event.event_id,
                "business_id": business_id,
                "order_id": order_id,
                "action": event.event_type,
            },
        )
        if claimed.first() is None:
            # This outbox event was already applied. A worker retry stops here.
            return
        if event.event_type in {"order.cancelled", "order.rejected"}:
            await OrderIntake.cancel(session, business_id=business_id, order_id=order_id, reason=_reason(event))
            return
        if event.event_type == "order.accepted":
            await OrderIntake.open_from_order(session, business_id=business_id, order_id=order_id)
            return
        await OrderIntake.on_order_updated(session, business_id=business_id, order_id=order_id)

    @staticmethod
    async def on_order_updated(
        session: AsyncSession, *, business_id: uuid.UUID, order_id: uuid.UUID
    ) -> None:
        from platform_core.resolvers.order_resolver import OrderResolver

        order = await OrderResolver.resolve(session, business_id=business_id, order_id=order_id)
        if order.status in {"cancelled", "rejected"}:
            await OrderIntake.cancel(
                session,
                business_id=business_id,
                order_id=order_id,
                reason=order.cancellation_reason,
            )
            return
        ticket = await _ticket_for(session, business_id, order_id)
        if ticket is None:
            if order.status in OPEN_ORDER_STATUSES:
                await OrderIntake.open_from_order(session, business_id=business_id, order_id=order_id)
            return
        if ticket.status in {"cancelled", "completed"}:
            return
        await OrderIntake.adjust(session, ticket=ticket, order=order)

    @staticmethod
    async def open_from_order(
        session: AsyncSession, *, business_id: uuid.UUID, order_id: uuid.UUID
    ) -> KitchenTicket | None:
        """One ticket for the order. A second accept, or a replay, returns the same one."""
        existing = await _ticket_for(session, business_id, order_id)
        if existing is not None:
            return existing
        from platform_core.models import FulfilmentJob, Offering
        from platform_core.resolvers.order_resolver import OrderResolver

        order = await OrderResolver.resolve(session, business_id=business_id, order_id=order_id)
        if order.status not in OPEN_ORDER_STATUSES | {"completed"}:
            return None
        order_lines = await OrderResolver.load_line_items(session, order_id=order.id)
        cooked = [line for line in order_lines if line.title != _DELIVERY_FEE]
        if not cooked:
            return None

        offering_ids = list({line.offering_id for line in cooked})
        kinds = {
            row.id: row.offering_type
            for row in (
                await session.execute(
                    select(Offering.id, Offering.offering_type).where(
                        Offering.business_id == business_id,
                        Offering.id.in_(offering_ids),
                    )
                )
            ).all()
        }
        routes = await KitchenService.routes_for(session, business_id=business_id)
        general_id: uuid.UUID | None = None
        planned: list[tuple[Any, uuid.UUID]] = []
        for line in cooked:
            station_ids = list(routes.get(line.offering_id) or [])
            if not station_ids:
                if kinds.get(line.offering_id) not in PREPARED_KINDS:
                    continue
                if general_id is None:
                    general = await KitchenService.ensure_general(session, business_id=business_id)
                    general_id = general.id
                station_ids = [general_id]
            for station_id in station_ids:
                planned.append((line, station_id))
        if not planned:
            return None

        job = await session.scalar(
            select(FulfilmentJob).where(
                FulfilmentJob.business_id == business_id,
                FulfilmentJob.order_id == order.id,
            )
        )
        address = job.delivery_address if job is not None and isinstance(job.delivery_address, dict) else None
        snap = service_snapshot(
            channel=order.channel,
            internal_reference=order.internal_reference,
            due_at=order.due_at,
            fulfilment_mode=job.mode if job is not None else None,
            delivery_address=address,
        )
        notes = await _prep_notes(session, business_id, order.id)
        try:
            async with session.begin_nested():
                ticket = KitchenTicket(
                    business_id=business_id,
                    location_id=order.location_id,
                    order_id=order.id,
                    ticket_number=await allocate_ticket_number(session, business_id),
                    channel=snap["channel"],
                    service_mode=snap["service_mode"],
                    service_label=snap["service_label"],
                    priority=snap["priority"],
                    status="new",
                    notes=notes,
                )
                session.add(ticket)
                await session.flush()
                for line, station_id in planned:
                    session.add(_line_from(ticket, line, station_id, origin="original"))
                session.add(_event(ticket, kind="opened", summary=f"{ticket.ticket_number} opened"))
                await session.flush()
                await OutboxService.publish(
                    session,
                    event_type="kitchen.ticket.created",
                    business_id=business_id,
                    payload={
                        "business_id": str(business_id),
                        "location_id": str(ticket.location_id),
                        "order_id": str(order.id),
                        "ticket_id": str(ticket.id),
                        "ticket_number": ticket.ticket_number,
                        "status": "new",
                    },
                    skip_notifications=True,
                )
                return ticket
        except IntegrityError:
            return await _ticket_for(session, business_id, order_id)

    @staticmethod
    async def adjust(session: AsyncSession, *, ticket: KitchenTicket, order: Any) -> None:
        """Apply an order edit without rewriting anything the kitchen has started.

        Before the ticket is started, a still-new line is what to cook, so the
        snapshot follows the order. After start, title, quantity, modifiers and
        timestamps stay. The pass shows an event, and a larger quantity arrives
        as its own new line.
        """
        from platform_core.resolvers.order_resolver import OrderResolver

        order_lines = [
            line
            for line in await OrderResolver.load_line_items(session, order_id=order.id)
            if line.title != _DELIVERY_FEE
        ]
        current = {line.id: line for line in order_lines}
        kitchen_lines = await KitchenService.lines_of(session, ticket.id)
        originals: dict[uuid.UUID, list[KitchenTicketLine]] = defaultdict(list)
        for line in kitchen_lines:
            if line.origin == "original":
                originals[line.order_line_id].append(line)

        locked = ticket.started_at is not None or any(line.started_at is not None for line in kitchen_lines)
        if not locked:
            notes = await _prep_notes(session, ticket.business_id, order.id)
            if notes != ticket.notes:
                ticket.notes = notes

        # What the pass was already told, so a later status-only order.updated
        # does not stack the same adjustment again.
        noted_qty, noted_mods = await _noted_requests(session, ticket.id)
        additions: list[KitchenTicketLine] = []
        for order_line_id, group in list(originals.items()):
            order_line = current.get(order_line_id)
            if order_line is None:
                _drop_missing(session, ticket, group, locked)
                continue
            record, words = modifier_snapshot(dict(order_line.options or {}))
            for line in group:
                if line.prep_status == "cancelled":
                    continue
                line_locked = locked or line.started_at is not None or line.prep_status != "new"
                if not line_locked:
                    line.quantity = order_line.quantity
                    line.title = order_line.title
                    line.modifiers = record
                    line.modifier_lines = words
                    continue
                held = _station_quantity(kitchen_lines, order_line_id, line.station_id) + sum(
                    added.quantity
                    for added in additions
                    if added.order_line_id == order_line_id and added.station_id == line.station_id
                )
                if order_line.quantity != held and noted_qty.get(line.id) != order_line.quantity:
                    if order_line.quantity < held:
                        session.add(
                            _event(
                                ticket,
                                kind="quantity_changed",
                                summary=(
                                    f"{line.title}: kitchen has {held}, "
                                    f"order now asks for {order_line.quantity}"
                                ),
                                line_id=line.id,
                                detail={"kitchen_quantity": held, "requested_quantity": order_line.quantity},
                            )
                        )
                        line.attention = line.attention or "adjust"
                        ticket.attention = ticket.attention or "adjust"
                    else:
                        extra = order_line.quantity - held
                        added = _line_from(
                            ticket, order_line, line.station_id, origin="added", quantity=extra
                        )
                        added.modifiers = record
                        added.modifier_lines = words
                        additions.append(added)
                        session.add(
                            _event(
                                ticket,
                                kind="line_added",
                                summary=f"Add {extra} × {order_line.title}",
                                line_id=line.id,
                                detail={"quantity": extra, "order_line_id": str(order_line_id)},
                            )
                        )
                already_noted = noted_mods.get(line.id)
                if not modifiers_match(line.modifiers or {}, record) and (
                    already_noted is None or not modifiers_match(already_noted, record)
                ):
                    session.add(
                        _event(
                            ticket,
                            kind="modifier_changed",
                            summary=f"{line.title}: choices changed to {', '.join(words) or 'none'}",
                            line_id=line.id,
                            detail={"was": line.modifiers or {}, "now": record},
                        )
                    )
                    line.attention = line.attention or "adjust"
                    ticket.attention = ticket.attention or "adjust"

        for line in order_lines:
            if line.id in originals:
                continue
            if line.title == _DELIVERY_FEE:
                continue
            for station_id in await _stations_for_line(session, ticket.business_id, line):
                additions.append(_line_from(ticket, line, station_id, origin="added"))
                session.add(
                    _event(
                        ticket,
                        kind="line_added",
                        summary=f"Add {line.quantity} × {line.title}",
                        detail={"quantity": line.quantity, "order_line_id": str(line.id)},
                    )
                )

        for added in additions:
            session.add(added)
        if additions:
            ticket.attention = ticket.attention or "adjust"
        await session.flush()

    @staticmethod
    async def cancel(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        order_id: uuid.UUID,
        reason: str | None,
    ) -> None:
        """Before cooking, the ticket leaves the pass. After start, the facts stay and the cancel is visible."""
        ticket = await _ticket_for(session, business_id, order_id)
        if ticket is None or ticket.status in {"completed", "cancelled"}:
            return
        if ticket.attention == "cancel":
            return
        lines = await KitchenService.lines_of(session, ticket.id)
        locked = ticket.started_at is not None or any(line.started_at is not None for line in lines)
        why = (reason or "Order cancelled").strip()[:200]
        if not locked:
            ticket.status = "cancelled"
            for line in lines:
                if line.prep_status != "completed":
                    line.prep_status = "cancelled"
            session.add(_event(ticket, kind="cancelled", summary=f"Cancelled before cooking. {why}"))
            await OutboxService.publish(
                session,
                event_type="kitchen.ticket.cancelled",
                business_id=business_id,
                payload={
                    "business_id": str(business_id),
                    "order_id": str(order_id),
                    "ticket_id": str(ticket.id),
                    "ticket_number": ticket.ticket_number,
                    "after_start": False,
                },
                skip_notifications=True,
            )
            await session.flush()
            return

        ticket.attention = "cancel"
        for line in lines:
            if line.prep_status in {"completed", "cancelled"}:
                continue
            if line.started_at is None and line.prep_status == "new":
                line.prep_status = "cancelled"
                continue
            # Started lines keep status, quantity, modifiers and timestamps.
            line.attention = "cancel"
            session.add(
                _event(
                    ticket,
                    kind="cancel_after_start",
                    summary=f"Cancel {line.quantity} × {line.title}. {why}",
                    line_id=line.id,
                    detail={"quantity": line.quantity, "prep_status": line.prep_status},
                )
            )
        await OutboxService.publish(
            session,
            event_type="kitchen.ticket.cancelled",
            business_id=business_id,
            payload={
                "business_id": str(business_id),
                "order_id": str(order_id),
                "ticket_id": str(ticket.id),
                "ticket_number": ticket.ticket_number,
                "after_start": True,
            },
            skip_notifications=True,
        )
        await session.flush()


def _drop_missing(
    session: AsyncSession,
    ticket: KitchenTicket,
    group: list[KitchenTicketLine],
    locked: bool,
) -> None:
    for line in group:
        if line.prep_status in {"cancelled", "completed"} or line.attention == "cancel":
            continue
        line_locked = locked or line.started_at is not None or line.prep_status != "new"
        if not line_locked:
            line.prep_status = "cancelled"
            session.add(
                _event(
                    ticket,
                    kind="line_removed",
                    summary=f"Removed {line.title} before cooking",
                    line_id=line.id,
                )
            )
            continue
        line.attention = "cancel"
        ticket.attention = ticket.attention or "cancel"
        session.add(
            _event(
                ticket,
                kind="cancel_after_start",
                summary=f"Take off {line.quantity} × {line.title}",
                line_id=line.id,
                detail={"quantity": line.quantity, "prep_status": line.prep_status},
            )
        )


def _station_quantity(
    lines: list[KitchenTicketLine], order_line_id: uuid.UUID, station_id: uuid.UUID
) -> int:
    """Portions still on this station for one order line, including extras added later."""
    return sum(
        line.quantity
        for line in lines
        if line.order_line_id == order_line_id
        and line.station_id == station_id
        and line.prep_status != "cancelled"
        and line.attention != "cancel"
    )


async def _noted_requests(
    session: AsyncSession, ticket_id: uuid.UUID
) -> tuple[dict[uuid.UUID, int], dict[uuid.UUID, dict[str, Any]]]:
    """The last quantity and modifier ask already shown on the pass, per line."""
    rows = list(
        (
            await session.scalars(
                select(KitchenLineEvent)
                .where(
                    KitchenLineEvent.ticket_id == ticket_id,
                    KitchenLineEvent.kind.in_(("quantity_changed", "modifier_changed")),
                )
                .order_by(KitchenLineEvent.created_at)
            )
        ).all()
    )
    quantities: dict[uuid.UUID, int] = {}
    modifiers: dict[uuid.UUID, dict[str, Any]] = {}
    for event in rows:
        if event.line_id is None:
            continue
        if event.kind == "quantity_changed":
            requested = (event.detail or {}).get("requested_quantity")
            if isinstance(requested, int):
                quantities[event.line_id] = requested
        elif event.kind == "modifier_changed":
            now = (event.detail or {}).get("now")
            if isinstance(now, dict):
                modifiers[event.line_id] = now
    return quantities, modifiers


async def _stations_for_line(session: AsyncSession, business_id: uuid.UUID, line: Any) -> list[uuid.UUID]:
    from platform_core.models import Offering

    routes = await KitchenService.routes_for(session, business_id=business_id)
    station_ids = list(routes.get(line.offering_id) or [])
    if station_ids:
        return station_ids
    kind = await session.scalar(
        select(Offering.offering_type).where(Offering.business_id == business_id, Offering.id == line.offering_id)
    )
    if kind not in PREPARED_KINDS:
        return []
    general = await KitchenService.ensure_general(session, business_id=business_id)
    return [general.id]


def _line_from(
    ticket: KitchenTicket,
    order_line: Any,
    station_id: uuid.UUID,
    *,
    origin: str,
    quantity: int | None = None,
) -> KitchenTicketLine:
    record, words = modifier_snapshot(dict(order_line.options or {}))
    return KitchenTicketLine(
        business_id=ticket.business_id,
        location_id=ticket.location_id,
        ticket_id=ticket.id,
        order_line_id=order_line.id,
        station_id=station_id,
        offering_id=order_line.offering_id,
        variant_id=order_line.variant_id,
        title=order_line.title,
        quantity=quantity if quantity is not None else order_line.quantity,
        modifiers=record,
        modifier_lines=words,
        prep_status="new",
        origin=origin,
    )


def _event(
    ticket: KitchenTicket,
    *,
    kind: str,
    summary: str,
    line_id: uuid.UUID | None = None,
    detail: dict[str, Any] | None = None,
) -> KitchenLineEvent:
    return KitchenLineEvent(
        business_id=ticket.business_id,
        location_id=ticket.location_id,
        ticket_id=ticket.id,
        line_id=line_id,
        kind=kind,
        summary=summary[:300],
        detail=detail or {},
    )


async def _ticket_for(
    session: AsyncSession, business_id: uuid.UUID, order_id: uuid.UUID
) -> KitchenTicket | None:
    return await session.scalar(
        select(KitchenTicket).where(
            KitchenTicket.business_id == business_id,
            KitchenTicket.order_id == order_id,
        )
    )


async def _module_on(session: AsyncSession, business_id: uuid.UUID) -> bool:
    row = (
        await session.execute(
            text(
                """
                SELECT activation_state FROM business_module_states
                WHERE business_id = :business_id AND module_id = 'kitchen'
                """
            ),
            {"business_id": business_id},
        )
    ).first()
    return row is not None and row[0] in {"enabled", "ready", "active"}


async def _prep_notes(session: AsyncSession, business_id: uuid.UUID, order_id: uuid.UUID) -> str:
    from platform_core.kitchen.snapshot import redact

    rows = (
        await session.execute(
            text(
                """
                SELECT body FROM orders_order_notes
                WHERE business_id = :business_id AND order_id = :order_id AND deleted_at IS NULL
                ORDER BY created_at
                """
            ),
            {"business_id": business_id, "order_id": order_id},
        )
    ).all()
    parts = [redact(str(row[0])) for row in rows]
    return " · ".join(part for part in parts if part)[:500]


def _reason(event: EventContext) -> str | None:
    reason = event.payload.get("reason")
    return str(reason) if reason else None
