"""Immutable permission registry (Document 06 / Doc 12 identifiers)."""

from __future__ import annotations

from typing import Any

import platform_core.permissions as perm
from platform_core.authorization.models import PermissionDefinition, PermissionGroup

_RESOURCE_LABELS: dict[str, str] = {
    "business": "Business Identity",
    "locations": "Locations",
    "team": "Team & Access",
    "settings": "Settings",
    "configuration": "Configuration",
    "entitlements": "Entitlements",
    "permissions": "Permissions",
    "website": "Website",
    "modules": "Modules",
    "notifications": "Notifications",
    "marketplace": "Marketplace",
    "commercial": "Commercial",
    "offerings": "Offerings",
    "orders": "Orders",
    "bookings": "Bookings",
    "payments": "Payments",
    "memberships": "Memberships",
    "customers": "Customers",
    "leads": "Leads",
    "inventory": "Inventory",
    "fulfilment": "Fulfilment",
    "workforce": "Workforce",
}


def _label(permission_id: str) -> str:
    _, action = permission_id.split(".", 1)
    return action.replace("_", " ").title()


def _group(permission_id: str) -> str:
    return permission_id.split(".", 1)[0]


_PERMISSIONS: dict[str, PermissionDefinition] = {
    pid: PermissionDefinition(
        permission_id=pid,
        display_name=_label(pid),
        group=_group(pid),
        description=f"Canonical permission {pid}",
    )
    for pid in sorted(perm.ALL_PERMISSIONS)
}

_GROUPS: dict[str, PermissionGroup] = {}
for permission in _PERMISSIONS.values():
    group = _GROUPS.setdefault(
        permission.group,
        PermissionGroup(
            group_id=permission.group,
            display_name=_RESOURCE_LABELS.get(permission.group, permission.group.title()),
            permissions=(),
        ),
    )
    existing = list(group.permissions)
    existing.append(permission.permission_id)
    _GROUPS[permission.group] = PermissionGroup(
        group_id=group.group_id,
        display_name=group.display_name,
        permissions=tuple(sorted(existing)),
    )


class PermissionRegistry:
    @staticmethod
    def list_permissions() -> list[dict[str, str]]:
        return [
            {
                "permission_id": p.permission_id,
                "display_name": p.display_name,
                "group": p.group,
            }
            for p in sorted(_PERMISSIONS.values(), key=lambda item: item.permission_id)
        ]

    @staticmethod
    def list_groups() -> list[dict[str, Any]]:
        return [
            {
                "group_id": group.group_id,
                "display_name": group.display_name,
                "permissions": list(group.permissions),
            }
            for group in sorted(_GROUPS.values(), key=lambda item: item.group_id)
        ]

    @staticmethod
    def get(permission_id: str) -> PermissionDefinition | None:
        return _PERMISSIONS.get(permission_id.strip())

    @staticmethod
    def get_or_raise(permission_id: str) -> PermissionDefinition:
        permission = PermissionRegistry.get(permission_id)
        if permission is None:
            from platform_core.exceptions import ValidationError

            raise ValidationError(
                f"Unknown permission '{permission_id}'",
                details={"field": "permission", "permission_id": permission_id},
            )
        return permission

    @staticmethod
    def all_permission_ids() -> frozenset[str]:
        return frozenset(str(pid) for pid in perm.ALL_PERMISSIONS)
