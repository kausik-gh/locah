"""Business entitlement validation (Stage 2G)."""

from __future__ import annotations

from typing import Any

from platform_core.entitlements.feature_registry import FeatureRegistry
from platform_core.entitlements.module_registry import ModuleRegistry
from platform_core.entitlements.plan_registry import PlanRegistry
from platform_core.exceptions import ValidationError


def validate_plan_id(plan_id: str) -> str:
    normalized = plan_id.strip().lower()
    PlanRegistry.get_or_raise(normalized)
    return normalized


def validate_module_id(module_id: str) -> str:
    normalized = module_id.strip()
    ModuleRegistry.get_or_raise(normalized)
    return normalized


def validate_feature_id(feature_id: str) -> str:
    normalized = feature_id.strip()
    FeatureRegistry.get_or_raise(normalized)
    return normalized


def validate_override_payload(raw: dict[str, Any]) -> dict[str, Any]:
    modules = raw.get("modules")
    features = raw.get("features")
    limits = raw.get("limits")

    if modules is not None:
        if not isinstance(modules, dict):
            raise ValidationError("modules must be an object", details={"field": "modules"})
        for module_id, override in modules.items():
            validate_module_id(module_id)
            if not isinstance(override, dict):
                raise ValidationError(
                    "module override must be an object",
                    details={"field": f"modules.{module_id}"},
                )
            entitled = override.get("entitled")
            if entitled is not None and not isinstance(entitled, bool):
                raise ValidationError(
                    "module override entitled must be boolean",
                    details={"field": f"modules.{module_id}.entitled"},
                )

    if features is not None:
        if not isinstance(features, dict):
            raise ValidationError("features must be an object", details={"field": "features"})
        for feature_id, override in features.items():
            validate_feature_id(feature_id)
            if not isinstance(override, dict):
                raise ValidationError(
                    "feature override must be an object",
                    details={"field": f"features.{feature_id}"},
                )
            for key in ("entitled", "enabled"):
                value = override.get(key)
                if value is not None and not isinstance(value, bool):
                    raise ValidationError(
                        f"feature override {key} must be boolean",
                        details={"field": f"features.{feature_id}.{key}"},
                    )

    if limits is not None:
        if not isinstance(limits, dict):
            raise ValidationError("limits must be an object", details={"field": "limits"})
        for limit_key, override in limits.items():
            if not isinstance(override, dict):
                raise ValidationError(
                    "limit override must be an object",
                    details={"field": f"limits.{limit_key}"},
                )
            max_value = override.get("max")
            if max_value is not None and not isinstance(max_value, int):
                raise ValidationError(
                    "limit override max must be an integer or null",
                    details={"field": f"limits.{limit_key}.max"},
                )

    return raw


def validate_dependency_graph(entitled_modules: frozenset[str], module_id: str) -> None:
    satisfied, missing = ModuleRegistry.dependencies_satisfied(module_id, entitled_modules)
    if not satisfied:
        raise ValidationError(
            f"Module '{module_id}' has unsatisfied dependencies",
            details={"field": "module_id", "missing_dependencies": list(missing)},
        )
