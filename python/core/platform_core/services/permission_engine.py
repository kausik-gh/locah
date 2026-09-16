"""Authorization engine service layer (Stage 2H)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.authorization.permission_registry import PermissionRegistry
from platform_core.authorization.resolver import AuthorizationService, EffectivePermissionResolver
from platform_core.authorization.role_registry import RoleRegistry
from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.gates import assert_business_mutable
from platform_core.models import (
    BusinessMembership,
    MembershipPermissionDenial,
    MembershipPermissionGrant,
)
from platform_core.permissions import ROLE_PRIMARY_OWNER
from platform_core.services.audit import AuditService
from platform_core.services.outbox import OutboxService
from platform_core.services.team import TeamService
from platform_core.validation.authorization import validate_override_payload


class PermissionEngineService:
    @staticmethod
    async def list_roles() -> list[dict[str, str]]:
        return list(RoleRegistry.list_roles())

    @staticmethod
    async def list_permissions() -> list[dict[str, str]]:
        return list(PermissionRegistry.list_permissions())

    @staticmethod
    async def permission_matrix() -> dict[str, Any]:
        return {
            "roles": RoleRegistry.list_roles(),
            "matrix": RoleRegistry.permission_matrix(),
            "groups": PermissionRegistry.list_groups(),
        }

    @staticmethod
    async def get_effective_permissions(
        session: AsyncSession, *, business_id: uuid.UUID, identity_id: uuid.UUID
    ) -> dict[str, Any]:
        resolved = await EffectivePermissionResolver.resolve(session, business_id, identity_id)
        serialized: dict[str, Any] = resolved.serialize()
        return serialized

    @staticmethod
    async def get_authorization_snapshot(
        session: AsyncSession, *, business_id: uuid.UUID, identity_id: uuid.UUID
    ) -> dict[str, Any]:
        snapshot = await EffectivePermissionResolver.build_snapshot(
            session, business_id, identity_id
        )
        snap_serialized: dict[str, Any] = snapshot.serialize()
        return snap_serialized

    @staticmethod
    async def authorize(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        identity_id: uuid.UUID,
        permission: str,
    ) -> dict[str, Any]:
        decision = await AuthorizationService.authorize(
            session,
            business_id=business_id,
            identity_id=identity_id,
            permission=permission,
        )
        decision_payload: dict[str, Any] = decision.serialize()
        return decision_payload

    @staticmethod
    async def _load_membership_for_update(
        session: AsyncSession, business_id: uuid.UUID, membership_id: uuid.UUID
    ) -> BusinessMembership:
        membership = await TeamService.get_membership_by_id_for_update(
            session, business_id, membership_id
        )
        if membership is None or membership.status != "active":
            raise ResourceNotFound("Membership")
        return membership

    @staticmethod
    async def patch_membership_overrides(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        membership_id: uuid.UUID,
        payload: dict[str, Any],
        actor_id: uuid.UUID,
        actor_membership: BusinessMembership,
        correlation_id: str,
    ) -> dict[str, Any]:
        target = await PermissionEngineService._load_membership_for_update(
            session, business_id, membership_id
        )
        from platform_core.models import Business

        biz_result = await session.execute(
            select(Business)
            .where(Business.id == business_id, Business.deleted_at.is_(None))
            .with_for_update()
        )
        biz = biz_result.scalars().first()
        if biz is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(biz.state, action="update_permission_overrides")

        if target.role == ROLE_PRIMARY_OWNER:
            raise ValidationError(
                "Primary Owner permissions cannot be overridden",
                details={"field": "membership_id"},
            )

        expected_version = payload.get("version")
        if expected_version is not None:
            if not isinstance(expected_version, int):
                raise ValidationError("version must be an integer", details={"field": "version"})
            if target.version != expected_version:
                raise ConflictError(
                    "Stale membership version",
                    details={
                        "expected_version": expected_version,
                        "current_version": target.version,
                    },
                )

        patch = validate_override_payload(payload)
        actor_permissions = await AuthorizationService.effective_permissions(
            session, business_id, actor_id
        )
        if actor_membership.role != ROLE_PRIMARY_OWNER:
            proposed_grants = set(patch.grants)
            excess = proposed_grants - actor_permissions
            if excess:
                from platform_core.exceptions import PermissionDelegationError

                raise PermissionDelegationError(excess)

        for permission in patch.grants:
            existing = await session.execute(
                select(MembershipPermissionGrant).where(
                    MembershipPermissionGrant.membership_id == membership_id,
                    MembershipPermissionGrant.permission == permission,
                )
            )
            if existing.scalars().first() is None:
                session.add(
                    MembershipPermissionGrant(
                        business_id=business_id,
                        membership_id=membership_id,
                        permission=permission,
                        granted_by=actor_id,
                    )
                )
                await OutboxService.publish(
                    session,
                    event_type="permission.override.created",
                    payload={
                        "business_id": str(business_id),
                        "membership_id": str(membership_id),
                        "permission": permission,
                        "effect": "grant",
                    },
                    business_id=business_id,
                    correlation_id=correlation_id,
                )

        for permission in patch.remove_grants:
            await session.execute(
                delete(MembershipPermissionGrant).where(
                    MembershipPermissionGrant.membership_id == membership_id,
                    MembershipPermissionGrant.permission == permission,
                )
            )
            await OutboxService.publish(
                session,
                event_type="permission.override.removed",
                payload={
                    "business_id": str(business_id),
                    "membership_id": str(membership_id),
                    "permission": permission,
                    "effect": "grant",
                },
                business_id=business_id,
                correlation_id=correlation_id,
            )

        for permission in patch.denials:
            existing = await session.execute(
                select(MembershipPermissionDenial).where(
                    MembershipPermissionDenial.membership_id == membership_id,
                    MembershipPermissionDenial.permission == permission,
                )
            )
            if existing.scalars().first() is None:
                session.add(
                    MembershipPermissionDenial(
                        business_id=business_id,
                        membership_id=membership_id,
                        permission=permission,
                        denied_by=actor_id,
                    )
                )
                await OutboxService.publish(
                    session,
                    event_type="permission.override.created",
                    payload={
                        "business_id": str(business_id),
                        "membership_id": str(membership_id),
                        "permission": permission,
                        "effect": "deny",
                    },
                    business_id=business_id,
                    correlation_id=correlation_id,
                )

        for permission in patch.remove_denials:
            await session.execute(
                delete(MembershipPermissionDenial).where(
                    MembershipPermissionDenial.membership_id == membership_id,
                    MembershipPermissionDenial.permission == permission,
                )
            )
            await OutboxService.publish(
                session,
                event_type="permission.override.removed",
                payload={
                    "business_id": str(business_id),
                    "membership_id": str(membership_id),
                    "permission": permission,
                    "effect": "deny",
                },
                business_id=business_id,
                correlation_id=correlation_id,
            )

        target.version += 1
        await session.flush()

        resolved = await EffectivePermissionResolver.resolve(
            session, business_id, target.identity_id
        )
        snapshot = resolved.serialize()

        await OutboxService.publish(
            session,
            event_type="authorization.snapshot.updated",
            payload={
                "business_id": str(business_id),
                "membership_id": str(membership_id),
                "identity_id": str(target.identity_id),
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="authorization.snapshot.updated",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="membership",
            resource_id=membership_id,
            action="update_permission_overrides",
            before_state=None,
            after_state=snapshot,
        )

        return snapshot  # type: ignore[no-any-return]
