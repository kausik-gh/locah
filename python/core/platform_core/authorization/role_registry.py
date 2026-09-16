"""Immutable role registry (Document 06 §4)."""

from __future__ import annotations

from platform_core.authorization.models import REGISTRY_VERSION, RoleDefinition, RoleProfile
from platform_core.permissions import (
    ALL_PERMISSIONS,
    BUSINESS_CLOSE,
    COMMERCIAL_MANAGE,
    ROLE_MANAGER,
    ROLE_MEMBER,
    ROLE_PRIMARY_OWNER,
    TEAM_INVITE,
    TEAM_MANAGE_TEMPLATES,
    TEAM_REMOVE,
    TEAM_UPDATE_ROLE,
    TEMPLATES,
)

_MANAGER_BASE: frozenset[str] = frozenset()
_MEMBER_BASE: frozenset[str] = frozenset()

_ROLES: dict[str, RoleDefinition] = {
    ROLE_PRIMARY_OWNER: RoleDefinition(
        role_id=ROLE_PRIMARY_OWNER,
        version=REGISTRY_VERSION,
        display_name="Primary Owner",
        description="Highest Business authority; exactly one per Business.",
        granted_permissions=frozenset(ALL_PERMISSIONS),
        inherited_permissions=frozenset(),
        denied_permissions=frozenset(),
    ),
    ROLE_MANAGER: RoleDefinition(
        role_id=ROLE_MANAGER,
        version=REGISTRY_VERSION,
        display_name="Manager",
        description="Broad delegated operational authority within delegation ceiling.",
        granted_permissions=_MANAGER_BASE,
        inherited_permissions=frozenset(),
        denied_permissions=frozenset(
            {BUSINESS_CLOSE, COMMERCIAL_MANAGE, TEAM_MANAGE_TEMPLATES}
        ),
    ),
    ROLE_MEMBER: RoleDefinition(
        role_id=ROLE_MEMBER,
        version=REGISTRY_VERSION,
        display_name="Member",
        description="Operational access granted explicitly via templates and overrides.",
        granted_permissions=_MEMBER_BASE,
        inherited_permissions=frozenset(),
        denied_permissions=frozenset(
            {
                TEAM_INVITE,
                TEAM_UPDATE_ROLE,
                TEAM_REMOVE,
                TEAM_MANAGE_TEMPLATES,
                COMMERCIAL_MANAGE,
                BUSINESS_CLOSE,
            }
        ),
    ),
}

_ROLE_PROFILES: dict[str, RoleProfile] = {
    ROLE_PRIMARY_OWNER: RoleProfile(role_id=ROLE_PRIMARY_OWNER, template_ids=()),
    ROLE_MANAGER: RoleProfile(role_id=ROLE_MANAGER, template_ids=tuple(sorted(TEMPLATES.keys()))),
    ROLE_MEMBER: RoleProfile(role_id=ROLE_MEMBER, template_ids=tuple(sorted(TEMPLATES.keys()))),
}


class RoleRegistry:
    @staticmethod
    def list_roles() -> list[dict[str, str]]:
        return [
            {
                "role_id": role.role_id,
                "display_name": role.display_name,
                "version": role.version,
            }
            for role_id in sorted(_ROLES)
            if (role := _ROLES.get(role_id)) is not None
        ]

    @staticmethod
    def get(role_id: str) -> RoleDefinition | None:
        return _ROLES.get(role_id.strip())

    @staticmethod
    def get_or_raise(role_id: str) -> RoleDefinition:
        role = RoleRegistry.get(role_id)
        if role is None:
            from platform_core.exceptions import ValidationError

            raise ValidationError(
                f"Unknown role '{role_id}'",
                details={"field": "role", "role_id": role_id},
            )
        return role

    @staticmethod
    def profile(role_id: str) -> RoleProfile | None:
        return _ROLE_PROFILES.get(role_id)

    @staticmethod
    def permission_matrix() -> dict[str, list[str]]:
        matrix: dict[str, list[str]] = {}
        for role in _ROLES.values():
            effective = role.granted_permissions - role.denied_permissions
            matrix[role.role_id] = sorted(effective)
        return matrix
