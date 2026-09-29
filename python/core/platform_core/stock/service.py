"""Stock depth operations (Capability Universe §15.1) — P1-10A.

Receive (with batch, expiry, serials, cost, buying unit), wastage with a
reason, cutting runs against owner-entered yields, stock counts whose
variances need approval, reorder min/max, expiry and valuation. Every change
is an `inventory_movements` row against the one `inventory_records` row, made
under that row's lock.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, OutsideLocationScope, ResourceNotFound, ValidationError
from platform_core.models import (
    Business,
    BusinessLocation,
    BusinessTrait,
    CustomerContact,
    InventoryBatch,
    InventoryConversion,
    InventoryCount,
    InventoryCountLine,
    InventoryMovement,
    InventoryRecord,
    InventorySerial,
    InventoryYield,
    InvoicingDocument,
    Offering,
    OfferingVariant,
)
from platform_core.resolvers.inventory_resolver import InventoryResolver
from platform_core.services.audit import AuditService
from platform_core.services.outbox import OutboxService
from platform_core.stock import ledger, profile

IST = ZoneInfo("Asia/Kolkata")
UNIT_WORDS = {"g": ("kg", 1000), "ml": ("L", 1000), "piece": ("pcs", 1)}


def today_ist() -> date:
    return datetime.now(IST).date()


def display_quantity(quantity: int, stock_unit: str) -> str:
    """Grams as kg, millilitres as litres, pieces as pieces — how the counter talks."""
    word, per = UNIT_WORDS.get(stock_unit, ("", 1))
    if per == 1:
        return f"{quantity} {word}".strip()
    value = quantity / per
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return f"{text} {word}"


def _uuid(raw: Any, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(raw))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Choose a {field}", details={"field": field}) from exc


def _int(raw: Any, field: str, *, minimum: int = 0) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Enter a whole number for {field}", details={"field": field}) from exc
    if value < minimum:
        raise ValidationError(f"{field.capitalize()} must be at least {minimum}", details={"field": field})
    return value


class StockService:
    # ------------------------------------------------------------ shared lookups
    @staticmethod
    def _scope_check(location_id: uuid.UUID, allowed: list[uuid.UUID] | None) -> None:
        if allowed is not None and location_id not in allowed:
            raise OutsideLocationScope()

    @staticmethod
    async def _location(session: AsyncSession, business_id: uuid.UUID, location_id: uuid.UUID,
                        allowed: list[uuid.UUID] | None) -> BusinessLocation:
        StockService._scope_check(location_id, allowed)
        location = await session.get(BusinessLocation, location_id)
        if location is None or location.business_id != business_id or location.deleted_at is not None:
            raise ResourceNotFound("Location")
        return location

    @staticmethod
    async def _offering(session: AsyncSession, business_id: uuid.UUID, offering_id: Any,
                        *, tracked: bool = True) -> Offering:
        offering = await session.get(Offering, _uuid(offering_id, "item"))
        if offering is None or offering.business_id != business_id or offering.deleted_at is not None:
            raise ResourceNotFound("Item")
        if tracked and not offering.track_inventory:
            raise ValidationError(f"Stock is not tracked for {offering.title} — turn on stock tracking first",
                                  details={"offering_id": str(offering.id), "needs": "track_inventory"})
        return offering

    @staticmethod
    async def _variant(session: AsyncSession, offering: Offering, raw: Any) -> uuid.UUID | None:
        has_variants = bool(offering.variant_options)
        if raw in (None, ""):
            if has_variants:
                raise ValidationError(f"Choose which {offering.title} (size, colour …)",
                                      details={"needs": "variant_id"})
            return None
        variant = await session.get(OfferingVariant, _uuid(raw, "variant"))
        if variant is None or variant.offering_id != offering.id or variant.deleted_at is not None:
            raise ValidationError("That size or colour is not part of this item")
        return uuid.UUID(str(variant.id))

    @staticmethod
    async def _record(session: AsyncSession, business_id: uuid.UUID, offering: Offering,
                      location_id: uuid.UUID, variant_id: uuid.UUID | None) -> InventoryRecord:
        from platform_core.services.inventory import InventoryService

        record = await InventoryService._get_or_create_record(
            session, business_id=business_id, offering=offering, location_id=location_id, variant_id=variant_id)
        return await ledger.lock(session, record)

    @staticmethod
    async def _record_by_id(session: AsyncSession, business_id: uuid.UUID, record_id: Any,
                            allowed: list[uuid.UUID] | None) -> tuple[InventoryRecord, Offering]:
        record = await session.get(InventoryRecord, _uuid(record_id, "stock line"))
        if record is None or record.business_id != business_id:
            raise ResourceNotFound("Stock line")
        StockService._scope_check(record.location_id, allowed)
        offering = await session.get(Offering, record.offering_id)
        assert offering is not None
        return await ledger.lock(session, record), offering

    @staticmethod
    async def _write(
        session: AsyncSession, record: InventoryRecord, offering: Offering, *, delta: int, movement_type: str,
        reason: str, actor_id: uuid.UUID, value_delta: int, event: str, reason_code: str | None = None,
        batch_id: uuid.UUID | None = None, source: tuple[str, uuid.UUID] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> InventoryMovement:
        before = InventoryResolver.serialize_record(record, offering=offering)
        record.quantity_on_hand += delta
        if record.quantity_on_hand < 0:
            raise ValidationError(f"Only {display_quantity(record.quantity_on_hand - delta, offering.stock_unit)} "
                                  f"of {offering.title} on record here")
        record.version += 1
        record.updated_at = datetime.now(timezone.utc)
        movement = InventoryMovement(
            business_id=record.business_id, offering_id=offering.id, variant_id=record.variant_id,
            location_id=record.location_id, inventory_record_id=record.id, movement_type=movement_type,
            quantity_delta=delta, quantity_after=record.quantity_on_hand, reason=reason[:300],
            actor_identity_id=actor_id, reason_code=reason_code, batch_id=batch_id, value_delta_paise=value_delta,
            source_type=source[0] if source else None, source_id=source[1] if source else None,
        )
        session.add(movement)
        await session.flush()
        after = InventoryResolver.serialize_record(record, offering=offering)
        payload = {"business_id": str(record.business_id), "offering_id": str(offering.id),
                   "variant_id": str(record.variant_id) if record.variant_id else None,
                   "location_id": str(record.location_id), "inventory_record_id": str(record.id),
                   "movement_type": movement_type, "quantity_delta": delta, "delta": delta,
                   "new_level": record.quantity_on_hand, "reason": reason[:300], "after": after, **(extra or {})}
        await OutboxService.publish(session, event_type="inventory.stock.updated", payload=payload,
                                    business_id=record.business_id)
        status = InventoryResolver.stock_status(record, offering=offering)
        if status == "low_stock" and delta < 0:
            await OutboxService.publish(session, event_type="inventory.stock.low", business_id=record.business_id,
                                        payload={**payload, "current_level": record.quantity_on_hand,
                                                 "threshold": record.low_stock_threshold})
        elif status == "out_of_stock" and delta < 0:
            await OutboxService.publish(session, event_type="inventory.stock.zero", business_id=record.business_id,
                                        payload=payload)
        elif delta > 0 and before["stock_status"] != "available" and status == "available":
            await OutboxService.publish(session, event_type="inventory.stock.replenished",
                                        business_id=record.business_id,
                                        payload={**payload, "added_quantity": delta})
        await OutboxService.publish(session, event_type=event, payload=payload, business_id=record.business_id)
        await AuditService.record(session, event_type=event, actor_identity_id=actor_id, actor_context="business",
                                  business_id=record.business_id, resource_type="inventory_record",
                                  resource_id=record.id, action=movement_type, before_state=before,
                                  after_state=after)
        return movement

    # ------------------------------------------------------------ profile
    @staticmethod
    async def configured(session: AsyncSession, business_id: uuid.UUID) -> dict[str, int]:
        live = (Offering.business_id == business_id, Offering.deleted_at.is_(None))
        row = (await session.execute(select(
            func.count().filter(Offering.stock_unit != "piece"),
            func.count().filter(Offering.batch_tracked.is_(True)),
            func.count().filter(Offering.serial_tracked.is_(True)),
            func.count().filter(func.jsonb_array_length(Offering.variant_options) > 0),
            func.count().filter(Offering.track_inventory.is_(True)),
        ).where(*live))).one()
        yields = (await session.execute(select(func.count()).select_from(InventoryYield).where(
            InventoryYield.business_id == business_id))).scalar() or 0
        return {"weighed": int(row[0]), "batch_tracked": int(row[1]), "serial_tracked": int(row[2]),
                "with_variants": int(row[3]), "tracked": int(row[4]), "yields": int(yields)}

    @staticmethod
    async def profile(session: AsyncSession, business_id: uuid.UUID) -> dict[str, Any]:
        from platform_core.catalog.recommendation import family_key_for
        from platform_core.catalog.taxonomy import SUBCATEGORIES

        business = await session.get(Business, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        traits = [t for t in (await session.execute(select(BusinessTrait.trait_key).where(
            BusinessTrait.business_id == business_id, BusinessTrait.enabled.is_(True)))).scalars()]
        family = None
        if business.subcategory_key and business.subcategory_key in SUBCATEGORIES:
            family = family_key_for(business.subcategory_key, SUBCATEGORIES[business.subcategory_key][1].playbook)
        hints = profile.family_hints(family)
        configured = await StockService.configured(session, business_id)
        active = profile.lenses(traits, hints, configured)
        return {
            "lenses": [{"key": k, "title": profile.LENSES[k].title, "primary_action": profile.LENSES[k].primary_action,
                        "empty": profile.LENSES[k].empty} for k in active],
            "primary": active[0],
            "yield_offered": profile.yield_offered(traits, hints, configured),
            "wastage_reasons": [{"key": k, "label": profile.WASTAGE_REASONS[k]}
                                for k in profile.wastage_reasons(active)],
            "configured": configured,
            "because": {"traits": sorted(traits), "playbook_hints": sorted(hints), "family": family},
        }

    # ------------------------------------------------------------ reading
    @staticmethod
    async def overview(
        session: AsyncSession, business_id: uuid.UUID, *, allowed: list[uuid.UUID] | None,
        location_id: uuid.UUID | None = None, q: str | None = None, status: str | None = None,
        can_see_cost: bool = False, limit: int = 200,
    ) -> dict[str, Any]:
        today = today_ist()
        query = (select(InventoryRecord, Offering, OfferingVariant)
                 .join(Offering, Offering.id == InventoryRecord.offering_id)
                 .outerjoin(OfferingVariant, OfferingVariant.id == InventoryRecord.variant_id)
                 .where(InventoryRecord.business_id == business_id, Offering.deleted_at.is_(None)))
        if location_id is not None:
            query = query.where(InventoryRecord.location_id == location_id)
        if allowed is not None:
            query = query.where(InventoryRecord.location_id.in_(allowed))
        if q:
            pattern = f"%{q.strip()}%"
            query = query.where(Offering.title.ilike(pattern) | Offering.sku.ilike(pattern)
                                | Offering.barcode.ilike(pattern) | OfferingVariant.name.ilike(pattern))
        rows = (await session.execute(query.order_by(Offering.title, OfferingVariant.sort_order)
                                      .limit(min(max(limit, 1), 500)))).all()
        ids = [r[0].id for r in rows]
        batch_stats: dict[uuid.UUID, dict[str, Any]] = {}
        serial_counts: dict[uuid.UUID, int] = {}
        if ids:
            for rec_id, next_exp, soon_qty, expired_qty, n in (await session.execute(select(
                InventoryBatch.inventory_record_id,
                func.min(InventoryBatch.expires_on).filter(InventoryBatch.expires_on >= today),
                func.coalesce(func.sum(InventoryBatch.quantity_on_hand).filter(
                    InventoryBatch.expires_on >= today, InventoryBatch.expires_on <= today + timedelta(days=30)), 0),
                func.coalesce(func.sum(InventoryBatch.quantity_on_hand).filter(InventoryBatch.expires_on < today), 0),
                func.count(),
            ).where(InventoryBatch.inventory_record_id.in_(ids), InventoryBatch.status == "active",
                    InventoryBatch.quantity_on_hand > 0).group_by(InventoryBatch.inventory_record_id))).all():
                batch_stats[rec_id] = {"next_expiry": next_exp.isoformat() if next_exp else None,
                                       "expiring_30d": int(soon_qty), "expired": int(expired_qty), "batches": int(n)}
            for rec_id, n in (await session.execute(select(InventorySerial.inventory_record_id, func.count()).where(
                    InventorySerial.inventory_record_id.in_(ids), InventorySerial.status == "in_stock")
                    .group_by(InventorySerial.inventory_record_id))).all():
                serial_counts[rec_id] = int(n)
        items = []
        totals = {"items": 0, "low": 0, "out": 0, "expiring_30d": 0, "expired": 0, "value_paise": 0, "not_valued": 0}
        for record, offering, variant in rows:
            base = InventoryResolver.serialize_record(record, offering=offering)
            if status and base["stock_status"] != status:
                continue
            available = base["quantity_available"]
            suggest = None
            if record.reorder_max is not None and record.low_stock_threshold is not None \
                    and available <= record.low_stock_threshold:
                suggest = max(record.reorder_max - available, 0)
            b = batch_stats.get(record.id, {})
            item = {
                **base,
                "title": offering.title, "sku": offering.sku, "barcode": offering.barcode,
                "kind": offering.offering_type, "stock_unit": offering.stock_unit,
                "variant": variant.name if variant else None,
                "variant_attributes": variant.attributes if variant else None,
                "category_id": str(offering.category_id) if offering.category_id else None,
                "on_hand_text": display_quantity(record.quantity_on_hand, offering.stock_unit),
                "available_text": display_quantity(available, offering.stock_unit),
                "reorder_min": record.low_stock_threshold, "reorder_max": record.reorder_max,
                "reorder_suggest": suggest,
                "reorder_suggest_text": display_quantity(suggest, offering.stock_unit) if suggest else None,
                "buy_units": offering.buy_units,
                "batch_tracked": offering.batch_tracked, "serial_tracked": offering.serial_tracked,
                "warranty_months": offering.warranty_months,
                "batches": b.get("batches", 0), "next_expiry": b.get("next_expiry"),
                "expiring_30d": b.get("expiring_30d", 0), "expired": b.get("expired", 0),
                "serials_in_stock": serial_counts.get(record.id, 0),
                "last_counted_at": record.last_counted_at.isoformat() if record.last_counted_at else None,
            }
            if can_see_cost:
                item["value_paise"] = record.stock_value_paise
                item["average_cost_paise"] = (round(record.stock_value_paise / record.quantity_on_hand)
                                              if record.quantity_on_hand > 0 else None)
                totals["value_paise"] += record.stock_value_paise
                if record.quantity_on_hand > 0 and record.stock_value_paise == 0:
                    totals["not_valued"] += 1
            items.append(item)
            totals["items"] += 1
            totals["low"] += base["stock_status"] == "low_stock"
            totals["out"] += base["stock_status"] == "out_of_stock"
            totals["expiring_30d"] += 1 if b.get("expiring_30d") else 0
            totals["expired"] += 1 if b.get("expired") else 0
        if not can_see_cost:
            totals.pop("value_paise")
            totals.pop("not_valued")
        return {"items": items, "totals": totals}

    @staticmethod
    async def expiring(session: AsyncSession, business_id: uuid.UUID, *, allowed: list[uuid.UUID] | None,
                       days: int = 30, location_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
        today = today_ist()
        query = (select(InventoryBatch, Offering).join(Offering, Offering.id == InventoryBatch.offering_id)
                 .where(InventoryBatch.business_id == business_id, InventoryBatch.status == "active",
                        InventoryBatch.quantity_on_hand > 0, InventoryBatch.expires_on.is_not(None),
                        InventoryBatch.expires_on <= today + timedelta(days=max(0, min(days, 365)))))
        if location_id is not None:
            query = query.where(InventoryBatch.location_id == location_id)
        if allowed is not None:
            query = query.where(InventoryBatch.location_id.in_(allowed))
        out = []
        for batch, offering in (await session.execute(query.order_by(InventoryBatch.expires_on))).all():
            left = (batch.expires_on - today).days
            out.append({**StockService.serialize_batch(batch, offering), "days_left": left,
                        "state": "expired" if left < 0 else "today" if left == 0 else "soon"})
        return out

    @staticmethod
    def serialize_batch(batch: InventoryBatch, offering: Offering) -> dict[str, Any]:
        return {"id": str(batch.id), "inventory_record_id": str(batch.inventory_record_id),
                "offering_id": str(batch.offering_id), "title": offering.title,
                "location_id": str(batch.location_id), "batch_code": batch.batch_code,
                "expires_on": batch.expires_on.isoformat() if batch.expires_on else None,
                "received_on": batch.received_on.isoformat(), "quantity_on_hand": batch.quantity_on_hand,
                "quantity_text": display_quantity(batch.quantity_on_hand, offering.stock_unit),
                "quantity_received": batch.quantity_received, "status": batch.status}

    @staticmethod
    async def record_detail(session: AsyncSession, business_id: uuid.UUID, record_id: Any,
                            allowed: list[uuid.UUID] | None, *, can_see_cost: bool) -> dict[str, Any]:
        record = await session.get(InventoryRecord, _uuid(record_id, "stock line"))
        if record is None or record.business_id != business_id:
            raise ResourceNotFound("Stock line")
        StockService._scope_check(record.location_id, allowed)
        offering = await session.get(Offering, record.offering_id)
        assert offering is not None
        batches = [StockService.serialize_batch(b, offering) for b in (await session.execute(
            select(InventoryBatch).where(InventoryBatch.inventory_record_id == record.id)
            .order_by(InventoryBatch.status, InventoryBatch.expires_on.nulls_last(), InventoryBatch.received_on)
            .limit(100))).scalars()]
        serials = [{"serial": s.serial, "status": s.status, "received_at": s.received_at.isoformat()}
                   for s in (await session.execute(select(InventorySerial).where(
                       InventorySerial.inventory_record_id == record.id, InventorySerial.status == "in_stock")
                       .order_by(InventorySerial.received_at).limit(200))).scalars()]
        moves = []
        for m in (await session.execute(select(InventoryMovement).where(
                InventoryMovement.inventory_record_id == record.id)
                .order_by(InventoryMovement.created_at.desc()).limit(50))).scalars():
            row = {"type": m.movement_type, "delta": m.quantity_delta, "after": m.quantity_after,
                   "delta_text": display_quantity(abs(m.quantity_delta), offering.stock_unit),
                   "reason": m.reason, "reason_code": m.reason_code, "at": m.created_at.isoformat()}
            if can_see_cost:
                row["value_delta_paise"] = m.value_delta_paise
            moves.append(row)
        base = InventoryResolver.serialize_record(record, offering=offering)
        variant = await session.get(OfferingVariant, record.variant_id) if record.variant_id else None
        detail = {**base, "title": offering.title, "stock_unit": offering.stock_unit,
                  "variant": variant.name if variant else None,
                  "on_hand_text": display_quantity(record.quantity_on_hand, offering.stock_unit),
                  "available_text": display_quantity(base["quantity_available"], offering.stock_unit),
                  "warranty_months": offering.warranty_months, "buy_units": offering.buy_units,
                  "batch_tracked": offering.batch_tracked, "serial_tracked": offering.serial_tracked,
                  "reorder_min": record.low_stock_threshold, "reorder_max": record.reorder_max,
                  "batches": batches, "serials": serials, "movements": moves}
        if can_see_cost:
            detail["value_paise"] = record.stock_value_paise
        return detail

    @staticmethod
    async def serial_lookup(session: AsyncSession, business_id: uuid.UUID, serial: str, *,
                            can_see_customer: bool) -> dict[str, Any]:
        value = (serial or "").strip().upper()
        if len(value) < 3:
            raise ValidationError("Enter the serial or IMEI number")
        row = (await session.execute(select(InventorySerial, Offering)
               .join(Offering, Offering.id == InventorySerial.offering_id)
               .where(InventorySerial.business_id == business_id, InventorySerial.serial == value))).first()
        if row is None:
            raise ResourceNotFound("Serial number")
        s, offering = row
        today = today_ist()
        out: dict[str, Any] = {
            "serial": s.serial, "title": offering.title, "status": s.status,
            "sold_at": s.sold_at.isoformat() if s.sold_at else None,
            "warranty_until": s.warranty_until.isoformat() if s.warranty_until else None,
            "in_warranty": bool(s.warranty_until and s.warranty_until >= today),
            "warranty_months": offering.warranty_months,
        }
        if s.sold_document_id:
            doc = await session.get(InvoicingDocument, s.sold_document_id)
            out["bill_number"] = doc.number if doc else None
        if can_see_customer and s.customer_contact_id:
            contact = await session.get(CustomerContact, s.customer_contact_id)
            out["customer"] = {"name": contact.display_name, "phone": contact.phone} if contact else None
        return out

    # ------------------------------------------------------------ item setup
    @staticmethod
    async def items(session: AsyncSession, business_id: uuid.UUID) -> list[dict[str, Any]]:
        """Goods this business could keep stock of — for pickers, never raw ids."""
        goods = ("product", "weighed_product", "menu_item", "digital_product", "package")
        offerings = list((await session.execute(select(Offering).where(
            Offering.business_id == business_id, Offering.deleted_at.is_(None), Offering.status != "archived",
            Offering.offering_type.in_(goods) | Offering.track_inventory.is_(True),
        ).order_by(Offering.title).limit(1000))).scalars())
        variants: dict[uuid.UUID, list[dict[str, Any]]] = {}
        for v in (await session.execute(select(OfferingVariant).where(
                OfferingVariant.offering_id.in_([o.id for o in offerings]), OfferingVariant.deleted_at.is_(None))
                .order_by(OfferingVariant.sort_order))).scalars():
            variants.setdefault(v.offering_id, []).append({"id": str(v.id), "name": v.name,
                                                           "attributes": v.attributes or {}})
        return [{"id": str(o.id), "title": o.title, "kind": o.offering_type, "stock_unit": o.stock_unit,
                 "track_inventory": o.track_inventory, "batch_tracked": o.batch_tracked,
                 "serial_tracked": o.serial_tracked, "warranty_months": o.warranty_months,
                 "buy_units": o.buy_units or [], "variant_options": o.variant_options or [],
                 "variants": variants.get(o.id, []),
                 "category_id": str(o.category_id) if o.category_id else None} for o in offerings]

    @staticmethod
    async def configure_item(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
                             offering_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
        offering = await StockService._offering(session, business_id, offering_id, tracked=False)
        if "track_inventory" in payload:
            offering.track_inventory = bool(payload["track_inventory"])
        if "batch_tracked" in payload:
            offering.batch_tracked = bool(payload["batch_tracked"])
        if "serial_tracked" in payload:
            want = bool(payload["serial_tracked"])
            if want and offering.stock_unit != "piece":
                raise ValidationError("Serial numbers are for items counted in pieces")
            offering.serial_tracked = want
        if "warranty_months" in payload:
            months = payload["warranty_months"]
            offering.warranty_months = None if months in (None, "") else _int(months, "warranty months")
            if offering.warranty_months is not None and offering.warranty_months > 240:
                raise ValidationError("Warranty up to 240 months")
        if "buy_units" in payload:
            units: list[dict[str, Any]] = []
            for raw in payload["buy_units"] or []:
                label = str((raw or {}).get("label") or "").strip()[:30]
                qty = _int((raw or {}).get("quantity"), "units per pack", minimum=1)
                if not label:
                    raise ValidationError("Name the buying unit (crate, case, box …)")
                if any(str(u["label"]).lower() == label.lower() for u in units):
                    raise ValidationError(f"'{label}' is listed twice")
                units.append({"label": label, "quantity": qty})
            offering.buy_units = units[:6]
        if (offering.batch_tracked or offering.serial_tracked) and not offering.track_inventory:
            offering.track_inventory = True
        offering.version += 1
        offering.updated_at = datetime.now(timezone.utc)
        await session.flush()
        await AuditService.record(session, event_type="inventory.item.configured", actor_identity_id=actor_id,
                                  actor_context="business", business_id=business_id, resource_type="offering",
                                  resource_id=offering.id, action="configure",
                                  after_state={"track_inventory": offering.track_inventory,
                                               "batch_tracked": offering.batch_tracked,
                                               "serial_tracked": offering.serial_tracked,
                                               "warranty_months": offering.warranty_months,
                                               "buy_units": offering.buy_units})
        return {"offering_id": str(offering.id), "track_inventory": offering.track_inventory,
                "batch_tracked": offering.batch_tracked, "serial_tracked": offering.serial_tracked,
                "warranty_months": offering.warranty_months, "buy_units": offering.buy_units}

    @staticmethod
    async def set_reorder(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, record_id: Any,
                          reorder_min: Any, reorder_max: Any, allowed: list[uuid.UUID] | None) -> dict[str, Any]:
        record, offering = await StockService._record_by_id(session, business_id, record_id, allowed)
        low = None if reorder_min in (None, "") else _int(reorder_min, "reorder level")
        high = None if reorder_max in (None, "") else _int(reorder_max, "maximum")
        if low is not None and high is not None and high < low:
            raise ValidationError("The maximum must be at least the reorder level")
        record.low_stock_threshold, record.reorder_max = low, high
        record.version += 1
        await session.flush()
        await AuditService.record(session, event_type="inventory.reorder.set", actor_identity_id=actor_id,
                                  actor_context="business", business_id=business_id,
                                  resource_type="inventory_record", resource_id=record.id, action="reorder",
                                  after_state={"reorder_min": low, "reorder_max": high})
        out: dict[str, Any] = InventoryResolver.serialize_record(record, offering=offering)
        return out | {"reorder_max": high}

    # ------------------------------------------------------------ receive
    @staticmethod
    async def receive(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
                      payload: dict[str, Any], allowed: list[uuid.UUID] | None) -> dict[str, Any]:
        """Goods in (§15.1): quantity in stock units or a buying unit, what it cost,
        its batch and expiry, its serial numbers. Goods receipt against a
        purchase order (P4 Buying) posts through this same function."""
        location_id = _uuid(payload.get("location_id"), "location")
        await StockService._location(session, business_id, location_id, allowed)
        offering = await StockService._offering(session, business_id, payload.get("offering_id"))
        variant_id = await StockService._variant(session, offering, payload.get("variant_id"))
        unit_label = str(payload.get("buy_unit") or "").strip()
        if unit_label:
            unit = next((u for u in offering.buy_units or [] if str(u.get("label")).lower() == unit_label.lower()),
                        None)
            if unit is None:
                raise ValidationError(f"{offering.title} is not bought by the {unit_label}")
            quantity = _int(payload.get("buy_quantity"), "how many", minimum=1) * int(unit["quantity"])
        else:
            quantity = _int(payload.get("quantity"), "quantity", minimum=1)
        cost = payload.get("total_cost_paise")
        cost_paise = None if cost in (None, "") else _int(cost, "cost")
        serials = ledger.clean_serials(payload.get("serials"))
        if offering.serial_tracked:
            if len(serials) != quantity:
                raise ValidationError(f"Enter {quantity} serial number(s) — one for each unit received",
                                      details={"needs": "serials", "quantity": quantity})
            taken = list((await session.execute(select(InventorySerial.serial).where(
                InventorySerial.business_id == business_id, InventorySerial.offering_id == offering.id,
                InventorySerial.serial.in_(serials)))).scalars())
            if taken:
                raise ConflictError(f"Already on record: {', '.join(taken[:5])}", details={"serials": taken})
        elif serials:
            raise ValidationError(f"{offering.title} does not keep serial numbers — turn that on for the item")
        batch_code = str(payload.get("batch_code") or "").strip()
        expires_raw = payload.get("expires_on")
        expires_on: date | None = None
        if expires_raw not in (None, ""):
            try:
                expires_on = expires_raw if isinstance(expires_raw, date) else date.fromisoformat(str(expires_raw))
            except ValueError as exc:
                raise ValidationError("Enter the expiry date") from exc
        if offering.batch_tracked and not batch_code:
            raise ValidationError(f"Enter the batch number printed on {offering.title}", details={"needs": "batch_code"})
        if not offering.batch_tracked and (batch_code or expires_on):
            raise ValidationError(f"{offering.title} does not keep batches — turn on batch & expiry for the item")
        if expires_on is not None and expires_on < today_ist():
            raise ValidationError("That batch has already expired — record it as wastage instead of receiving it")

        record = await StockService._record(session, business_id, offering, location_id, variant_id)
        value = cost_paise if cost_paise is not None else ledger.average_value(record, quantity)
        batch: InventoryBatch | None = None
        if offering.batch_tracked:
            batch = InventoryBatch(business_id=business_id, location_id=location_id, inventory_record_id=record.id,
                                   offering_id=offering.id, variant_id=variant_id, batch_code=batch_code[:60],
                                   expires_on=expires_on, quantity_received=quantity, quantity_on_hand=quantity,
                                   created_by=actor_id)
            session.add(batch)
            await session.flush()
        for serial in serials:
            session.add(InventorySerial(business_id=business_id, location_id=location_id,
                                        inventory_record_id=record.id, offering_id=offering.id,
                                        variant_id=variant_id, serial=serial, created_by=actor_id))
        record.stock_value_paise += value
        words = f"{unit_label} × {payload.get('buy_quantity')}" if unit_label else display_quantity(
            quantity, offering.stock_unit)
        note = str(payload.get("note") or "").strip()
        reason = f"Received {words}" + (f" — {note}" if note else "")
        movement = await StockService._write(
            session, record, offering, delta=quantity, movement_type="receipt", reason=reason, actor_id=actor_id,
            value_delta=value, event="inventory.received", batch_id=batch.id if batch else None,
            extra={"batch_id": str(batch.id) if batch else None,
                   "expires_on": expires_on.isoformat() if expires_on else None})
        return {"movement_id": str(movement.id), "inventory_record_id": str(record.id),
                "quantity": quantity, "quantity_text": display_quantity(quantity, offering.stock_unit),
                "on_hand_text": display_quantity(record.quantity_on_hand, offering.stock_unit),
                "batch_id": str(batch.id) if batch else None, "serials": serials}

    # ------------------------------------------------------------ operational job parts
    @staticmethod
    async def consume_for_job(session: AsyncSession, *, business_id: uuid.UUID, job_id: uuid.UUID,
                              record_id: uuid.UUID, quantity: int, serials: list[str],
                              customer_contact_id: uuid.UUID, actor_id: uuid.UUID,
                              allowed: list[uuid.UUID] | None) -> InventoryMovement:
        """The Inventory-owned consumption contract. Caller supplies a locked, idempotent job.

        A job never edits stock or movements itself. This operation, the job-part
        provenance row and the job transition commit in one database transaction.
        """
        record, offering = await StockService._record_by_id(session, business_id, record_id, allowed)
        if quantity < 1:
            raise ValidationError("Part quantity must be positive")
        if quantity > record.quantity_on_hand - record.quantity_reserved:
            raise ValidationError(f"Only {display_quantity(max(record.quantity_on_hand - record.quantity_reserved, 0), offering.stock_unit)} of {offering.title} is free")
        cleaned = ledger.clean_serials(serials)
        if offering.serial_tracked:
            await ledger.sell_serials(session, record, offering, cleaned, quantity=quantity,
                                      strict=True, sold_at=datetime.now(timezone.utc),
                                      customer_id=customer_contact_id)
        elif cleaned:
            raise ValidationError("This part does not track serial numbers")
        allocations = await ledger.take(session, record, offering, quantity, today=today_ist())
        value = sum(a.value_paise for a in allocations)
        return await StockService._write(
            session, record, offering, delta=-quantity, movement_type="job_consumption",
            reason=f"Used on job {job_id}", actor_id=actor_id,
            value_delta=-value, event="inventory.job_part.consumed",
            source=("job", job_id),
            batch_id=allocations[0].batch_id if len(allocations) == 1 else None,
            extra={"job_id": str(job_id), "allocations": [a.as_json() for a in allocations]},
        )

    # ------------------------------------------------------------ wastage
    @staticmethod
    async def record_wastage(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
                             payload: dict[str, Any], allowed: list[uuid.UUID] | None) -> dict[str, Any]:
        record, offering = await StockService._record_by_id(session, business_id, payload.get("inventory_record_id"),
                                                             allowed)
        reason_code = str(payload.get("reason_code") or "")
        if reason_code not in profile.WASTAGE_REASONS:
            raise ValidationError("Choose why it was wasted")
        serials = ledger.clean_serials(payload.get("serials"))
        quantity = len(serials) if offering.serial_tracked and serials else _int(
            payload.get("quantity"), "quantity", minimum=1)
        available = record.quantity_on_hand - record.quantity_reserved
        if quantity > available:
            raise ValidationError(f"Only {display_quantity(max(available, 0), offering.stock_unit)} of "
                                  f"{offering.title} is free to write off here (the rest is reserved for orders)")
        batch_id = payload.get("batch_id")
        allocations: list[ledger.Allocation]
        if batch_id:
            batch = await session.get(InventoryBatch, _uuid(batch_id, "batch"), with_for_update=True)
            if batch is None or batch.inventory_record_id != record.id or batch.status != "active":
                raise ValidationError("That batch is not in stock here")
            if quantity > batch.quantity_on_hand:
                raise ValidationError(f"Batch {batch.batch_code} has only "
                                      f"{display_quantity(batch.quantity_on_hand, offering.stock_unit)}")
            value = ledger.average_value(record, quantity)
            batch.quantity_on_hand -= quantity
            batch.status = "depleted" if batch.quantity_on_hand == 0 else batch.status
            batch.version += 1
            record.stock_value_paise = max(record.stock_value_paise - value, 0)
            allocations = [ledger.Allocation(batch.id, quantity, value)]
        else:
            allocations = await ledger.take(session, record, offering, quantity, today=today_ist())
        if offering.serial_tracked:
            if len(serials) != quantity:
                raise ValidationError("Enter the serial number of each unit written off")
            for serial in serials:
                row = (await session.execute(select(InventorySerial).where(
                    InventorySerial.business_id == business_id, InventorySerial.offering_id == offering.id,
                    InventorySerial.serial == serial, InventorySerial.status == "in_stock").with_for_update())
                ).scalars().first()
                if row is None:
                    raise ValidationError(f"Serial {serial} is not in stock")
                row.status = "written_off"
                row.version += 1
        value = sum(a.value_paise for a in allocations)
        note = str(payload.get("note") or "").strip()[:200]
        movement = await StockService._write(
            session, record, offering, delta=-quantity, movement_type="wastage",
            reason=f"{profile.WASTAGE_REASONS[reason_code]}" + (f" — {note}" if note else ""), actor_id=actor_id,
            value_delta=-value, event="inventory.wastage.recorded", reason_code=reason_code,
            batch_id=allocations[0].batch_id if len(allocations) == 1 else None,
            extra={"reason_code": reason_code, "allocations": [a.as_json() for a in allocations]})
        return {"movement_id": str(movement.id), "quantity_text": display_quantity(quantity, offering.stock_unit),
                "on_hand_text": display_quantity(record.quantity_on_hand, offering.stock_unit)}

    @staticmethod
    async def write_off_batch(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, batch_id: Any,
                              note: str | None, allowed: list[uuid.UUID] | None) -> dict[str, Any]:
        batch = await session.get(InventoryBatch, _uuid(batch_id, "batch"), with_for_update=True)
        if batch is None or batch.business_id != business_id:
            raise ResourceNotFound("Batch")
        StockService._scope_check(batch.location_id, allowed)
        if batch.status != "active" or batch.quantity_on_hand <= 0:
            raise ConflictError("This batch has nothing left to write off")
        record, offering = await StockService._record_by_id(session, business_id, batch.inventory_record_id, allowed)
        quantity = batch.quantity_on_hand
        if quantity > record.quantity_on_hand - record.quantity_reserved:
            raise ConflictError("Part of this batch is reserved for orders — deliver or cancel them first")
        value = ledger.average_value(record, quantity)
        batch.quantity_on_hand, batch.status = 0, "written_off"
        batch.version += 1
        record.stock_value_paise = max(record.stock_value_paise - value, 0)
        expired = batch.expires_on is not None and batch.expires_on < today_ist()
        code = "expired" if expired else "damaged"
        text = f"Batch {batch.batch_code} written off" + (f" — {note.strip()[:200]}" if note and note.strip() else "")
        await StockService._write(session, record, offering, delta=-quantity, movement_type="wastage", reason=text,
                                  actor_id=actor_id, value_delta=-value, event="inventory.wastage.recorded",
                                  reason_code=code, batch_id=batch.id, extra={"reason_code": code})
        return StockService.serialize_batch(batch, offering)

    # ------------------------------------------------------------ yields and cutting runs
    @staticmethod
    async def list_yields(session: AsyncSession, business_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = list((await session.execute(select(InventoryYield).where(
            InventoryYield.business_id == business_id).order_by(InventoryYield.created_at))).scalars())
        titles = {o.id: o for o in (await session.execute(select(Offering).where(Offering.id.in_(
            [r.source_offering_id for r in rows] + [r.output_offering_id for r in rows])))).scalars()}
        # Accuracy: actual ÷ expected over the last 20 runs of each pair (§15.1 "feeds yield accuracy").
        runs = list((await session.execute(select(InventoryConversion).where(
            InventoryConversion.business_id == business_id).order_by(InventoryConversion.created_at.desc())
            .limit(200))).scalars())
        out = []
        for y in rows:
            pairs = [(o.get("expected") or 0, o.get("actual") or 0) for run in runs
                     if run.source_offering_id == y.source_offering_id
                     for o in run.outputs if o.get("offering_id") == str(y.output_offering_id) and o.get("expected")][:20]
            expected = sum(p[0] for p in pairs)
            src, dst = titles.get(y.source_offering_id), titles.get(y.output_offering_id)
            out.append({"id": str(y.id), "source_offering_id": str(y.source_offering_id),
                        "source_title": src.title if src else "", "output_offering_id": str(y.output_offering_id),
                        "output_title": dst.title if dst else "", "yield_bp": y.yield_bp,
                        "yield_percent": round(y.yield_bp / 100, 2), "note": y.note, "runs": len(pairs),
                        "actual_percent_of_expected": round(sum(p[1] for p in pairs) * 100 / expected, 1)
                        if expected else None})
        return out

    @staticmethod
    async def set_yield(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
                        payload: dict[str, Any]) -> dict[str, Any]:
        source = await StockService._offering(session, business_id, payload.get("source_offering_id"))
        output = await StockService._offering(session, business_id, payload.get("output_offering_id"))
        if source.id == output.id:
            raise ValidationError("A yield goes from one item to a different item")
        if source.stock_unit != output.stock_unit:
            raise ValidationError("Both items must be counted the same way (both by weight, or both in pieces)")
        percent = payload.get("yield_percent")
        try:
            bp = round(float(str(percent)) * 100)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Enter the yield as a percentage, e.g. 80") from exc
        if not 1 <= bp <= 10000:
            raise ValidationError("A yield is between 0.01% and 100%")
        row = (await session.execute(select(InventoryYield).where(
            InventoryYield.business_id == business_id, InventoryYield.source_offering_id == source.id,
            InventoryYield.output_offering_id == output.id).with_for_update())).scalars().first()
        note = str(payload.get("note") or "").strip()[:200] or None
        if row is None:
            row = InventoryYield(business_id=business_id, source_offering_id=source.id,
                                 output_offering_id=output.id, yield_bp=bp, note=note, created_by=actor_id)
            session.add(row)
        else:
            row.yield_bp, row.note, row.version = bp, note, row.version + 1
        await session.flush()
        await AuditService.record(session, event_type="inventory.yield.set", actor_identity_id=actor_id,
                                  actor_context="business", business_id=business_id,
                                  resource_type="inventory_yield", resource_id=row.id, action="set",
                                  after_state={"source": source.title, "output": output.title, "yield_bp": bp})
        return {"id": str(row.id), "yield_bp": bp}

    @staticmethod
    async def convert(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
                      payload: dict[str, Any], allowed: list[uuid.UUID] | None) -> dict[str, Any]:
        """A cutting run (§15.1 yield): a quantity of the source becomes the
        outputs actually weighed out; the rest is trim. The source's value is
        carried into the outputs by weight, so the cost of a kilo of curry cut
        includes what was trimmed from the whole bird."""
        key = str(payload.get("idempotency_key") or "").strip()[:80] or None
        if key:
            found = (await session.execute(select(InventoryConversion).where(
                InventoryConversion.business_id == business_id,
                InventoryConversion.idempotency_key == key))).scalars().first()
            if found:
                return StockService.serialize_conversion(found)
        location_id = _uuid(payload.get("location_id"), "location")
        await StockService._location(session, business_id, location_id, allowed)
        source = await StockService._offering(session, business_id, payload.get("source_offering_id"))
        source_qty = _int(payload.get("source_quantity"), "quantity cut", minimum=1)
        raw_outputs = list(payload.get("outputs") or [])
        if not raw_outputs:
            raise ValidationError("Enter what came out of the cut")
        outs: list[tuple[Offering, int]] = []
        for raw in raw_outputs:
            output = await StockService._offering(session, business_id, (raw or {}).get("offering_id"))
            qty = _int((raw or {}).get("quantity"), "weight out", minimum=0)
            if output.id == source.id:
                raise ValidationError("The output must be a different item from the one cut")
            if output.stock_unit != source.stock_unit:
                raise ValidationError(f"{output.title} is counted differently from {source.title}")
            if any(o.id == output.id for o, _ in outs):
                raise ValidationError(f"{output.title} is listed twice")
            if output.variant_options or source.variant_options:
                raise ValidationError("Cutting runs work on items without sizes or colours")
            outs.append((output, qty))
        total_out = sum(q for _, q in outs)
        if total_out <= 0:
            raise ValidationError("Enter the weight of at least one output")
        if total_out > source_qty:
            raise ValidationError(f"The outputs weigh more than the {display_quantity(source_qty, source.stock_unit)} "
                                  f"that was cut")
        src_record = await StockService._record(session, business_id, source, location_id, None)
        free = src_record.quantity_on_hand - src_record.quantity_reserved
        if source_qty > free:
            raise ValidationError(f"Only {display_quantity(max(free, 0), source.stock_unit)} of {source.title} "
                                  f"is free to cut here")
        yields = {y.output_offering_id: y.yield_bp for y in (await session.execute(select(InventoryYield).where(
            InventoryYield.business_id == business_id, InventoryYield.source_offering_id == source.id))).scalars()}
        conversion = InventoryConversion(business_id=business_id, location_id=location_id,
                                         source_offering_id=source.id, source_quantity=source_qty, outputs=[],
                                         trim_quantity=source_qty - total_out,
                                         note=str(payload.get("note") or "").strip()[:300] or None,
                                         actor_identity_id=actor_id, idempotency_key=key)
        session.add(conversion)
        await session.flush()
        allocations = await ledger.take(session, src_record, source, source_qty, today=today_ist())
        taken_value = sum(a.value_paise for a in allocations)
        await StockService._write(session, src_record, source, delta=-source_qty, movement_type="conversion_out",
                                  reason=f"Cut into {', '.join(o.title for o, _ in outs)}", actor_id=actor_id,
                                  value_delta=-taken_value, event="inventory.converted",
                                  source=("conversion", conversion.id))
        records: list[dict[str, Any]] = []
        left = taken_value
        for i, (output, qty) in enumerate(outs):
            share = left if i == len(outs) - 1 else round(taken_value * qty / total_out)
            share = min(share, left)
            left -= share
            expected = round(source_qty * yields[output.id] / 10000) if output.id in yields else None
            records.append({"offering_id": str(output.id), "title": output.title, "actual": qty,
                            "expected": expected, "value_paise": share})
            if qty <= 0:
                continue
            rec = await StockService._record(session, business_id, output, location_id, None)
            rec.stock_value_paise += share
            await StockService._write(session, rec, output, delta=qty, movement_type="conversion_in",
                                      reason=f"Cut from {display_quantity(source_qty, source.stock_unit)} "
                                             f"{source.title}", actor_id=actor_id, value_delta=share,
                                      event="inventory.converted", source=("conversion", conversion.id))
        conversion.outputs = records
        await session.flush()
        return StockService.serialize_conversion(conversion, source=source)

    @staticmethod
    def serialize_conversion(c: InventoryConversion, *, source: Offering | None = None) -> dict[str, Any]:
        unit = source.stock_unit if source else "g"
        return {"id": str(c.id), "source_offering_id": str(c.source_offering_id),
                "source_title": source.title if source else None, "source_quantity": c.source_quantity,
                "source_text": display_quantity(c.source_quantity, unit),
                "outputs": [{**o, "actual_text": display_quantity(int(o.get("actual") or 0), unit),
                             "expected_text": display_quantity(int(o["expected"]), unit)
                             if o.get("expected") is not None else None} for o in c.outputs],
                "trim_quantity": c.trim_quantity, "trim_text": display_quantity(c.trim_quantity, unit),
                "trim_percent": round(c.trim_quantity * 100 / c.source_quantity, 1) if c.source_quantity else 0,
                "note": c.note, "at": c.created_at.isoformat() if c.created_at else None}

    @staticmethod
    async def recent_conversions(session: AsyncSession, business_id: uuid.UUID,
                                 allowed: list[uuid.UUID] | None, limit: int = 20) -> list[dict[str, Any]]:
        q = select(InventoryConversion).where(InventoryConversion.business_id == business_id)
        if allowed is not None:
            q = q.where(InventoryConversion.location_id.in_(allowed))
        rows = list((await session.execute(q.order_by(InventoryConversion.created_at.desc()).limit(limit))).scalars())
        sources = {o.id: o for o in (await session.execute(select(Offering).where(
            Offering.id.in_([r.source_offering_id for r in rows])))).scalars()}
        return [StockService.serialize_conversion(r, source=sources.get(r.source_offering_id)) for r in rows]

    @staticmethod
    async def wastage_summary(session: AsyncSession, business_id: uuid.UUID, allowed: list[uuid.UUID] | None,
                              *, days: int = 30, can_see_cost: bool = False) -> dict[str, Any]:
        since = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 365)))
        q = (select(InventoryMovement.reason_code, Offering.stock_unit, func.sum(-InventoryMovement.quantity_delta),
                    func.sum(-InventoryMovement.value_delta_paise), func.count())
             .join(Offering, Offering.id == InventoryMovement.offering_id)
             .where(InventoryMovement.business_id == business_id, InventoryMovement.movement_type == "wastage",
                    InventoryMovement.created_at >= since)
             .group_by(InventoryMovement.reason_code, Offering.stock_unit))
        if allowed is not None:
            q = q.where(InventoryMovement.location_id.in_(allowed))
        by_reason: dict[str, dict[str, Any]] = {}
        for code, unit, qty, value, n in (await session.execute(q)).all():
            entry = by_reason.setdefault(code or "other", {"reason": code or "other",
                                                           "label": profile.WASTAGE_REASONS.get(code or "other"),
                                                           "entries": 0, "quantities": [], "value_paise": 0})
            entry["entries"] += int(n)
            entry["quantities"].append(display_quantity(int(qty or 0), unit))
            entry["value_paise"] += int(value or 0)
        trim_q = select(func.coalesce(func.sum(InventoryConversion.trim_quantity), 0),
                        func.coalesce(func.sum(InventoryConversion.source_quantity), 0), func.count()).where(
            InventoryConversion.business_id == business_id, InventoryConversion.created_at >= since)
        if allowed is not None:
            trim_q = trim_q.where(InventoryConversion.location_id.in_(allowed))
        trim, cut, runs = (await session.execute(trim_q)).one()
        reasons = list(by_reason.values())
        if not can_see_cost:
            for r in reasons:
                r.pop("value_paise")
        return {"days": days, "reasons": reasons,
                "cutting": {"runs": int(runs), "trim_percent": round(int(trim) * 100 / int(cut), 1) if cut else None}}

    # ------------------------------------------------------------ counts
    @staticmethod
    def serialize_count(c: InventoryCount) -> dict[str, Any]:
        return {"id": str(c.id), "location_id": str(c.location_id),
                "category_id": str(c.category_id) if c.category_id else None, "label": c.label,
                "status": c.status, "submitted_at": c.submitted_at.isoformat() if c.submitted_at else None,
                "decided_at": c.decided_at.isoformat() if c.decided_at else None, "decision_note": c.decision_note,
                "created_at": c.created_at.isoformat() if c.created_at else None, "version": c.version}

    @staticmethod
    async def start_count(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
                          payload: dict[str, Any], allowed: list[uuid.UUID] | None) -> dict[str, Any]:
        location_id = _uuid(payload.get("location_id"), "location")
        await StockService._location(session, business_id, location_id, allowed)
        category_id = uuid.UUID(str(payload["category_id"])) if payload.get("category_id") else None
        busy = (await session.execute(select(InventoryCount.id).where(
            InventoryCount.business_id == business_id, InventoryCount.location_id == location_id,
            InventoryCount.status.in_(("open", "submitted")),
            (InventoryCount.category_id == category_id) if category_id else InventoryCount.category_id.is_(None),
        ))).scalars().first()
        if busy:
            raise ConflictError("A count for this shelf is already open — finish it first", details={"count_id": str(busy)})
        q = (select(InventoryRecord).join(Offering, Offering.id == InventoryRecord.offering_id)
             .where(InventoryRecord.business_id == business_id, InventoryRecord.location_id == location_id,
                    Offering.deleted_at.is_(None), Offering.track_inventory.is_(True)))
        if category_id:
            q = q.where(Offering.category_id == category_id)
        records = list((await session.execute(q)).scalars())
        if not records:
            raise ValidationError("Nothing is tracked here yet — receive stock first")
        label = str(payload.get("label") or "").strip()[:120] or f"Count {today_ist():%d %b %Y}"
        count = InventoryCount(business_id=business_id, location_id=location_id, category_id=category_id,
                               label=label, started_by=actor_id)
        session.add(count)
        await session.flush()
        for rec in records:
            session.add(InventoryCountLine(business_id=business_id, count_id=count.id, inventory_record_id=rec.id,
                                           expected_quantity=max(rec.quantity_on_hand, 0)))
        await session.flush()
        await AuditService.record(session, event_type="inventory.count.started", actor_identity_id=actor_id,
                                  actor_context="business", business_id=business_id, resource_type="inventory_count",
                                  resource_id=count.id, action="start", after_state={"lines": len(records)})
        return StockService.serialize_count(count)

    @staticmethod
    async def _count(session: AsyncSession, business_id: uuid.UUID, count_id: Any,
                     allowed: list[uuid.UUID] | None, *, lock: bool = False) -> InventoryCount:
        q = select(InventoryCount).where(InventoryCount.business_id == business_id,
                                         InventoryCount.id == _uuid(count_id, "count"))
        if lock:
            q = q.with_for_update()
        count = (await session.execute(q)).scalars().first()
        if count is None:
            raise ResourceNotFound("Stock count")
        StockService._scope_check(count.location_id, allowed)
        return count

    @staticmethod
    async def get_count(session: AsyncSession, business_id: uuid.UUID, count_id: Any,
                        allowed: list[uuid.UUID] | None, *, blind: bool) -> dict[str, Any]:
        """`blind`: the counter does not see the system figure while counting
        (a count that shows the answer is not a count)."""
        count = await StockService._count(session, business_id, count_id, allowed)
        rows = (await session.execute(select(InventoryCountLine, InventoryRecord, Offering, OfferingVariant)
                .join(InventoryRecord, InventoryRecord.id == InventoryCountLine.inventory_record_id)
                .join(Offering, Offering.id == InventoryRecord.offering_id)
                .outerjoin(OfferingVariant, OfferingVariant.id == InventoryRecord.variant_id)
                .where(InventoryCountLine.count_id == count.id)
                .order_by(Offering.title, OfferingVariant.sort_order))).all()
        lines = []
        variances = 0
        for line, rec, offering, variant in rows:
            variance = None if line.counted_quantity is None else line.counted_quantity - line.expected_quantity
            variances += 1 if variance else 0
            entry = {"id": str(line.id), "inventory_record_id": str(rec.id), "title": offering.title,
                     "variant": variant.name if variant else None, "stock_unit": offering.stock_unit,
                     "counted_quantity": line.counted_quantity,
                     "counted_text": display_quantity(line.counted_quantity, offering.stock_unit)
                     if line.counted_quantity is not None else None}
            if not blind or count.status != "open":
                entry.update({"expected_quantity": line.expected_quantity,
                              "expected_text": display_quantity(line.expected_quantity, offering.stock_unit),
                              "variance": variance,
                              "variance_text": (("+" if variance > 0 else "−") +
                                                display_quantity(abs(variance), offering.stock_unit))
                              if variance else None})
            lines.append(entry)
        return {**StockService.serialize_count(count), "lines": lines,
                "counted": sum(1 for x in lines if x["counted_quantity"] is not None), "variances": variances}

    @staticmethod
    async def list_counts(session: AsyncSession, business_id: uuid.UUID,
                          allowed: list[uuid.UUID] | None) -> list[dict[str, Any]]:
        q = select(InventoryCount).where(InventoryCount.business_id == business_id)
        if allowed is not None:
            q = q.where(InventoryCount.location_id.in_(allowed))
        return [StockService.serialize_count(c) for c in (await session.execute(
            q.order_by(InventoryCount.created_at.desc()).limit(30))).scalars()]

    @staticmethod
    async def record_count(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, count_id: Any,
                           lines: list[dict[str, Any]], allowed: list[uuid.UUID] | None) -> dict[str, Any]:
        count = await StockService._count(session, business_id, count_id, allowed, lock=True)
        if count.status != "open":
            raise ConflictError("This count has been submitted")
        by_record = {str(line.inventory_record_id): line for line in (await session.execute(
            select(InventoryCountLine).where(InventoryCountLine.count_id == count.id))).scalars()}
        now = datetime.now(timezone.utc)
        for raw in lines:
            line = by_record.get(str((raw or {}).get("inventory_record_id")))
            if line is None:
                raise ValidationError("That item is not part of this count")
            value = raw.get("counted_quantity")
            line.counted_quantity = None if value in (None, "") else _int(value, "count")
            line.counted_by, line.counted_at = actor_id, now
        count.version += 1
        await session.flush()
        return StockService.serialize_count(count)

    @staticmethod
    async def submit_count(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, count_id: Any,
                           allowed: list[uuid.UUID] | None) -> dict[str, Any]:
        count = await StockService._count(session, business_id, count_id, allowed, lock=True)
        if count.status != "open":
            raise ConflictError("This count is already submitted")
        counted = (await session.execute(select(func.count()).select_from(InventoryCountLine).where(
            InventoryCountLine.count_id == count.id, InventoryCountLine.counted_quantity.is_not(None)))).scalar()
        if not counted:
            raise ValidationError("Count at least one item before submitting")
        count.status, count.submitted_by, count.submitted_at = "submitted", actor_id, datetime.now(timezone.utc)
        count.version += 1
        await session.flush()
        await OutboxService.publish(session, event_type="inventory.count.submitted", business_id=business_id,
                                    payload={"business_id": str(business_id), "count_id": str(count.id),
                                             "location_id": str(count.location_id)})
        return StockService.serialize_count(count)

    @staticmethod
    async def decide_count(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, count_id: Any,
                           approve: bool, note: str | None, allowed: list[uuid.UUID] | None) -> dict[str, Any]:
        """Variances need approval (§15.1). Approval applies each variance as a
        movement — against the stock as it is now, so sales made while the
        shelf was counted are not undone."""
        count = await StockService._count(session, business_id, count_id, allowed, lock=True)
        if count.status != "submitted":
            raise ConflictError("Only a submitted count can be approved or sent back")
        now = datetime.now(timezone.utc)
        count.decided_by, count.decided_at = actor_id, now
        count.decision_note = (note or "").strip()[:300] or None
        count.version += 1
        if not approve:
            count.status = "cancelled"
            await session.flush()
            await OutboxService.publish(session, event_type="inventory.count.rejected", business_id=business_id,
                                        payload={"business_id": str(business_id), "count_id": str(count.id)})
            return StockService.serialize_count(count)
        applied = 0
        lines = list((await session.execute(select(InventoryCountLine).where(
            InventoryCountLine.count_id == count.id, InventoryCountLine.counted_quantity.is_not(None)))).scalars())
        for line in lines:
            record, offering = await StockService._record_by_id(session, business_id, line.inventory_record_id,
                                                                allowed)
            record.last_counted_at = now
            assert line.counted_quantity is not None
            variance = line.counted_quantity - line.expected_quantity
            if variance == 0:
                continue
            delta = max(variance, -record.quantity_on_hand)
            if delta < 0:
                allocations = await ledger.take(session, record, offering, -delta, today=today_ist())
                value = -sum(a.value_paise for a in allocations)
            else:
                value = ledger.average_value(record, delta)
                record.stock_value_paise += value
            await StockService._write(session, record, offering, delta=delta, movement_type="count_variance",
                                      reason=f"{count.label}: counted {display_quantity(line.counted_quantity, offering.stock_unit)}"
                                             f", expected {display_quantity(line.expected_quantity, offering.stock_unit)}",
                                      actor_id=actor_id, value_delta=value, event="inventory.count.variance",
                                      source=("count", count.id))
            applied += 1
        count.status = "approved"
        await session.flush()
        await OutboxService.publish(session, event_type="inventory.count.approved", business_id=business_id,
                                    payload={"business_id": str(business_id), "count_id": str(count.id),
                                             "variances_applied": applied})
        await AuditService.record(session, event_type="inventory.count.approved", actor_identity_id=actor_id,
                                  actor_context="business", business_id=business_id, resource_type="inventory_count",
                                  resource_id=count.id, action="approve", after_state={"variances_applied": applied})
        return StockService.serialize_count(count) | {"variances_applied": applied}

    # ------------------------------------------------------------ expiry reminders
    @staticmethod
    def expiry_anchor(expires_on: date) -> datetime:
        return datetime.combine(expires_on, time(9, 0), IST).astimezone(timezone.utc)
