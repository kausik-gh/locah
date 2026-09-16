"""Business type configuration validation (Stage 2F)."""

from __future__ import annotations

from typing import Any

from platform_core.business_type_profiles import BusinessTypeProfileRegistry, PROFILE_VERSION
from platform_core.business_types import SUPPORTED_BUSINESS_TYPES
from platform_core.exceptions import ValidationError

DEPRECATED_BUSINESS_TYPES: frozenset[str] = frozenset()


def validate_business_type_value(business_type: str) -> str:
    normalized = business_type.strip().lower()
    if normalized not in SUPPORTED_BUSINESS_TYPES:
        raise ValidationError(
            f"Unsupported business_type '{business_type}'",
            details={"field": "business_type", "supported": sorted(SUPPORTED_BUSINESS_TYPES)},
        )
    if normalized in DEPRECATED_BUSINESS_TYPES:
        raise ValidationError(
            f"Deprecated business_type '{business_type}'",
            details={"field": "business_type", "status": "deprecated"},
        )
    profile = BusinessTypeProfileRegistry.get(normalized)
    if profile is None:
        raise ValidationError(
            "Invalid business type profile",
            details={"field": "business_type", "reason": "profile_not_found"},
        )
    if profile.status != "active":
        raise ValidationError(
            "Business type profile is not active",
            details={"field": "business_type", "status": profile.status},
        )
    return normalized


def validate_type_change_payload(raw: dict[str, Any], *, onboarding_completed: bool) -> str:
    if "business_type" not in raw:
        raise ValidationError(
            "business_type is required",
            details={"field": "business_type"},
        )
    business_type_raw = raw["business_type"]
    if not isinstance(business_type_raw, str):
        raise ValidationError(
            "business_type must be a string",
            details={"field": "business_type"},
        )
    business_type = validate_business_type_value(business_type_raw)
    if onboarding_completed and not raw.get("confirm_type_change"):
        raise ValidationError(
            "confirm_type_change is required after onboarding",
            details={"field": "confirm_type_change", "required": True},
        )
    return business_type


def profile_version_status(stored_version: str | None, current_version: str) -> str:
    if stored_version is None:
        return "current"
    if stored_version != current_version:
        return "upgrade_available"
    return "current"


def assert_profile_version_compatible(stored_version: str | None, current_version: str) -> None:
    if stored_version is not None and stored_version != current_version:
        # Advisory only — Doc 07 §8.2 recommendation updates must not mutate state.
        return


def current_profile_version() -> str:
    return str(PROFILE_VERSION)
