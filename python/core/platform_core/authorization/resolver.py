"""Effective permission and authorization resolvers (Stage 2H)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.authorization.models import (
    REGISTRY_VERSION,
    AuthorizationDecision,
    PermissionOverride,
    PermissionSnapshot,
    ResolvedPermissions,
)
from platform_core.authorization.permission_registry import PermissionRegistry
from platform_core.authorization.role_registry import RoleRegistry
from platform_core.entitlements.resolver import PlatformCapabilityResolver
from platform_core.exceptions import MembershipRequired, ResourceNotFound
from platform_core.models import (
    Business,
    BusinessMembership,
    MembershipAppliedTemplate,
    MembershipPermissionDenial,
    MembershipPermissionGrant,
)
from platform_core.permissions import ROLE_PRIMARY_OWNER, TEMPLATES
from platform_core.services.business import BusinessService
from platform_core.services.team import TeamService


@dataclass(frozen=True)
class MembershipPermissionData:
    grants: tuple[str, ...]
    denials: tuple[str, ...]
    template_ids: tuple[str, ...]


class EffectivePermissionResolver:
    @staticmethod
    async def _load_membership(
        session: AsyncSession, business_id: uuid.UUID, identity_id: uuid.UUID
    ) -> BusinessMembership:
        membership = await TeamService.get_active_membership(session, identity_id, business_id)
        if membership is None:
            raise MembershipRequired()
        return membership

    @staticmethod
    async def _load_permission_data(
        session: AsyncSession, membership_id: uuid.UUID
    ) -> MembershipPermissionData:
        # One round-trip instead of three: grants, denials and applied templates
        # keyed by the same membership_id, tagged so the caller can split them.
        rows = (
            await session.execute(
                select(
                    literal("g").label("kind"),
                    MembershipPermissionGrant.permission.label("value"),
                ).where(MembershipPermissionGrant.membership_id == membership_id)
                .union_all(
                    select(
                        literal("d").label("kind"),
                        MembershipPermissionDenial.permission.label("value"),
                    ).where(MembershipPermissionDenial.membership_id == membership_id),
                    select(
                        literal("t").label("kind"),
                        MembershipAppliedTemplate.template_id.label("value"),
                    ).where(MembershipAppliedTemplate.membership_id == membership_id),
                )
            )
        ).all()
        return MembershipPermissionData(
            grants=tuple(r.value for r in rows if r.kind == "g"),
            denials=tuple(r.value for r in rows if r.kind == "d"),
            template_ids=tuple(r.value for r in rows if r.kind == "t"),
        )

    @staticmethod
    async def resolve_with_parts(
        session: AsyncSession,
        *,
        business: Business,
        membership: BusinessMembership,
    ) -> ResolvedPermissions:
        """`resolve()` when the Business row and active membership are already
        in hand — skips two redundant SELECTs. A primary owner gets the full
        permission set regardless of grants/denials/templates
        (`resolve_from_parts`), so their permission-data load is skipped too."""
        if membership.role == ROLE_PRIMARY_OWNER:
            permission_data = MembershipPermissionData(
                grants=(), denials=(), template_ids=()
            )
        else:
            permission_data = await EffectivePermissionResolver._load_permission_data(
                session, membership.id
            )
        return EffectivePermissionResolver.resolve_from_parts(
            business=business,
            membership=membership,
            permission_data=permission_data,
        )

    @staticmethod
    def resolve_from_parts(
        *,
        business: Business,
        membership: BusinessMembership,
        permission_data: MembershipPermissionData,
    ) -> ResolvedPermissions:
        role = RoleRegistry.get_or_raise(membership.role)
        effective: set[str] = set(role.granted_permissions) - set(role.denied_permissions)
        inherited: set[str] = set()

        for template_id in permission_data.template_ids:
            template_perms = TEMPLATES.get(template_id, frozenset())
            inherited.update(template_perms)
            effective.update(template_perms)

        for permission in permission_data.grants:
            effective.add(permission)

        overrides: list[PermissionOverride] = []
        for permission in permission_data.grants:
            overrides.append(
                PermissionOverride(permission_id=permission, effect="grant", source="membership_override")
            )
        for permission in permission_data.denials:
            overrides.append(
                PermissionOverride(permission_id=permission, effect="deny", source="membership_override")
            )

        denied = set(permission_data.denials)
        effective -= denied

        if membership.role == ROLE_PRIMARY_OWNER:
            effective = set(PermissionRegistry.all_permission_ids())

        layers = {
            "system_role": {
                "role_id": role.role_id,
                "granted": sorted(role.granted_permissions),
                "denied": sorted(role.denied_permissions),
            },
            "membership_role": {
                "templates": list(permission_data.template_ids),
                "grants": list(permission_data.grants),
            },
            "membership_overrides": {
                "grants": list(permission_data.grants),
                "denials": list(permission_data.denials),
            },
            "custom_roles": {"status": "placeholder", "active": False},
            "abac": {"status": "placeholder", "active": False},
        }

        return ResolvedPermissions(
            business_id=str(business.id),
            identity_id=str(membership.identity_id),
            membership_id=str(membership.id),
            role=membership.role,
            effective_permissions=frozenset(effective),
            denied_permissions=frozenset(denied),
            inherited_permissions=frozenset(inherited),
            overrides=tuple(overrides),
            layers=layers,
            registry_version=REGISTRY_VERSION,
            version=membership.version,
        )

    @staticmethod
    async def resolve(
        session: AsyncSession, business_id: uuid.UUID, identity_id: uuid.UUID
    ) -> ResolvedPermissions:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        membership = await EffectivePermissionResolver._load_membership(
            session, business_id, identity_id
        )
        permission_data = await EffectivePermissionResolver._load_permission_data(
            session, membership.id
        )
        return EffectivePermissionResolver.resolve_from_parts(
            business=business,
            membership=membership,
            permission_data=permission_data,
        )

    @staticmethod
    async def build_snapshot(
        session: AsyncSession, business_id: uuid.UUID, identity_id: uuid.UUID
    ) -> PermissionSnapshot:
        resolved = await EffectivePermissionResolver.resolve(session, business_id, identity_id)
        capabilities = await PlatformCapabilityResolver.resolve(session, business_id)
        return PermissionSnapshot(
            business_id=resolved.business_id,
            identity_id=resolved.identity_id,
            membership_id=resolved.membership_id,
            role=resolved.role,
            effective_permissions=resolved.effective_permissions,
            granted_roles=(resolved.role,),
            denied_permissions=resolved.denied_permissions,
            inherited_permissions=resolved.inherited_permissions,
            overrides=resolved.overrides,
            capability_summary=capabilities.capabilities,
            registry_version=resolved.registry_version,
            version=resolved.version,
        )


class AuthorizationService:
    @staticmethod
    async def authorize(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        identity_id: uuid.UUID,
        permission: str,
    ) -> AuthorizationDecision:
        PermissionRegistry.get_or_raise(permission)
        resolved = await EffectivePermissionResolver.resolve(session, business_id, identity_id)
        allowed = permission in resolved.effective_permissions
        overridden = any(
            o.permission_id == permission and o.effect == "grant" for o in resolved.overrides
        ) or any(o.permission_id == permission and o.effect == "deny" for o in resolved.overrides)

        if allowed:
            reason = "permission_granted"
        elif permission in resolved.denied_permissions:
            reason = "permission_denied_by_override"
        else:
            reason = "permission_not_granted"

        return AuthorizationDecision(
            allowed=allowed,
            permission=permission,
            reason=reason,
            source_role=resolved.role,
            overridden=overridden,
            registry_version=REGISTRY_VERSION,
        )

    @staticmethod
    async def effective_permissions(
        session: AsyncSession, business_id: uuid.UUID, identity_id: uuid.UUID
    ) -> frozenset[str]:
        resolved = await EffectivePermissionResolver.resolve(session, business_id, identity_id)
        return frozenset(resolved.effective_permissions)
