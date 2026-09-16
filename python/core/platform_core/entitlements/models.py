"""Entitlement domain model (Document 08)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REGISTRY_VERSION = "1.0"


@dataclass(frozen=True)
class UsageLimit:
    limit_key: str
    display_name: str
    max_value: int | None
    unit: str = "count"


@dataclass(frozen=True)
class FeatureDefinition:
    feature_id: str
    module_id: str
    display_name: str
    description: str
    default_enabled: bool = True
    entitlement_required: bool = True


@dataclass(frozen=True)
class ModuleDefinition:
    module_id: str
    display_name: str
    module_class: str
    description: str
    dependencies: tuple[str, ...]
    default_state: str = "not_enabled"
    features: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanDefinition:
    plan_id: str
    version: str
    display_name: str
    description: str
    module_ids: frozenset[str]
    feature_ids: frozenset[str]
    usage_limits: tuple[UsageLimit, ...]
    status: str = "active"


@dataclass(frozen=True)
class CapabilityDefinition:
    capability_id: str
    display_name: str
    required_module_id: str | None = None
    required_feature_id: str | None = None
    limit_key: str | None = None


@dataclass(frozen=True)
class FeatureState:
    feature_id: str
    module_id: str
    entitled: bool
    enabled: bool
    source: str


@dataclass(frozen=True)
class ModuleState:
    module_id: str
    entitled: bool
    activation_state: str
    configuration_ready: bool
    dependency_satisfied: bool
    source: str


@dataclass(frozen=True)
class BusinessEntitlement:
    business_id: str
    plan_id: str
    entitled_modules: frozenset[str]
    entitled_features: frozenset[str]
    usage_limits: dict[str, int | None]
    sources: dict[str, Any]


@dataclass(frozen=True)
class ResolvedEntitlement:
    business_id: str
    plan_id: str
    plan_version: str
    registry_version: str
    business_type: str
    entitled_modules: frozenset[str]
    entitled_features: frozenset[str]
    module_states: dict[str, ModuleState]
    feature_states: dict[str, FeatureState]
    usage_limits: dict[str, int | None]
    layers: dict[str, Any]
    version: int

    def serialize(self) -> dict[str, Any]:
        return {
            "business_id": self.business_id,
            "plan_id": self.plan_id,
            "plan_version": self.plan_version,
            "registry_version": self.registry_version,
            "business_type": self.business_type,
            "entitled_modules": sorted(self.entitled_modules),
            "entitled_features": sorted(self.entitled_features),
            "module_states": {
                mid: {
                    "module_id": state.module_id,
                    "entitled": state.entitled,
                    "activation_state": state.activation_state,
                    "configuration_ready": state.configuration_ready,
                    "dependency_satisfied": state.dependency_satisfied,
                    "source": state.source,
                }
                for mid, state in self.module_states.items()
            },
            "feature_states": {
                fid: {
                    "feature_id": state.feature_id,
                    "module_id": state.module_id,
                    "entitled": state.entitled,
                    "enabled": state.enabled,
                    "source": state.source,
                }
                for fid, state in self.feature_states.items()
            },
            "usage_limits": self.usage_limits,
            "layers": self.layers,
            "version": self.version,
        }


@dataclass(frozen=True)
class CapabilitySnapshot:
    business_id: str
    capabilities: dict[str, bool]
    details: dict[str, dict[str, Any]]
    version: int

    def serialize(self) -> dict[str, Any]:
        return {
            "business_id": self.business_id,
            "capabilities": self.capabilities,
            "details": self.details,
            "version": self.version,
        }


@dataclass
class BusinessOverrideLayer:
    modules: dict[str, dict[str, Any]] = field(default_factory=dict)
    features: dict[str, dict[str, Any]] = field(default_factory=dict)
    limits: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_metadata(cls, raw: dict[str, Any] | None) -> BusinessOverrideLayer:
        if not isinstance(raw, dict):
            return cls()
        modules = raw.get("modules")
        features = raw.get("features")
        limits = raw.get("limits")
        return cls(
            modules=dict(modules) if isinstance(modules, dict) else {},
            features=dict(features) if isinstance(features, dict) else {},
            limits=dict(limits) if isinstance(limits, dict) else {},
        )

    def serialize(self) -> dict[str, Any]:
        return {
            "modules": self.modules,
            "features": self.features,
            "limits": self.limits,
        }
