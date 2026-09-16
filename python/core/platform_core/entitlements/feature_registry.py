"""Immutable feature registry (Document 08 capability tiers)."""

from __future__ import annotations

from platform_core.entitlements.models import FeatureDefinition
from platform_core.entitlements.module_registry import ModuleRegistry

_ADVANCED_DEFAULTS: dict[str, bool] = {
    "inventory.core": True,
    "inventory.barcode": True,
    "inventory.stock_transfer": False,
    "inventory.purchase_orders": False,
    "inventory.batch_tracking": False,
    "inventory.expiry": False,
    "analytics.advanced": False,
}


def _feature(
    feature_id: str,
    module_id: str,
    display_name: str,
    description: str,
) -> FeatureDefinition:
    default_enabled = _ADVANCED_DEFAULTS.get(feature_id, feature_id.endswith(".core"))
    return FeatureDefinition(
        feature_id=feature_id,
        module_id=module_id,
        display_name=display_name,
        description=description,
        default_enabled=default_enabled,
    )


_FEATURES: dict[str, FeatureDefinition] = {}

for module in ModuleRegistry.list_modules():
    module_def = ModuleRegistry.get(module["module_id"])
    if module_def is None:
        continue
    for feature_id in module_def.features:
        suffix = feature_id.split(".", 1)[-1].replace("_", " ").title()
        _FEATURES[feature_id] = _feature(
            feature_id,
            module_def.module_id,
            suffix,
            f"{module_def.display_name} — {suffix}",
        )


class FeatureRegistry:
    @staticmethod
    def list_features(*, module_id: str | None = None) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        for feature in sorted(_FEATURES.values(), key=lambda f: f.feature_id):
            if module_id and feature.module_id != module_id:
                continue
            items.append(
                {
                    "feature_id": feature.feature_id,
                    "module_id": feature.module_id,
                    "display_name": feature.display_name,
                }
            )
        return items

    @staticmethod
    def get(feature_id: str) -> FeatureDefinition | None:
        return _FEATURES.get(feature_id.strip())

    @staticmethod
    def get_or_raise(feature_id: str) -> FeatureDefinition:
        feature = FeatureRegistry.get(feature_id)
        if feature is None:
            from platform_core.exceptions import ValidationError

            raise ValidationError(
                f"Unknown feature '{feature_id}'",
                details={"field": "feature_id", "feature_id": feature_id},
            )
        return feature

    @staticmethod
    def for_module(module_id: str) -> tuple[FeatureDefinition, ...]:
        return tuple(
            feature for feature in _FEATURES.values() if feature.module_id == module_id
        )
