"""Booking validation (Stage 7)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from platform_core.exceptions import ResourceStateDenied, ValidationError

BOOKING_STATUSES = frozenset({
    "pending", "confirmed", "checked_in", "completed", "cancelled", "rejected", "no_show",
})
TERMINAL_STATUSES = frozenset({"completed", "cancelled", "rejected", "no_show"})
RESERVATION_MODES = frozenset({
    "appointment", "accommodation", "table", "class_session", "rental",
})
RESERVABLE_OFFERING_TYPES = frozenset({
    "service", "accommodation", "class_session", "rental", "menu_item", "product",
})
PAYMENT_METHODS = frozenset({"cod", "online", "pay_at_business", "pay_later"})
PAYMENT_STATUSES = frozenset({
    "pending", "pending_offline", "deposit_paid", "paid", "refunded",
})
NOTE_BODY_MAX = 5000
REASON_MAX = 500

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"confirmed", "rejected", "cancelled"}),
    "confirmed": frozenset({"checked_in", "cancelled", "no_show"}),
    "checked_in": frozenset({"completed", "cancelled", "no_show"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
    "rejected": frozenset(),
    "no_show": frozenset(),
}

RESCHEDULABLE_STATUSES = frozenset({"pending", "confirmed"})

STATUS_EVENT_MAP: dict[str, str] = {
    "confirmed": "booking.confirmed",
    "rejected": "booking.rejected",
    "checked_in": "booking.checked_in",
    "completed": "booking.completed",
    "cancelled": "booking.cancelled",
    "no_show": "booking.no_show",
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


def parse_datetime(value: Any, *, field: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValidationError(
                f"Invalid datetime for {field}",
                details={"errors": [_field_error(field, "Invalid ISO datetime")]},
            ) from exc
    raise ValidationError(
        f"Invalid datetime for {field}",
        details={"errors": [_field_error(field, "Required datetime")]},
    )


def assert_transition_allowed(current: str, target: str, *, action: str = "update") -> None:
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise ResourceStateDenied(
            "booking",
            current,
            action=action,
            allowed_states=sorted(allowed),
        )


def validate_slot_times(starts_at: datetime, ends_at: datetime) -> None:
    if ends_at <= starts_at:
        raise ValidationError(
            "Booking end must be after start",
            details={"errors": [_field_error("ends_at", "Must be after starts_at")]},
        )


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


def validate_create_payload(raw: dict[str, Any]) -> dict[str, Any]:
    mode = str(raw.get("reservation_mode") or "appointment").strip().lower()
    if mode not in RESERVATION_MODES:
        raise ValidationError(
            "Invalid reservation mode",
            details={"errors": [_field_error("reservation_mode", "Unsupported mode")]},
        )
    starts_at = parse_datetime(raw["starts_at"], field="starts_at")
    ends_at = parse_datetime(raw["ends_at"], field="ends_at")
    validate_slot_times(starts_at, ends_at)
    party_size = int(raw.get("party_size") or 1)
    if party_size <= 0:
        raise ValidationError(
            "Invalid party size",
            details={"errors": [_field_error("party_size", "Must be > 0")]},
        )
    guest_count = raw.get("guest_count")
    parsed_guest: int | None = int(guest_count) if guest_count is not None else None
    capacity = raw.get("capacity")
    parsed_capacity: int | None = int(capacity) if capacity is not None else None
    payment_method = str(raw.get("payment_method") or "cod").strip().lower()
    if payment_method not in PAYMENT_METHODS:
        raise ValidationError(
            "Invalid payment method",
            details={"errors": [_field_error("payment_method", "Unsupported")]},
        )
    idempotency_key = raw.get("idempotency_key")
    if idempotency_key is not None:
        idempotency_key = str(idempotency_key).strip() or None
    title = raw.get("title")
    if title is not None:
        title = str(title).strip() or None
    return {
        "location_id": validate_uuid(raw["location_id"], field="location_id"),
        "customer_contact_id": validate_optional_uuid(
            raw.get("customer_contact_id"), field="customer_contact_id"
        ),
        "offering_id": validate_optional_uuid(raw.get("offering_id"), field="offering_id"),
        "provider_id": validate_optional_uuid(
            raw.get("provider_id") or raw.get("employee_id"), field="provider_id"
        ),
        "reservation_mode": mode,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "party_size": party_size,
        "guest_count": parsed_guest,
        "capacity": parsed_capacity,
        "payment_method": payment_method,
        "title": title,
        "internal_reference": (
            str(raw["internal_reference"]).strip() if raw.get("internal_reference") else None
        ),
        "idempotency_key": idempotency_key,
    }


def validate_status_transition_payload(raw: dict[str, Any], *, current_status: str) -> dict[str, Any]:
    target = str(raw["status"]).strip().lower()
    if target not in BOOKING_STATUSES:
        raise ValidationError(
            "Invalid booking status",
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
    if target in {"cancelled", "rejected", "no_show"} and not reason:
        raise ValidationError(
            "Reason is required",
            details={"errors": [_field_error("reason", "Required")]},
        )
    return {"status": target, "reason": reason}


def validate_reschedule_payload(raw: dict[str, Any], *, current_status: str) -> dict[str, Any]:
    if current_status not in RESCHEDULABLE_STATUSES:
        raise ResourceStateDenied(
            "booking",
            current_status,
            action="reschedule",
            allowed_states=sorted(RESCHEDULABLE_STATUSES),
        )
    starts_at = parse_datetime(raw["starts_at"], field="starts_at")
    ends_at = parse_datetime(raw["ends_at"], field="ends_at")
    validate_slot_times(starts_at, ends_at)
    reason = raw.get("reason")
    if reason is not None:
        reason = str(reason).strip() or None
    return {"starts_at": starts_at, "ends_at": ends_at, "reason": reason}


def validate_availability_query(raw: dict[str, Any]) -> dict[str, Any]:
    starts_at = parse_datetime(raw["starts_at"], field="starts_at")
    ends_at = parse_datetime(raw["ends_at"], field="ends_at")
    validate_slot_times(starts_at, ends_at)
    mode = str(raw.get("reservation_mode") or "appointment").strip().lower()
    if mode not in RESERVATION_MODES:
        raise ValidationError(
            "Invalid reservation mode",
            details={"errors": [_field_error("reservation_mode", "Unsupported")]},
        )
    party_size = int(raw.get("party_size") or 1)
    return {
        "location_id": validate_uuid(raw["location_id"], field="location_id"),
        "provider_id": validate_optional_uuid(
            raw.get("provider_id") or raw.get("employee_id"), field="provider_id"
        ),
        "offering_id": validate_optional_uuid(raw.get("offering_id"), field="offering_id"),
        "reservation_mode": mode,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "party_size": party_size,
        "capacity": int(raw["capacity"]) if raw.get("capacity") is not None else None,
        "exclude_booking_id": validate_optional_uuid(
            raw.get("exclude_booking_id"), field="exclude_booking_id"
        ),
    }


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
