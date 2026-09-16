"""Business-Type Configuration Profile domain model (Document 07 §16 — conceptual)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


PROFILE_VERSION = "1.0"


@dataclass(frozen=True)
class ModuleSeed:
    """Recommended module capability — advisory only (BTYPE-002)."""

    module_id: str
    rationale: str
    rank: int = 0


@dataclass(frozen=True)
class NavigationSeed:
    """Navigation emphasis hints — not enforced routing."""

    groups: tuple[dict[str, Any], ...]
    default_route: str = "dashboard"
    workspace_layout: str = "operations_first"


@dataclass(frozen=True)
class DashboardSeed:
    """Dashboard emphasis hints — not fixed widgets."""

    emphasis: tuple[str, ...]


@dataclass(frozen=True)
class OperationalDefaults:
    """Suggested operational defaults — merged with explicit Business settings."""

    booking_enabled: bool = False
    inventory_enabled: bool = False
    delivery_enabled: bool = False
    default_service_duration_minutes: int | None = None
    working_mode: str = "single_location"
    location_behavior: str = "physical_optional"


@dataclass(frozen=True)
class BusinessTypeProfile:
    """Immutable versioned Business-Type Configuration Profile."""

    type_id: str
    version: str
    display_name: str
    description: str
    category: str
    characteristics: tuple[str, ...]
    module_seeds: tuple[ModuleSeed, ...]
    navigation: NavigationSeed
    terminology: dict[str, str]
    dashboard: DashboardSeed
    operational_defaults: OperationalDefaults
    status: str = "active"

    def serialize(self) -> dict[str, Any]:
        return {
            "type_id": self.type_id,
            "version": self.version,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "status": self.status,
            "characteristics": list(self.characteristics),
            "module_seeds": [
                {
                    "module_id": m.module_id,
                    "rationale": m.rationale,
                    "rank": m.rank,
                    "recommended": True,
                }
                for m in self.module_seeds
            ],
            "navigation": {
                "groups": list(self.navigation.groups),
                "default_route": self.navigation.default_route,
                "workspace_layout": self.navigation.workspace_layout,
            },
            "terminology": dict(self.terminology),
            "dashboard": {"emphasis": list(self.dashboard.emphasis)},
            "operational_defaults": {
                "booking_enabled": self.operational_defaults.booking_enabled,
                "inventory_enabled": self.operational_defaults.inventory_enabled,
                "delivery_enabled": self.operational_defaults.delivery_enabled,
                "default_service_duration_minutes": (
                    self.operational_defaults.default_service_duration_minutes
                ),
                "working_mode": self.operational_defaults.working_mode,
                "location_behavior": self.operational_defaults.location_behavior,
            },
        }


@dataclass(frozen=True)
class ConfigurationProfile:
    """Resolved configuration layers for a Business."""

    business_id: str
    business_type: str
    profile_version: str
    profile: dict[str, Any]
    resolved: dict[str, Any]
    layers: dict[str, Any]
    version: int

    def serialize(self) -> dict[str, Any]:
        return {
            "business_id": self.business_id,
            "business_type": self.business_type,
            "profile_version": self.profile_version,
            "profile": self.profile,
            "resolved": self.resolved,
            "layers": self.layers,
            "version": self.version,
        }
