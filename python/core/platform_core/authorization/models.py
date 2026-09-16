"""Authorization domain model (Document 06)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REGISTRY_VERSION = "1.0"


@dataclass(frozen=True)
class PermissionDefinition:
    permission_id: str
    display_name: str
    group: str
    description: str


@dataclass(frozen=True)
class PermissionGroup:
    group_id: str
    display_name: str
    permissions: tuple[str, ...]


@dataclass(frozen=True)
class RoleDefinition:
    role_id: str
    version: str
    display_name: str
    description: str
    granted_permissions: frozenset[str]
    inherited_permissions: frozenset[str]
    denied_permissions: frozenset[str]


@dataclass(frozen=True)
class RoleProfile:
    role_id: str
    template_ids: tuple[str, ...]


@dataclass(frozen=True)
class PermissionOverride:
    permission_id: str
    effect: str
    source: str


@dataclass(frozen=True)
class EffectivePermission:
    permission_id: str
    source: str
    overridden: bool


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    permission: str
    reason: str
    source_role: str | None
    overridden: bool
    registry_version: str

    def serialize(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "permission": self.permission,
            "reason": self.reason,
            "source_role": self.source_role,
            "overridden": self.overridden,
            "registry_version": self.registry_version,
        }


@dataclass(frozen=True)
class PermissionSnapshot:
    business_id: str
    identity_id: str
    membership_id: str
    role: str
    effective_permissions: frozenset[str]
    granted_roles: tuple[str, ...]
    denied_permissions: frozenset[str]
    inherited_permissions: frozenset[str]
    overrides: tuple[PermissionOverride, ...]
    capability_summary: dict[str, bool]
    registry_version: str
    version: int

    def serialize(self) -> dict[str, Any]:
        return {
            "business_id": self.business_id,
            "identity_id": self.identity_id,
            "membership_id": self.membership_id,
            "role": self.role,
            "effective_permissions": sorted(self.effective_permissions),
            "granted_roles": list(self.granted_roles),
            "denied_permissions": sorted(self.denied_permissions),
            "inherited_permissions": sorted(self.inherited_permissions),
            "overrides": [
                {"permission_id": o.permission_id, "effect": o.effect, "source": o.source}
                for o in self.overrides
            ],
            "capability_summary": self.capability_summary,
            "registry_version": self.registry_version,
            "version": self.version,
        }


@dataclass(frozen=True)
class ResolvedPermissions:
    business_id: str
    identity_id: str
    membership_id: str
    role: str
    effective_permissions: frozenset[str]
    denied_permissions: frozenset[str]
    inherited_permissions: frozenset[str]
    overrides: tuple[PermissionOverride, ...]
    layers: dict[str, Any]
    registry_version: str
    version: int

    def serialize(self) -> dict[str, Any]:
        return {
            "business_id": self.business_id,
            "identity_id": self.identity_id,
            "membership_id": self.membership_id,
            "role": self.role,
            "effective_permissions": sorted(self.effective_permissions),
            "denied_permissions": sorted(self.denied_permissions),
            "inherited_permissions": sorted(self.inherited_permissions),
            "overrides": [
                {"permission_id": o.permission_id, "effect": o.effect, "source": o.source}
                for o in self.overrides
            ],
            "layers": self.layers,
            "registry_version": self.registry_version,
            "version": self.version,
        }


@dataclass
class OverridePatch:
    grants: list[str] = field(default_factory=list)
    denials: list[str] = field(default_factory=list)
    remove_grants: list[str] = field(default_factory=list)
    remove_denials: list[str] = field(default_factory=list)
