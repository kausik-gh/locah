"""Membership domain validation (Stage 6 — Doc 11 §9.5).

Fixed-duration plans and explicit manual renewal only. `recurring` billing is
reserved for FL-DEC-005 and is rejected at write time until that decision closes.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from platform_core.exceptions import ResourceStateDenied, ValidationError

NAME_MIN = 1
NAME_MAX = 160
DESC_MAX = 2000
REASON_MAX = 500
DURATION_MAX_DAYS = 3650

PLAN_STATUSES = frozenset({"draft", "active", "archived"})
PLAN_VISIBILITY = frozenset({"public", "private"})
BILLING_MODELS = frozenset({"fixed_duration", "recurring"})
LAUNCH_BILLING_MODELS = frozenset({"fixed_duration"})  # FL-DEC-005 gate

ENROLMENT_STATUSES = frozenset(
    {"pending", "active", "paused", "expired", "cancelled", "completed"}
)
ENROLMENT_TERMINAL = frozenset({"expired", "cancelled", "completed"})
PAYMENT_METHODS = frozenset({"cod", "online", "pay_at_business", "pay_later"})

# Manual lifecycle. Expiry is service/scheduler-driven from `ends_at`.
ALLOWED_ENROLMENT_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"active", "cancelled"}),
    "active": frozenset({"paused", "cancelled", "expired", "completed"}),
    "paused": frozenset({"active", "cancelled", "expired"}),
    "expired": frozenset(),
    "cancelled": frozenset(),
    "completed": frozenset(),
}

ENROLMENT_STATUS_EVENT_MAP: dict[str, str] = {
    "active": "membership.enrolment.activated",
    "paused": "membership.enrolment.paused",
    "expired": "membership.enrolment.expired",
    "cancelled": "membership.enrolment.cancelled",
    "completed": "membership.enrolment.completed",
}


def _field_error(field: str, message: str) -> dict[str, str]:
    return {"field": field, "message": message}


def validate_uuid(value: Any, *, field: str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            f"Invalid UUID for {field}",
            details={"errors": [_field_error(field, "Must be a valid UUID")]},
        ) from exc


def validate_optional_uuid(value: Any, *, field: str) -> UUID | None:
    if value is None:
        return None
    return validate_uuid(value, field=field)


def validate_name(name: Any) -> str:
    if name is None or not str(name).strip():
        raise ValidationError(
            "Plan name is required",
            details={"errors": [_field_error("name", "Plan name is required")]},
        )
    normalized = str(name).strip()
    if not (NAME_MIN <= len(normalized) <= NAME_MAX):
        raise ValidationError(
            "Invalid plan name length",
            details={"errors": [_field_error("name", f"Name must be 1–{NAME_MAX} characters")]},
        )
    return normalized


def validate_description(value: Any) -> str | None:
    if value is None or not str(value).strip():
        return None
    normalized = str(value).strip()
    if len(normalized) > DESC_MAX:
        raise ValidationError(
            "Description too long",
            details={"errors": [_field_error("description", f"At most {DESC_MAX} characters")]},
        )
    return normalized


def validate_amount(value: Any, *, field: str = "price_amount") -> float:
    if value is None:
        return 0.0
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValidationError(
            "Invalid amount",
            details={"errors": [_field_error(field, "Must be a number")]},
        ) from exc
    if amount < 0:
        raise ValidationError(
            "Amount cannot be negative",
            details={"errors": [_field_error(field, "Must be zero or positive")]},
        )
    return float(amount)


def validate_currency(value: Any) -> str:
    return str(value or "INR").strip().upper()


def validate_billing_model(value: Any) -> str:
    normalized = str(value or "fixed_duration").strip().lower()
    if normalized not in BILLING_MODELS:
        raise ValidationError(
            "Invalid billing model",
            details={
                "errors": [
                    _field_error(
                        "billing_model",
                        f"Must be one of: {', '.join(sorted(BILLING_MODELS))}",
                    )
                ]
            },
        )
    if normalized not in LAUNCH_BILLING_MODELS:
        raise ValidationError(
            "Recurring membership billing is not available at First Launch",
            details={
                "errors": [
                    _field_error(
                        "billing_model",
                        "Only fixed_duration plans can be created (FL-DEC-005 pending)",
                    )
                ]
            },
        )
    return normalized


def validate_duration_days(value: Any, *, required: bool = True) -> int | None:
    if value is None:
        if required:
            raise ValidationError(
                "Plan duration is required",
                details={
                    "errors": [_field_error("duration_days", "duration_days is required")]
                },
            )
        return None
    try:
        days = int(value)
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            "Invalid duration",
            details={"errors": [_field_error("duration_days", "Must be a whole number of days")]},
        ) from exc
    if not (1 <= days <= DURATION_MAX_DAYS):
        raise ValidationError(
            "Duration out of range",
            details={
                "errors": [
                    _field_error("duration_days", f"Must be between 1 and {DURATION_MAX_DAYS} days")
                ]
            },
        )
    return days


def validate_plan_status(value: Any) -> str:
    normalized = str(value or "draft").strip().lower()
    if normalized not in PLAN_STATUSES:
        raise ValidationError(
            "Invalid plan status",
            details={
                "errors": [
                    _field_error("status", f"Must be one of: {', '.join(sorted(PLAN_STATUSES))}")
                ]
            },
        )
    return normalized


def validate_visibility(value: Any) -> str:
    normalized = str(value or "private").strip().lower()
    if normalized not in PLAN_VISIBILITY:
        raise ValidationError(
            "Invalid visibility",
            details={
                "errors": [
                    _field_error("visibility", f"Must be one of: {', '.join(sorted(PLAN_VISIBILITY))}")
                ]
            },
        )
    return normalized


def validate_reason(value: Any, *, field: str = "reason") -> str | None:
    if value is None or not str(value).strip():
        return None
    normalized = str(value).strip()
    if len(normalized) > REASON_MAX:
        raise ValidationError(
            "Reason too long",
            details={"errors": [_field_error(field, f"At most {REASON_MAX} characters")]},
        )
    return normalized


def validate_datetime(value: Any, *, field: str) -> datetime:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            f"Invalid timestamp for {field}",
            details={"errors": [_field_error(field, "Must be an ISO-8601 datetime")]},
        ) from exc


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------
def validate_plan_create_payload(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": validate_name(raw.get("name")),
        "description": validate_description(raw.get("description")),
        "offering_id": validate_optional_uuid(raw.get("offering_id"), field="offering_id"),
        "price_amount": validate_amount(raw.get("price_amount")),
        "currency": validate_currency(raw.get("currency")),
        "billing_model": validate_billing_model(raw.get("billing_model")),
        "duration_days": validate_duration_days(raw.get("duration_days"), required=True),
        "status": validate_plan_status(raw.get("status")),
        "visibility": validate_visibility(raw.get("visibility")),
        "offering_access": _validate_offering_access(raw.get("offering_access")),
    }


def validate_plan_patch_payload(raw: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if "name" in raw:
        patch["name"] = validate_name(raw["name"])
    if "description" in raw:
        patch["description"] = validate_description(raw["description"])
    if "offering_id" in raw:
        patch["offering_id"] = validate_optional_uuid(raw["offering_id"], field="offering_id")
    if "price_amount" in raw:
        patch["price_amount"] = validate_amount(raw["price_amount"])
    if "currency" in raw:
        patch["currency"] = validate_currency(raw["currency"])
    if "duration_days" in raw:
        patch["duration_days"] = validate_duration_days(raw["duration_days"], required=False)
    if "status" in raw:
        patch["status"] = validate_plan_status(raw["status"])
    if "visibility" in raw:
        patch["visibility"] = validate_visibility(raw["visibility"])
    if "offering_access" in raw:
        patch["offering_access"] = _validate_offering_access(raw["offering_access"])
    if not patch:
        raise ValidationError("No plan fields to update")
    return patch


def _validate_offering_access(value: Any) -> list[UUID]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError(
            "offering_access must be a list of offering ids",
            details={"errors": [_field_error("offering_access", "Must be a list of UUIDs")]},
        )
    return [validate_uuid(v, field=f"offering_access[{i}]") for i, v in enumerate(value)]


def validate_enrolment_create_payload(raw: dict[str, Any]) -> dict[str, Any]:
    method = str(raw.get("payment_method") or "cod").strip().lower()
    if method not in PAYMENT_METHODS:
        raise ValidationError(
            "Invalid payment method",
            details={
                "errors": [
                    _field_error(
                        "payment_method", f"Must be one of: {', '.join(sorted(PAYMENT_METHODS))}"
                    )
                ]
            },
        )
    starts_at = (
        validate_datetime(raw["starts_at"], field="starts_at") if raw.get("starts_at") else None
    )
    return {
        "plan_id": validate_uuid(raw.get("plan_id"), field="plan_id"),
        "customer_contact_id": validate_uuid(
            raw.get("customer_contact_id"), field="customer_contact_id"
        ),
        "starts_at": starts_at,
        "payment_method": method,
        "auto_renew": bool(raw.get("auto_renew", False)),
        "idempotency_key": (str(raw["idempotency_key"]) if raw.get("idempotency_key") else None),
    }


def assert_enrolment_transition_allowed(
    current: str, target: str, *, action: str = "update enrolment"
) -> None:
    allowed = ALLOWED_ENROLMENT_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise ResourceStateDenied(
            "membership_enrolment",
            current,
            action=action,
            allowed_states=sorted(allowed),
        )
