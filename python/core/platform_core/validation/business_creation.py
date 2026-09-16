"""Business creation input validation (Stage 2A)."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from platform_core.business_types import (
    DEFAULT_BUSINESS_TYPE,
    DEFAULT_COUNTRY,
    DEFAULT_CURRENCY,
    DEFAULT_LANGUAGE,
    DEFAULT_TIMEZONE,
    DISPLAY_NAME_MAX,
    DISPLAY_NAME_MIN,
    RESERVED_SLUGS,
    SLUG_MAX,
    SLUG_MIN,
    SUPPORTED_BUSINESS_TYPES,
    SUPPORTED_COUNTRIES,
    SUPPORTED_CURRENCIES,
    SUPPORTED_LANGUAGES,
    SUPPORTED_TIMEZONES,
)
from platform_core.exceptions import ValidationError

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _field_error(field: str, message: str) -> dict[str, str]:
    return {"field": field, "message": message}


class BusinessCreationInput:
    """Normalized, validated create payload."""

    def __init__(
        self,
        *,
        display_name: str,
        business_type: str,
        slug: str | None,
        logo_asset_id: UUID | None,
        timezone: str,
        currency: str,
        country: str,
        language: str,
    ) -> None:
        self.display_name = display_name
        self.business_type = business_type
        self.slug = slug
        self.logo_asset_id = logo_asset_id
        self.timezone = timezone
        self.currency = currency
        self.country = country
        self.language = language


def validate_business_creation_payload(raw: dict[str, Any]) -> BusinessCreationInput:
    errors: list[dict[str, str]] = []

    # Reject oversized / malformed top-level payloads early
    if len(raw) > 20:
        raise ValidationError("Request payload has too many fields", details={"fields": len(raw)})

    display_name_raw = raw.get("display_name")
    if display_name_raw is None:
        errors.append(_field_error("display_name", "display_name is required"))
        display_name = ""
    elif not isinstance(display_name_raw, str):
        errors.append(_field_error("display_name", "display_name must be a string"))
        display_name = ""
    else:
        display_name = display_name_raw.strip()
        if not display_name:
            errors.append(_field_error("display_name", "display_name must not be empty or whitespace"))
        elif len(display_name) < DISPLAY_NAME_MIN:
            errors.append(
                _field_error(
                    "display_name",
                    f"display_name must be at least {DISPLAY_NAME_MIN} characters",
                )
            )
        elif len(display_name) > DISPLAY_NAME_MAX:
            errors.append(
                _field_error(
                    "display_name",
                    f"display_name must be at most {DISPLAY_NAME_MAX} characters",
                )
            )

    business_type_raw = raw.get("business_type", DEFAULT_BUSINESS_TYPE)
    if business_type_raw is None:
        business_type = DEFAULT_BUSINESS_TYPE
    elif not isinstance(business_type_raw, str):
        errors.append(_field_error("business_type", "business_type must be a string"))
        business_type = DEFAULT_BUSINESS_TYPE
    else:
        business_type = business_type_raw.strip().lower()
        if business_type not in SUPPORTED_BUSINESS_TYPES:
            errors.append(
                _field_error(
                    "business_type",
                    f"Unsupported business_type '{business_type_raw}'",
                )
            )

    slug: str | None = None
    if "slug" in raw and raw["slug"] is not None:
        if not isinstance(raw["slug"], str):
            errors.append(_field_error("slug", "slug must be a string"))
        else:
            slug = raw["slug"].strip().lower()
            if len(slug) < SLUG_MIN or len(slug) > SLUG_MAX:
                errors.append(
                    _field_error(
                        "slug",
                        f"slug must be between {SLUG_MIN} and {SLUG_MAX} characters",
                    )
                )
            elif not _SLUG_RE.match(slug):
                errors.append(
                    _field_error(
                        "slug",
                        "slug must be lowercase alphanumeric with optional hyphens",
                    )
                )
            elif slug in RESERVED_SLUGS:
                errors.append(_field_error("slug", f"slug '{slug}' is reserved"))

    logo_asset_id: UUID | None = None
    if "logo_asset_id" in raw and raw["logo_asset_id"] is not None:
        try:
            logo_asset_id = UUID(str(raw["logo_asset_id"]))
        except (ValueError, TypeError):
            errors.append(_field_error("logo_asset_id", "logo_asset_id must be a UUID"))

    timezone = DEFAULT_TIMEZONE
    if "timezone" in raw and raw["timezone"] is not None:
        if not isinstance(raw["timezone"], str):
            errors.append(_field_error("timezone", "timezone must be a string"))
        else:
            timezone = raw["timezone"].strip()
            if timezone not in SUPPORTED_TIMEZONES:
                errors.append(_field_error("timezone", f"Unsupported timezone '{timezone}'"))

    currency = DEFAULT_CURRENCY
    if "currency" in raw and raw["currency"] is not None:
        if not isinstance(raw["currency"], str):
            errors.append(_field_error("currency", "currency must be a string"))
        else:
            currency = raw["currency"].strip().upper()
            if currency not in SUPPORTED_CURRENCIES:
                errors.append(_field_error("currency", f"Unsupported currency '{currency}'"))

    country = DEFAULT_COUNTRY
    if "country" in raw and raw["country"] is not None:
        if not isinstance(raw["country"], str):
            errors.append(_field_error("country", "country must be a string"))
        else:
            country = raw["country"].strip().upper()
            if country not in SUPPORTED_COUNTRIES:
                errors.append(_field_error("country", f"Unsupported country '{country}'"))

    language = DEFAULT_LANGUAGE
    if "language" in raw and raw["language"] is not None:
        if not isinstance(raw["language"], str):
            errors.append(_field_error("language", "language must be a string"))
        else:
            language = raw["language"].strip().lower()
            if language not in SUPPORTED_LANGUAGES:
                errors.append(_field_error("language", f"Unsupported language '{language}'"))

    if errors:
        raise ValidationError("Business creation validation failed", details={"errors": errors})

    return BusinessCreationInput(
        display_name=display_name,
        business_type=business_type,
        slug=slug,
        logo_asset_id=logo_asset_id,
        timezone=timezone,
        currency=currency,
        country=country,
        language=language,
    )
