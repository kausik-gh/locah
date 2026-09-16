import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.context import MembershipInfo
from platform_core.exceptions import (
    ConflictError,
    MembershipRequired,
    PermissionDenied,
    ResourceNotFound,
    ValidationError,
)
from platform_core.gates import assert_business_mutable
from platform_core.models import (
    Business,
    BusinessMembership,
    MembershipPermissionGrant,
)
from platform_core.permissions import (
    ROLE_MANAGER,
    ROLE_MEMBER,
    ROLE_PRIMARY_OWNER,
    TEAM_REMOVE,
    TEAM_UPDATE_ROLE,
)
from platform_core.services.audit import AuditService
from platform_core.services.outbox import OutboxService

CANONICAL_ROLES: frozenset[str] = frozenset({ROLE_PRIMARY_OWNER, ROLE_MANAGER, ROLE_MEMBER})

ROLE_RANK: dict[str, int] = {
    ROLE_PRIMARY_OWNER: 3,
    ROLE_MANAGER: 2,
    ROLE_MEMBER: 1,
}

ALLOWED_MEMBERSHIP_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"active", "removed"}),
    "active": frozenset({"suspended", "removed"}),
    "suspended": frozenset({"active", "removed"}),
    "removed": frozenset(),
}


class TeamService:
    @staticmethod
    async def get_active_membership(
        session: AsyncSession, identity_id: uuid.UUID, business_id: uuid.UUID
    ) -> BusinessMembership | None:
        result = await session.execute(
            select(BusinessMembership).where(
                BusinessMembership.identity_id == identity_id,
                BusinessMembership.business_id == business_id,
                BusinessMembership.status == "active",
                BusinessMembership.deleted_at.is_(None),
            )
        )
        return result.scalars().first()

    @staticmethod
    async def get_membership(
        session: AsyncSession, identity_id: uuid.UUID, business_id: uuid.UUID
    ) -> BusinessMembership | None:
        """Any non-deleted membership row (active, pending, suspended, removed)."""
        result = await session.execute(
            select(BusinessMembership).where(
                BusinessMembership.identity_id == identity_id,
                BusinessMembership.business_id == business_id,
                BusinessMembership.deleted_at.is_(None),
            )
        )
        return result.scalars().first()

    @staticmethod
    async def get_membership_by_id(
        session: AsyncSession, business_id: uuid.UUID, membership_id: uuid.UUID
    ) -> BusinessMembership | None:
        result = await session.execute(
            select(BusinessMembership).where(
                BusinessMembership.id == membership_id,
                BusinessMembership.business_id == business_id,
                BusinessMembership.deleted_at.is_(None),
            )
        )
        return result.scalars().first()

    @staticmethod
    async def get_membership_by_id_for_update(
        session: AsyncSession, business_id: uuid.UUID, membership_id: uuid.UUID
    ) -> BusinessMembership | None:
        result = await session.execute(
            select(BusinessMembership)
            .where(
                BusinessMembership.id == membership_id,
                BusinessMembership.business_id == business_id,
                BusinessMembership.deleted_at.is_(None),
            )
            .with_for_update()
        )
        return result.scalars().first()

    @staticmethod
    async def list_members(
        session: AsyncSession, business_id: uuid.UUID
    ) -> list[BusinessMembership]:
        result = await session.execute(
            select(BusinessMembership).where(
                BusinessMembership.business_id == business_id,
                BusinessMembership.deleted_at.is_(None),
                BusinessMembership.status != "removed",
            )
        )
        return list(result.scalars().all())

    @staticmethod
    def to_membership_info(m: BusinessMembership) -> MembershipInfo:
        scope = list(m.location_scope) if m.location_scope else None
        return MembershipInfo(
            id=m.id,
            business_id=m.business_id,
            identity_id=m.identity_id,
            role=m.role,
            status=m.status,
            location_scope=scope,
        )

    @staticmethod
    def serialize_membership(m: BusinessMembership) -> dict[str, Any]:
        location_scope = (
            [str(lid) for lid in m.location_scope] if m.location_scope is not None else None
        )
        return {
            "id": str(m.id),
            "identity_id": str(m.identity_id),
            "role": m.role,
            "status": m.status,
            "location_scope": location_scope,
            "invited_at": m.invited_at.isoformat() if m.invited_at else None,
            "activated_at": m.activated_at.isoformat() if m.activated_at else None,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        }

    @staticmethod
    def validate_status_transition(current: str, target: str) -> None:
        allowed = ALLOWED_MEMBERSHIP_TRANSITIONS.get(current, frozenset())
        if target not in allowed:
            raise ValidationError(
                f"Invalid membership status transition: {current} → {target}",
                details={"from_status": current, "to_status": target},
            )

    @staticmethod
    def assert_can_assign_role(actor_role: str, new_role: str) -> None:
        if new_role not in CANONICAL_ROLES:
            raise ValidationError(
                f"Invalid role: {new_role}",
                details={"role": new_role, "allowed_roles": sorted(CANONICAL_ROLES)},
            )
        if new_role == ROLE_PRIMARY_OWNER:
            raise PermissionDenied(TEAM_UPDATE_ROLE)
        if ROLE_RANK[new_role] > ROLE_RANK[actor_role]:
            raise PermissionDenied(TEAM_UPDATE_ROLE)
        if new_role == ROLE_MANAGER and actor_role != ROLE_PRIMARY_OWNER:
            raise PermissionDenied(TEAM_UPDATE_ROLE)

    @staticmethod
    def assert_can_manage_target(
        actor: BusinessMembership,
        target: BusinessMembership,
        *,
        action: str,
    ) -> None:
        if target.role == ROLE_PRIMARY_OWNER:
            raise PermissionDenied(TEAM_REMOVE if action == "remove" else TEAM_UPDATE_ROLE)
        if actor.identity_id == target.identity_id:
            if action == "remove" and actor.role == ROLE_PRIMARY_OWNER:
                raise PermissionDenied(TEAM_REMOVE)
            return
        if actor.role == ROLE_MANAGER and target.role == ROLE_MANAGER:
            raise PermissionDenied(TEAM_REMOVE if action == "remove" else TEAM_UPDATE_ROLE)
        if actor.role != ROLE_PRIMARY_OWNER:
            if ROLE_RANK[target.role] >= ROLE_RANK[actor.role]:
                raise PermissionDenied(
                    TEAM_REMOVE if action == "remove" else TEAM_UPDATE_ROLE
                )

    @staticmethod
    async def resolve_permissions(
        session: AsyncSession,
        membership: BusinessMembership,
        *,
        business: Business | None = None,
    ) -> frozenset[str]:
        from platform_core.authorization.resolver import (
            AuthorizationService,
            EffectivePermissionResolver,
        )

        # Perf: when the caller already holds the Business + active membership
        # (the gate chain in resolve_request_context does), skip the resolver's
        # re-fetch of both and go straight to the permission-data load.
        if business is not None:
            resolved = await EffectivePermissionResolver.resolve_with_parts(
                session, business=business, membership=membership
            )
            return frozenset(resolved.effective_permissions)

        perms = await AuthorizationService.effective_permissions(
            session, membership.business_id, membership.identity_id
        )
        return frozenset(perms)

    @staticmethod
    async def grant_permissions(
        session: AsyncSession,
        *,
        membership: BusinessMembership,
        permissions: set[str],
        granted_by: uuid.UUID,
        actor_permissions: frozenset[str],
        is_primary_owner: bool,
        correlation_id: str | None = None,
    ) -> None:
        if not is_primary_owner:
            excess = permissions - actor_permissions
            if excess:
                from platform_core.exceptions import PermissionDelegationError

                raise PermissionDelegationError(excess)

        for perm in permissions:
            session.add(
                MembershipPermissionGrant(
                    business_id=membership.business_id,
                    membership_id=membership.id,
                    permission=perm,
                    granted_by=granted_by,
                )
            )
        await session.flush()
        await OutboxService.publish(
            session,
            event_type="permission.granted",
            payload={
                "membership_id": str(membership.id),
                "business_id": str(membership.business_id),
                "permissions": sorted(permissions),
                "granted_by": str(granted_by),
            },
            business_id=membership.business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="permission.granted",
            actor_identity_id=granted_by,
            actor_context="business",
            business_id=membership.business_id,
            resource_type="membership",
            resource_id=membership.id,
            action="grant_permissions",
            after_state={"permissions": sorted(permissions)},
        )

    @staticmethod
    async def invite_member(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        identity_id: uuid.UUID,
        role: str,
        invited_by: uuid.UUID,
        correlation_id: str | None = None,
    ) -> BusinessMembership:
        """Create a pending membership directly, without the email invitation flow.

        Emits `membership.created` with `source="direct_invite"`, mirroring
        `create_membership_from_invitation` (`source="invitation"`). Without this
        the direct-invite path was invisible to Notifications, Audit, and every
        other event consumer, while the email path was not.
        """
        membership = BusinessMembership(
            business_id=business_id,
            identity_id=identity_id,
            role=role,
            status="pending",
            invited_at=datetime.now(timezone.utc),
        )
        session.add(membership)
        await session.flush()

        await OutboxService.publish(
            session,
            event_type="membership.created",
            payload={
                "business_id": str(business_id),
                "membership_id": str(membership.id),
                "identity_id": str(identity_id),
                "role": role,
                "status": membership.status,
                "source": "direct_invite",
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="membership.created",
            actor_identity_id=invited_by,
            actor_context="business",
            business_id=business_id,
            resource_type="membership",
            resource_id=membership.id,
            action="invite_member",
            after_state={
                "role": role,
                "status": membership.status,
                "identity_id": str(identity_id),
            },
        )
        return membership

    @staticmethod
    async def activate_membership(
        session: AsyncSession, membership: BusinessMembership
    ) -> BusinessMembership:
        TeamService.validate_status_transition(membership.status, "active")
        membership.status = "active"
        membership.activated_at = datetime.now(timezone.utc)
        await session.flush()
        return membership

    @staticmethod
    async def create_membership_from_invitation(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        identity_id: uuid.UUID,
        role: str,
        location_scope: list[uuid.UUID] | None,
        invited_by: uuid.UUID,
        correlation_id: str,
    ) -> BusinessMembership:
        """Create an active membership when an invitation is accepted (Stage 2D)."""
        existing = await TeamService.get_membership(session, identity_id, business_id)
        if existing is not None:
            if existing.status == "active":
                raise ConflictError("Membership already active for this identity")
            if existing.status == "suspended":
                raise ConflictError("Membership is suspended for this identity")
            if existing.status == "pending":
                existing.role = role
                existing.location_scope = location_scope
                membership = await TeamService.activate_membership(session, existing)
            elif existing.status == "removed":
                now = datetime.now(timezone.utc)
                existing.role = role
                existing.location_scope = location_scope
                existing.status = "active"
                existing.invited_at = now
                existing.activated_at = now
                existing.version += 1
                await session.flush()
                membership = existing
            else:
                raise ConflictError("Membership already exists for this identity")
        else:
            membership = BusinessMembership(
                business_id=business_id,
                identity_id=identity_id,
                role=role,
                status="active",
                location_scope=location_scope,
                invited_at=datetime.now(timezone.utc),
                activated_at=datetime.now(timezone.utc),
            )
            session.add(membership)
            await session.flush()

        await OutboxService.publish(
            session,
            event_type="membership.created",
            payload={
                "business_id": str(business_id),
                "membership_id": str(membership.id),
                "identity_id": str(identity_id),
                "role": role,
                "status": membership.status,
                "source": "invitation",
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="membership.created",
            actor_identity_id=identity_id,
            actor_context="personal",
            business_id=business_id,
            resource_type="membership",
            resource_id=membership.id,
            action="accept_invitation",
            after_state={
                "role": role,
                "status": membership.status,
                "invited_by": str(invited_by),
            },
        )
        return membership

    @staticmethod
    async def update_membership(
        session: AsyncSession,
        *,
        business: Business,
        target: BusinessMembership,
        actor: BusinessMembership,
        correlation_id: str,
        role: str | None = None,
        location_scope: list[uuid.UUID] | None = None,
        update_role: bool = False,
        update_location_scope: bool = False,
    ) -> BusinessMembership:
        assert_business_mutable(business.state, action="update_membership")
        if target.status == "removed":
            raise ValidationError("Cannot update a removed membership")

        TeamService.assert_can_manage_target(actor, target, action="update")
        before = TeamService.serialize_membership(target)

        if update_role:
            if role is None:
                raise ValidationError("role is required when updating role")
            # Doc 12 §8.9: permission gate [8] precedes resource/workflow-state
            # gate [9]. Whether the actor may assign this role is decided before
            # whether the target's current state permits a role change.
            TeamService.assert_can_assign_role(actor.role, role)
            if target.status != "active":
                raise ValidationError("Role changes require an active membership")
            target.role = role

        if update_location_scope:
            target.location_scope = location_scope

        if not update_role and not update_location_scope:
            raise ValidationError("No membership fields to update")

        target.version += 1
        await session.flush()

        after = TeamService.serialize_membership(target)
        await TeamService._publish_membership_event(
            session,
            event_type="membership.updated",
            audit_action="update",
            business=business,
            target=target,
            actor_id=actor.identity_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state=after,
        )
        return target

    @staticmethod
    async def suspend_membership(
        session: AsyncSession,
        *,
        business: Business,
        target: BusinessMembership,
        actor: BusinessMembership,
        correlation_id: str,
    ) -> BusinessMembership:
        assert_business_mutable(business.state, action="suspend_membership")
        TeamService.assert_can_manage_target(actor, target, action="update")
        if target.status == "suspended":
            raise ConflictError("Membership is already suspended")
        TeamService.validate_status_transition(target.status, "suspended")

        before = {"status": target.status}
        target.status = "suspended"
        target.version += 1
        await session.flush()

        await TeamService._publish_membership_event(
            session,
            event_type="membership.suspended",
            audit_action="suspend",
            business=business,
            target=target,
            actor_id=actor.identity_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state={"status": target.status},
        )
        return target

    @staticmethod
    async def reactivate_membership(
        session: AsyncSession,
        *,
        business: Business,
        target: BusinessMembership,
        actor: BusinessMembership,
        correlation_id: str,
    ) -> BusinessMembership:
        assert_business_mutable(business.state, action="reactivate_membership")
        TeamService.assert_can_manage_target(actor, target, action="update")
        if target.status == "active":
            raise ConflictError("Membership is already active")
        TeamService.validate_status_transition(target.status, "active")

        before = {"status": target.status}
        target.status = "active"
        if target.activated_at is None:
            target.activated_at = datetime.now(timezone.utc)
        target.version += 1
        await session.flush()

        await TeamService._publish_membership_event(
            session,
            event_type="membership.reactivated",
            audit_action="reactivate",
            business=business,
            target=target,
            actor_id=actor.identity_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state={"status": target.status},
        )
        return target

    @staticmethod
    async def remove_membership(
        session: AsyncSession,
        *,
        business: Business,
        target: BusinessMembership,
        actor: BusinessMembership,
        correlation_id: str,
    ) -> BusinessMembership:
        assert_business_mutable(business.state, action="remove_membership")
        is_self = actor.identity_id == target.identity_id
        if not is_self:
            TeamService.assert_can_manage_target(actor, target, action="remove")
        elif target.role == ROLE_PRIMARY_OWNER:
            raise PermissionDenied(TEAM_REMOVE)

        if target.status == "removed":
            raise ConflictError("Membership is already removed")
        TeamService.validate_status_transition(target.status, "removed")

        before = TeamService.serialize_membership(target)
        target.status = "removed"
        target.version += 1
        await session.flush()

        await TeamService._publish_membership_event(
            session,
            event_type="membership.removed",
            audit_action="remove",
            business=business,
            target=target,
            actor_id=actor.identity_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state={"status": target.status},
        )
        return target

    @staticmethod
    async def transfer_primary_ownership(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_identity_id: uuid.UUID,
        target_membership_id: uuid.UUID,
        correlation_id: str,
        demote_to_role: str = ROLE_MANAGER,
    ) -> tuple[BusinessMembership, BusinessMembership]:
        if demote_to_role not in {ROLE_MANAGER, ROLE_MEMBER}:
            raise ValidationError(
                f"Invalid demote role: {demote_to_role}",
                details={"demote_to_role": demote_to_role},
            )

        business_result = await session.execute(
            select(Business).where(Business.id == business_id).with_for_update()
        )
        business = business_result.scalars().first()
        if not business or business.deleted_at is not None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="transfer_ownership")

        actor_membership = await TeamService.get_membership(
            session, actor_identity_id, business_id
        )
        if actor_membership is None or actor_membership.role != ROLE_PRIMARY_OWNER:
            raise PermissionDenied(TEAM_UPDATE_ROLE)

        actor = await TeamService.get_membership_by_id_for_update(
            session, business_id, actor_membership.id
        )
        target = await TeamService.get_membership_by_id_for_update(
            session, business_id, target_membership_id
        )
        if actor is None or target is None:
            raise ResourceNotFound("Membership")
        if actor.status != "active":
            raise MembershipRequired()
        if target.status != "active":
            raise ValidationError("Ownership transfer target must be an active member")
        if target.role == ROLE_PRIMARY_OWNER:
            raise ValidationError("Target is already the primary owner")
        if target.identity_id == actor_identity_id:
            raise ValidationError("Cannot transfer ownership to yourself")

        before = {
            "primary_owner_identity_id": str(business.primary_owner_identity_id),
            "actor_role": actor.role,
            "target_role": target.role,
        }

        actor.role = demote_to_role
        actor.version += 1
        target.role = ROLE_PRIMARY_OWNER
        target.version += 1
        business.primary_owner_identity_id = target.identity_id
        business.version += 1
        await session.flush()

        after = {
            "primary_owner_identity_id": str(business.primary_owner_identity_id),
            "actor_role": actor.role,
            "target_role": target.role,
        }

        await OutboxService.publish(
            session,
            event_type="ownership.transferred",
            payload={
                "business_id": str(business_id),
                "from_identity_id": str(actor.identity_id),
                "to_identity_id": str(target.identity_id),
                "from_membership_id": str(actor.id),
                "to_membership_id": str(target.id),
                "demote_to_role": demote_to_role,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="ownership.transferred",
            actor_identity_id=actor_identity_id,
            actor_context="business",
            business_id=business_id,
            resource_type="business",
            resource_id=business_id,
            action="transfer_ownership",
            before_state=before,
            after_state=after,
        )
        return actor, target

    @staticmethod
    async def _publish_membership_event(
        session: AsyncSession,
        *,
        event_type: str,
        audit_action: str,
        business: Business,
        target: BusinessMembership,
        actor_id: uuid.UUID,
        correlation_id: str,
        before_state: dict[str, Any],
        after_state: dict[str, Any],
    ) -> None:
        await OutboxService.publish(
            session,
            event_type=event_type,
            payload={
                "business_id": str(business.id),
                "membership_id": str(target.id),
                "identity_id": str(target.identity_id),
                "before": before_state,
                "after": after_state,
            },
            business_id=business.id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type=event_type,
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business.id,
            resource_type="membership",
            resource_id=target.id,
            action=audit_action,
            before_state=before_state,
            after_state=after_state,
        )
