"""Bookable resource configuration APIs.

The supply side of the booking engine: what a business has to sell time on.
Reuses the bookings permission set rather than inventing one, because
configuring a room is the same operational authority as configuring the hours
it can be booked in.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.permissions import BOOKINGS_MANAGE_AVAILABILITY, BOOKINGS_READ
from platform_core.services.booking_allocation import BookingAllocationService
from platform_core.services.booking_resource import BookingResourceService
from platform_core.validation.booking import parse_datetime

router = APIRouter(prefix="/v1/platform/businesses", tags=["bookings"])


class CreateResourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID
    resource_type: str
    name: str
    code: str | None = None
    allocation_mode: str = "exclusive"
    capacity: int = Field(default=1, ge=1)
    min_party_size: int | None = Field(default=None, ge=1)
    max_party_size: int | None = Field(default=None, ge=1)
    buffer_before_minutes: int = Field(default=0, ge=0, le=1440)
    buffer_after_minutes: int = Field(default=0, ge=0, le=1440)
    granularity: str = "slot"
    is_active: bool = True
    metadata: dict[str, Any] | None = None


class UpdateResourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int | None = Field(default=None, ge=1)
    resource_type: str | None = None
    name: str | None = None
    code: str | None = None
    allocation_mode: str | None = None
    capacity: int | None = Field(default=None, ge=1)
    min_party_size: int | None = Field(default=None, ge=1)
    max_party_size: int | None = Field(default=None, ge=1)
    buffer_before_minutes: int | None = Field(default=None, ge=0, le=1440)
    buffer_after_minutes: int | None = Field(default=None, ge=0, le=1440)
    granularity: str | None = None
    is_active: bool | None = None
    metadata: dict[str, Any] | None = None


@router.get("/{business_id}/bookings/resources")
async def list_resources(
    business_id: UUID,
    location_id: UUID | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    actor: BusinessActorContext = Depends(require_business_actor(BOOKINGS_READ, "bookings")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    resources = await BookingResourceService.list_resources(
        session,
        business_id=business_id,
        location_id=location_id,
        resource_type=resource_type,
        include_inactive=include_inactive,
    )
    return {
        "data": {"resources": resources},
        "meta": {"correlation_id": actor.request.correlation_id, "count": len(resources)},
    }


@router.post("/{business_id}/bookings/resources")
async def create_resource(
    business_id: UUID,
    body: CreateResourceRequest,
    actor: BusinessActorContext = Depends(
        require_business_actor(BOOKINGS_MANAGE_AVAILABILITY, "bookings")
    ),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    resource = await BookingResourceService.create(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(),
    )
    await session.commit()
    return {
        "data": BookingResourceService.serialize(resource),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.patch("/{business_id}/bookings/resources/{resource_id}")
async def update_resource(
    business_id: UUID,
    resource_id: UUID,
    body: UpdateResourceRequest,
    actor: BusinessActorContext = Depends(
        require_business_actor(BOOKINGS_MANAGE_AVAILABILITY, "bookings")
    ),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    payload = body.model_dump(exclude_unset=True)
    expected_version = payload.pop("version", None)
    resource = await BookingResourceService.update(
        session,
        business_id=business_id,
        resource_id=resource_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=payload,
        expected_version=expected_version,
    )
    await session.commit()
    return {
        "data": BookingResourceService.serialize(resource),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.delete("/{business_id}/bookings/resources/{resource_id}")
async def archive_resource(
    business_id: UUID,
    resource_id: UUID,
    actor: BusinessActorContext = Depends(
        require_business_actor(BOOKINGS_MANAGE_AVAILABILITY, "bookings")
    ),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    resource = await BookingResourceService.archive(
        session,
        business_id=business_id,
        resource_id=resource_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
    )
    await session.commit()
    return {
        "data": BookingResourceService.serialize(resource),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/bookings/resources/availability")
async def resource_availability(
    business_id: UUID,
    starts_at: str = Query(...),
    ends_at: str = Query(...),
    location_id: UUID | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    party_size: int = Query(default=1, ge=1),
    exclude_booking_id: UUID | None = Query(default=None),
    actor: BusinessActorContext = Depends(require_business_actor(BOOKINGS_READ, "bookings")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Which resources could take a booking in this window.

    Same service the public path and booking creation use, so a slot offered
    here is a slot the allocator agrees with.
    """
    free = await BookingAllocationService.free_resources(
        session,
        business_id=business_id,
        location_id=location_id,
        resource_type=resource_type,
        starts_at=parse_datetime(starts_at, field="starts_at"),
        ends_at=parse_datetime(ends_at, field="ends_at"),
        party_size=party_size,
        exclude_booking_id=exclude_booking_id,
    )
    return {
        "data": {"resources": free},
        "meta": {"correlation_id": actor.request.correlation_id, "count": len(free)},
    }
