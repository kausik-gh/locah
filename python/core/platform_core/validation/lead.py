"""Lead domain validation (Stage 6 — Doc 11 §10.2)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from platform_core.exceptions import ResourceStateDenied, ValidationError
from platform_core.validation.contact import validate_email, validate_phone

DISPLAY_NAME_MIN = 1
DISPLAY_NAME_MAX = 160
MESSAGE_MAX = 4000
NOTE_BODY_MAX = 4000
REASON_MAX = 500

LEAD_STATUSES = frozenset({"new", "contacted", "qualified", "won", "lost"})
TERMINAL_STATUSES = frozenset({"won", "lost"})
LEAD_SOURCES = frozenset({"manual", "website_enquiry", "marketplace", "import"})

# Doc 11 §10.2: New → Contacted → Qualified → Won | Lost. A lead may also be
# marked Lost from any non-terminal state, and re-opened from Lost.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "new": frozenset({"contacted", "qualified", "won", "lost"}),
    "contacted": frozenset({"qualified", "won", "lost"}),
    "qualified": frozenset({"won", "lost"}),
    "won": frozenset(),
    "lost": frozenset({"new", "contacted", "qualified"}),
}

STATUS_EVENT_MAP: dict[str, str] = {
    "contacted": "lead.contacted",
    "qualified": "lead.qualified",
    "won": "lead.won",
    "lost": "lead.lost",
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


def validate_display_name(name: Any) -> str:
    if name is None or not str(name).strip():
        raise ValidationError(
            "Lead contact name is required",
            details={"errors": [_field_error("display_name", "Contact name is required")]},
        )
    normalized = str(name).strip()
    if not (DISPLAY_NAME_MIN <= len(normalized) <= DISPLAY_NAME_MAX):
        raise ValidationError(
            "Invalid contact name length",
            details={
                "errors": [
                    _field_error(
                        "display_name",
                        f"Contact name must be 1–{DISPLAY_NAME_MAX} characters",
                    )
                ]
            },
        )
    return normalized


def validate_message(message: Any) -> str | None:
    if message is None or not str(message).strip():
        return None
    normalized = str(message).strip()
    if len(normalized) > MESSAGE_MAX:
        raise ValidationError(
            "Message too long",
            details={"errors": [_field_error("message", f"At most {MESSAGE_MAX} characters")]},
        )
    return normalized


def validate_source(source: Any) -> str:
    if source is None:
        return "manual"
    normalized = str(source).strip().lower()
    if normalized not in LEAD_SOURCES:
        raise ValidationError(
            "Invalid lead source",
            details={
                "errors": [
                    _field_error("source", f"Must be one of: {', '.join(sorted(LEAD_SOURCES))}")
                ]
            },
        )
    return normalized


def validate_origin_context(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError(
            "origin_context must be an object",
            details={"errors": [_field_error("origin_context", "Must be a JSON object")]},
        )
    return value


def validate_follow_up_at(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            "Invalid follow-up timestamp",
            details={"errors": [_field_error("next_follow_up_at", "Must be an ISO-8601 datetime")]},
        ) from exc


def validate_reason(value: Any, *, field: str) -> str | None:
    if value is None or not str(value).strip():
        return None
    normalized = str(value).strip()
    if len(normalized) > REASON_MAX:
        raise ValidationError(
            "Reason too long",
            details={"errors": [_field_error(field, f"At most {REASON_MAX} characters")]},
        )
    return normalized


def validate_note_body(body: Any) -> str:
    if body is None or not str(body).strip():
        raise ValidationError(
            "Note body is required",
            details={"errors": [_field_error("body", "Note body is required")]},
        )
    normalized = str(body).strip()
    if len(normalized) > NOTE_BODY_MAX:
        raise ValidationError(
            "Note too long",
            details={"errors": [_field_error("body", f"At most {NOTE_BODY_MAX} characters")]},
        )
    return normalized


def assert_transition_allowed(current: str, target: str, *, action: str = "move lead stage") -> None:
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise ResourceStateDenied(
            "lead",
            current,
            action=action,
            allowed_states=sorted(allowed),
        )


def validate_create_payload(raw: dict[str, Any]) -> dict[str, Any]:
    email = raw.get("email")
    phone = raw.get("phone")
    return {
        "display_name": validate_display_name(raw.get("display_name")),
        "email": validate_email(email) if email else None,
        "phone": validate_phone(phone) if phone else None,
        "message": validate_message(raw.get("message")),
        "source": validate_source(raw.get("source")),
        "origin_context": validate_origin_context(raw.get("origin_context")),
        "offering_id": validate_optional_uuid(raw.get("offering_id"), field="offering_id"),
        "assignee_identity_id": validate_optional_uuid(
            raw.get("assignee_identity_id"), field="assignee_identity_id"
        ),
        "next_follow_up_at": validate_follow_up_at(raw.get("next_follow_up_at")),
    }


def validate_patch_payload(raw: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if "display_name" in raw:
        patch["display_name"] = validate_display_name(raw["display_name"])
    if "email" in raw:
        patch["email"] = validate_email(raw["email"]) if raw["email"] else None
    if "phone" in raw:
        patch["phone"] = validate_phone(raw["phone"]) if raw["phone"] else None
    if "message" in raw:
        patch["message"] = validate_message(raw["message"])
    if "offering_id" in raw:
        patch["offering_id"] = validate_optional_uuid(raw["offering_id"], field="offering_id")
    if "next_follow_up_at" in raw:
        patch["next_follow_up_at"] = validate_follow_up_at(raw["next_follow_up_at"])
    if not patch:
        raise ValidationError("No lead fields to update")
    return patch


def validate_move_stage_payload(raw: dict[str, Any], *, current_status: str) -> dict[str, Any]:
    target = str(raw.get("status") or "").strip().lower()
    if target not in LEAD_STATUSES:
        raise ValidationError(
            "Invalid lead status",
            details={
                "errors": [
                    _field_error("status", f"Must be one of: {', '.join(sorted(LEAD_STATUSES))}")
                ]
            },
        )
    assert_transition_allowed(current_status, target)
    reason = validate_reason(raw.get("reason"), field="reason")
    if target == "lost" and not reason:
        raise ValidationError(
            "A reason is required when marking a lead lost",
            details={"errors": [_field_error("reason", "Reason is required for lost leads")]},
        )
    return {"status": target, "reason": reason}


def validate_assign_payload(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "assignee_identity_id": validate_optional_uuid(
            raw.get("assignee_identity_id"), field="assignee_identity_id"
        )
    }
