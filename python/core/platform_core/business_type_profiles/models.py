"""Business-Type Configuration Profile domain model (Document 07 §16 — conceptual)."""

from __future__ import annotations

from dataclasses import dataclass, field
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
class ResourceSemantics:
    """How a business type talks about, and defaults, its bookable resources.

    The booking engine is deliberately ignorant of verticals: it knows only
    exclusive and pooled subjects over intervals. This is where a hotel learns
    to say "Room" and sell by the night while a gym says "Class" and sells
    seats, without either becoming a branch in the allocator.

    `kinds` is what a business of this type is offered when configuring supply.
    It is a suggestion, not a whitelist - resource_type is free text, so a
    business with something unusual is never blocked.
    """

    noun: str = "Resource"
    noun_plural: str = "Resources"
    kinds: tuple[str, ...] = ()
    default_allocation_mode: str = "exclusive"
    default_granularity: str = "slot"
    # Whether this type books a person, a thing, or both. Drives what the
    # Workspace asks for, not what the engine permits.
    books_providers: bool = True
    books_resources: bool = False

    def serialize(self) -> dict[str, Any]:
        return {
            "noun": self.noun,
            "noun_plural": self.noun_plural,
            "kinds": list(self.kinds),
            "default_allocation_mode": self.default_allocation_mode,
            "default_granularity": self.default_granularity,
            "books_providers": self.books_providers,
            "books_resources": self.books_resources,
        }


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
    resource_semantics: ResourceSemantics = field(default_factory=ResourceSemantics)
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
            "resource_semantics": self.resource_semantics.serialize(),
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
