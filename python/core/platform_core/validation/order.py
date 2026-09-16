"""Order validation (Stage 6)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from platform_core.exceptions import ResourceStateDenied, ValidationError

ORDER_STATUSES = frozenset({
    "pending", "accepted", "preparing", "ready", "completed", "cancelled", "rejected",
})
TERMINAL_STATUSES = frozenset({"completed", "cancelled", "rejected"})
PAYMENT_METHODS = frozenset({"cod", "online", "pay_at_business", "pay_later"})
PAYMENT_STATUSES = frozenset({"pending", "pending_offline", "paid", "refunded"})
NOTE_BODY_MAX = 5000
INTERNAL_REF_MAX = 120
REASON_MAX = 500

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"accepted", "rejected", "cancelled"}),
    "accepted": frozenset({"preparing", "cancelled"}),
    "preparing": frozenset({"ready", "cancelled"}),
    "ready": frozenset({"completed", "cancelled"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
    "rejected": frozenset(),
}

STATUS_EVENT_MAP: dict[str, str] = {
    "accepted": "order.accepted",
    "preparing": "order.preparing",
    "ready": "order.ready",
    "completed": "order.completed",
    "cancelled": "order.cancelled",
    "rejected": "order.rejected",
}


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


def validate_optional_uuid(value: Any, *, field: str) -> UUID | None:
    if value is None:
        return None
    return validate_uuid(value, field=field)


def assert_transition_allowed(current: str, target: str, *, action: str = "update") -> None:
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise ResourceStateDenied(
            "order",
            current,
            action=action,
            allowed_states=sorted(allowed),
        )


def validate_line_item(raw: dict[str, Any], *, index: int) -> dict[str, Any]:
    prefix = f"items[{index}]"
    offering_id = validate_uuid(raw.get("offering_id"), field=f"{prefix}.offering_id")
    variant_id = validate_optional_uuid(raw.get("variant_id"), field=f"{prefix}.variant_id")
    quantity = int(raw.get("quantity", 0))
    if quantity <= 0:
        raise ValidationError(
            "Invalid line quantity",
            details={"errors": [_field_error(f"{prefix}.quantity", "Must be > 0")]},
        )
    unit_price = raw.get("unit_price")
    parsed_price: Decimal | None = None
    if unit_price is not None:
        parsed_price = Decimal(str(unit_price))
        if parsed_price < 0:
            raise ValidationError(
                "Invalid unit price",
                details={"errors": [_field_error(f"{prefix}.unit_price", "Must be >= 0")]},
            )
    return {
        "offering_id": offering_id,
        "variant_id": variant_id,
        "quantity": quantity,
        "unit_price": parsed_price,
    }


def validate_create_payload(raw: dict[str, Any]) -> dict[str, Any]:
    items = raw.get("items") or []
    if not items:
        raise ValidationError(
            "Order must have at least one line item",
            details={"errors": [_field_error("items", "Required")]},
        )
    payment_method = str(raw.get("payment_method") or "cod").strip().lower()
    if payment_method not in PAYMENT_METHODS:
        raise ValidationError(
            "Invalid payment method",
            details={"errors": [_field_error("payment_method", "Unsupported method")]},
        )
    discount = Decimal(str(raw.get("discount_amount") or 0))
    if discount < 0:
        raise ValidationError(
            "Invalid discount",
            details={"errors": [_field_error("discount_amount", "Must be >= 0")]},
        )
    internal_ref = raw.get("internal_reference")
    if internal_ref is not None:
        internal_ref = str(internal_ref).strip() or None
        if internal_ref and len(internal_ref) > INTERNAL_REF_MAX:
            raise ValidationError(
                "Internal reference too long",
                details={"errors": [_field_error("internal_reference", "Too long")]},
            )
    idempotency_key = raw.get("idempotency_key")
    if idempotency_key is not None:
        idempotency_key = str(idempotency_key).strip() or None
    return {
        "location_id": validate_uuid(raw["location_id"], field="location_id"),
        "customer_contact_id": validate_optional_uuid(
            raw.get("customer_contact_id"), field="customer_contact_id"
        ),
        "payment_method": payment_method,
        "currency": str(raw.get("currency") or "INR").strip().upper(),
        "discount_amount": discount,
        "internal_reference": internal_ref,
        "idempotency_key": idempotency_key,
        "items": [validate_line_item(item, index=i) for i, item in enumerate(items)],
    }


def validate_patch_payload(raw: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if "internal_reference" in raw:
        ref = raw["internal_reference"]
        patch["internal_reference"] = str(ref).strip() if ref else None
    if "payment_status" in raw:
        ps = str(raw["payment_status"]).strip().lower()
        if ps not in PAYMENT_STATUSES:
            raise ValidationError(
                "Invalid payment status",
                details={"errors": [_field_error("payment_status", "Invalid")]},
            )
        patch["payment_status"] = ps
    return patch


def validate_status_transition_payload(raw: dict[str, Any], *, current_status: str) -> dict[str, Any]:
    target = str(raw["status"]).strip().lower()
    if target not in ORDER_STATUSES:
        raise ValidationError(
            "Invalid order status",
            details={"errors": [_field_error("status", "Invalid status")]},
        )
    assert_transition_allowed(current_status, target, action="transition")
    reason = raw.get("reason")
    if reason is not None:
        reason = str(reason).strip() or None
        if reason and len(reason) > REASON_MAX:
            raise ValidationError(
                "Reason too long",
                details={"errors": [_field_error("reason", "Too long")]},
            )
    if target in {"cancelled", "rejected"} and not reason:
        raise ValidationError(
            "Reason is required for cancellation or rejection",
            details={"errors": [_field_error("reason", "Required")]},
        )
    return {"status": target, "reason": reason}


def validate_note_body(body: str | None) -> str:
    if body is None or not str(body).strip():
        raise ValidationError(
            "Note body is required",
            details={"errors": [_field_error("body", "Required")]},
        )
    normalized = str(body).strip()
    if len(normalized) > NOTE_BODY_MAX:
        raise ValidationError(
            "Note too long",
            details={"errors": [_field_error("body", "Too long")]},
        )
    return normalized
