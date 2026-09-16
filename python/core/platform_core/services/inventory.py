"""Inventory service (Stage 5)."""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ValidationError
from platform_core.gates import assert_business_mutable
from platform_core.models import InventoryMovement, InventoryRecord, Offering
from platform_core.resolvers.inventory_resolver import InventoryResolver
from platform_core.resolvers.location_resolver import LocationResolver
from platform_core.resolvers.offering_resolver import OfferingResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService
from platform_core.validation.inventory import validate_adjustment_payload, validate_opening_stock_payload


class InventoryService:
    @staticmethod
    def serialize_record(
        record: InventoryRecord,
        *,
        offering: Offering | None = None,
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            InventoryResolver.serialize_record(record, offering=offering),
        )

    @staticmethod
    def _check_version(record: InventoryRecord, expected_version: int | None) -> None:
        if expected_version is None:
            return
        if record.version != expected_version:
            raise ConflictError(
                "Stale inventory version",
                details={
                    "expected_version": expected_version,
                    "current_version": record.version,
                },
            )

    @staticmethod
    async def _validate_refs(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        offering_id: uuid.UUID,
        location_id: uuid.UUID,
        variant_id: uuid.UUID | None,
    ) -> Offering:
        offering = await OfferingResolver.resolve(
            session, business_id=business_id, offering_id=offering_id
        )
        InventoryResolver.require_track_inventory(offering)
        await LocationResolver.resolve(
            session, business_id=business_id, location_id=location_id
        )
        if variant_id:
            variant = await OfferingResolver.resolve_variant(
                session, business_id=business_id, variant_id=variant_id
            )
            if variant.offering_id != offering.id:
                raise ValidationError(
                    "Variant does not belong to product",
                    details={"variant_id": str(variant_id), "offering_id": str(offering_id)},
                )
        return offering

    @staticmethod
    async def _get_or_create_record(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        offering: Offering,
        location_id: uuid.UUID,
        variant_id: uuid.UUID | None,
    ) -> InventoryRecord:
        record = await InventoryResolver.resolve_or_none(
            session,
            business_id=business_id,
            offering_id=offering.id,
            location_id=location_id,
            variant_id=variant_id,
        )
        if record:
            return record
        record = InventoryRecord(
            business_id=business_id,
            offering_id=offering.id,
            variant_id=variant_id,
            location_id=location_id,
            low_stock_threshold=offering.low_stock_threshold,
        )
        session.add(record)
        await session.flush()
        return record

    @staticmethod
    async def _publish_stock_events(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        offering: Offering,
        record: InventoryRecord,
        actor_id: uuid.UUID,
        correlation_id: str,
        quantity_delta: int,
        movement_type: str,
        reason: str,
        before_state: dict[str, Any],
        after_state: dict[str, Any],
        actor_context: str = "business",
    ) -> None:
        base_payload: dict[str, Any] = {
            "business_id": str(business_id),
            "offering_id": str(offering.id),
            "product_id": str(offering.id),
            "variant_id": str(record.variant_id) if record.variant_id else None,
            "location_id": str(record.location_id),
            "inventory_record_id": str(record.id),
            "delta": quantity_delta,
            "quantity_delta": quantity_delta,
            "new_level": record.quantity_on_hand,
            "reason": reason,
            "movement_type": movement_type,
            "after": after_state,
        }
        await OutboxService.publish(
            session,
            event_type="inventory.stock.updated",
            payload=base_payload,
            business_id=business_id,
            correlation_id=correlation_id,
        )
        status = InventoryResolver.stock_status(record, offering=offering)
        if status == "low_stock":
            await OutboxService.publish(
                session,
                event_type="inventory.stock.low",
                payload={
                    **base_payload,
                    "current_level": record.quantity_on_hand,
                    "threshold": record.low_stock_threshold or offering.low_stock_threshold,
                },
                business_id=business_id,
                correlation_id=correlation_id,
            )
        elif status == "out_of_stock":
            await OutboxService.publish(
                session,
                event_type="inventory.stock.zero",
                payload=base_payload,
                business_id=business_id,
                correlation_id=correlation_id,
            )
        elif movement_type == "adjustment" and quantity_delta > 0:
            await OutboxService.publish(
                session,
                event_type="inventory.stock.replenished",
                payload={
                    **base_payload,
                    "added_quantity": quantity_delta,
                },
                business_id=business_id,
                correlation_id=correlation_id,
            )
        audit_event = (
            "inventory.opening_stock.set"
            if movement_type == "opening_stock"
            else "inventory.adjusted"
        )
        await OutboxService.publish(
            session,
            event_type=audit_event,
            payload=base_payload,
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type=audit_event,
            actor_identity_id=actor_id,
            actor_context=actor_context,
            business_id=business_id,
            resource_type="inventory_record",
            resource_id=record.id,
            action="adjusted" if movement_type == "adjustment" else "opening_stock",
            before_state=before_state,
            after_state=after_state,
        )

    @staticmethod
    async def list_for_business(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        location_id: uuid.UUID | None = None,
        offering_id: uuid.UUID | None = None,
        stock_status: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        query = (
            select(InventoryRecord, Offering)
            .join(Offering, Offering.id == InventoryRecord.offering_id)
            .where(
                InventoryRecord.business_id == business_id,
                Offering.deleted_at.is_(None),
            )
        )
        if location_id:
            query = query.where(InventoryRecord.location_id == location_id)
        if offering_id:
            query = query.where(InventoryRecord.offering_id == offering_id)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.where(
                Offering.title.ilike(pattern) | Offering.sku.ilike(pattern)
            )
        rows = (await session.execute(query.order_by(Offering.title))).all()
        results: list[dict[str, Any]] = []
        for record, offering in rows:
            item = InventoryService.serialize_record(record, offering=offering)
            item["product_title"] = offering.title
            item["product_sku"] = offering.sku
            if stock_status and item["stock_status"] != stock_status:
                continue
            results.append(item)
        return results

    @staticmethod
    async def set_opening_stock(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> InventoryRecord:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="set opening stock")
        validated = validate_opening_stock_payload(payload)
        offering = await InventoryService._validate_refs(
            session,
            business_id=business_id,
            offering_id=validated["offering_id"],
            location_id=validated["location_id"],
            variant_id=validated["variant_id"],
        )
        existing = await InventoryResolver.resolve_or_none(
            session,
            business_id=business_id,
            offering_id=offering.id,
            location_id=validated["location_id"],
            variant_id=validated["variant_id"],
        )
        if existing and existing.quantity_on_hand > 0:
            raise ConflictError(
                "Opening stock already recorded for this product/location",
                details={"inventory_record_id": str(existing.id)},
            )
        record = existing or await InventoryService._get_or_create_record(
            session,
            business_id=business_id,
            offering=offering,
            location_id=validated["location_id"],
            variant_id=validated["variant_id"],
        )
        before = InventoryService.serialize_record(record, offering=offering)
        delta = validated["quantity"] - record.quantity_on_hand
        record.quantity_on_hand = validated["quantity"]
        record.version += 1
        movement = InventoryMovement(
            business_id=business_id,
            offering_id=offering.id,
            variant_id=validated["variant_id"],
            location_id=validated["location_id"],
            inventory_record_id=record.id,
            movement_type="opening_stock",
            quantity_delta=delta,
            quantity_after=record.quantity_on_hand,
            reason=validated["reason"],
            actor_identity_id=actor_id,
        )
        session.add(movement)
        await session.flush()
        after = InventoryService.serialize_record(record, offering=offering)
        await InventoryService._publish_stock_events(
            session,
            business_id=business_id,
            offering=offering,
            record=record,
            actor_id=actor_id,
            correlation_id=correlation_id,
            quantity_delta=delta,
            movement_type="opening_stock",
            reason=validated["reason"],
            before_state=before,
            after_state=after,
        )
        return record

    @staticmethod
    async def adjust_stock(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
        expected_version: int | None = None,
    ) -> InventoryRecord:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="adjust inventory")
        validated = validate_adjustment_payload(payload)
        offering = await InventoryService._validate_refs(
            session,
            business_id=business_id,
            offering_id=validated["offering_id"],
            location_id=validated["location_id"],
            variant_id=validated["variant_id"],
        )
        record = await InventoryService._get_or_create_record(
            session,
            business_id=business_id,
            offering=offering,
            location_id=validated["location_id"],
            variant_id=validated["variant_id"],
        )
        InventoryService._check_version(record, expected_version)
        before = InventoryService.serialize_record(record, offering=offering)
        new_qty = record.quantity_on_hand + validated["quantity_delta"]
        if new_qty < 0:
            raise ValidationError(
                "Insufficient stock for adjustment",
                details={
                    "quantity_on_hand": record.quantity_on_hand,
                    "quantity_delta": validated["quantity_delta"],
                },
            )
        record.quantity_on_hand = new_qty
        record.version += 1
        movement = InventoryMovement(
            business_id=business_id,
            offering_id=offering.id,
            variant_id=validated["variant_id"],
            location_id=validated["location_id"],
            inventory_record_id=record.id,
            movement_type=validated["movement_type"],
            quantity_delta=validated["quantity_delta"],
            quantity_after=record.quantity_on_hand,
            reason=validated["reason"],
            actor_identity_id=actor_id,
        )
        session.add(movement)
        await session.flush()
        after = InventoryService.serialize_record(record, offering=offering)
        await InventoryService._publish_stock_events(
            session,
            business_id=business_id,
            offering=offering,
            record=record,
            actor_id=actor_id,
            correlation_id=correlation_id,
            quantity_delta=validated["quantity_delta"],
            movement_type=validated["movement_type"],
            reason=validated["reason"],
            before_state=before,
            after_state=after,
        )
        return record

    @staticmethod
    async def export_inventory(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        location_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        return await InventoryService.list_for_business(
            session,
            business_id,
            location_id=location_id,
        )

    @staticmethod
    async def _available_quantity(record: InventoryRecord) -> int:
        return max(record.quantity_on_hand - record.quantity_reserved, 0)

    @staticmethod
    async def reserve_for_order(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        offering_id: uuid.UUID,
        location_id: uuid.UUID,
        variant_id: uuid.UUID | None,
        quantity: int,
        actor_id: uuid.UUID,
        correlation_id: str,
        order_id: uuid.UUID,
        reason: str,
        actor_context: str = "business",
    ) -> InventoryRecord:
        if quantity <= 0:
            raise ValidationError("Reservation quantity must be positive")
        offering = await InventoryService._validate_refs(
            session,
            business_id=business_id,
            offering_id=offering_id,
            location_id=location_id,
            variant_id=variant_id,
        )
        record = await InventoryService._get_or_create_record(
            session,
            business_id=business_id,
            offering=offering,
            location_id=location_id,
            variant_id=variant_id,
        )
        available = await InventoryService._available_quantity(record)
        if available < quantity:
            raise ValidationError(
                "Insufficient available stock",
                details={
                    "offering_id": str(offering_id),
                    "available": available,
                    "requested": quantity,
                },
            )
        before = InventoryService.serialize_record(record, offering=offering)
        record.quantity_reserved += quantity
        record.version += 1
        movement = InventoryMovement(
            business_id=business_id,
            offering_id=offering.id,
            variant_id=variant_id,
            location_id=location_id,
            inventory_record_id=record.id,
            movement_type="reservation",
            quantity_delta=quantity,
            quantity_after=record.quantity_on_hand,
            reason=f"{reason} (order:{order_id})",
            actor_identity_id=actor_id,
        )
        session.add(movement)
        await session.flush()
        after = InventoryService.serialize_record(record, offering=offering)
        await InventoryService._publish_stock_events(
            session,
            business_id=business_id,
            offering=offering,
            record=record,
            actor_id=actor_id,
            correlation_id=correlation_id,
            quantity_delta=0,
            movement_type="reservation",
            reason=reason,
            before_state=before,
            after_state=after,
            actor_context=actor_context,
        )
        return record

    @staticmethod
    async def release_reservation_for_order(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        offering_id: uuid.UUID,
        location_id: uuid.UUID,
        variant_id: uuid.UUID | None,
        quantity: int,
        actor_id: uuid.UUID,
        correlation_id: str,
        order_id: uuid.UUID,
        reason: str,
    ) -> InventoryRecord | None:
        if quantity <= 0:
            return None
        offering = await OfferingResolver.resolve(
            session, business_id=business_id, offering_id=offering_id
        )
        if not offering.track_inventory:
            return None
        record = await InventoryResolver.resolve_or_none(
            session,
            business_id=business_id,
            offering_id=offering_id,
            location_id=location_id,
            variant_id=variant_id,
        )
        if record is None:
            return None
        release_qty = min(quantity, record.quantity_reserved)
        if release_qty <= 0:
            return record
        before = InventoryService.serialize_record(record, offering=offering)
        record.quantity_reserved -= release_qty
        record.version += 1
        movement = InventoryMovement(
            business_id=business_id,
            offering_id=offering.id,
            variant_id=variant_id,
            location_id=location_id,
            inventory_record_id=record.id,
            movement_type="reversal",
            quantity_delta=-release_qty,
            quantity_after=record.quantity_on_hand,
            reason=f"{reason} (order:{order_id})",
            actor_identity_id=actor_id,
        )
        session.add(movement)
        await session.flush()
        after = InventoryService.serialize_record(record, offering=offering)
        await InventoryService._publish_stock_events(
            session,
            business_id=business_id,
            offering=offering,
            record=record,
            actor_id=actor_id,
            correlation_id=correlation_id,
            quantity_delta=0,
            movement_type="reversal",
            reason=reason,
            before_state=before,
            after_state=after,
        )
        return record

    @staticmethod
    async def deduct_reserved_for_order(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        offering_id: uuid.UUID,
        location_id: uuid.UUID,
        variant_id: uuid.UUID | None,
        quantity: int,
        actor_id: uuid.UUID,
        correlation_id: str,
        order_id: uuid.UUID,
        reason: str,
    ) -> InventoryRecord | None:
        if quantity <= 0:
            return None
        offering = await OfferingResolver.resolve(
            session, business_id=business_id, offering_id=offering_id
        )
        if not offering.track_inventory:
            return None
        record = await InventoryResolver.resolve_or_none(
            session,
            business_id=business_id,
            offering_id=offering_id,
            location_id=location_id,
            variant_id=variant_id,
        )
        if record is None:
            raise ValidationError(
                "Inventory record missing for deduction",
                details={"offering_id": str(offering_id)},
            )
        deduct_qty = min(quantity, record.quantity_reserved, record.quantity_on_hand)
        if deduct_qty < quantity:
            raise ValidationError(
                "Insufficient reserved stock for deduction",
                details={
                    "requested": quantity,
                    "deductible": deduct_qty,
                },
            )
        before = InventoryService.serialize_record(record, offering=offering)
        record.quantity_on_hand -= deduct_qty
        record.quantity_reserved -= deduct_qty
        record.version += 1
        movement = InventoryMovement(
            business_id=business_id,
            offering_id=offering.id,
            variant_id=variant_id,
            location_id=location_id,
            inventory_record_id=record.id,
            movement_type="deduction",
            quantity_delta=-deduct_qty,
            quantity_after=record.quantity_on_hand,
            reason=f"{reason} (order:{order_id})",
            actor_identity_id=actor_id,
        )
        session.add(movement)
        await session.flush()
        after = InventoryService.serialize_record(record, offering=offering)
        await InventoryService._publish_stock_events(
            session,
            business_id=business_id,
            offering=offering,
            record=record,
            actor_id=actor_id,
            correlation_id=correlation_id,
            quantity_delta=-deduct_qty,
            movement_type="deduction",
            reason=reason,
            before_state=before,
            after_state=after,
        )
        return record
