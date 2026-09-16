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
from platform_core.permissions import ENTITLEMENTS_READ, ENTITLEMENTS_UPDATE
from platform_core.services.business_entitlements import BusinessEntitlementService

router = APIRouter(tags=["entitlements"])


class PatchBusinessOverridesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modules: dict[str, dict[str, Any]] | None = None
    features: dict[str, dict[str, Any]] | None = None
    limits: dict[str, dict[str, Any]] | None = None
    version: int | None = Field(default=None, ge=1)


class PatchBusinessPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    version: int | None = Field(default=None, ge=1)


@router.get("/v1/platform/plans")
async def list_plans(ctx: RequestContext = Depends(get_request_context)) -> dict[str, Any]:
    data = await BusinessEntitlementService.list_plans()
    return {"data": data, "meta": {"correlation_id": ctx.correlation_id}}


@router.get("/v1/platform/modules")
async def list_modules(
    module_class: str | None = None,
    ctx: RequestContext = Depends(get_request_context),
) -> dict[str, Any]:
    data = await BusinessEntitlementService.list_modules(module_class=module_class)
    return {"data": data, "meta": {"correlation_id": ctx.correlation_id}}


@router.get("/v1/platform/modules/{module_id}")
async def get_module(
    module_id: str,
    ctx: RequestContext = Depends(get_request_context),
) -> dict[str, Any]:
    data = await BusinessEntitlementService.get_module(module_id)
    return {"data": data, "meta": {"correlation_id": ctx.correlation_id}}


@router.get("/v1/platform/features")
async def list_features(
    module_id: str | None = None,
    ctx: RequestContext = Depends(get_request_context),
) -> dict[str, Any]:
    data = await BusinessEntitlementService.list_features(module_id=module_id)
    return {"data": data, "meta": {"correlation_id": ctx.correlation_id}}


@router.get("/v1/platform/features/{feature_id}")
async def get_feature(
    feature_id: str,
    ctx: RequestContext = Depends(get_request_context),
) -> dict[str, Any]:
    data = await BusinessEntitlementService.get_feature(feature_id)
    return {"data": data, "meta": {"correlation_id": ctx.correlation_id}}


@router.get("/v1/platform/businesses/{business_id}/entitlements")
async def get_business_entitlements(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(ENTITLEMENTS_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await BusinessEntitlementService.get_business_entitlements(session, business_id)
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.get("/v1/platform/businesses/{business_id}/capabilities")
async def get_business_capabilities(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(ENTITLEMENTS_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await BusinessEntitlementService.get_business_capabilities(session, business_id)
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.patch("/v1/platform/businesses/{business_id}/entitlements/overrides")
async def patch_business_overrides(
    business_id: UUID,
    body: PatchBusinessOverridesRequest,
    actor: BusinessActorContext = Depends(require_business_actor(ENTITLEMENTS_UPDATE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    payload = body.model_dump(exclude_unset=True)
    data = await BusinessEntitlementService.patch_business_overrides(
        session,
        business_id=business_id,
        payload=payload,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
    )
    await session.commit()
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.patch("/v1/platform/businesses/{business_id}/entitlements/plan")
async def patch_business_plan(
    business_id: UUID,
    body: PatchBusinessPlanRequest,
    actor: BusinessActorContext = Depends(require_business_actor(ENTITLEMENTS_UPDATE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    payload = body.model_dump(exclude_unset=True)
    data = await BusinessEntitlementService.patch_business_plan(
        session,
        business_id=business_id,
        payload=payload,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
    )
    await session.commit()
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}
