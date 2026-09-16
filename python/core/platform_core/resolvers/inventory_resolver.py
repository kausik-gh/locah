"""Inventory lookup resolver (Stage 5)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ResourceNotFound, ValidationError
from platform_core.models import InventoryMovement, InventoryRecord, Offering


class InventoryResolver:
    @staticmethod
    def stock_status(
        record: InventoryRecord,
        *,
        offering: Offering | None = None,
    ) -> str:
        qty = record.quantity_on_hand
        if qty <= 0:
            return "out_of_stock"
        threshold = record.low_stock_threshold
        if threshold is None and offering is not None:
            threshold = offering.low_stock_threshold
        if threshold is not None and qty <= threshold:
            return "low_stock"
        return "available"

    @staticmethod
    async def resolve_record(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        record_id: uuid.UUID,
    ) -> InventoryRecord:
        result = await session.execute(
            select(InventoryRecord).where(
                InventoryRecord.id == record_id,
                InventoryRecord.business_id == business_id,
            )
        )
        record = result.scalars().first()
        if record is None:
            raise ResourceNotFound("Inventory record")
        return record

    @staticmethod
    async def resolve_or_none(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        offering_id: uuid.UUID,
        location_id: uuid.UUID,
        variant_id: uuid.UUID | None,
    ) -> InventoryRecord | None:
        query = select(InventoryRecord).where(
            InventoryRecord.business_id == business_id,
            InventoryRecord.offering_id == offering_id,
            InventoryRecord.location_id == location_id,
        )
        if variant_id is None:
            query = query.where(InventoryRecord.variant_id.is_(None))
        else:
            query = query.where(InventoryRecord.variant_id == variant_id)
        result = await session.execute(query)
        return result.scalars().first()

    @staticmethod
    def require_track_inventory(offering: Offering) -> None:
        if not offering.track_inventory:
            raise ValidationError(
                "Offering does not track inventory",
                details={"offering_id": str(offering.id)},
            )

    @staticmethod
    def serialize_record(
        record: InventoryRecord,
        *,
        offering: Offering | None = None,
    ) -> dict[str, Any]:
        available = record.quantity_on_hand - record.quantity_reserved
        return {
            "id": str(record.id),
            "business_id": str(record.business_id),
            "offering_id": str(record.offering_id),
            "variant_id": str(record.variant_id) if record.variant_id else None,
            "location_id": str(record.location_id),
            "quantity_on_hand": record.quantity_on_hand,
            "quantity_reserved": record.quantity_reserved,
            "quantity_available": max(available, 0),
            "low_stock_threshold": record.low_stock_threshold,
            "stock_status": InventoryResolver.stock_status(record, offering=offering),
            "version": record.version,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
        }

    @staticmethod
    def serialize_movement(movement: InventoryMovement) -> dict[str, Any]:
        return {
            "id": str(movement.id),
            "business_id": str(movement.business_id),
            "offering_id": str(movement.offering_id),
            "variant_id": str(movement.variant_id) if movement.variant_id else None,
            "location_id": str(movement.location_id),
            "inventory_record_id": str(movement.inventory_record_id),
            "movement_type": movement.movement_type,
            "quantity_delta": movement.quantity_delta,
            "quantity_after": movement.quantity_after,
            "reason": movement.reason,
            "actor_identity_id": (
                str(movement.actor_identity_id) if movement.actor_identity_id else None
            ),
            "created_at": movement.created_at.isoformat(),
        }
