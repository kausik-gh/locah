"""Customer domain validation (Stage 4)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from platform_core.exceptions import ValidationError
from platform_core.validation.contact import validate_email, validate_phone

DISPLAY_NAME_MIN = 1
DISPLAY_NAME_MAX = 120
TAG_MAX = 64
TAGS_MAX = 20
NOTE_BODY_MAX = 4000
VALID_STATUSES = frozenset({"active", "blocked", "archived"})


def _field_error(field: str, message: str) -> dict[str, str]:
    return {"field": field, "message": message}


def validate_display_name(name: str | None) -> str:
    if name is None or not str(name).strip():
        raise ValidationError(
            "Customer display name is required",
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


def validate_tags(tags: Any) -> list[str]:
    if tags is None:
        return []
    if not isinstance(tags, list):
        raise ValidationError(
            "Tags must be a list",
            details={"errors": [_field_error("tags", "Must be a list of strings")]},
        )
    if len(tags) > TAGS_MAX:
        raise ValidationError(
            "Too many tags",
            details={"errors": [_field_error("tags", f"At most {TAGS_MAX} tags allowed")]},
        )
    normalized: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(tags):
        if not isinstance(raw, str):
            raise ValidationError(
                "Invalid tag",
                details={"errors": [_field_error(f"tags[{index}]", "Must be a string")]},
            )
        tag = raw.strip().lower()
        if not tag:
            continue
        if len(tag) > TAG_MAX:
            raise ValidationError(
                "Tag too long",
                details={
                    "errors": [_field_error(f"tags[{index}]", f"Tag must be at most {TAG_MAX} characters")]
                },
            )
        if tag not in seen:
            seen.add(tag)
            normalized.append(tag)
    return normalized


def validate_status(status: str | None, *, field: str = "status") -> str:
    if status is None:
        return "active"
    normalized = str(status).strip().lower()
    if normalized not in VALID_STATUSES:
        raise ValidationError(
            "Invalid customer status",
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


def validate_note_body(body: str | None) -> str:
    if body is None or not str(body).strip():
        raise ValidationError(
            "Note body is required",
            details={"errors": [_field_error("body", "Note body is required")]},
        )
    normalized = str(body).strip()
    if len(normalized) > NOTE_BODY_MAX:
        raise ValidationError(
            "Note too long",
            details={
                "errors": [_field_error("body", f"Note must be at most {NOTE_BODY_MAX} characters")]
            },
        )
    return normalized


def validate_customer_create_payload(raw: dict[str, Any]) -> dict[str, Any]:
    phone = validate_phone(raw.get("phone"), field="phone")
    email = validate_email(raw.get("email"), field="email")
    if not phone and not email:
        raise ValidationError(
            "Customer requires at least one contact method",
            details={
                "errors": [
                    _field_error("phone", "Provide phone or email"),
                    _field_error("email", "Provide phone or email"),
                ]
            },
        )
    return {
        "display_name": validate_display_name(raw.get("display_name")),
        "phone": phone,
        "email": email,
        "status": validate_status(raw.get("status")),
        "tags": validate_tags(raw.get("tags")),
        "identity_id": validate_optional_uuid(raw.get("identity_id"), field="identity_id"),
        "preferred_location_id": validate_optional_uuid(
            raw.get("preferred_location_id"), field="preferred_location_id"
        ),
    }


def validate_customer_patch_payload(raw: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if "display_name" in raw:
        patch["display_name"] = validate_display_name(raw["display_name"])
    if "phone" in raw:
        patch["phone"] = validate_phone(raw.get("phone"), field="phone")
    if "email" in raw:
        patch["email"] = validate_email(raw.get("email"), field="email")
    if "status" in raw:
        patch["status"] = validate_status(raw["status"])
    if "tags" in raw:
        patch["tags"] = validate_tags(raw["tags"])
    if "identity_id" in raw:
        patch["identity_id"] = validate_optional_uuid(raw["identity_id"], field="identity_id")
    if "preferred_location_id" in raw:
        patch["preferred_location_id"] = validate_optional_uuid(
            raw["preferred_location_id"], field="preferred_location_id"
        )
    return patch
