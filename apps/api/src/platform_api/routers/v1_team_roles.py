"""Roles and the team as an owner sees them (Capability Universe §7.2–§7.3;
Business OS Guide §5): role templates, custom roles, and giving a person a
role with its scope."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.authorization.role_templates import ROLE_TEMPLATES
from platform_core.exceptions import ResourceNotFound
from platform_core.permissions import (
    ROLE_PRIMARY_OWNER,
    TEAM_INVITE,
    TEAM_MANAGE_TEMPLATES,
    TEAM_READ,
    TEAM_UPDATE_ROLE,
)
from platform_core.services.roles import RoleService, business_locations
from platform_core.services.staff import StaffService
from platform_core.services.team import TeamService

router = APIRouter(prefix="/v1/platform/businesses", tags=["team-roles"])


def _meta(actor: BusinessActorContext) -> dict[str, Any]:
    return {"correlation_id": actor.request.correlation_id}


async def _actor_permissions(session: AsyncSession, business_id: UUID, actor: BusinessActorContext) -> frozenset[str]:
    from platform_core.authorization.resolver import AuthorizationService

    return frozenset(await AuthorizationService.effective_permissions(
        session, business_id=business_id, identity_id=actor.request.identity_id))


@router.get("/{business_id}/roles")
async def list_roles(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(TEAM_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await RoleService.catalogue(session, business_id)
    data["locations"] = [{"id": k, "name": v} for k, v in (await business_locations(session, business_id)).items()]
    return {"data": data, "meta": _meta(actor)}


class CustomRoleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=60)
    based_on: str | None = None
    permissions: list[str] = Field(max_length=120)
    scope: str = "business"


class CustomRolePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=60)
    permissions: list[str] | None = Field(default=None, max_length=120)


@router.post("/{business_id}/roles/custom")
async def create_custom_role(
    business_id: UUID,
    body: CustomRoleCreate,
    actor: BusinessActorContext = Depends(require_business_actor(TEAM_MANAGE_TEMPLATES)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    role = await RoleService.create_custom_role(
        session, business_id, name=body.name, based_on=body.based_on, permissions=body.permissions,
        scope=body.scope, actor_id=actor.request.identity_id,
        actor_permissions=await _actor_permissions(session, business_id, actor),
        is_owner=actor.actor_membership.role == ROLE_PRIMARY_OWNER,
    )
    await session.commit()
    return {"data": role, "meta": _meta(actor)}


@router.patch("/{business_id}/roles/custom/{role_id}")
async def update_custom_role(
    business_id: UUID,
    role_id: UUID,
    body: CustomRolePatch,
    actor: BusinessActorContext = Depends(require_business_actor(TEAM_MANAGE_TEMPLATES)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    role = await RoleService.update_custom_role(
        session, business_id, role_id, name=body.name, permissions=body.permissions,
        actor_id=actor.request.identity_id,
        actor_permissions=await _actor_permissions(session, business_id, actor),
        is_owner=actor.actor_membership.role == ROLE_PRIMARY_OWNER,
    )
    await session.commit()
    return {"data": role, "meta": _meta(actor)}


@router.delete("/{business_id}/roles/custom/{role_id}")
async def archive_custom_role(
    business_id: UUID,
    role_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(TEAM_MANAGE_TEMPLATES)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await RoleService.archive_custom_role(session, business_id, role_id, actor_id=actor.request.identity_id)
    await session.commit()
    return {"data": {"archived": True}, "meta": _meta(actor)}


class AssignRole(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=2, max_length=80)
    location_ids: list[UUID] = Field(default_factory=list, max_length=200)


@router.put("/{business_id}/members/{membership_id}/role")
async def assign_role(
    business_id: UUID,
    membership_id: UUID,
    body: AssignRole,
    actor: BusinessActorContext = Depends(require_business_actor(TEAM_UPDATE_ROLE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    target = await TeamService.get_membership_by_id_for_update(session, business_id, membership_id)
    if target is None or target.deleted_at is not None:
        raise ResourceNotFound("Member")
    TeamService.assert_can_manage_target(actor.actor_membership, target, action="update_role")
    await RoleService.apply(
        session, target, role_key=body.role, location_ids=body.location_ids,
        actor_id=actor.request.identity_id,
        actor_permissions=await _actor_permissions(session, business_id, actor),
        actor_role=actor.actor_membership.role, correlation_id=actor.request.correlation_id,
    )
    await session.commit()
    return {"data": (await team_view(session, business_id))["members"], "meta": _meta(actor)}


class AddPerson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=254)
    role: str = Field(min_length=2, max_length=80)
    location_ids: list[UUID] = Field(default_factory=list, max_length=200)


@router.post("/{business_id}/team/people")
async def add_person(
    business_id: UUID,
    body: AddPerson,
    actor: BusinessActorContext = Depends(require_business_actor(TEAM_INVITE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Add a person with a role; returns their one-time join link path."""
    invitation, token = await StaffService.add_person(
        session, actor.business, actor.actor_membership, name=body.name, email=body.email, role_key=body.role,
        location_ids=body.location_ids, actor_permissions=await _actor_permissions(session, business_id, actor),
        correlation_id=actor.request.correlation_id,
    )
    await session.commit()
    return {"data": {"invitation_id": str(invitation.id), "join_path": f"/join/{token}"}, "meta": _meta(actor)}


@router.post("/{business_id}/team/invitations/{invitation_id}/link")
async def new_join_link(
    business_id: UUID,
    invitation_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(TEAM_INVITE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    token = await StaffService.new_link(session, business_id, invitation_id)
    await session.commit()
    return {"data": {"join_path": f"/join/{token}"}, "meta": _meta(actor)}


async def team_view(session: AsyncSession, business_id: UUID) -> dict[str, Any]:
    """Members with names, roles in words, scope and locations; people who
    have been added but not joined yet."""
    custom = await RoleService.custom_roles(session, business_id)
    locations = await business_locations(session, business_id)
    members = await TeamService.list_members(session, business_id)
    ids = [str(m.identity_id) for m in members]
    given = {str(r[0]): r[1] for r in (await session.execute(
        text("SELECT membership_id, display_name FROM business_invitations WHERE business_id = :b "
             "AND membership_id IS NOT NULL AND display_name IS NOT NULL"), {"b": str(business_id)},
    )).all()}
    people = {str(r[0]): (r[1], r[2]) for r in (await session.execute(
        text("SELECT id, email, display_name FROM platform_identities WHERE id = ANY(CAST(:ids AS uuid[]))"),
        {"ids": ids},
    )).all()} if ids else {}
    out = []
    for m in sorted(members, key=lambda x: (x.role != ROLE_PRIMARY_OWNER, x.created_at)):
        email, name = people.get(str(m.identity_id), (None, None))
        out.append({
            "id": str(m.id), "identity_id": str(m.identity_id), "email": email,
            "name": given.get(str(m.id)) or name or (email.split("@")[0] if email else "Team member"),
            "status": m.status, "role": RoleService.role_view(m, custom),
            "locations": [{"id": str(x), "name": locations.get(str(x), "Removed location")}
                          for x in (m.location_scope or [])],
            "activated_at": m.activated_at.isoformat() if m.activated_at else None,
        })
    pending = []
    for inv in (await session.execute(
        text("""SELECT id, display_name, invited_email, role_template, location_scope, expires_at, created_at
                FROM business_invitations WHERE business_id = :b AND status = 'pending'
                ORDER BY created_at DESC"""), {"b": str(business_id)},
    )).all():
        role_key = inv[3] or ""
        label = next((r["label"] for r in custom if r["key"] == role_key), None) if role_key.startswith("custom:") \
            else (ROLE_TEMPLATES[role_key].label if role_key in ROLE_TEMPLATES else "Team member")
        pending.append({
            "invitation_id": str(inv[0]), "name": inv[1] or inv[2].split("@")[0], "email": inv[2],
            "role_label": label or "Team member",
            "locations": [locations.get(str(x), "Removed location") for x in (inv[4] or [])],
            "expires_at": inv[5].isoformat(), "expired": inv[5] <= datetime.now(timezone.utc),
        })
    return {"members": out, "invited": pending}


@router.get("/{business_id}/team")
async def team(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(TEAM_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return {"data": await team_view(session, business_id), "meta": _meta(actor)}
