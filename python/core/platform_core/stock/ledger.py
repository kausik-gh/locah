"""The detail behind one stock number: its value, its batches, its serials.

Callers (a bill, an order, a receipt, a count) still change
`inventory_records.quantity_on_hand` and write the movement. They call these
helpers *with the record locked* so that, in the same transaction:

* the value on hand moves at weighted-average cost (§15.1 "Valuation"):
  goods leave at the current average, goods arrive at what they cost, and
  goods coming back return at the value they left with;
* batches are picked first-expiry-first-out (§15.1 "Batches and expiry"):
  unexpired batches by expiry, then stock recorded without a batch, and only
  then expired stock — which is reported, because selling it is the owner's
  problem to see, not LOCAH's to hide;
* serial numbers are captured at sale and returned on a return (§15.1
  "Serials and warranty").

Every allocation is written onto the bill or order line, so a cancellation or a
return puts stock back into the same batches at the same value.
"""

from __future__ import annotations

import calendar
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ValidationError
from platform_core.models import InventoryBatch, InventoryRecord, InventorySerial, Offering

IST = ZoneInfo("Asia/Kolkata")


def add_months(day: date, months: int) -> date:
    year, month = divmod(day.year * 12 + day.month - 1 + months, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def clean_serials(raw: Any) -> list[str]:
    """Serials as typed or scanned: trimmed, upper-cased for matching, de-duplicated."""
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [part for chunk in raw.splitlines() for part in chunk.split(",")]
    out: list[str] = []
    for item in raw:
        value = str(item).strip().upper()
        if not value:
            continue
        if not 3 <= len(value) <= 64:
            raise ValidationError(f"Serial number {value[:20]} should be 3 to 64 characters")
        if value in out:
            raise ValidationError(f"Serial number {value} is entered twice")
        out.append(value)
    return out


@dataclass
class Allocation:
    batch_id: uuid.UUID | None
    quantity: int
    value_paise: int
    expired: bool = False

    def as_json(self) -> dict[str, Any]:
        return {"batch_id": str(self.batch_id) if self.batch_id else None, "quantity": self.quantity,
                "value_paise": self.value_paise, **({"expired": True} if self.expired else {})}

    @staticmethod
    def from_json(raw: dict[str, Any]) -> Allocation:
        batch = raw.get("batch_id")
        return Allocation(uuid.UUID(str(batch)) if batch else None, int(raw.get("quantity") or 0),
                          int(raw.get("value_paise") or 0), bool(raw.get("expired")))


async def lock(session: AsyncSession, record: InventoryRecord) -> InventoryRecord:
    """Re-read the record under a row lock so concurrent sales cannot lose an update."""
    await session.refresh(record, with_for_update=True)
    return record


def average_value(record: InventoryRecord, quantity: int) -> int:
    """Value of `quantity` at the record's current weighted average."""
    if record.quantity_on_hand <= 0 or record.stock_value_paise <= 0 or quantity <= 0:
        return 0
    value = int(record.stock_value_paise)
    return min(value, round(value * quantity / int(record.quantity_on_hand)))


async def active_batches(session: AsyncSession, record_id: uuid.UUID, *, for_update: bool = False
                         ) -> list[InventoryBatch]:
    q = select(InventoryBatch).where(InventoryBatch.inventory_record_id == record_id,
                                     InventoryBatch.status == "active", InventoryBatch.quantity_on_hand > 0)
    if for_update:
        q = q.with_for_update()
    rows = list((await session.execute(q)).scalars())
    rows.sort(key=lambda b: (b.expires_on is None, b.expires_on or date.max, b.received_on, b.created_at))
    return rows


def _spread_value(total: int, allocations: list[Allocation]) -> None:
    qty = sum(a.quantity for a in allocations)
    left = total
    for i, a in enumerate(allocations):
        share = left if i == len(allocations) - 1 else (round(total * a.quantity / qty) if qty else 0)
        share = min(share, left)
        a.value_paise = share
        left -= share


async def take(session: AsyncSession, record: InventoryRecord, offering: Offering, quantity: int,
               *, today: date) -> list[Allocation]:
    """Take `quantity` out of a locked record, before its quantity is reduced.

    Returns where it came from (batch or none) and at what value; lowers the
    record's value. Never refuses: whether a sale may go short is the caller's
    rule (the counter never refuses a sale that already happened)."""
    if quantity <= 0:
        return []
    value = average_value(record, min(quantity, max(record.quantity_on_hand, 0)))
    allocations: list[Allocation] = []
    remaining = quantity
    if offering.batch_tracked:
        batches = await active_batches(session, record.id, for_update=True)
        in_batches = sum(b.quantity_on_hand for b in batches)
        unbatched = max(record.quantity_on_hand - in_batches, 0)
        usable = [b for b in batches if b.expires_on is None or b.expires_on >= today]
        expired = [b for b in batches if b.expires_on is not None and b.expires_on < today]
        for batch in usable:
            if remaining <= 0:
                break
            q = min(remaining, batch.quantity_on_hand)
            batch.quantity_on_hand -= q
            batch.status = "depleted" if batch.quantity_on_hand == 0 else batch.status
            batch.version += 1
            allocations.append(Allocation(batch.id, q, 0))
            remaining -= q
        if remaining > 0 and unbatched > 0:
            q = min(remaining, unbatched)
            allocations.append(Allocation(None, q, 0))
            remaining -= q
        for batch in expired:
            if remaining <= 0:
                break
            q = min(remaining, batch.quantity_on_hand)
            batch.quantity_on_hand -= q
            batch.status = "depleted" if batch.quantity_on_hand == 0 else batch.status
            batch.version += 1
            allocations.append(Allocation(batch.id, q, 0, expired=True))
            remaining -= q
    if remaining > 0:
        allocations.append(Allocation(None, remaining, 0))
    _spread_value(value, allocations)
    record.stock_value_paise = max(record.stock_value_paise - value, 0)
    await session.flush()
    return allocations


async def put_back(session: AsyncSession, record: InventoryRecord, offering: Offering, quantity: int,
                   allocations: list[Allocation] | None) -> list[Allocation]:
    """Return `quantity` into a locked record: into the batches it left from, at
    the value it left with; anything beyond that at the current average."""
    if quantity <= 0:
        return []
    out: list[Allocation] = []
    remaining = quantity
    for a in allocations or []:
        if remaining <= 0 or a.quantity <= 0:
            break
        q = min(remaining, a.quantity)
        value = round(a.value_paise * q / a.quantity)
        if a.batch_id is not None and offering.batch_tracked:
            batch = await session.get(InventoryBatch, a.batch_id, with_for_update=True)
            if batch is not None and batch.inventory_record_id == record.id:
                room = batch.quantity_received - batch.quantity_on_hand
                back = min(q, max(room, 0))
                if back > 0:
                    batch.quantity_on_hand += back
                    if batch.status == "depleted":
                        batch.status = "active"
                    batch.version += 1
        out.append(Allocation(a.batch_id, q, value, a.expired))
        remaining -= q
    if remaining > 0:
        out.append(Allocation(None, remaining, average_value(record, remaining)))
    record.stock_value_paise += sum(a.value_paise for a in out)
    await session.flush()
    return out


# ---------------------------------------------------------------- serials
async def sell_serials(
    session: AsyncSession, record: InventoryRecord, offering: Offering, serials: list[str], *,
    quantity: int, strict: bool, sold_at: datetime, document_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None, customer_id: uuid.UUID | None = None,
) -> list[str]:
    """Mark the serials on a sale as sold. `strict` (a Workspace bill, an order)
    refuses a missing or unknown serial; the counter records the sale and
    returns the problems for the team to fix, because the sale happened."""
    problems: list[str] = []
    if not offering.serial_tracked:
        return problems
    if len(serials) != quantity:
        msg = f"{offering.title}: {quantity} sold but {len(serials)} serial number(s) given"
        if strict:
            raise ValidationError(msg, details={"offering_id": str(offering.id), "needs": "serials"})
        problems.append(msg)
    for serial in serials:
        row = (await session.execute(select(InventorySerial).where(
            InventorySerial.business_id == record.business_id, InventorySerial.offering_id == offering.id,
            InventorySerial.serial == serial).with_for_update())).scalars().first()
        if row is None or row.status != "in_stock":
            msg = (f"{offering.title}: serial {serial} is not in stock" if row is None or row.status == "sold"
                   else f"{offering.title}: serial {serial} was written off")
            if strict:
                raise ValidationError(msg, details={"serial": serial})
            problems.append(msg)
            continue
        if row.location_id != record.location_id:
            msg = f"{offering.title}: serial {serial} is recorded at another location"
            if strict:
                raise ValidationError(msg, details={"serial": serial})
            problems.append(msg)
        row.status, row.sold_at = "sold", sold_at
        row.sold_document_id, row.sold_order_id, row.customer_contact_id = document_id, order_id, customer_id
        row.warranty_until = (add_months(sold_at.astimezone(IST).date(), offering.warranty_months)
                              if offering.warranty_months else None)
        row.version += 1
    await session.flush()
    return problems


async def return_serials(session: AsyncSession, record: InventoryRecord, offering: Offering,
                         serials: list[str]) -> None:
    if not offering.serial_tracked:
        return
    for serial in serials:
        row = (await session.execute(select(InventorySerial).where(
            InventorySerial.business_id == record.business_id, InventorySerial.offering_id == offering.id,
            InventorySerial.serial == serial).with_for_update())).scalars().first()
        if row is None or row.status != "sold":
            continue
        row.status, row.location_id, row.inventory_record_id = "in_stock", record.location_id, record.id
        row.sold_at = row.sold_document_id = row.sold_order_id = row.customer_contact_id = None
        row.warranty_until = None
        row.version += 1
    await session.flush()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
