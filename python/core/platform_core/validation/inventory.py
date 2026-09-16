"""Inventory validation (Stage 5)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from platform_core.exceptions import ValidationError

ADJUSTMENT_REASON_MAX = 500
MOVEMENT_TYPES = frozenset({"opening_stock", "adjustment"})


def _field_error(field: str, message: str) -> dict[str, str]:
    return {"field": field, "message": message}


def validate_uuid(value: Any, *, field: str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError as exc:
        raise ValidationError(
            f"Invalid UUID for {field}",
            details={"errors": [_field_error(field, "Must be a valid UUID")]},
        ) from exc


def validate_reason(reason: str | None) -> str:
    if reason is None or not str(reason).strip():
        raise ValidationError(
            "Reason is required for inventory adjustments",
            details={"errors": [_field_error("reason", "Reason is required")]},
        )
    normalized = str(reason).strip()
    if len(normalized) > ADJUSTMENT_REASON_MAX:
        raise ValidationError(
            "Reason too long",
            details={"errors": [_field_error("reason", "Too long")]},
        )
    return normalized


def validate_adjustment_payload(raw: dict[str, Any]) -> dict[str, Any]:
    quantity_delta = int(raw["quantity_delta"])
    if quantity_delta == 0:
        raise ValidationError(
            "Adjustment delta cannot be zero",
            details={"errors": [_field_error("quantity_delta", "Must be non-zero")]},
        )
    movement_type = str(raw.get("movement_type") or "adjustment").strip().lower()
    if movement_type not in MOVEMENT_TYPES:
        raise ValidationError(
            "Invalid movement type",
            details={"errors": [_field_error("movement_type", "Unsupported type")]},
        )
    return {
        "offering_id": validate_uuid(raw["offering_id"], field="offering_id"),
        "location_id": validate_uuid(raw["location_id"], field="location_id"),
        "variant_id": validate_uuid(raw["variant_id"], field="variant_id") if raw.get("variant_id") else None,
        "quantity_delta": quantity_delta,
        "movement_type": movement_type,
        "reason": validate_reason(raw.get("reason")),
    }


def validate_opening_stock_payload(raw: dict[str, Any]) -> dict[str, Any]:
    quantity = int(raw["quantity"])
    if quantity < 0:
        raise ValidationError(
            "Opening stock cannot be negative",
            details={"errors": [_field_error("quantity", "Must be >= 0")]},
        )
    return {
        "offering_id": validate_uuid(raw["offering_id"], field="offering_id"),
        "location_id": validate_uuid(raw["location_id"], field="location_id"),
        "variant_id": validate_uuid(raw["variant_id"], field="variant_id") if raw.get("variant_id") else None,
        "quantity": quantity,
        "reason": validate_reason(raw.get("reason") or "Opening stock"),
    }
