from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import (
    BusinessActorContext,
    get_request_context,
    require_business_actor,
    resolve_business_actor,
)
from platform_core.context import RequestContext
from platform_core.exceptions import MembershipRequired, ResourceNotFound
from platform_core.permissions import TEAM_READ, TEAM_REMOVE, TEAM_UPDATE_ROLE
from platform_core.services.business import BusinessService
from platform_core.services.team import TeamService

router = APIRouter(prefix="/v1/platform/businesses", tags=["membership"])


class UpdateMembershipRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str | None = None
    location_scope: list[UUID] | None = None


class TransferOwnershipRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_membership_id: UUID
    demote_to_role: str = Field(default="manager", pattern="^(manager|member)$")


async def _load_target(
    session: AsyncSession, business_id: UUID, membership_id: UUID
) -> Any:
    target = await TeamService.get_membership_by_id(session, business_id, membership_id)
    if target is None or target.status == "removed":
        raise ResourceNotFound("Membership")
    return target


@router.get("/{business_id}/members")
async def list_members(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(TEAM_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    members = await TeamService.list_members(session, business_id)
    return {
        "data": [TeamService.serialize_membership(m) for m in members],
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/members/{membership_id}")
async def get_member(
    business_id: UUID,
    membership_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(TEAM_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    target = await _load_target(session, business_id, membership_id)
    return {
        "data": TeamService.serialize_membership(target),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.patch("/{business_id}/members/{membership_id}")
async def patch_member(
    business_id: UUID,
    membership_id: UUID,
    body: UpdateMembershipRequest,
    actor: BusinessActorContext = Depends(require_business_actor(TEAM_UPDATE_ROLE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    target = await _load_target(session, business_id, membership_id)
    fields = body.model_dump(exclude_unset=True)
    updated = await TeamService.update_membership(
        session,
        business=actor.business,
        target=target,
        actor=actor.actor_membership,
        correlation_id=actor.request.correlation_id,
        role=fields.get("role"),
        location_scope=fields.get("location_scope"),
        update_role="role" in fields,
        update_location_scope="location_scope" in fields,
    )
    await session.commit()
    return {
        "data": TeamService.serialize_membership(updated),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/members/{membership_id}/suspend")
async def suspend_member(
    business_id: UUID,
    membership_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(TEAM_UPDATE_ROLE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    target = await _load_target(session, business_id, membership_id)
    updated = await TeamService.suspend_membership(
        session,
        business=actor.business,
        target=target,
        actor=actor.actor_membership,
        correlation_id=actor.request.correlation_id,
    )
    await session.commit()
    return {
        "data": TeamService.serialize_membership(updated),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/members/{membership_id}/reactivate")
async def reactivate_member(
    business_id: UUID,
    membership_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(TEAM_UPDATE_ROLE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    target = await _load_target(session, business_id, membership_id)
    updated = await TeamService.reactivate_membership(
        session,
        business=actor.business,
        target=target,
        actor=actor.actor_membership,
        correlation_id=actor.request.correlation_id,
    )
    await session.commit()
    return {
        "data": TeamService.serialize_membership(updated),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.delete("/{business_id}/members/{membership_id}")
async def remove_member(
    business_id: UUID,
    membership_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    business = await BusinessService.get_by_id(session, business_id)
    if not business:
        raise ResourceNotFound("Business")
    actor_membership = await TeamService.get_active_membership(
        session, ctx.identity_id, business_id
    )
    if actor_membership is None:
        raise MembershipRequired()

    target = await _load_target(session, business_id, membership_id)
    is_self = actor_membership.identity_id == target.identity_id
    if not is_self:
        actor = await resolve_business_actor(business_id, TEAM_REMOVE, ctx, session)
        actor_membership = actor.actor_membership
        business = actor.business

    updated = await TeamService.remove_membership(
        session,
        business=business,
        target=target,
        actor=actor_membership,
        correlation_id=ctx.correlation_id,
    )
    await session.commit()
    return {
        "data": TeamService.serialize_membership(updated),
        "meta": {"correlation_id": ctx.correlation_id},
    }


@router.post("/{business_id}/members/transfer-ownership")
async def transfer_ownership(
    business_id: UUID,
    body: TransferOwnershipRequest,
    actor: BusinessActorContext = Depends(require_business_actor(TEAM_UPDATE_ROLE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    former_owner, new_owner = await TeamService.transfer_primary_ownership(
        session,
        business_id=business_id,
        actor_identity_id=actor.request.identity_id,
        target_membership_id=body.target_membership_id,
        correlation_id=actor.request.correlation_id,
        demote_to_role=body.demote_to_role,
    )
    await session.commit()
    return {
        "data": {
            "former_owner": TeamService.serialize_membership(former_owner),
            "new_owner": TeamService.serialize_membership(new_owner),
            "primary_owner_identity_id": str(new_owner.identity_id),
        },
        "meta": {"correlation_id": actor.request.correlation_id},
    }
