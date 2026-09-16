from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import get_request_context
from platform_core.context import RequestContext
from platform_core.services.consumer_activity import ConsumerActivityService
from platform_core.services.identity import IdentityService

router = APIRouter(prefix="/v1/me", tags=["identity"])


class ProfileResponse(BaseModel):
    id: str
    email: str
    display_name: str | None
    avatar_url: str | None


class ContextResponse(BaseModel):
    identity_id: str
    active_context: str
    business_id: str | None
    location_id: str | None
    is_super_admin: bool
    permissions: list[str]
    entitled_modules: list[str]
    module_states: dict[str, str]
    default_business_id: str | None = None
    last_business_id: str | None = None
    primary_business_id: str | None = None


@router.get("")
async def get_me_v1(
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    identity = await IdentityService.get_by_id(session, ctx.identity_id)
    await session.commit()
    return {
        "data": ProfileResponse(
            id=str(ctx.identity_id),
            email=ctx.email,
            display_name=identity.display_name if identity else ctx.display_name,
            avatar_url=identity.avatar_url if identity else None,
        ).model_dump(),
        "meta": {"correlation_id": ctx.correlation_id},
    }


@router.get("/context")
async def get_context(
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    prefs = await IdentityService.get_consumer_preferences(session, ctx.identity_id)
    return {
        "data": ContextResponse(
            identity_id=str(ctx.identity_id),
            active_context=ctx.active_context.value,
            business_id=str(ctx.business_id) if ctx.business_id else None,
            location_id=str(ctx.location_id) if ctx.location_id else None,
            is_super_admin=ctx.is_super_admin,
            permissions=sorted(ctx.effective_permissions),
            entitled_modules=sorted(ctx.effective_entitlements.modules),
            module_states={k: v.activation_state for k, v in ctx.module_states.items()},
            default_business_id=prefs.get("default_business_id"),
            last_business_id=prefs.get("last_business_id"),
            primary_business_id=prefs.get("primary_business_id"),
        ).model_dump(),
        "meta": {"correlation_id": ctx.correlation_id},
    }


@router.get("/activity")
async def get_my_activity(
    resource_type: str | None = Query(default=None),
    business_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """My Activity — the caller's own consumer-side activity (Doc 09 ACC-011).

    Identity-scoped, not Business-scoped: this is the consumer surface, and it
    must stay separate from the Business Workspace (Doc 11 §17.7 exit: "My
    Activity remains separate from Workspace"). No Business permission is
    consulted and none is required — the rows belong to the caller.

    Coverage is currently Bookings only. Orders and Payments do not write to
    `consumer_activity_projections` yet, and guest activity is not linked to an
    account pending FL-DEC-024, so this feed is deliberately partial rather
    than padded with data it cannot truthfully claim.
    """
    activities = await ConsumerActivityService.list_for_identity(
        session,
        identity_id=ctx.identity_id,
        resource_type=resource_type,
        business_id=business_id,
        limit=limit,
    )
    return {
        "data": activities,
        "meta": {
            "correlation_id": ctx.correlation_id,
            "count": len(activities),
            # Named so the consumer UI can state its own limits truthfully
            # instead of implying an empty feed means no activity happened.
            "covered_resource_types": ["booking"],
        },
    }
