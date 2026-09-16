"""Location domain service (Stage 3)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ResourceNotFound, ResourceStateDenied, ValidationError
from platform_core.gates import assert_business_mutable
from platform_core.models import BusinessLocation
from platform_core.resolvers.location_resolver import LocationResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService
from platform_core.validation.location import validate_location_create_payload, validate_location_patch_payload


class LocationService:
    @staticmethod
    def serialize_location(location: BusinessLocation) -> dict[str, Any]:
        return {
            "id": str(location.id),
            "business_id": str(location.business_id),
            "name": location.name,
            "timezone": location.timezone,
            "address": location.address,
            "hours": location.hours,
            "is_primary": location.is_primary,
            "status": location.status,
            "internal_code": location.internal_code,
            "phone": location.phone,
            "email": location.email,
            "notes": location.notes,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "version": location.version,
            "created_at": location.created_at.isoformat(),
            "updated_at": location.updated_at.isoformat(),
        }

    @staticmethod
    def _check_version(location: BusinessLocation, expected_version: int | None) -> None:
        if expected_version is None:
            return
        if location.version != expected_version:
            raise ConflictError(
                "Stale location version",
                details={
                    "expected_version": expected_version,
                    "current_version": location.version,
                },
            )

    @staticmethod
    async def _publish(
        session: AsyncSession,
        *,
        event_type: str,
        audit_action: str,
        business_id: uuid.UUID,
        location: BusinessLocation,
        actor_id: uuid.UUID,
        correlation_id: str,
        before_state: dict[str, Any] | None,
        after_state: dict[str, Any],
    ) -> None:
        await OutboxService.publish(
            session,
            event_type=event_type,
            payload={
                "business_id": str(business_id),
                "location_id": str(location.id),
                "version": location.version,
                "after": after_state,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type=event_type,
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="location",
            resource_id=location.id,
            action=audit_action,
            before_state=before_state,
            after_state=after_state,
        )

    @staticmethod
    async def list_for_business(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        status: str | None = None,
        search: str | None = None,
    ) -> list[BusinessLocation]:
        query = select(BusinessLocation).where(
            BusinessLocation.business_id == business_id,
            BusinessLocation.deleted_at.is_(None),
        )
        if status is not None:
            query = query.where(BusinessLocation.status == status)
        if search:
            term = f"%{search.strip()}%"
            query = query.where(BusinessLocation.name.ilike(term))
        query = query.order_by(BusinessLocation.is_primary.desc(), BusinessLocation.name)
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(
        session: AsyncSession, business_id: uuid.UUID, location_id: uuid.UUID
    ) -> BusinessLocation | None:
        try:
            return await LocationResolver.resolve(
                session, business_id=business_id, location_id=location_id
            )
        except ResourceNotFound:
            return None

    @staticmethod
    async def create_location(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> BusinessLocation:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="create_location")

        validated = validate_location_create_payload(payload)
        if validated["is_primary"]:
            existing_primary = await BusinessService.get_primary_location(session, business_id)
            if existing_primary is not None:
                raise ConflictError(
                    "Primary location already exists",
                    details={"primary_location_id": str(existing_primary.id)},
                )

        location = BusinessLocation(
            business_id=business_id,
            name=validated["name"],
            timezone=validated["timezone"],
            address=validated["address"],
            hours=validated.get("hours"),
            is_primary=validated["is_primary"],
            status="active",
            internal_code=validated["internal_code"],
            phone=validated["phone"],
            email=validated["email"],
            notes=validated["notes"],
            latitude=validated["latitude"],
            longitude=validated["longitude"],
        )
        session.add(location)
        await session.flush()

        after = LocationService.serialize_location(location)
        await LocationService._publish(
            session,
            event_type="location.created",
            audit_action="create",
            business_id=business_id,
            location=location,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=None,
            after_state=after,
        )
        return location

    @staticmethod
    async def update_location(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        location_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
        expected_version: int | None = None,
    ) -> BusinessLocation:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="update_location")

        location = await LocationResolver.resolve(
            session, business_id=business_id, location_id=location_id
        )
        LocationService._check_version(location, expected_version)

        patch = validate_location_patch_payload(payload)
        if not patch:
            return location

        if "status" in patch:
            new_status = patch["status"]
            if location.status == "archived" and new_status != "archived" and new_status != "active":
                raise ResourceStateDenied(
                    "location",
                    location.status,
                    action="update",
                    allowed_states=["archived", "active"],
                )

        before = LocationService.serialize_location(location)
        for key, value in patch.items():
            setattr(location, key, value)
        location.version += 1
        await session.flush()

        after = LocationService.serialize_location(location)
        await LocationService._publish(
            session,
            event_type="location.updated",
            audit_action="update",
            business_id=business_id,
            location=location,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state=after,
        )
        return location

    @staticmethod
    async def set_primary(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        location_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        expected_version: int | None = None,
    ) -> BusinessLocation:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="set_primary_location")

        location = await LocationResolver.resolve_active(
            session,
            business_id=business_id,
            location_id=location_id,
            action="set_primary",
        )
        LocationService._check_version(location, expected_version)

        if location.is_primary:
            return location

        before = LocationService.serialize_location(location)
        await session.execute(
            update(BusinessLocation)
            .where(
                BusinessLocation.business_id == business_id,
                BusinessLocation.deleted_at.is_(None),
                BusinessLocation.is_primary.is_(True),
            )
            .values(is_primary=False)
        )
        location.is_primary = True
        location.version += 1
        await session.flush()

        after = LocationService.serialize_location(location)
        await LocationService._publish(
            session,
            event_type="location.updated",
            audit_action="set_primary",
            business_id=business_id,
            location=location,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state=after,
        )
        return location

    @staticmethod
    async def archive_location(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        location_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        expected_version: int | None = None,
    ) -> BusinessLocation:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="archive_location")

        location = await LocationResolver.resolve(
            session, business_id=business_id, location_id=location_id
        )
        LocationService._check_version(location, expected_version)

        if location.is_primary:
            raise ValidationError(
                "Cannot archive primary location",
                details={
                    "errors": [
                        {
                            "field": "location_id",
                            "message": "Assign a new primary location before archiving",
                        }
                    ]
                },
            )
        if location.status == "archived":
            return location

        before = LocationService.serialize_location(location)
        location.status = "archived"
        location.version += 1
        await session.flush()

        after = LocationService.serialize_location(location)
        await LocationService._publish(
            session,
            event_type="location.archived",
            audit_action="archive",
            business_id=business_id,
            location=location,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state=after,
        )
        return location

    @staticmethod
    async def reactivate_location(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        location_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        expected_version: int | None = None,
    ) -> BusinessLocation:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="reactivate_location")

        location = await LocationResolver.resolve(
            session, business_id=business_id, location_id=location_id
        )
        LocationService._check_version(location, expected_version)

        if location.status != "archived":
            raise ResourceStateDenied(
                "location",
                location.status,
                action="reactivate",
                allowed_states=["archived"],
            )

        before = LocationService.serialize_location(location)
        location.status = "active"
        location.version += 1
        await session.flush()

        after = LocationService.serialize_location(location)
        await LocationService._publish(
            session,
            event_type="location.updated",
            audit_action="reactivate",
            business_id=business_id,
            location=location,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state=after,
        )
        return location

    # Backward-compatible helper for legacy router and business creation flows.
    @staticmethod
    async def create_location_simple(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        name: str,
        timezone: str = "UTC",
        address: dict[str, Any] | None = None,
    ) -> BusinessLocation:
        location = BusinessLocation(
            business_id=business_id,
            name=name,
            timezone=timezone,
            address=address,
            is_primary=False,
            status="active",
        )
        session.add(location)
        await session.flush()
        return location
