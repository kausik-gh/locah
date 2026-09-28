"""Adding staff and their logins (founder instruction; Capability Universe §7.3).

The owner adds a person with a role and scope. LOCAH makes a one-time join
link — only its hash is stored — that the owner shares however they like
(WhatsApp, SMS, in person). The person opens it, creates their login with the
invited email (or signs in if they already have one) and joins with the role
already set. Nobody but the person ever knows their password.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import (
    ConflictError,
    PermissionDelegationError,
    ResourceNotFound,
    ValidationError,
)
from platform_core.models import Business, BusinessInvitation, BusinessMembership
from platform_core.permissions import ROLE_PRIMARY_OWNER


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def mask_email(email: str) -> str:
    name, _, domain = email.partition("@")
    return f"{name[:1]}{'•' * max(2, min(len(name) - 1, 6))}@{domain}" if domain else email


class StaffService:
    @staticmethod
    async def add_person(
        session: AsyncSession, business: Business, actor: BusinessMembership, *, name: str, email: str,
        role_key: str, location_ids: list[uuid.UUID], actor_permissions: frozenset[str], correlation_id: str,
    ) -> tuple[BusinessInvitation, str]:
        from platform_core.services.invitation import InvitationService
        from platform_core.services.roles import RoleService
        from platform_core.services.team import TeamService

        name = (name or "").strip()
        if not 1 <= len(name) <= 80:
            raise ValidationError("Enter their name", details={"field": "name"})
        system_role, permissions, scope, _ = await RoleService.resolve_role(session, business.id, role_key)
        if actor.role != ROLE_PRIMARY_OWNER:
            TeamService.assert_can_assign_role(actor.role, system_role)
            excess = set(permissions) - set(actor_permissions)
            if excess:
                raise PermissionDelegationError(excess)
        locations = (await RoleService._check_locations(session, business.id, location_ids)
                     if scope == "location" else None)
        invitation = await InvitationService.create_invitation(
            session, business=business, actor=actor, invited_email=email, invited_role=system_role,
            correlation_id=correlation_id, location_scope=locations,
        )
        token = secrets.token_urlsafe(24)
        invitation.role_template = role_key
        invitation.access_scope = scope
        invitation.display_name = name
        invitation.join_token_hash = _hash(token)
        await session.flush()
        return invitation, token

    @staticmethod
    async def new_link(session: AsyncSession, business_id: uuid.UUID, invitation_id: uuid.UUID) -> str:
        """A fresh link for a pending invitation; the previous one stops working."""
        from datetime import timedelta

        from platform_core.services.invitation import INVITATION_TTL_HOURS, InvitationService

        inv = await InvitationService.get_by_id_for_update(session, business_id, invitation_id)
        if inv is None:
            raise ResourceNotFound("Invitation")
        if inv.status != "pending":
            raise ConflictError("This person has already joined or the invitation was withdrawn")
        token = secrets.token_urlsafe(24)
        inv.join_token_hash = _hash(token)
        inv.expires_at = datetime.now(timezone.utc) + timedelta(hours=INVITATION_TTL_HOURS)
        inv.version += 1
        await session.flush()
        return token

    @staticmethod
    async def public_view(session: AsyncSession, token: str) -> dict[str, Any]:
        """What the join page shows. The token is the only credential."""
        from platform_core.authorization.role_templates import ROLE_TEMPLATES, SCOPE_WORDS
        from platform_core.context_resolver import bind_public_context

        if not token or len(token) < 20:
            raise ResourceNotFound("Invitation")
        await session.execute(text("SELECT set_config('app.current_join_token', :h, true)"), {"h": _hash(token)})
        inv = (await session.execute(
            select(BusinessInvitation).where(BusinessInvitation.join_token_hash == _hash(token))
        )).scalars().first()
        if inv is None:
            raise ResourceNotFound("Invitation")
        await bind_public_context(session, inv.business_id)
        business = (await session.execute(select(Business).where(Business.id == inv.business_id))).scalars().first()
        if business is None or business.deleted_at is not None:
            raise ResourceNotFound("Invitation")
        role: dict[str, Any] = {"label": "Team member", "does": None, "home": None}
        key = inv.role_template or ""
        if key.startswith("custom:"):
            row = (await session.execute(
                text("SELECT name, based_on FROM business_custom_roles WHERE id = CAST(:id AS uuid) "
                     "AND business_id = :b"), {"id": key[7:], "b": str(inv.business_id)},
            )).first()
            if row:
                base = ROLE_TEMPLATES.get(row[1] or "")
                role = {"label": row[0], "does": base.does if base else None, "home": base.home if base else None}
        elif key in ROLE_TEMPLATES:
            t = ROLE_TEMPLATES[key]
            role = {"label": t.label, "does": t.does, "home": t.home}
        names = {str(r[0]): r[1] for r in (await session.execute(
            text("SELECT id, name FROM business_locations WHERE business_id = :b"), {"b": str(inv.business_id)},
        )).all()}
        now = datetime.now(timezone.utc)
        expires = inv.expires_at if inv.expires_at.tzinfo else inv.expires_at.replace(tzinfo=timezone.utc)
        status = "expired" if inv.status == "pending" and expires <= now else inv.status
        return {
            "business": {"id": str(business.id), "name": business.display_name},
            "invitation_id": str(inv.id), "name": inv.display_name, "email_hint": mask_email(inv.invited_email),
            "role": role, "scope_words": SCOPE_WORDS.get(inv.access_scope, ""),
            "locations": [names.get(str(x), "A location") for x in (inv.location_scope or [])],
            "status": status, "expires_at": expires.isoformat(),
        }

    @staticmethod
    async def apply_invited_role(
        session: AsyncSession, invitation: BusinessInvitation, membership: BusinessMembership,
        correlation_id: str | None,
    ) -> None:
        """On acceptance: give the new member the role the owner chose. The
        inviter's authority is re-checked now, not only when they invited."""
        from platform_core.authorization.resolver import AuthorizationService
        from platform_core.services.roles import RoleService
        from platform_core.services.team import TeamService

        if not invitation.role_template:
            return
        inviter = await TeamService.get_active_membership(session, invitation.invited_by, invitation.business_id)
        if inviter is None:
            raise ConflictError("The person who added you is no longer on the team. Ask the owner for a new link.")
        perms = await AuthorizationService.effective_permissions(
            session, business_id=invitation.business_id, identity_id=invitation.invited_by)
        await RoleService.apply(
            session, membership, role_key=invitation.role_template,
            location_ids=list(invitation.location_scope or []), actor_id=invitation.invited_by,
            actor_permissions=frozenset(perms), actor_role=inviter.role, correlation_id=correlation_id,
        )
        if invitation.display_name:
            await session.execute(
                text("UPDATE platform_identities SET display_name = :n WHERE id = :i AND display_name IS NULL"),
                {"n": invitation.display_name, "i": str(membership.identity_id)},
            )
