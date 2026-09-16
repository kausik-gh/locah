"""Platform location APIs (Stage 3)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.exceptions import ResourceNotFound
from platform_core.permissions import (
    LOCATIONS_CREATE,
    LOCATIONS_DELETE,
    LOCATIONS_READ,
    LOCATIONS_UPDATE,
)
from platform_core.services.location import LocationService

router = APIRouter(prefix="/v1/platform/businesses", tags=["locations"])


class VersionedBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int | None = Field(default=None, ge=1)


class CreateLocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    timezone: str = "UTC"
    address: dict[str, Any] | None = None
    hours: dict[str, Any] | None = None
    internal_code: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_primary: bool = False


class PatchLocationRequest(VersionedBody):
    name: str | None = None
    timezone: str | None = None
    address: dict[str, Any] | None = None
    hours: dict[str, Any] | None = None
    internal_code: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    status: str | None = None


def _patch_payload(body: BaseModel) -> dict[str, Any]:
    return body.model_dump(exclude_unset=True)


@router.get("/{business_id}/locations")
async def list_locations(
    business_id: UUID,
    status: str | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=120),
    actor: BusinessActorContext = Depends(require_business_actor(LOCATIONS_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    locations = await LocationService.list_for_business(
        session, business_id, status=status, search=search
    )
    return {
        "data": [LocationService.serialize_location(loc) for loc in locations],
        "meta": {"correlation_id": actor.request.correlation_id, "count": len(locations)},
    }


@router.post("/{business_id}/locations")
async def create_location(
    business_id: UUID,
    body: CreateLocationRequest,
    actor: BusinessActorContext = Depends(require_business_actor(LOCATIONS_CREATE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    payload = body.model_dump()
    location = await LocationService.create_location(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=payload,
    )
    await session.commit()
    return {
        "data": LocationService.serialize_location(location),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/locations/{location_id}")
async def get_location(
    business_id: UUID,
    location_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(LOCATIONS_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    location = await LocationService.get_by_id(session, business_id, location_id)
    if location is None:
        raise ResourceNotFound("Location")
    return {
        "data": LocationService.serialize_location(location),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.patch("/{business_id}/locations/{location_id}")
async def patch_location(
    business_id: UUID,
    location_id: UUID,
    body: PatchLocationRequest,
    actor: BusinessActorContext = Depends(require_business_actor(LOCATIONS_UPDATE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    payload = _patch_payload(body)
    version = payload.pop("version", None)
    location = await LocationService.update_location(
        session,
        business_id=business_id,
        location_id=location_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=payload,
        expected_version=version,
    )
    await session.commit()
    return {
        "data": LocationService.serialize_location(location),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/locations/{location_id}/set-primary")
async def set_primary_location(
    business_id: UUID,
    location_id: UUID,
    body: VersionedBody,
    actor: BusinessActorContext = Depends(require_business_actor(LOCATIONS_UPDATE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    location = await LocationService.set_primary(
        session,
        business_id=business_id,
        location_id=location_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        expected_version=body.version,
    )
    await session.commit()
    return {
        "data": LocationService.serialize_location(location),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/locations/{location_id}/archive")
async def archive_location(
    business_id: UUID,
    location_id: UUID,
    body: VersionedBody,
    actor: BusinessActorContext = Depends(require_business_actor(LOCATIONS_DELETE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    location = await LocationService.archive_location(
        session,
        business_id=business_id,
        location_id=location_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        expected_version=body.version,
    )
    await session.commit()
    return {
        "data": LocationService.serialize_location(location),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/locations/{location_id}/reactivate")
async def reactivate_location(
    business_id: UUID,
    location_id: UUID,
    body: VersionedBody,
    actor: BusinessActorContext = Depends(require_business_actor(LOCATIONS_UPDATE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    location = await LocationService.reactivate_location(
        session,
        business_id=business_id,
        location_id=location_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        expected_version=body.version,
    )
    await session.commit()
    return {
        "data": LocationService.serialize_location(location),
        "meta": {"correlation_id": actor.request.correlation_id},
    }
