"""Location lookup resolver (Stage 3)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ResourceNotFound, ResourceStateDenied
from platform_core.models import BusinessLocation


class LocationResolver:
    @staticmethod
    async def resolve(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        location_id: uuid.UUID,
    ) -> BusinessLocation:
        result = await session.execute(
            select(BusinessLocation).where(
                BusinessLocation.id == location_id,
                BusinessLocation.business_id == business_id,
                BusinessLocation.deleted_at.is_(None),
            )
        )
        location = result.scalars().first()
        if location is None:
            raise ResourceNotFound("Location")
        return location

    @staticmethod
    def require_active(location: BusinessLocation, *, action: str = "update") -> None:
        if location.status != "active":
            raise ResourceStateDenied(
                "location",
                location.status,
                action=action,
                allowed_states=["active"],
            )

    @staticmethod
    async def resolve_active(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        location_id: uuid.UUID,
        action: str = "update",
    ) -> BusinessLocation:
        location = await LocationResolver.resolve(
            session, business_id=business_id, location_id=location_id
        )
        LocationResolver.require_active(location, action=action)
        return location
