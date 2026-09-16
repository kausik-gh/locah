"""Payment validation (Stage 9)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from platform_core.exceptions import ResourceStateDenied, ValidationError

SOURCE_TYPES = frozenset({"order", "booking", "membership"})
PAYMENT_METHODS = frozenset({"online", "cod", "pay_at_business", "pay_later"})
PAYMENT_STATUSES = frozenset({
    "pending", "processing", "pending_offline", "succeeded",
    "failed", "partially_refunded", "refunded",
})
REFUNDABLE_STATUSES = frozenset({"succeeded", "partially_refunded"})
MERCHANT_STATUSES = frozenset(
    {"not_connected", "pending", "active", "suspended", "invalid_credentials"}
)
PROVIDERS = frozenset({"stub", "razorpay", "cod_only"})
REASON_MAX = 500

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"processing", "pending_offline", "failed"}),
    "processing": frozenset({"succeeded", "failed", "pending_offline"}),
    "pending_offline": frozenset({"succeeded", "failed"}),
    "succeeded": frozenset({"partially_refunded", "refunded"}),
    "partially_refunded": frozenset({"refunded"}),
    "failed": frozenset(),
    "refunded": frozenset(),
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
            "payment",
            current,
            action=action,
            allowed_states=sorted(allowed),
        )


def validate_create_payment_payload(raw: dict[str, Any]) -> dict[str, Any]:
    source_type = str(raw["source_type"]).strip().lower()
    if source_type not in SOURCE_TYPES:
        raise ValidationError(
            "Invalid payment source type",
            details={"errors": [_field_error("source_type", "Unsupported source")]},
        )
    payment_method = str(raw.get("payment_method") or "online").strip().lower()
    if payment_method not in PAYMENT_METHODS:
        raise ValidationError(
            "Invalid payment method",
            details={"errors": [_field_error("payment_method", "Unsupported method")]},
        )
    amount = Decimal(str(raw["amount"]))
    if amount <= 0:
        raise ValidationError(
            "Invalid payment amount",
            details={"errors": [_field_error("amount", "Must be > 0")]},
        )
    idempotency_key = raw.get("idempotency_key")
    if idempotency_key is not None:
        idempotency_key = str(idempotency_key).strip() or None
    return {
        "source_type": source_type,
        "source_id": validate_uuid(raw["source_id"], field="source_id"),
        "customer_contact_id": validate_optional_uuid(
            raw.get("customer_contact_id"), field="customer_contact_id"
        ),
        "amount": amount,
        "currency": str(raw.get("currency") or "INR").strip().upper(),
        "payment_method": payment_method,
        "idempotency_key": idempotency_key,
    }


def validate_refund_payload(raw: dict[str, Any], *, max_amount: Decimal) -> dict[str, Any]:
    amount = Decimal(str(raw["amount"]))
    if amount <= 0:
        raise ValidationError(
            "Invalid refund amount",
            details={"errors": [_field_error("amount", "Must be > 0")]},
        )
    if amount > max_amount:
        raise ValidationError(
            "Refund exceeds refundable balance",
            details={"max_refundable": str(max_amount), "requested": str(amount)},
        )
    reason = raw.get("reason")
    if reason is not None:
        reason = str(reason).strip() or None
        if reason and len(reason) > REASON_MAX:
            raise ValidationError(
                "Reason too long",
                details={"errors": [_field_error("reason", "Too long")]},
            )
    if not reason:
        raise ValidationError(
            "Refund reason is required",
            details={"errors": [_field_error("reason", "Required")]},
        )
    return {"amount": amount, "reason": reason}


def validate_merchant_update_payload(raw: dict[str, Any]) -> dict[str, Any]:
    provider = str(raw.get("provider") or "stub").strip().lower()
    if provider not in PROVIDERS:
        raise ValidationError(
            "Invalid payment provider",
            details={"errors": [_field_error("provider", "Unsupported provider")]},
        )
    status = str(raw.get("status") or "pending").strip().lower()
    if status not in MERCHANT_STATUSES:
        raise ValidationError(
            "Invalid merchant connection status",
            details={"errors": [_field_error("status", "Invalid status")]},
        )
    metadata = raw.get("provider_metadata") or {}
    if not isinstance(metadata, dict):
        raise ValidationError(
            "Invalid provider metadata",
            details={"errors": [_field_error("provider_metadata", "Must be an object")]},
        )
    return {"provider": provider, "status": status, "provider_metadata": metadata}
