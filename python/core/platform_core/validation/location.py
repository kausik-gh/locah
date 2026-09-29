"""Location domain validation (Stage 3)."""

from __future__ import annotations

import re
from typing import Any

from platform_core.exceptions import ValidationError
from platform_core.validation.contact import validate_email, validate_phone

LOCATION_NAME_MIN = 1
LOCATION_NAME_MAX = 120
INTERNAL_CODE_MAX = 64
NOTES_MAX = 2000
VALID_STATUSES = frozenset({"active", "archived"})
STOCK_ROLES = frozenset({"store", "warehouse", "van"})


def _field_error(field: str, message: str) -> dict[str, str]:
    return {"field": field, "message": message}


def validate_location_name(name: str | None) -> str:
    if name is None or not str(name).strip():
        raise ValidationError(
            "Location name is required",
            details={"errors": [_field_error("name", "Name is required")]},
        )
    normalized = str(name).strip()
    if len(normalized) < LOCATION_NAME_MIN or len(normalized) > LOCATION_NAME_MAX:
        raise ValidationError(
            "Invalid location name length",
            details={
                "errors": [
                    _field_error(
                        "name",
                        f"Name must be between {LOCATION_NAME_MIN} and {LOCATION_NAME_MAX} characters",
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


def validate_timezone(timezone: str | None) -> str:
    if timezone is None or not str(timezone).strip():
        return "UTC"
    return str(timezone).strip()


def validate_latitude(value: Any) -> float | None:
    if value is None:
        return None
    try:
        lat = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            "Invalid latitude",
            details={"errors": [_field_error("latitude", "Must be a numeric value")]},
        ) from exc
    if not (-90 <= lat <= 90):
        raise ValidationError(
            "Invalid latitude",
            details={"errors": [_field_error("latitude", "Must be between -90 and 90")]},
        )
    return lat


def validate_longitude(value: Any) -> float | None:
    if value is None:
        return None
    try:
        lng = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            "Invalid longitude",
            details={"errors": [_field_error("longitude", "Must be a numeric value")]},
        ) from exc
    if not (-180 <= lng <= 180):
        raise ValidationError(
            "Invalid longitude",
            details={"errors": [_field_error("longitude", "Must be between -180 and 180")]},
        )
    return lng


def validate_geo_pair(
    latitude: float | None, longitude: float | None
) -> tuple[float | None, float | None]:
    if latitude is None and longitude is None:
        return None, None
    if latitude is None or longitude is None:
        raise ValidationError(
            "Coordinates require both latitude and longitude",
            details={
                "errors": [
                    _field_error("latitude", "Both latitude and longitude are required"),
                    _field_error("longitude", "Both latitude and longitude are required"),
                ]
            },
        )
    return latitude, longitude


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


DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def validate_hours(value: Any) -> dict[str, Any] | None:
    """Weekly opening hours: {"mon": [["09:00", "13:00"], ["16:00", "21:00"]], ...}.

    A day left out or empty is closed. Up to three spans a day, each opening
    before it closes; an optional note ("Closed on festival days"). The same
    hours set when bookings and WhatsApp offer times (journeys._hours_for).
    """
    if value is None:
        return None
    bad = ValidationError("Invalid opening hours", details={"errors": [
        _field_error("hours", "Give each day's opening and closing times as HH:MM")]})
    if not isinstance(value, dict) or set(value) - {*DAYS, "note"}:
        raise bad
    out: dict[str, Any] = {}
    for day in DAYS:
        spans = value.get(day) or []
        if not isinstance(spans, list) or len(spans) > 3:
            raise bad
        clean = []
        for span in spans:
            if (not isinstance(span, (list, tuple)) or len(span) != 2
                    or not all(isinstance(t, str) and _HHMM.match(t) for t in span) or span[0] >= span[1]):
                raise bad
            clean.append([span[0], span[1]])
        clean.sort()
        if any(a[1] > b[0] for a, b in zip(clean, clean[1:], strict=False)):
            raise bad
        if clean:
            out[day] = clean
    note = value.get("note")
    if note is not None:
        if not isinstance(note, str) or len(note) > 200:
            raise bad
        if note.strip():
            out["note"] = note.strip()
    return out


def validate_location_create_payload(raw: dict[str, Any]) -> dict[str, Any]:
    latitude = validate_latitude(raw.get("latitude"))
    longitude = validate_longitude(raw.get("longitude"))
    latitude, longitude = validate_geo_pair(latitude, longitude)
    return {
        "name": validate_location_name(raw.get("name")),
        "timezone": validate_timezone(raw.get("timezone")),
        "address": raw.get("address"),
        "hours": validate_hours(raw.get("hours")),
        "internal_code": validate_internal_code(raw.get("internal_code")),
        "phone": validate_phone(raw.get("phone"), field="phone"),
        "email": validate_email(raw.get("email"), field="email"),
        "notes": validate_notes(raw.get("notes")),
        "latitude": latitude,
        "longitude": longitude,
        "is_primary": bool(raw.get("is_primary", False)),
        "stock_role": _stock_role(raw.get("stock_role"), default="store"),
    }


def validate_location_patch_payload(raw: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if "name" in raw:
        patch["name"] = validate_location_name(raw["name"])
    if "timezone" in raw:
        patch["timezone"] = validate_timezone(raw["timezone"])
    if "address" in raw:
        patch["address"] = raw["address"]
    if "hours" in raw:
        patch["hours"] = validate_hours(raw["hours"])
    if "internal_code" in raw:
        patch["internal_code"] = validate_internal_code(raw["internal_code"])
    if "phone" in raw:
        patch["phone"] = validate_phone(raw.get("phone"), field="phone")
    if "email" in raw:
        patch["email"] = validate_email(raw.get("email"), field="email")
    if "notes" in raw:
        patch["notes"] = validate_notes(raw["notes"])
    if "latitude" in raw or "longitude" in raw:
        latitude = validate_latitude(raw.get("latitude"))
        longitude = validate_longitude(raw.get("longitude"))
        latitude, longitude = validate_geo_pair(latitude, longitude)
        patch["latitude"] = latitude
        patch["longitude"] = longitude
    if "status" in raw:
        status = str(raw["status"]).strip().lower()
        if status not in VALID_STATUSES:
            raise ValidationError(
                "Invalid location status",
                details={
                    "errors": [
                        _field_error(
                            "status",
                            f"Status must be one of: {', '.join(sorted(VALID_STATUSES))}",
                        )
                    ]
                },
            )
        patch["status"] = status
    if "stock_role" in raw:
        patch["stock_role"] = _stock_role(raw.get("stock_role"), default="store")
    return patch


def _stock_role(raw: Any, *, default: str) -> str:
    if raw is None or str(raw).strip() == "":
        return default
    role = str(raw).strip().lower()
    if role not in STOCK_ROLES:
        raise ValidationError(
            "Location stock role must be store, warehouse, or van",
            details={"errors": [_field_error("stock_role", "Use store, warehouse, or van")]},
        )
    return role
