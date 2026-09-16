from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import require_permission
from platform_core.context import RequestContext
from platform_core.exceptions import ResourceNotFound
from platform_core.permissions import (
    BUSINESS_READ,
    BUSINESS_UPDATE,
    LOCATIONS_CREATE,
    LOCATIONS_READ,
)
from platform_core.services.business import BusinessService
from platform_core.services.location import LocationService

router = APIRouter(prefix="/v1/b", tags=["business"])


class BusinessPatchRequest(BaseModel):
    display_name: str | None = None
    visibility: str | None = None


class LocationCreateRequest(BaseModel):
    name: str
    timezone: str = "UTC"
    address: dict[str, Any] | None = None


@router.get("/{business_id}")
async def get_business(
    business_id: UUID,
    ctx: RequestContext = Depends(require_permission(BUSINESS_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    if ctx.business_id != business_id:
        raise ResourceNotFound("Business")
    business = await BusinessService.get_by_id(session, business_id)
    if not business:
        raise ResourceNotFound("Business")
    return {
        "data": {
            "id": str(business.id),
            "slug": business.slug,
            "display_name": business.display_name,
            # Three independent axes (Doc 03 §1.6): `state` is lifecycle,
            # `status` is platform standing, `visibility` is public exposure.
            # `status` is what the Workspace Home reads to render the commercial
            # recovery state (Doc 09 CORE-001); without it the UI cannot tell a
            # suspended Business from a healthy one.
            "state": business.state,
            "status": business.status,
            "visibility": business.visibility,
        },
        "meta": {"correlation_id": ctx.correlation_id},
    }


@router.patch("/{business_id}")
async def patch_business(
    business_id: UUID,
    body: BusinessPatchRequest,
    ctx: RequestContext = Depends(require_permission(BUSINESS_UPDATE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    if ctx.business_id != business_id:
        raise ResourceNotFound("Business")
    business = await BusinessService.get_by_id(session, business_id)
    if not business:
        raise ResourceNotFound("Business")
    await BusinessService.update_business(
        session, business, display_name=body.display_name, visibility=body.visibility
    )
    await session.commit()
    return {
        "data": {
            "id": str(business.id),
            "display_name": business.display_name,
            "visibility": business.visibility,
        },
        "meta": {"correlation_id": ctx.correlation_id},
    }


@router.get("/{business_id}/locations")
async def list_locations(
    business_id: UUID,
    ctx: RequestContext = Depends(require_permission(LOCATIONS_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    if ctx.business_id != business_id:
        raise ResourceNotFound("Business")
    locations = await LocationService.list_for_business(session, business_id)
    return {
        "data": [
            {
                "id": str(loc.id),
                "name": loc.name,
                "timezone": loc.timezone,
                "is_primary": loc.is_primary,
            }
            for loc in locations
        ],
        "meta": {"correlation_id": ctx.correlation_id},
    }


@router.post("/{business_id}/locations")
async def create_location(
    business_id: UUID,
    body: LocationCreateRequest,
    ctx: RequestContext = Depends(require_permission(LOCATIONS_CREATE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    if ctx.business_id != business_id:
        raise ResourceNotFound("Business")
    location = await LocationService.create_location_simple(
        session,
        business_id=business_id,
        name=body.name,
        timezone=body.timezone,
        address=body.address,
    )
    await session.commit()
    return {
        "data": {"id": str(location.id), "name": location.name},
        "meta": {"correlation_id": ctx.correlation_id},
    }
