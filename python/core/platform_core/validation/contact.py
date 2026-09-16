"""Shared contact field validation (Stage 2E / Stage 3)."""

from __future__ import annotations

import re

from platform_core.exceptions import ValidationError

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def field_error(field: str, message: str) -> dict[str, str]:
    return {"field": field, "message": message}


def validate_email(value: str | None, *, field: str = "email") -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    if not _EMAIL_RE.match(normalized):
        raise ValidationError(
            "Invalid email address",
            details={"errors": [field_error(field, "invalid email address")]},
        )
    return normalized


def validate_phone(value: str | None, *, field: str = "phone") -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
