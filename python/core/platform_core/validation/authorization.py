"""Authorization validation (Stage 2H)."""

from __future__ import annotations

from typing import Any

from platform_core.authorization.models import OverridePatch
from platform_core.authorization.permission_registry import PermissionRegistry
from platform_core.exceptions import ValidationError


def validate_override_payload(raw: dict[str, Any]) -> OverridePatch:
    grants_raw = raw.get("grants", [])
    denials_raw = raw.get("denials", [])
    remove_grants_raw = raw.get("remove_grants", [])
    remove_denials_raw = raw.get("remove_denials", [])

    for field_name, value in (
        ("grants", grants_raw),
        ("denials", denials_raw),
        ("remove_grants", remove_grants_raw),
        ("remove_denials", remove_denials_raw),
    ):
        if not isinstance(value, list):
            raise ValidationError(f"{field_name} must be an array", details={"field": field_name})

    all_lists = {
        "grants": grants_raw,
        "denials": denials_raw,
        "remove_grants": remove_grants_raw,
        "remove_denials": remove_denials_raw,
    }
    seen: set[str] = set()
    for field_name, values in all_lists.items():
        for item in values:
            if not isinstance(item, str):
                raise ValidationError(
                    f"{field_name} entries must be strings",
                    details={"field": field_name},
                )
            PermissionRegistry.get_or_raise(item)
            key = f"{field_name}:{item}"
            if key in seen:
                raise ValidationError(
                    "Duplicate override entry",
                    details={"field": field_name, "permission": item},
                )
            seen.add(key)

    overlap = set(grants_raw) & set(denials_raw)
    if overlap:
        raise ValidationError(
            "Permission cannot be both granted and denied",
            details={"permissions": sorted(overlap)},
        )

    if not any([grants_raw, denials_raw, remove_grants_raw, remove_denials_raw]):
        raise ValidationError(
            "At least one override operation is required",
            details={"field": "overrides"},
        )

    return OverridePatch(
        grants=list(grants_raw),
        denials=list(denials_raw),
        remove_grants=list(remove_grants_raw),
        remove_denials=list(remove_denials_raw),
    )
