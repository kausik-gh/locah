"""Roles an owner gives people (Capability Universe §7.2–§7.3; Business OS Guide §5).

A role is a permission set + scope + default surface. Owners pick a template,
or clone one into a custom role; nobody can hand out more than they hold
themselves. Assigning a role replaces whatever that person had before — the
role is the one place their access is defined.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.authorization.role_templates import (
    OWNER,
    PERMISSION_WORDS,
    ROLE_TEMPLATES,
    SCOPE_WORDS,
    SURFACES,
    describe,
)
from platform_core.exceptions import (
    ConflictError,
    PermissionDelegationError,
    ResourceNotFound,
    ValidationError,
)
from platform_core.models import (
    BusinessMembership,
    MembershipAppliedTemplate,
    MembershipPermissionDenial,
    MembershipPermissionGrant,
)
from platform_core.permissions import ALL_PERMISSIONS, ROLE_MANAGER, ROLE_MEMBER, ROLE_PRIMARY_OWNER
from platform_core.services.audit import AuditService
from platform_core.services.outbox import OutboxService
from platform_core.services.team import TeamService

# Scopes the platform can enforce today: assignment since P2-01 (§7.3 — the
# server filter and the assigned-record RLS arm). "Self" waits for staff
# self-service (own profile and time).
ENFORCED_SCOPES = ("business", "location", "assignment")


def _operational(states: dict[str, str]) -> set[str]:
    return {k for k, v in states.items() if v in ("enabled", "ready", "active")}


class RoleService:
    # ------------------------------------------------------------------ catalogue
    @staticmethod
    async def catalogue(session: AsyncSession, business_id: uuid.UUID) -> dict[str, Any]:
        from platform_core.services.module_readiness import module_states

        live = _operational(await module_states(session, business_id))
        templates = [describe(t) for t in ROLE_TEMPLATES.values() if t.offered(live)]
        custom = await RoleService.custom_roles(session, business_id)
        return {
            "owner": describe(OWNER),
            "templates": templates,
            "custom": custom,
            "permission_words": PERMISSION_WORDS,
            "scopes": {k: SCOPE_WORDS[k] for k in ENFORCED_SCOPES},
        }

    @staticmethod
    async def custom_roles(session: AsyncSession, business_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (await session.execute(
            text("""
                SELECT r.id, r.name, r.based_on, r.permissions, r.access_scope,
                       (SELECT count(*) FROM business_memberships m
                         WHERE m.business_id = r.business_id AND m.role_template = 'custom:' || r.id::text
                           AND m.deleted_at IS NULL AND m.status <> 'removed') AS holders
                FROM business_custom_roles r
                WHERE r.business_id = :b AND r.archived_at IS NULL ORDER BY lower(r.name)
            """),
            {"b": str(business_id)},
        )).all()
        return [
            {"key": f"custom:{r[0]}", "id": str(r[0]), "label": r[1], "based_on": r[2],
             "based_on_label": ROLE_TEMPLATES[r[2]].label if r[2] in ROLE_TEMPLATES else None,
             "permissions": sorted(r[3] or []), "scope": r[4], "scope_words": SCOPE_WORDS[r[4]],
             "surface": "workspace", "surface_words": SURFACES["workspace"],
             "home": ROLE_TEMPLATES[r[2]].home if r[2] in ROLE_TEMPLATES else "Your work today",
             "holders": int(r[5])}
            for r in rows
        ]

    # ------------------------------------------------------------------ custom roles
    @staticmethod
    def _check_permissions(permissions: list[str], actor_permissions: frozenset[str], is_owner: bool) -> list[str]:
        clean = sorted(set(permissions))
        unknown = [x for x in clean if x not in ALL_PERMISSIONS]
        if unknown:
            raise ValidationError("Unknown permission", details={"field": "permissions", "unknown": unknown})
        if not clean:
            raise ValidationError("Choose at least one thing this role can do", details={"field": "permissions"})
        if not is_owner:
            excess = set(clean) - set(actor_permissions)
            if excess:
                raise PermissionDelegationError(excess)
        return clean

    @staticmethod
    def _check_scope(scope: str) -> None:
        if scope not in ENFORCED_SCOPES:
            raise ValidationError("That scope is not available yet", details={"field": "scope"})

    @staticmethod
    async def create_custom_role(
        session: AsyncSession, business_id: uuid.UUID, *, name: str, based_on: str | None,
        permissions: list[str], scope: str, actor_id: uuid.UUID, actor_permissions: frozenset[str],
        is_owner: bool,
    ) -> dict[str, Any]:
        name = (name or "").strip()
        if not 2 <= len(name) <= 60:
            raise ValidationError("Give the role a name (2–60 characters)", details={"field": "name"})
        if based_on is not None and based_on not in ROLE_TEMPLATES:
            raise ValidationError("Unknown role to start from", details={"field": "based_on"})
        RoleService._check_scope(scope)
        clean = RoleService._check_permissions(permissions, actor_permissions, is_owner)
        if scope == "assignment":
            from platform_core.authorization.assignment_scope import ASSIGNMENT_PERMISSIONS

            wider = sorted(set(clean) - ASSIGNMENT_PERMISSIONS)
            if wider:
                raise ValidationError(
                    "A role limited to its own assignments can only hold bookings, enquiries, quotes and their "
                    "customers — not: " + ", ".join(PERMISSION_WORDS.get(x, x) for x in wider),
                    details={"field": "permissions", "not_assignable": wider})
        if name.lower() in {t.label.lower() for t in ROLE_TEMPLATES.values()} | {"owner"}:
            raise ConflictError("A built-in role already has that name")
        clash = (await session.execute(
            text("SELECT 1 FROM business_custom_roles WHERE business_id = :b AND lower(name) = lower(:n) "
                 "AND archived_at IS NULL"), {"b": str(business_id), "n": name},
        )).first()
        if clash:
            raise ConflictError("You already have a role with that name")
        role_id = (await session.execute(
            text("""INSERT INTO business_custom_roles (business_id, name, based_on, permissions, access_scope, created_by)
                    VALUES (:b, :n, :base, CAST(:p AS text[]), :s, :u) RETURNING id"""),
            {"b": str(business_id), "n": name, "base": based_on, "p": clean, "s": scope, "u": str(actor_id)},
        )).scalar_one()
        await AuditService.record(
            session, event_type="role.changed", actor_identity_id=actor_id, actor_context="business",
            business_id=business_id, resource_type="custom_role", resource_id=role_id, action="create_custom_role",
            after_state={"name": name, "permissions": clean, "scope": scope, "based_on": based_on},
        )
        return next(r for r in await RoleService.custom_roles(session, business_id) if r["id"] == str(role_id))

    @staticmethod
    async def update_custom_role(
        session: AsyncSession, business_id: uuid.UUID, role_id: uuid.UUID, *, name: str | None,
        permissions: list[str] | None, actor_id: uuid.UUID, actor_permissions: frozenset[str], is_owner: bool,
    ) -> dict[str, Any]:
        current = next((r for r in await RoleService.custom_roles(session, business_id) if r["id"] == str(role_id)),
                       None)
        if current is None:
            raise ResourceNotFound("Role")
        new_name = (name or current["label"]).strip()
        clean = (RoleService._check_permissions(permissions, actor_permissions, is_owner)
                 if permissions is not None else current["permissions"])
        await session.execute(
            text("""UPDATE business_custom_roles SET name = :n, permissions = CAST(:p AS text[]), updated_at = now()
                    WHERE business_id = :b AND id = :id"""),
            {"n": new_name, "p": clean, "b": str(business_id), "id": str(role_id)},
        )
        await AuditService.record(
            session, event_type="role.changed", actor_identity_id=actor_id, actor_context="business",
            business_id=business_id, resource_type="custom_role", resource_id=role_id, action="update_custom_role",
            before_state={"name": current["label"], "permissions": current["permissions"]},
            after_state={"name": new_name, "permissions": clean},
        )
        return next(r for r in await RoleService.custom_roles(session, business_id) if r["id"] == str(role_id))

    @staticmethod
    async def archive_custom_role(
        session: AsyncSession, business_id: uuid.UUID, role_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> None:
        current = next((r for r in await RoleService.custom_roles(session, business_id) if r["id"] == str(role_id)),
                       None)
        if current is None:
            raise ResourceNotFound("Role")
        if current["holders"]:
            raise ConflictError(f"{current['holders']} people hold this role. Give them another role first.")
        await session.execute(
            text("UPDATE business_custom_roles SET archived_at = now() WHERE business_id = :b AND id = :id"),
            {"b": str(business_id), "id": str(role_id)},
        )
        await AuditService.record(
            session, event_type="role.changed", actor_identity_id=actor_id, actor_context="business",
            business_id=business_id, resource_type="custom_role", resource_id=role_id, action="archive_custom_role",
        )

    # ------------------------------------------------------------------ assignment
    @staticmethod
    async def resolve_role(
        session: AsyncSession, business_id: uuid.UUID, role_key: str
    ) -> tuple[str, frozenset[str], str, str]:
        """(system role, permissions, scope, label) for a template key or custom role."""
        from platform_core.services.module_readiness import module_states

        if role_key.startswith("custom:"):
            role = next((r for r in await RoleService.custom_roles(session, business_id) if r["key"] == role_key),
                        None)
            if role is None:
                raise ValidationError("Unknown role", details={"field": "role"})
            return ROLE_MEMBER, frozenset(role["permissions"]), role["scope"], role["label"]
        tpl = ROLE_TEMPLATES.get(role_key)
        live = _operational(await module_states(session, business_id))
        if tpl is None or not tpl.offered(live):
            raise ValidationError("That role is not available for this business", details={"field": "role"})
        return tpl.system_role, tpl.permissions, tpl.scope, tpl.label

    @staticmethod
    async def _check_locations(session: AsyncSession, business_id: uuid.UUID,
                               location_ids: list[uuid.UUID]) -> list[uuid.UUID]:
        ids = sorted(set(location_ids), key=str)
        if not ids:
            raise ValidationError("Choose at least one location", details={"field": "location_ids"})
        found = {r[0] for r in (await session.execute(
            text("SELECT id FROM business_locations WHERE business_id = :b AND id = ANY(CAST(:ids AS uuid[])) "
                 "AND deleted_at IS NULL"), {"b": str(business_id), "ids": [str(x) for x in ids]},
        )).all()}
        if len(found) != len(ids):
            raise ValidationError("Unknown location", details={"field": "location_ids"})
        return ids

    @staticmethod
    async def apply(
        session: AsyncSession, membership: BusinessMembership, *, role_key: str, location_ids: list[uuid.UUID],
        actor_id: uuid.UUID, actor_permissions: frozenset[str], actor_role: str, correlation_id: str | None = None,
    ) -> BusinessMembership:
        """Give `membership` a role and scope. Validates the delegation ceiling:
        a non-owner can only hand out permissions they hold themselves."""
        business_id = membership.business_id
        if membership.role == ROLE_PRIMARY_OWNER:
            raise ValidationError("The owner's role cannot be changed here", details={"field": "role"})
        system_role, permissions, scope, label = await RoleService.resolve_role(session, business_id, role_key)
        if actor_role != ROLE_PRIMARY_OWNER:
            TeamService.assert_can_assign_role(actor_role, system_role)
            excess = set(permissions) - set(actor_permissions)
            if excess:
                raise PermissionDelegationError(excess)
        locations = (await RoleService._check_locations(session, business_id, location_ids)
                     if scope == "location" else [])
        before = {"role": membership.role, "role_template": membership.role_template,
                  "access_scope": membership.access_scope,
                  "location_scope": [str(x) for x in membership.location_scope or []]}
        membership.role = system_role
        membership.role_template = role_key
        membership.access_scope = scope
        membership.location_scope = locations or None
        membership.updated_at = datetime.now(timezone.utc)
        membership.version = (membership.version or 1) + 1
        for model in (MembershipAppliedTemplate, MembershipPermissionGrant, MembershipPermissionDenial):
            await session.execute(delete(model).where(model.membership_id == membership.id))
        session.add(MembershipAppliedTemplate(
            membership_id=membership.id,
            template_id=role_key if role_key.startswith("custom:") else f"role:{role_key}",
            applied_by=actor_id,
        ))
        await session.flush()
        after = {"role": system_role, "role_template": role_key, "access_scope": scope,
                 "location_scope": [str(x) for x in locations]}
        await OutboxService.publish(
            session, event_type="role.changed",
            payload={"business_id": str(business_id), "membership_id": str(membership.id), **after},
            business_id=business_id, correlation_id=correlation_id,
        )
        await AuditService.record(
            session, event_type="role.changed", actor_identity_id=actor_id, actor_context="business",
            business_id=business_id, resource_type="membership", resource_id=membership.id, action="assign_role",
            before_state=before, after_state={**after, "label": label},
        )
        return membership

    @staticmethod
    def role_view(membership: BusinessMembership, custom: list[dict[str, Any]]) -> dict[str, Any]:
        """How a member's role reads in the Team list."""
        if membership.role == ROLE_PRIMARY_OWNER:
            return {"key": "owner", "label": OWNER.label, "scope": "business", "home": OWNER.home}
        key = membership.role_template
        if key and key.startswith("custom:"):
            role = next((r for r in custom if r["key"] == key), None)
            if role:
                return {"key": key, "label": role["label"], "scope": role["scope"], "home": role["home"]}
        tpl = ROLE_TEMPLATES.get(key or "")
        if tpl:
            return {"key": tpl.key, "label": tpl.label, "scope": tpl.scope, "home": tpl.home}
        label = "Manager" if membership.role == ROLE_MANAGER else "Team member"
        return {"key": None, "label": label, "scope": membership.access_scope, "home": None}


async def business_locations(session: AsyncSession, business_id: uuid.UUID) -> dict[str, str]:
    rows = (await session.execute(
        text("SELECT id, name FROM business_locations WHERE business_id = :b AND deleted_at IS NULL "
             "ORDER BY is_primary DESC, name"), {"b": str(business_id)},
    )).all()
    return {str(r[0]): r[1] for r in rows}
