from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import (
    BusinessActorContext,
    get_identity_context,
    require_business_actor,
)
from platform_core.context import RequestContext
from platform_core.exceptions import ResourceNotFound
from platform_core.permissions import TEAM_INVITE, TEAM_READ
from platform_core.services.invitation import InvitationService
from platform_core.services.team import TeamService

router = APIRouter(prefix="/v1/platform/businesses", tags=["invitations"])


class CreateInvitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invited_email: str = Field(..., min_length=3, max_length=320)
    invited_role: str = Field(default="member", pattern="^(manager|member)$")
    location_scope: list[UUID] | None = None


async def _load_invitation(
    session: AsyncSession, business_id: UUID, invitation_id: UUID
) -> Any:
    invitation = await InvitationService.get_by_id(session, business_id, invitation_id)
    if invitation is None:
        raise ResourceNotFound("Invitation")
    return invitation


@router.post("/{business_id}/invitations")
async def create_invitation(
    business_id: UUID,
    body: CreateInvitationRequest,
    actor: BusinessActorContext = Depends(require_business_actor(TEAM_INVITE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    invitation = await InvitationService.create_invitation(
        session,
        business=actor.business,
        actor=actor.actor_membership,
        invited_email=body.invited_email,
        invited_role=body.invited_role,
        location_scope=body.location_scope,
        correlation_id=actor.request.correlation_id,
    )
    await session.commit()
    return {
        "data": InvitationService.serialize_invitation(invitation),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/invitations")
async def list_invitations(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(TEAM_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    invitations = await InvitationService.list_for_business(session, business_id)
    return {
        "data": [InvitationService.serialize_invitation(i) for i in invitations],
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/invitations/{invitation_id}")
async def get_invitation(
    business_id: UUID,
    invitation_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(TEAM_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    invitation = await _load_invitation(session, business_id, invitation_id)
    return {
        "data": InvitationService.serialize_invitation(invitation),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/invitations/{invitation_id}/resend")
async def resend_invitation(
    business_id: UUID,
    invitation_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(TEAM_INVITE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    invitation = await _load_invitation(session, business_id, invitation_id)
    updated = await InvitationService.resend_invitation(
        session,
        business=actor.business,
        invitation=invitation,
        actor=actor.actor_membership,
        correlation_id=actor.request.correlation_id,
    )
    await session.commit()
    return {
        "data": InvitationService.serialize_invitation(updated),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/invitations/{invitation_id}/accept")
async def accept_invitation(
    business_id: UUID,
    invitation_id: UUID,
    ctx: RequestContext = Depends(get_identity_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    invitation, membership = await InvitationService.accept_invitation(
        session,
        business_id=business_id,
        invitation_id=invitation_id,
        accepter_identity_id=ctx.identity_id,
        accepter_email=ctx.email,
        correlation_id=ctx.correlation_id,
    )
    await session.commit()
    return {
        "data": {
            "invitation": InvitationService.serialize_invitation(invitation),
            "membership": TeamService.serialize_membership(membership),
        },
        "meta": {"correlation_id": ctx.correlation_id},
    }


@router.post("/{business_id}/invitations/{invitation_id}/decline")
async def decline_invitation(
    business_id: UUID,
    invitation_id: UUID,
    ctx: RequestContext = Depends(get_identity_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    invitation = await InvitationService.decline_invitation(
        session,
        business_id=business_id,
        invitation_id=invitation_id,
        decliner_identity_id=ctx.identity_id,
        decliner_email=ctx.email,
        correlation_id=ctx.correlation_id,
    )
    await session.commit()
    return {
        "data": InvitationService.serialize_invitation(invitation),
        "meta": {"correlation_id": ctx.correlation_id},
    }


@router.delete("/{business_id}/invitations/{invitation_id}")
async def revoke_invitation(
    business_id: UUID,
    invitation_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(TEAM_INVITE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    invitation = await _load_invitation(session, business_id, invitation_id)
    updated = await InvitationService.revoke_invitation(
        session,
        business=actor.business,
        invitation=invitation,
        actor=actor.actor_membership,
        correlation_id=actor.request.correlation_id,
    )
    await session.commit()
    return {
        "data": InvitationService.serialize_invitation(updated),
        "meta": {"correlation_id": actor.request.correlation_id},
    }
