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
)
from platform_core.context import RequestContext
from platform_core.permissions import CONFIGURATION_READ, CONFIGURATION_UPDATE
from platform_core.services.business_configuration import BusinessConfigurationService

router = APIRouter(tags=["configuration"])


class PatchBusinessTypeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_type: str
    confirm_type_change: bool | None = None
    version: int | None = Field(default=None, ge=1)


@router.get("/v1/platform/business-types")
async def list_business_types(
    ctx: RequestContext = Depends(get_request_context),
) -> dict[str, Any]:
    data = await BusinessConfigurationService.list_available_types()
    return {"data": data, "meta": {"correlation_id": ctx.correlation_id}}


@router.get("/v1/platform/business-types/{type_id}/profile")
async def get_business_type_profile(
    type_id: str,
    ctx: RequestContext = Depends(get_request_context),
) -> dict[str, Any]:
    data = await BusinessConfigurationService.get_type_profile(type_id)
    return {"data": data, "meta": {"correlation_id": ctx.correlation_id}}


@router.get("/v1/platform/businesses/{business_id}/configuration/profile")
async def get_business_configuration_profile(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(CONFIGURATION_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await BusinessConfigurationService.get_business_profile(session, business_id)
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.get("/v1/platform/businesses/{business_id}/configuration")
async def get_resolved_configuration(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(CONFIGURATION_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await BusinessConfigurationService.get_resolved_configuration(session, business_id)
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.patch("/v1/platform/businesses/{business_id}/configuration/type")
async def patch_business_type(
    business_id: UUID,
    body: PatchBusinessTypeRequest,
    actor: BusinessActorContext = Depends(require_business_actor(CONFIGURATION_UPDATE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    payload = body.model_dump(exclude_unset=True)
    data = await BusinessConfigurationService.patch_business_type(
        session,
        business_id=business_id,
        payload=payload,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
    )
    await session.commit()
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}
