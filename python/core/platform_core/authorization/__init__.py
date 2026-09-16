"""Central authorization registries and resolvers."""

from platform_core.authorization.models import REGISTRY_VERSION
from platform_core.authorization.permission_registry import PermissionRegistry
from platform_core.authorization.resolver import AuthorizationService, EffectivePermissionResolver
from platform_core.authorization.role_registry import RoleRegistry

__all__ = [
    "AuthorizationService",
    "EffectivePermissionResolver",
    "PermissionRegistry",
    "REGISTRY_VERSION",
    "RoleRegistry",
]
