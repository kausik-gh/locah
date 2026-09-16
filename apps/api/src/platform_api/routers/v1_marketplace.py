"""Business Marketplace presence settings (core-marketplace-presence)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.permissions import MARKETPLACE_CONFIGURE, MARKETPLACE_READ
from platform_core.services.marketplace_presence import MarketplacePresenceService

router = APIRouter(prefix="/v1/b", tags=["marketplace"])


class OptInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmed: bool = False


class VisibilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visibility: str  # private | unlisted only via this endpoint


@router.get("/{business_id}/marketplace")
async def get_marketplace_settings(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(MARKETPLACE_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await MarketplacePresenceService.get_settings(session, business_id=business_id)
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.post("/{business_id}/marketplace/opt-in")
async def opt_in_discoverable(
    business_id: UUID,
    body: OptInRequest,
    actor: BusinessActorContext = Depends(require_business_actor(MARKETPLACE_CONFIGURE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await MarketplacePresenceService.opt_in_discoverable(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        confirmed=body.confirmed,
    )
    await session.commit()
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.post("/{business_id}/marketplace/visibility")
async def set_visibility(
    business_id: UUID,
    body: VisibilityRequest,
    actor: BusinessActorContext = Depends(require_business_actor(MARKETPLACE_CONFIGURE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await MarketplacePresenceService.set_visibility(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        visibility=body.visibility,
    )
    await session.commit()
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}
