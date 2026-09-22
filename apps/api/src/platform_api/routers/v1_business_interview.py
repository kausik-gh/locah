from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import get_request_context, resolve_business_actor
from platform_core.context import RequestContext
from platform_core.exceptions import PermissionDenied, ServiceUnavailable
from platform_core.interview.models import InterviewCommand
from platform_core.interview import voice as voice_module
from platform_core.permissions import BUSINESS_UPDATE, WEBSITE_EDIT
from platform_core.services.business_interview import BusinessInterviewService

router = APIRouter(prefix="/v1/b/{business_id}/interview", tags=["business-interview"])


async def owner(business_id: UUID, ctx: RequestContext, session: AsyncSession) -> None:
    actor = await resolve_business_actor(business_id, BUSINESS_UPDATE, ctx, session)
    if actor.actor_membership.role != "primary_owner":
        raise PermissionDenied(BUSINESS_UPDATE)
    if WEBSITE_EDIT not in actor.request.effective_permissions:
        raise PermissionDenied(WEBSITE_EDIT)


@router.get("")
async def get_interview(business_id: UUID, ctx: RequestContext = Depends(get_request_context),
                        session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    await owner(business_id, ctx, session)
    return {"data": await BusinessInterviewService.get(session, business_id)}


@router.post("")
async def update_interview(business_id: UUID, body: InterviewCommand,
                           ctx: RequestContext = Depends(get_request_context),
                           session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    await owner(business_id, ctx, session)
    return {"data": await BusinessInterviewService.execute(session, business_id, body,
            actor_id=ctx.identity_id, correlation_id=ctx.correlation_id)}


@router.post("/voice/session")
async def create_voice_session(business_id: UUID, ctx: RequestContext = Depends(get_request_context),
                               session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    """Mint a short-lived credential so this owner's browser can open a voice socket.

    Same owner guard as every other interview command, because starting to talk
    is starting to edit. The response carries a credential that expires in
    minutes and the session configuration built from this Business's own
    Blueprint — never the account key, which stays in this process.
    """
    await owner(business_id, ctx, session)
    business = await BusinessInterviewService.load_business(session, business_id)
    blueprint = BusinessInterviewService.read(business)
    try:
        minted = await voice_module.mint_client_secret()
    except voice_module.VoiceSessionError as exc:
        raise ServiceUnavailable(str(exc)) from exc
    return {"data": {
        **minted,
        "url": voice_module.REALTIME_URL,
        "model": voice_module.VOICE_MODEL,
        "voice": voice_module.VOICE_NAME,
        "session": voice_module.session_config(blueprint),
        "revision": blueprint.revision,
    }}
