"""Business settings validation (Stage 2E — core-settings)."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from platform_core.business_types import (
    DISPLAY_NAME_MAX,
    DISPLAY_NAME_MIN,
    SUPPORTED_COUNTRIES,
    SUPPORTED_CURRENCIES,
    SUPPORTED_LANGUAGES,
    SUPPORTED_TIMEZONES,
)
from platform_core.exceptions import ValidationError

IMMUTABLE_BUSINESS_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "business_id",
        "slug",
        "primary_owner_identity_id",
        "created_at",
        "business_type",
        "state",
        "status",
    }
)

DESCRIPTION_MAX = 5000
TAGLINE_MAX = 200
WEBSITE_URL_MAX = 500
BRAND_COLOR_MAX = 32
SUPPORTED_DATE_FORMATS: frozenset[str] = frozenset({"DMY", "MDY", "YMD"})
SUPPORTED_TIME_FORMATS: frozenset[str] = frozenset({"12h", "24h"})
SUPPORTED_MEASUREMENT: frozenset[str] = frozenset({"metric", "imperial"})
SUPPORTED_DASHBOARDS: frozenset[str] = frozenset({"dashboard", "operations"})
SUPPORTED_FONT_THEMES: frozenset[str] = frozenset({"modern", "warm", "bold"})
SUPPORTED_VISIBILITY: frozenset[str] = frozenset({"private", "unlisted", "discoverable"})
VISIBILITY_TO_COLUMN: frozenset[str] = SUPPORTED_VISIBILITY

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_LOCALE_RE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")
_HEX_COLOR_RE = re.compile(r"^#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})$")


def _field_error(field: str, message: str) -> dict[str, str]:
    return {"field": field, "message": message}


def reject_immutable_fields(raw: dict[str, Any]) -> None:
    forbidden = IMMUTABLE_BUSINESS_FIELDS.intersection(raw.keys())
    if forbidden:
        raise ValidationError(
            "Immutable business fields cannot be modified",
            details={
                "errors": [
                    _field_error(field, "field is immutable") for field in sorted(forbidden)
                ]
            },
        )


def validate_regional_settings(raw: dict[str, Any]) -> dict[str, Any]:
    reject_immutable_fields(raw)
    errors: list[dict[str, str]] = []
    updates: dict[str, Any] = {}

    if "timezone" in raw:
        tz = raw["timezone"]
        if not isinstance(tz, str):
            errors.append(_field_error("timezone", "timezone must be a string"))
        else:
            tz = tz.strip()
            if tz not in SUPPORTED_TIMEZONES:
                errors.append(_field_error("timezone", f"Unsupported timezone '{tz}'"))
            else:
                updates["timezone"] = tz

    if "currency" in raw:
        cur = raw["currency"]
        if not isinstance(cur, str):
            errors.append(_field_error("currency", "currency must be a string"))
        else:
            cur = cur.strip().upper()
            if cur not in SUPPORTED_CURRENCIES:
                errors.append(_field_error("currency", f"Unsupported currency '{cur}'"))
            else:
                updates["currency"] = cur

    if "country" in raw:
        country = raw["country"]
        if not isinstance(country, str):
            errors.append(_field_error("country", "country must be a string"))
        else:
            country = country.strip().upper()
            if country not in SUPPORTED_COUNTRIES:
                errors.append(_field_error("country", f"Unsupported country '{country}'"))
            else:
                updates["country"] = country

    if "language" in raw:
        lang = raw["language"]
        if not isinstance(lang, str):
            errors.append(_field_error("language", "language must be a string"))
        else:
            lang = lang.strip().lower()
            if lang not in SUPPORTED_LANGUAGES:
                errors.append(_field_error("language", f"Unsupported language '{lang}'"))
            else:
                updates["language"] = lang

    if "locale" in raw:
        locale = raw["locale"]
        if not isinstance(locale, str):
            errors.append(_field_error("locale", "locale must be a string"))
        else:
            locale = locale.strip()
            if not _LOCALE_RE.match(locale):
                errors.append(_field_error("locale", "locale must match language-COUNTRY (e.g. en-IN)"))
            else:
                updates["locale"] = locale

    if "notifications" in raw:
        notif = raw["notifications"]
        if not isinstance(notif, dict):
            errors.append(_field_error("notifications", "notifications must be an object"))
        else:
            allowed = {"transactional_email", "transactional_in_app", "marketing_email"}
            cleaned: dict[str, bool] = {}
            for key, value in notif.items():
                if key not in allowed:
                    errors.append(_field_error(f"notifications.{key}", "unknown notification preference"))
                    continue
                if not isinstance(value, bool):
                    errors.append(_field_error(f"notifications.{key}", "must be a boolean"))
                else:
                    cleaned[key] = value
            if cleaned:
                updates["notifications"] = cleaned

    if errors:
        raise ValidationError("Settings validation failed", details={"errors": errors})

    if updates.get("language") and updates.get("country") and "locale" not in updates:
        updates["locale"] = f"{updates['language']}-{updates['country']}"
    elif "language" in updates and "country" in raw and "locale" not in updates:
        pass

    return updates


def validate_profile_fields(raw: dict[str, Any]) -> dict[str, Any]:
    reject_immutable_fields(raw)
    errors: list[dict[str, str]] = []
    updates: dict[str, Any] = {}

    if "display_name" in raw:
        name = raw["display_name"]
        if not isinstance(name, str):
            errors.append(_field_error("display_name", "display_name must be a string"))
        else:
            name = name.strip()
            if len(name) < DISPLAY_NAME_MIN:
                errors.append(
                    _field_error(
                        "display_name",
                        f"display_name must be at least {DISPLAY_NAME_MIN} characters",
                    )
                )
            elif len(name) > DISPLAY_NAME_MAX:
                errors.append(
                    _field_error(
                        "display_name",
                        f"display_name must be at most {DISPLAY_NAME_MAX} characters",
                    )
                )
            else:
                updates["display_name"] = name

    if "description" in raw:
        desc = raw["description"]
        if desc is not None and not isinstance(desc, str):
            errors.append(_field_error("description", "description must be a string"))
        elif isinstance(desc, str) and len(desc) > DESCRIPTION_MAX:
            errors.append(
                _field_error(
                    "description",
                    f"description must be at most {DESCRIPTION_MAX} characters",
                )
            )
        else:
            updates["description"] = desc

    if "tagline" in raw:
        tagline = raw["tagline"]
        if tagline is not None and not isinstance(tagline, str):
            errors.append(_field_error("tagline", "tagline must be a string"))
        elif isinstance(tagline, str) and len(tagline) > TAGLINE_MAX:
            errors.append(_field_error("tagline", f"tagline must be at most {TAGLINE_MAX} characters"))
        else:
            updates["tagline"] = tagline

    if "website_url" in raw:
        url = raw["website_url"]
        if url is not None and not isinstance(url, str):
            errors.append(_field_error("website_url", "website_url must be a string"))
        elif isinstance(url, str) and len(url) > WEBSITE_URL_MAX:
            errors.append(_field_error("website_url", "website_url is too long"))
        else:
            updates["website_url"] = url

    if "contact" in raw:
        contact = raw["contact"]
        if contact is not None and not isinstance(contact, dict):
            errors.append(_field_error("contact", "contact must be an object"))
        else:
            cleaned = validate_contact(contact or {})
            updates["contact"] = cleaned

    if "social_links" in raw:
        links = raw["social_links"]
        if links is not None and not isinstance(links, dict):
            errors.append(_field_error("social_links", "social_links must be an object"))
        else:
            updates["social_links"] = {k: str(v) for k, v in (links or {}).items() if v is not None}

    if errors:
        raise ValidationError("Profile validation failed", details={"errors": errors})
    return updates


def validate_contact(contact: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    cleaned: dict[str, Any] = {}
    for key in ("email", "phone", "secondary_phone"):
        if key not in contact:
            continue
        value = contact[key]
        if value is None:
            cleaned[key] = None
            continue
        if not isinstance(value, str):
            errors.append(_field_error(f"contact.{key}", "must be a string"))
            continue
        value = value.strip()
        if key == "email" and value and not _EMAIL_RE.match(value):
            errors.append(_field_error("contact.email", "invalid email address"))
        cleaned[key] = value or None
    if errors:
        raise ValidationError("Contact validation failed", details={"errors": errors})
    return cleaned


def validate_branding_fields(raw: dict[str, Any]) -> dict[str, Any]:
    reject_immutable_fields(raw)
    errors: list[dict[str, str]] = []
    updates: dict[str, Any] = {}

    for asset_field in ("logo_asset_id", "cover_asset_id"):
        if asset_field not in raw:
            continue
        value = raw[asset_field]
        if value is None:
            updates[asset_field] = None
            continue
        try:
            updates[asset_field] = UUID(str(value))
        except (ValueError, TypeError):
            errors.append(_field_error(asset_field, f"{asset_field} must be a UUID"))

    if "display_name" in raw:
        updates.update(validate_profile_fields({"display_name": raw["display_name"]}))

    if "tagline" in raw:
        tagline = raw["tagline"]
        if tagline is not None and not isinstance(tagline, str):
            errors.append(_field_error("tagline", "tagline must be a string"))
        elif isinstance(tagline, str) and len(tagline) > TAGLINE_MAX:
            errors.append(_field_error("tagline", f"tagline must be at most {TAGLINE_MAX} characters"))
        else:
            updates["tagline"] = tagline

    branding: dict[str, Any] = {}
    if "brand_color" in raw:
        color = raw["brand_color"]
        if color is not None and not isinstance(color, str):
            errors.append(_field_error("brand_color", "brand_color must be a string"))
        elif isinstance(color, str):
            color = color.strip()
            if len(color) > BRAND_COLOR_MAX:
                errors.append(_field_error("brand_color", "brand_color is too long"))
            elif color and not _HEX_COLOR_RE.match(color):
                errors.append(_field_error("brand_color", "brand_color must be a hex color"))
            else:
                branding["brand_color"] = color or None

    if "font_theme" in raw:
        theme = raw["font_theme"]
        if theme is not None and not isinstance(theme, str):
            errors.append(_field_error("font_theme", "font_theme must be a string"))
        else:
            theme = (theme or "").strip().lower()
            if theme and theme not in SUPPORTED_FONT_THEMES:
                errors.append(_field_error("font_theme", f"Unsupported font_theme '{theme}'"))
            else:
                branding["font_theme"] = theme or None

    if branding:
        updates["branding"] = branding

    if errors:
        raise ValidationError("Branding validation failed", details={"errors": errors})
    return updates


def validate_preferences_fields(raw: dict[str, Any]) -> dict[str, Any]:
    reject_immutable_fields(raw)
    errors: list[dict[str, str]] = []
    updates: dict[str, Any] = {}

    if "visibility" in raw:
        vis = raw["visibility"]
        if not isinstance(vis, str):
            errors.append(_field_error("visibility", "visibility must be a string"))
        elif vis not in SUPPORTED_VISIBILITY:
            errors.append(_field_error("visibility", f"Unsupported visibility '{vis}'"))
        else:
            updates["visibility"] = vis

    if "onboarding_completed" in raw:
        val = raw["onboarding_completed"]
        if not isinstance(val, bool):
            errors.append(_field_error("onboarding_completed", "onboarding_completed must be a boolean"))
        else:
            updates["onboarding_completed"] = val

    pref: dict[str, Any] = {}
    for key, allowed in (
        ("date_format", SUPPORTED_DATE_FORMATS),
        ("time_format", SUPPORTED_TIME_FORMATS),
        ("measurement_system", SUPPORTED_MEASUREMENT),
        ("default_dashboard", SUPPORTED_DASHBOARDS),
    ):
        if key not in raw:
            continue
        value = raw[key]
        if not isinstance(value, str):
            errors.append(_field_error(key, f"{key} must be a string"))
            continue
        value = value.strip()
        if value not in allowed:
            errors.append(_field_error(key, f"Unsupported {key} '{value}'"))
        else:
            pref[key] = value

    if pref:
        updates["preferences"] = pref

    if errors:
        raise ValidationError("Preferences validation failed", details={"errors": errors})
    return updates


async def validate_media_asset_reference(
    session: AsyncSession,
    *,
    business_id: UUID,
    asset_id: UUID,
    field: str,
) -> None:
    result = await session.execute(
        text(
            "SELECT id FROM media_assets WHERE id = :id AND status <> 'deleted' "
            "AND (business_id IS NULL OR business_id = :bid)"
        ),
        {"id": str(asset_id), "bid": str(business_id)},
    )
    if result.first() is None:
        raise ValidationError(
            f"{field} does not reference an available media asset",
            details={"errors": [_field_error(field, f"{field} not found")]},
        )
