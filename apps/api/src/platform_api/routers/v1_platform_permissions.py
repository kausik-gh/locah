from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import (
    BusinessActorContext,
    get_request_context,
    require_business_actor,
)
from platform_core.context import RequestContext
from platform_core.permissions import PERMISSIONS_READ, PERMISSIONS_UPDATE
from platform_core.services.permission_engine import PermissionEngineService

router = APIRouter(tags=["permissions"])


class PatchPermissionOverridesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grants: list[str] | None = None
    denials: list[str] | None = None
    remove_grants: list[str] | None = None
    remove_denials: list[str] | None = None
    version: int | None = Field(default=None, ge=1)


@router.get("/v1/platform/roles")
async def list_roles(ctx: RequestContext = Depends(get_request_context)) -> dict[str, Any]:
    data = await PermissionEngineService.list_roles()
    return {"data": data, "meta": {"correlation_id": ctx.correlation_id}}


@router.get("/v1/platform/permissions")
async def list_permissions(ctx: RequestContext = Depends(get_request_context)) -> dict[str, Any]:
    data = await PermissionEngineService.list_permissions()
    return {"data": data, "meta": {"correlation_id": ctx.correlation_id}}


@router.get("/v1/platform/businesses/{business_id}/permissions/matrix")
async def get_permission_matrix(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(PERMISSIONS_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await PermissionEngineService.permission_matrix()
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.get("/v1/platform/businesses/{business_id}/permissions/effective")
async def get_effective_permissions(
    business_id: UUID,
    identity_id: UUID | None = Query(default=None),
    actor: BusinessActorContext = Depends(require_business_actor(PERMISSIONS_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    target_identity = identity_id or actor.request.identity_id
    data = await PermissionEngineService.get_effective_permissions(
        session, business_id=business_id, identity_id=target_identity
    )
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.get("/v1/platform/businesses/{business_id}/permissions/snapshot")
async def get_authorization_snapshot(
    business_id: UUID,
    identity_id: UUID | None = Query(default=None),
    actor: BusinessActorContext = Depends(require_business_actor(PERMISSIONS_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    target_identity = identity_id or actor.request.identity_id
    data = await PermissionEngineService.get_authorization_snapshot(
        session, business_id=business_id, identity_id=target_identity
    )
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.patch("/v1/platform/businesses/{business_id}/members/{membership_id}/permissions/overrides")
async def patch_membership_permission_overrides(
    business_id: UUID,
    membership_id: UUID,
    body: PatchPermissionOverridesRequest,
    actor: BusinessActorContext = Depends(require_business_actor(PERMISSIONS_UPDATE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    payload = body.model_dump(exclude_unset=True)
    data = await PermissionEngineService.patch_membership_overrides(
        session,
        business_id=business_id,
        membership_id=membership_id,
        payload=payload,
        actor_id=actor.request.identity_id,
        actor_membership=actor.actor_membership,
        correlation_id=actor.request.correlation_id,
    )
    await session.commit()
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}
