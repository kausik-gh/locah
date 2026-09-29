"""Transfers, van stock, job-consumption contracts, client-owned stock, customer assets.

Founder refinement — Inventory §§2, 17, 19. One ledger. A van is a location.
Stock in transit is not available at the source or the destination. Receipt
is what completes the move. Jobs are not imported: this module is the one
job-parts contract. Jobs calls consume_record_for_job and return_unused with its
job id as job_ref; consume_for_job is Inventory's own door (lines from a van).
Both write the same movement and the same "what this job has out" record.

Client-owned quantity lives on its own inventory_records row (owner_customer_id).
Sale, reservation, POS and the stock home read only rows whose owner is null.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, OutsideLocationScope, ResourceNotFound, ValidationError
from platform_core.models import (
    CustomerAsset,
    CustomerContact,
    InventoryBatch,
    InventoryFieldKey,
    InventoryJobUse,
    InventoryMovement,
    InventoryRecord,
    InventoryTransfer,
    InventoryTransferLine,
    Offering,
)
from platform_core.services.outbox import OutboxService
from platform_core.stock import ledger
from platform_core.stock.service import StockService, display_quantity, today_ist

ASSET_KINDS = frozenset({"vehicle", "device", "ac_unit", "machine", "pet", "policy", "other"})
_NIL = uuid.UUID("00000000-0000-0000-0000-000000000000")


def _key(raw: Any) -> str:
    text = str(raw or "").strip()
    if not 8 <= len(text) <= 80:
        raise ValidationError("Give an idempotency key between 8 and 80 characters",
                              details={"field": "idempotency_key"})
    return text


def _qty(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Enter a whole quantity", details={"field": "quantity"}) from exc
    if value < 1:
        raise ValidationError("Quantity must be at least 1", details={"field": "quantity"})
    return value


class InventoryFieldService:
    # ---------------------------------------------------------------- keys
    @staticmethod
    async def _saved(session: AsyncSession, business_id: uuid.UUID, key: str) -> dict[str, Any] | None:
        row = await session.get(InventoryFieldKey, (business_id, key))
        if row is None:
            return None
        return dict(row.snapshot)

    @staticmethod
    async def replayed(session: AsyncSession, business_id: uuid.UUID, key: str) -> dict[str, Any] | None:
        """The answer already given for this idempotency key, if it was used."""
        return await InventoryFieldService._saved(session, business_id, key)

    @staticmethod
    async def _remember(
        session: AsyncSession, business_id: uuid.UUID, key: str, action: str,
        subject_id: uuid.UUID | None, snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        session.add(InventoryFieldKey(
            business_id=business_id, idempotency_key=key, action=action,
            subject_id=subject_id, snapshot=snapshot,
        ))
        await session.flush()
        return snapshot

    # ---------------------------------------------------------------- locations and lines
    @staticmethod
    def _scope_touch(allowed: list[uuid.UUID] | None, *location_ids: uuid.UUID) -> None:
        if allowed is None:
            return
        if not any(loc in allowed for loc in location_ids):
            raise OutsideLocationScope()

    @staticmethod
    async def _lines_of(session: AsyncSession, transfer_id: uuid.UUID) -> list[InventoryTransferLine]:
        rows = (await session.execute(select(InventoryTransferLine).where(
            InventoryTransferLine.transfer_id == transfer_id
        ).order_by(InventoryTransferLine.offering_id))).scalars()
        return list(rows)

    @staticmethod
    async def serialize(session: AsyncSession, transfer: InventoryTransfer) -> dict[str, Any]:
        lines = await InventoryFieldService._lines_of(session, transfer.id)
        offerings = {o.id: o for o in (await session.execute(select(Offering).where(
            Offering.id.in_([ln.offering_id for ln in lines] or [uuid.uuid4()])))).scalars()}
        names = {}
        for loc in (transfer.source_location_id, transfer.destination_location_id):
            location = await StockService._location(session, transfer.business_id, loc, None)
            names[loc] = location.name
        return {
            "id": str(transfer.id),
            "status": transfer.status,
            "requires_approval": transfer.requires_approval,
            "source_location_id": str(transfer.source_location_id),
            "source_name": names.get(transfer.source_location_id),
            "destination_location_id": str(transfer.destination_location_id),
            "destination_name": names.get(transfer.destination_location_id),
            "note": transfer.note,
            "version": transfer.version,
            "created_at": transfer.created_at.isoformat() if transfer.created_at else None,
            "lines": [{
                "offering_id": str(ln.offering_id),
                "variant_id": str(ln.variant_id) if ln.variant_id else None,
                "title": offerings[ln.offering_id].title if ln.offering_id in offerings else "",
                "quantity": ln.quantity,
                "quantity_text": display_quantity(
                    ln.quantity, offerings[ln.offering_id].stock_unit if ln.offering_id in offerings else "piece"),
            } for ln in lines],
        }

    @staticmethod
    async def _lock(session: AsyncSession, business_id: uuid.UUID, transfer_id: uuid.UUID) -> InventoryTransfer:
        transfer = (await session.execute(select(InventoryTransfer).where(
            InventoryTransfer.id == transfer_id, InventoryTransfer.business_id == business_id,
        ).with_for_update())).scalars().first()
        if transfer is None:
            raise ResourceNotFound("Transfer")
        return transfer

    # ---------------------------------------------------------------- request / approve / send / receive
    @staticmethod
    async def list_transfers(
        session: AsyncSession, business_id: uuid.UUID, allowed: list[uuid.UUID] | None,
        *, status: str | None = None,
    ) -> list[dict[str, Any]]:
        q = select(InventoryTransfer).where(InventoryTransfer.business_id == business_id)
        if status:
            q = q.where(InventoryTransfer.status == status)
        if allowed is not None:
            q = q.where(
                InventoryTransfer.source_location_id.in_(allowed)
                | InventoryTransfer.destination_location_id.in_(allowed)
            )
        rows = list((await session.execute(q.order_by(InventoryTransfer.created_at.desc()).limit(80))).scalars())
        return [await InventoryFieldService.serialize(session, row) for row in rows]

    @staticmethod
    async def request_transfer(
        session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
        payload: dict[str, Any], allowed: list[uuid.UUID] | None,
    ) -> dict[str, Any]:
        key = _key(payload.get("idempotency_key"))
        found = (await session.execute(select(InventoryTransfer).where(
            InventoryTransfer.business_id == business_id, InventoryTransfer.idempotency_key == key,
        ))).scalars().first()
        if found:
            return await InventoryFieldService.serialize(session, found)
        source_id = uuid.UUID(str(payload.get("source_location_id")))
        dest_id = uuid.UUID(str(payload.get("destination_location_id")))
        if source_id == dest_id:
            raise ValidationError("Send stock to a different location")
        InventoryFieldService._scope_touch(allowed, source_id, dest_id)
        await StockService._location(session, business_id, source_id, None)
        await StockService._location(session, business_id, dest_id, None)
        raw_lines = list(payload.get("lines") or [])
        if not raw_lines:
            raise ValidationError("Add at least one item to move")
        parsed: list[tuple[Offering, uuid.UUID | None, int]] = []
        seen: set[tuple[uuid.UUID, uuid.UUID]] = set()
        for raw in raw_lines:
            offering = await StockService._offering(session, business_id, (raw or {}).get("offering_id"))
            if offering.serial_tracked:
                raise ValidationError(
                    f"{offering.title} is tracked by serial number. This transfer moves quantities; "
                    "serial moves are not part of this step.",
                    details={"offering_id": str(offering.id)},
                )
            variant_id = await StockService._variant(session, offering, (raw or {}).get("variant_id"))
            quantity = _qty((raw or {}).get("quantity"))
            marker = (offering.id, variant_id or _NIL)
            if marker in seen:
                raise ValidationError(f"{offering.title} is listed twice")
            seen.add(marker)
            parsed.append((offering, variant_id, quantity))
        note = str(payload.get("note") or "").strip()[:300] or None
        transfer = InventoryTransfer(
            business_id=business_id, source_location_id=source_id, destination_location_id=dest_id,
            status="requested", requires_approval=bool(payload.get("requires_approval")),
            idempotency_key=key, note=note, requested_by=actor_id,
        )
        session.add(transfer)
        await session.flush()
        for offering, variant_id, quantity in parsed:
            session.add(InventoryTransferLine(
                business_id=business_id, transfer_id=transfer.id, offering_id=offering.id,
                variant_id=variant_id, quantity=quantity,
            ))
        await session.flush()
        body = await InventoryFieldService.serialize(session, transfer)
        await OutboxService.publish(
            session, event_type="inventory.transfer.requested", business_id=business_id,
            payload={"business_id": str(business_id), "transfer_id": str(transfer.id),
                     "requires_approval": transfer.requires_approval, "after": body},
        )
        return body

    @staticmethod
    async def approve(
        session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
        transfer_id: uuid.UUID, payload: dict[str, Any], allowed: list[uuid.UUID] | None,
    ) -> dict[str, Any]:
        key = _key(payload.get("idempotency_key"))
        saved = await InventoryFieldService._saved(session, business_id, key)
        if saved:
            return saved
        transfer = await InventoryFieldService._lock(session, business_id, transfer_id)
        InventoryFieldService._scope_touch(allowed, transfer.source_location_id, transfer.destination_location_id)
        if not transfer.requires_approval:
            raise ValidationError("This transfer does not need approval")
        if transfer.status != "requested":
            raise ConflictError("Only a requested transfer can be approved",
                                details={"status": transfer.status})
        transfer.status = "approved"
        transfer.version += 1
        await session.flush()
        body = await InventoryFieldService.serialize(session, transfer)
        await OutboxService.publish(
            session, event_type="inventory.transfer.approved", business_id=business_id,
            payload={"business_id": str(business_id), "transfer_id": str(transfer.id),
                     "actor_id": str(actor_id), "after": body},
        )
        return await InventoryFieldService._remember(session, business_id, key, "approve", transfer.id, body)

    @staticmethod
    async def _capture(session: AsyncSession, taken: list[ledger.Allocation]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for alloc in taken:
            code = None
            expires = None
            if alloc.batch_id is not None:
                batch = await session.get(InventoryBatch, alloc.batch_id)
                if batch is not None:
                    code = batch.batch_code
                    expires = batch.expires_on.isoformat() if batch.expires_on else None
            out.append({
                "batch_code": code, "expires_on": expires, "quantity": alloc.quantity,
                "value_paise": alloc.value_paise,
            })
        return out

    @staticmethod
    async def send(
        session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
        transfer_id: uuid.UUID, payload: dict[str, Any], allowed: list[uuid.UUID] | None,
    ) -> dict[str, Any]:
        """Leave the source. The destination does not gain the quantity yet."""
        key = _key(payload.get("idempotency_key"))
        saved = await InventoryFieldService._saved(session, business_id, key)
        if saved:
            return saved
        transfer = await InventoryFieldService._lock(session, business_id, transfer_id)
        # Sending is the source location's act.
        await StockService._location(session, business_id, transfer.source_location_id, allowed)
        if transfer.requires_approval and transfer.status == "requested":
            raise ValidationError("This transfer needs approval before it can leave")
        if transfer.status not in ("requested", "approved"):
            raise ConflictError("This transfer is not waiting to leave", details={"status": transfer.status})
        lines = await InventoryFieldService._lines_of(session, transfer.id)
        for line in lines:
            offering = await StockService._offering(session, business_id, line.offering_id)
            record = await StockService._record(
                session, business_id, offering, transfer.source_location_id, line.variant_id)
            free = record.quantity_on_hand - record.quantity_reserved
            if line.quantity > free:
                raise ValidationError(
                    f"Only {display_quantity(max(free, 0), offering.stock_unit)} of {offering.title} "
                    "is free to send. Reserved stock stays for orders.",
                    details={"available": max(free, 0), "requested": line.quantity},
                )
            taken = await ledger.take(session, record, offering, line.quantity, today=today_ist())
            value = sum(a.value_paise for a in taken)
            line.value_paise = value
            line.allocations = await InventoryFieldService._capture(session, taken)
            await StockService._write(
                session, record, offering, delta=-line.quantity, movement_type="transfer_out",
                reason=f"Transfer to {transfer.destination_location_id}", actor_id=actor_id,
                value_delta=-value, event="inventory.transfer.in_transit",
                source=("transfer", transfer.id), extra={"transfer_id": str(transfer.id)},
            )
        transfer.status = "in_transit"
        transfer.version += 1
        await session.flush()
        body = await InventoryFieldService.serialize(session, transfer)
        return await InventoryFieldService._remember(session, business_id, key, "send", transfer.id, body)

    @staticmethod
    async def _land_batches(
        session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
        record: InventoryRecord, offering: Offering, allocations: list[dict[str, Any]],
    ) -> None:
        for raw in allocations:
            code = raw.get("batch_code")
            quantity = int(raw.get("quantity") or 0)
            if not code or quantity <= 0:
                continue
            expires_raw = raw.get("expires_on")
            expires = date.fromisoformat(str(expires_raw)) if expires_raw else None
            session.add(InventoryBatch(
                business_id=business_id, location_id=record.location_id, inventory_record_id=record.id,
                offering_id=offering.id, variant_id=record.variant_id, batch_code=str(code)[:60],
                expires_on=expires, received_on=today_ist(), quantity_received=quantity,
                quantity_on_hand=quantity, created_by=actor_id,
            ))
        await session.flush()

    @staticmethod
    async def receive(
        session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
        transfer_id: uuid.UUID, payload: dict[str, Any], allowed: list[uuid.UUID] | None,
    ) -> dict[str, Any]:
        """Receipt completes the movement. The destination gains exactly the quantity sent."""
        key = _key(payload.get("idempotency_key"))
        saved = await InventoryFieldService._saved(session, business_id, key)
        if saved:
            return saved
        transfer = await InventoryFieldService._lock(session, business_id, transfer_id)
        saved = await InventoryFieldService._saved(session, business_id, key)
        if saved:
            return saved
        await StockService._location(session, business_id, transfer.destination_location_id, allowed)
        if transfer.status != "in_transit":
            raise ConflictError("Only stock that is in transit can be received",
                                details={"status": transfer.status})
        lines = await InventoryFieldService._lines_of(session, transfer.id)
        for line in lines:
            offering = await StockService._offering(session, business_id, line.offering_id)
            record = await StockService._record(
                session, business_id, offering, transfer.destination_location_id, line.variant_id)
            record.stock_value_paise += int(line.value_paise or 0)
            await StockService._write(
                session, record, offering, delta=line.quantity, movement_type="transfer_in",
                reason=f"Received transfer {transfer.id}", actor_id=actor_id,
                value_delta=int(line.value_paise or 0), event="inventory.transfer.received",
                source=("transfer", transfer.id), extra={"transfer_id": str(transfer.id)},
            )
            await InventoryFieldService._land_batches(
                session, business_id, actor_id, record, offering, list(line.allocations or []))
        transfer.status = "received"
        transfer.version += 1
        await session.flush()
        body = await InventoryFieldService.serialize(session, transfer)
        return await InventoryFieldService._remember(session, business_id, key, "receive", transfer.id, body)

    # ---------------------------------------------------------------- van board
    @staticmethod
    async def van_board(
        session: AsyncSession, business_id: uuid.UUID, allowed: list[uuid.UUID] | None,
    ) -> dict[str, Any]:
        from platform_core.models import BusinessLocation

        q = select(BusinessLocation).where(
            BusinessLocation.business_id == business_id, BusinessLocation.deleted_at.is_(None),
            BusinessLocation.stock_role == "van", BusinessLocation.status == "active",
        )
        if allowed is not None:
            q = q.where(BusinessLocation.id.in_(allowed))
        vans = list((await session.execute(q.order_by(BusinessLocation.name))).scalars())
        out = []
        for van in vans:
            rows = (await session.execute(select(InventoryRecord, Offering).join(
                Offering, Offering.id == InventoryRecord.offering_id,
            ).where(
                InventoryRecord.business_id == business_id, InventoryRecord.location_id == van.id,
                InventoryRecord.owner_customer_id.is_(None), Offering.deleted_at.is_(None),
            ).order_by(Offering.title))).all()
            lines = []
            for record, offering in rows:
                available = max(record.quantity_on_hand - record.quantity_reserved, 0)
                lines.append({
                    "offering_id": str(offering.id),
                    "variant_id": str(record.variant_id) if record.variant_id else None,
                    "title": offering.title,
                    "on_hand": record.quantity_on_hand,
                    "reserved": record.quantity_reserved,
                    "available": available,
                    "on_hand_text": display_quantity(record.quantity_on_hand, offering.stock_unit),
                    "available_text": display_quantity(available, offering.stock_unit),
                })
            inbound = await InventoryFieldService.list_transfers(session, business_id, [van.id], status="in_transit")
            inbound = [t for t in inbound if t["destination_location_id"] == str(van.id)]
            outbound = [t for t in await InventoryFieldService.list_transfers(
                session, business_id, [van.id], status="in_transit") if t["source_location_id"] == str(van.id)]
            out.append({
                "location_id": str(van.id), "name": van.name, "lines": lines,
                "inbound": inbound, "outbound": outbound,
            })
        return {"vans": out}

    # ---------------------------------------------------------------- job contract (no jobs tables)
    @staticmethod
    async def _job_use(
        session: AsyncSession, business_id: uuid.UUID, location_id: uuid.UUID, job_ref: uuid.UUID,
        offering_id: uuid.UUID, variant_id: uuid.UUID | None,
    ) -> InventoryJobUse:
        row = (await session.execute(select(InventoryJobUse).where(
            InventoryJobUse.business_id == business_id, InventoryJobUse.location_id == location_id,
            InventoryJobUse.job_ref == job_ref, InventoryJobUse.offering_id == offering_id,
            InventoryJobUse.variant_id == variant_id if variant_id else InventoryJobUse.variant_id.is_(None),
        ).with_for_update())).scalars().first()
        if row is None:
            row = InventoryJobUse(
                business_id=business_id, location_id=location_id, job_ref=job_ref,
                offering_id=offering_id, variant_id=variant_id,
            )
            session.add(row)
            await session.flush()
        return row

    @staticmethod
    async def _consume(
        session: AsyncSession, record: InventoryRecord, offering: Offering, *, job_ref: uuid.UUID,
        quantity: int, serials: list[str], customer_contact_id: uuid.UUID | None, actor_id: uuid.UUID,
    ) -> InventoryMovement:
        """The one stock movement for a part used on a job, whichever door it came through.

        Takes the quantity (batches first-expiry, serials sold to the job's
        customer), writes one `job_consumption` movement, and adds it to what
        this job has out at this location — the bound every return is held to.
        """
        if record.owner_customer_id is not None:
            raise ValidationError("That is the customer's own stock, not a part to use")
        if quantity < 1:
            raise ValidationError("Part quantity must be positive")
        free = record.quantity_on_hand - record.quantity_reserved
        if quantity > free:
            raise ValidationError(
                f"Only {display_quantity(max(free, 0), offering.stock_unit)} of {offering.title} is free here",
                details={"available": max(free, 0)},
            )
        cleaned = ledger.clean_serials(serials)
        if offering.serial_tracked:
            await ledger.sell_serials(session, record, offering, cleaned, quantity=quantity, strict=True,
                                      sold_at=datetime.now(timezone.utc), customer_id=customer_contact_id)
        elif cleaned:
            raise ValidationError("This part does not track serial numbers")
        taken = await ledger.take(session, record, offering, quantity, today=today_ist())
        value = sum(a.value_paise for a in taken)
        movement = await StockService._write(
            session, record, offering, delta=-quantity, movement_type="job_consumption",
            reason=f"Used on job {job_ref}", actor_id=actor_id, value_delta=-value,
            event="inventory.job.consumed", source=("job", job_ref),
            batch_id=taken[0].batch_id if len(taken) == 1 else None,
            extra={"job_ref": str(job_ref), "allocations": [a.as_json() for a in taken]},
        )
        use = await InventoryFieldService._job_use(
            session, record.business_id, record.location_id, job_ref, offering.id, record.variant_id)
        use.quantity_out += quantity
        use.value_out_paise += value
        use.allocations = list(use.allocations or []) + await InventoryFieldService._capture(session, taken)
        return movement

    @staticmethod
    async def consume_record_for_job(
        session: AsyncSession, *, business_id: uuid.UUID, job_ref: uuid.UUID, record_id: uuid.UUID,
        quantity: int, serials: list[str], customer_contact_id: uuid.UUID | None, actor_id: uuid.UUID,
        allowed: list[uuid.UUID] | None,
    ) -> InventoryMovement:
        """Jobs' door: one chosen stock line. The caller holds the locked job and its idempotency."""
        record, offering = await StockService._record_by_id(session, business_id, record_id, allowed)
        return await InventoryFieldService._consume(
            session, record, offering, job_ref=job_ref, quantity=quantity, serials=serials,
            customer_contact_id=customer_contact_id, actor_id=actor_id)

    @staticmethod
    async def job_uses(session: AsyncSession, business_id: uuid.UUID, job_ref: uuid.UUID) -> list[dict[str, Any]]:
        """What a job has taken, given back and still has out, per location and item."""
        from platform_core.models import BusinessLocation

        rows = (await session.execute(select(InventoryJobUse, Offering, BusinessLocation.name).join(
            Offering, Offering.id == InventoryJobUse.offering_id,
        ).join(BusinessLocation, BusinessLocation.id == InventoryJobUse.location_id).where(
            InventoryJobUse.business_id == business_id, InventoryJobUse.job_ref == job_ref,
        ).order_by(Offering.title))).all()
        return [{
            "location_id": str(use.location_id), "location_name": place, "offering_id": str(use.offering_id),
            "variant_id": str(use.variant_id) if use.variant_id else None, "title": offering.title,
            "quantity_out": use.quantity_out, "quantity_back": use.quantity_back,
            "open": max(use.quantity_out - use.quantity_back, 0),
            "open_text": display_quantity(max(use.quantity_out - use.quantity_back, 0), offering.stock_unit),
            "serial_tracked": bool(offering.serial_tracked),
        } for use, offering, place in rows]

    @staticmethod
    async def free_stock(
        session: AsyncSession, business_id: uuid.UUID, location_ids: list[uuid.UUID] | None,
    ) -> list[dict[str, Any]]:
        """Business-owned stock free to use at these locations (None: every location)."""
        from platform_core.models import BusinessLocation

        q = select(InventoryRecord, Offering, BusinessLocation).join(
            Offering, Offering.id == InventoryRecord.offering_id,
        ).join(BusinessLocation, BusinessLocation.id == InventoryRecord.location_id).where(
            InventoryRecord.business_id == business_id, InventoryRecord.owner_customer_id.is_(None),
            InventoryRecord.quantity_on_hand > InventoryRecord.quantity_reserved,
            Offering.deleted_at.is_(None), BusinessLocation.deleted_at.is_(None),
        )
        if location_ids is not None:
            if not location_ids:
                return []
            q = q.where(InventoryRecord.location_id.in_(location_ids))
        rows = (await session.execute(q.order_by(Offering.title, BusinessLocation.name))).all()
        return [{
            "inventory_record_id": str(record.id), "offering_id": str(offering.id),
            "variant_id": str(record.variant_id) if record.variant_id else None, "title": offering.title,
            "location_id": str(location.id), "location_name": location.name,
            "is_van": location.stock_role == "van", "serial_tracked": bool(offering.serial_tracked),
            "available": record.quantity_on_hand - record.quantity_reserved,
            "available_text": display_quantity(record.quantity_on_hand - record.quantity_reserved, offering.stock_unit),
        } for record, offering, location in rows]

    @staticmethod
    async def consume_for_job(
        session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, payload: dict[str, Any],
        allowed: list[uuid.UUID] | None,
    ) -> dict[str, Any]:
        """Inventory's door: lines taken from one stock location (usually a van) against a job
        reference. Same movement as Jobs' door; its own idempotency key."""
        key = _key(payload.get("idempotency_key"))
        saved = await InventoryFieldService._saved(session, business_id, key)
        if saved:
            return saved
        location_id = uuid.UUID(str(payload.get("location_id")))
        job_ref = uuid.UUID(str(payload.get("job_ref")))
        await StockService._location(session, business_id, location_id, allowed)
        used = []
        for raw in list(payload.get("lines") or []):
            offering = await StockService._offering(session, business_id, (raw or {}).get("offering_id"))
            variant_id = await StockService._variant(session, offering, (raw or {}).get("variant_id"))
            quantity = _qty((raw or {}).get("quantity"))
            record = await StockService._record(session, business_id, offering, location_id, variant_id)
            await InventoryFieldService._consume(
                session, record, offering, job_ref=job_ref, quantity=quantity,
                serials=list((raw or {}).get("serials") or []), customer_contact_id=None, actor_id=actor_id)
            used.append({
                "offering_id": str(offering.id), "title": offering.title, "quantity": quantity,
                "on_hand": record.quantity_on_hand,
                "on_hand_text": display_quantity(record.quantity_on_hand, offering.stock_unit),
            })
        if not used:
            raise ValidationError("Say which parts were used")
        body = {"job_ref": str(job_ref), "location_id": str(location_id), "lines": used}
        return await InventoryFieldService._remember(session, business_id, key, "job_consume", job_ref, body)

    @staticmethod
    async def return_unused(
        session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, payload: dict[str, Any],
        allowed: list[uuid.UUID] | None,
    ) -> dict[str, Any]:
        """Put unused parts back on the same location. Cannot exceed what that job took."""
        key = _key(payload.get("idempotency_key"))
        saved = await InventoryFieldService._saved(session, business_id, key)
        if saved:
            return saved
        location_id = uuid.UUID(str(payload.get("location_id")))
        job_ref = uuid.UUID(str(payload.get("job_ref")))
        await StockService._location(session, business_id, location_id, allowed)
        returned = []
        for raw in list(payload.get("lines") or []):
            offering = await StockService._offering(session, business_id, (raw or {}).get("offering_id"))
            if offering.serial_tracked:
                raise ValidationError(f"{offering.title} is tracked by serial number; bring it back through a "
                                      "stock adjustment so each serial is put back by hand")
            variant_id = await StockService._variant(session, offering, (raw or {}).get("variant_id"))
            quantity = _qty((raw or {}).get("quantity"))
            use = await InventoryFieldService._job_use(session, business_id, location_id, job_ref, offering.id, variant_id)
            open_qty = use.quantity_out - use.quantity_back
            if quantity > open_qty:
                raise ValidationError(
                    f"This job only has {display_quantity(max(open_qty, 0), offering.stock_unit)} of "
                    f"{offering.title} still out",
                    details={"open": max(open_qty, 0)},
                )
            open_value = int(use.value_out_paise) - int(use.value_back_paise)
            share = open_value if quantity == open_qty else round(open_value * quantity / open_qty)
            share = min(max(share, 0), open_value)
            record = await StockService._record(session, business_id, offering, location_id, variant_id)
            record.stock_value_paise += share
            await StockService._write(
                session, record, offering, delta=quantity, movement_type="job_return",
                reason=f"Unused parts back from job {job_ref}", actor_id=actor_id, value_delta=share,
                event="inventory.job.returned", source=("job", job_ref), extra={"job_ref": str(job_ref)},
            )
            # Restore batch identity for the slice coming back. Codes were stored at consumption;
            # the original batch row stayed at this location with a lower quantity.
            left = quantity
            landing: list[dict[str, Any]] = []
            kept: list[dict[str, Any]] = []
            for raw_alloc in list(use.allocations or []):
                have = int(raw_alloc.get("quantity") or 0)
                if left <= 0 or have <= 0:
                    kept.append(raw_alloc)
                    continue
                take_n = min(left, have)
                landing.append({**raw_alloc, "quantity": take_n})
                if have > take_n:
                    kept.append({**raw_alloc, "quantity": have - take_n})
                left -= take_n
            await InventoryFieldService._land_batches(session, business_id, actor_id, record, offering, landing)
            use.allocations = kept
            use.quantity_back += quantity
            use.value_back_paise += share
            returned.append({
                "offering_id": str(offering.id), "title": offering.title, "quantity": quantity,
                "on_hand": record.quantity_on_hand,
                "on_hand_text": display_quantity(record.quantity_on_hand, offering.stock_unit),
            })
        if not returned:
            raise ValidationError("Say which unused parts came back")
        body = {"job_ref": str(job_ref), "location_id": str(location_id), "lines": returned}
        return await InventoryFieldService._remember(session, business_id, key, "job_return", job_ref, body)

    # ---------------------------------------------------------------- client-owned stock
    @staticmethod
    async def _client_record(
        session: AsyncSession, business_id: uuid.UUID, offering: Offering, location_id: uuid.UUID,
        variant_id: uuid.UUID | None, customer_id: uuid.UUID,
    ) -> InventoryRecord:
        q = select(InventoryRecord).where(
            InventoryRecord.business_id == business_id, InventoryRecord.offering_id == offering.id,
            InventoryRecord.location_id == location_id, InventoryRecord.owner_customer_id == customer_id,
        )
        if variant_id is None:
            q = q.where(InventoryRecord.variant_id.is_(None))
        else:
            q = q.where(InventoryRecord.variant_id == variant_id)
        record = (await session.execute(q.with_for_update())).scalars().first()
        if record is None:
            record = InventoryRecord(
                business_id=business_id, offering_id=offering.id, variant_id=variant_id,
                location_id=location_id, owner_customer_id=customer_id,
                low_stock_threshold=offering.low_stock_threshold,
            )
            session.add(record)
            await session.flush()
        return await ledger.lock(session, record)

    @staticmethod
    async def _customer(session: AsyncSession, business_id: uuid.UUID, customer_id: uuid.UUID) -> CustomerContact:
        customer = await session.get(CustomerContact, customer_id)
        if customer is None or customer.business_id != business_id or customer.deleted_at is not None:
            raise ResourceNotFound("Customer")
        return customer

    @staticmethod
    async def move_client_stock(
        session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, payload: dict[str, Any],
        allowed: list[uuid.UUID] | None,
    ) -> dict[str, Any]:
        """Inward or outward for one client's goods. Never touches the business-owned balance."""
        key = _key(payload.get("idempotency_key"))
        saved = await InventoryFieldService._saved(session, business_id, key)
        if saved:
            return saved
        direction = str(payload.get("direction") or "")
        if direction not in ("inward", "outward"):
            raise ValidationError("Say whether this is inward or outward")
        location_id = uuid.UUID(str(payload.get("location_id")))
        customer_id = uuid.UUID(str(payload.get("customer_id")))
        await StockService._location(session, business_id, location_id, allowed)
        await InventoryFieldService._customer(session, business_id, customer_id)
        offering = await StockService._offering(session, business_id, payload.get("offering_id"))
        variant_id = await StockService._variant(session, offering, payload.get("variant_id"))
        quantity = _qty(payload.get("quantity"))
        record = await InventoryFieldService._client_record(
            session, business_id, offering, location_id, variant_id, customer_id)
        if direction == "outward":
            free = record.quantity_on_hand - record.quantity_reserved
            if quantity > free:
                raise ValidationError(
                    f"This client has only {display_quantity(max(free, 0), offering.stock_unit)} here",
                    details={"available": max(free, 0)},
                )
            taken = await ledger.take(session, record, offering, quantity, today=today_ist())
            value = -sum(a.value_paise for a in taken)
            delta = -quantity
            movement = "client_outward"
        else:
            value = 0
            delta = quantity
            record.stock_value_paise += 0
            movement = "client_inward"
        await StockService._write(
            session, record, offering, delta=delta, movement_type=movement,
            reason=str(payload.get("note") or f"Client stock {direction}")[:300], actor_id=actor_id,
            value_delta=value, event="inventory.client_stock.moved", source=("customer", customer_id),
            extra={"customer_id": str(customer_id), "direction": direction},
        )
        body = {
            "customer_id": str(customer_id), "location_id": str(location_id),
            "offering_id": str(offering.id), "direction": direction, "quantity": quantity,
            "on_hand": record.quantity_on_hand, "owner": "client",
            "on_hand_text": display_quantity(record.quantity_on_hand, offering.stock_unit),
        }
        return await InventoryFieldService._remember(session, business_id, key, f"client_{direction}", customer_id, body)

    @staticmethod
    async def list_client_stock(
        session: AsyncSession, business_id: uuid.UUID, allowed: list[uuid.UUID] | None,
        *, customer_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        q = (select(InventoryRecord, Offering).join(Offering, Offering.id == InventoryRecord.offering_id)
             .where(InventoryRecord.business_id == business_id, InventoryRecord.owner_customer_id.is_not(None)))
        if customer_id is not None:
            q = q.where(InventoryRecord.owner_customer_id == customer_id)
        if allowed is not None:
            q = q.where(InventoryRecord.location_id.in_(allowed))
        out = []
        for record, offering in (await session.execute(q.order_by(Offering.title))).all():
            available = max(record.quantity_on_hand - record.quantity_reserved, 0)
            out.append({
                "id": str(record.id), "customer_id": str(record.owner_customer_id),
                "location_id": str(record.location_id), "offering_id": str(offering.id),
                "title": offering.title, "on_hand": record.quantity_on_hand, "available": available,
                "owner": "client",
                "on_hand_text": display_quantity(record.quantity_on_hand, offering.stock_unit),
            })
        return out

    # ---------------------------------------------------------------- customer assets
    @staticmethod
    def _traits(raw: Any) -> dict[str, Any]:
        if raw in (None, ""):
            return {}
        if not isinstance(raw, dict):
            raise ValidationError("Details on an asset are a set of named values")
        if len(raw) > 40:
            raise ValidationError("Too many details on this asset")
        clean: dict[str, Any] = {}
        for key, value in raw.items():
            name = str(key).strip()
            if not name or len(name) > 40:
                raise ValidationError("Each detail needs a short name")
            if isinstance(value, bool):
                clean[name] = value
            elif isinstance(value, (int, float)):
                clean[name] = value
            elif isinstance(value, str) and len(value.strip()) <= 200:
                clean[name] = value.strip()
            else:
                raise ValidationError(f"{name} should be text, a number, or yes/no")
        return clean

    @staticmethod
    def serialize_asset(asset: CustomerAsset) -> dict[str, Any]:
        return {
            "id": str(asset.id), "customer_id": str(asset.customer_id), "asset_kind": asset.asset_kind,
            "label": asset.label, "identifier": asset.identifier, "traits": asset.traits or {},
            "status": asset.status, "notes": asset.notes, "version": asset.version,
        }

    @staticmethod
    async def record_asset(
        session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, payload: dict[str, Any],
    ) -> dict[str, Any]:
        raw_key = str(payload.get("idempotency_key") or "").strip()
        if raw_key:
            key = _key(raw_key)
            found = (await session.execute(select(CustomerAsset).where(
                CustomerAsset.business_id == business_id, CustomerAsset.idempotency_key == key,
                CustomerAsset.deleted_at.is_(None),
            ))).scalars().first()
            if found:
                return InventoryFieldService.serialize_asset(found)
        else:
            key = None
        kind = str(payload.get("asset_kind") or "").strip()
        if kind not in ASSET_KINDS:
            raise ValidationError("Choose what this asset is", details={"kinds": sorted(ASSET_KINDS)})
        label = str(payload.get("label") or "").strip()
        if not 1 <= len(label) <= 160:
            raise ValidationError("Give the asset a name")
        customer_id = uuid.UUID(str(payload.get("customer_id")))
        await InventoryFieldService._customer(session, business_id, customer_id)
        identifier = str(payload.get("identifier") or "").strip()[:80] or None
        notes = str(payload.get("notes") or "").strip()[:500] or None
        asset = CustomerAsset(
            business_id=business_id, customer_id=customer_id, asset_kind=kind, label=label,
            identifier=identifier, traits=InventoryFieldService._traits(payload.get("traits")),
            notes=notes, idempotency_key=key,
        )
        session.add(asset)
        await session.flush()
        body = InventoryFieldService.serialize_asset(asset)
        await OutboxService.publish(
            session, event_type="customer_asset.recorded", business_id=business_id,
            payload={"business_id": str(business_id), "customer_id": str(customer_id),
                     "asset_id": str(asset.id), "asset_kind": kind, "actor_id": str(actor_id), "after": body},
        )
        return body

    @staticmethod
    async def list_assets(
        session: AsyncSession, business_id: uuid.UUID, *, customer_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        q = select(CustomerAsset).where(
            CustomerAsset.business_id == business_id, CustomerAsset.deleted_at.is_(None),
            CustomerAsset.status == "active",
        )
        if customer_id is not None:
            q = q.where(CustomerAsset.customer_id == customer_id)
        rows = (await session.execute(q.order_by(CustomerAsset.label))).scalars()
        return [InventoryFieldService.serialize_asset(row) for row in rows]
