"""Employee domain validation (Stage 3)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from platform_core.exceptions import ValidationError
from platform_core.validation.contact import validate_email, validate_phone

DISPLAY_NAME_MIN = 1
DISPLAY_NAME_MAX = 120
INTERNAL_CODE_MAX = 64
NOTES_MAX = 2000
VALID_STATUSES = frozenset({"active", "inactive", "archived"})


def _field_error(field: str, message: str) -> dict[str, str]:
    return {"field": field, "message": message}


def validate_display_name(name: str | None) -> str:
    if name is None or not str(name).strip():
        raise ValidationError(
            "Employee display name is required",
            details={"errors": [_field_error("display_name", "Display name is required")]},
        )
    normalized = str(name).strip()
    if len(normalized) < DISPLAY_NAME_MIN or len(normalized) > DISPLAY_NAME_MAX:
        raise ValidationError(
            "Invalid display name length",
            details={
                "errors": [
                    _field_error(
                        "display_name",
                        f"Display name must be between {DISPLAY_NAME_MIN} and {DISPLAY_NAME_MAX} characters",
                    )
                ]
            },
        )
    return normalized


def validate_internal_code(code: str | None) -> str | None:
    if code is None:
        return None
    normalized = str(code).strip()
    if not normalized:
        return None
    if len(normalized) > INTERNAL_CODE_MAX:
        raise ValidationError(
            "Internal code too long",
            details={
                "errors": [
                    _field_error(
                        "internal_code",
                        f"Internal code must be at most {INTERNAL_CODE_MAX} characters",
                    )
                ]
            },
        )
    return normalized


def validate_notes(notes: str | None) -> str | None:
    if notes is None:
        return None
    normalized = str(notes).strip()
    if not normalized:
        return None
    if len(normalized) > NOTES_MAX:
        raise ValidationError(
            "Notes too long",
            details={
                "errors": [_field_error("notes", f"Notes must be at most {NOTES_MAX} characters")]
            },
        )
    return normalized


def validate_status(status: str | None, *, field: str = "status") -> str:
    if status is None:
        return "active"
    normalized = str(status).strip().lower()
    if normalized not in VALID_STATUSES:
        raise ValidationError(
            "Invalid employee status",
            details={
                "errors": [
                    _field_error(
                        field,
                        f"Status must be one of: {', '.join(sorted(VALID_STATUSES))}",
                    )
                ]
            },
        )
    return normalized


def validate_optional_uuid(value: Any, *, field: str) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError as exc:
        raise ValidationError(
            f"Invalid UUID for {field}",
            details={"errors": [_field_error(field, "Must be a valid UUID")]},
        ) from exc


def validate_location_id_list(values: Any) -> list[UUID]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValidationError(
            "location_ids must be a list",
            details={"errors": [_field_error("location_ids", "Must be a list of UUIDs")]},
        )
    parsed: list[UUID] = []
    for index, value in enumerate(values):
        item = validate_optional_uuid(value, field=f"location_ids[{index}]")
        if item is not None:
            parsed.append(item)
    return parsed


def validate_employee_create_payload(raw: dict[str, Any]) -> dict[str, Any]:
    location_ids = validate_location_id_list(raw.get("location_ids"))
    primary_location_id = validate_optional_uuid(
        raw.get("primary_location_id"), field="primary_location_id"
    )
    if primary_location_id is not None and primary_location_id not in location_ids:
        location_ids.append(primary_location_id)
    return {
        "display_name": validate_display_name(raw.get("display_name")),
        "email": validate_email(raw.get("email"), field="email"),
        "phone": validate_phone(raw.get("phone"), field="phone"),
        "designation": (str(raw["designation"]).strip() if raw.get("designation") else None),
        "internal_code": validate_internal_code(raw.get("internal_code")),
        "status": validate_status(raw.get("status")),
        "notes": validate_notes(raw.get("notes")),
        "identity_id": validate_optional_uuid(raw.get("identity_id"), field="identity_id"),
        "membership_id": validate_optional_uuid(raw.get("membership_id"), field="membership_id"),
        "location_ids": location_ids,
        "primary_location_id": primary_location_id,
    }


def validate_employee_patch_payload(raw: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if "display_name" in raw:
        patch["display_name"] = validate_display_name(raw["display_name"])
    if "email" in raw:
        patch["email"] = validate_email(raw.get("email"), field="email")
    if "phone" in raw:
        patch["phone"] = validate_phone(raw.get("phone"), field="phone")
    if "designation" in raw:
        patch["designation"] = (
            str(raw["designation"]).strip() if raw.get("designation") else None
        )
    if "internal_code" in raw:
        patch["internal_code"] = validate_internal_code(raw["internal_code"])
    if "status" in raw:
        patch["status"] = validate_status(raw["status"])
    if "notes" in raw:
        patch["notes"] = validate_notes(raw["notes"])
    if "identity_id" in raw:
        patch["identity_id"] = validate_optional_uuid(raw["identity_id"], field="identity_id")
    if "membership_id" in raw:
        patch["membership_id"] = validate_optional_uuid(
            raw["membership_id"], field="membership_id"
        )
    return patch
