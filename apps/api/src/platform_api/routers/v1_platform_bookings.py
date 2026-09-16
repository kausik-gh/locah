"""Platform bookings APIs (Stage 7)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.permissions import (
    BOOKINGS_CANCEL,
    BOOKINGS_CREATE,
    BOOKINGS_MANAGE_AVAILABILITY,
    BOOKINGS_READ,
    BOOKINGS_UPDATE,
)
from platform_core.resolvers.booking_resolver import BookingResolver
from platform_core.services.availability import AvailabilityService
from platform_core.services.booking import BookingService
from platform_core.services.booking_lifecycle import BookingLifecycleService
from platform_core.services.booking_note import BookingNoteService
from platform_core.validation.booking import validate_availability_query

router = APIRouter(prefix="/v1/platform/businesses", tags=["bookings"])


class VersionedBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int | None = Field(default=None, ge=1)


class CreateBookingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID
    customer_contact_id: UUID | None = None
    offering_id: UUID | None = None
    provider_id: UUID | None = None
    employee_id: UUID | None = None  # legacy alias → provider_id
    reservation_mode: str = "appointment"
    title: str | None = None
    starts_at: str
    ends_at: str
    party_size: int = Field(default=1, ge=1)
    guest_count: int | None = None
    capacity: int | None = Field(default=None, ge=1)
    payment_method: str = "cod"
    internal_reference: str | None = None
    idempotency_key: str | None = None


class PatchBookingRequest(VersionedBody):
    internal_reference: str | None = None
    payment_status: str | None = None


class StatusTransitionRequest(VersionedBody):
    status: str
    reason: str | None = None


class RescheduleRequest(VersionedBody):
    starts_at: str
    ends_at: str
    reason: str | None = None


class CancelBookingRequest(VersionedBody):
    reason: str


class CreateNoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str


class BookingsPolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    require_deposit: bool | None = None
    deposit_amount: float | None = None
    deposit_percent: float | None = None
    cancel_window_hours: int | None = Field(default=None, ge=0)


class AvailabilityCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID
    provider_id: UUID | None = None
    employee_id: UUID | None = None  # legacy alias → provider_id
    offering_id: UUID | None = None
    reservation_mode: str = "appointment"
    starts_at: str
    ends_at: str
    party_size: int = Field(default=1, ge=1)
    capacity: int | None = Field(default=None, ge=1)
    exclude_booking_id: UUID | None = None


def _patch_payload(body: BaseModel) -> dict[str, Any]:
    data = body.model_dump(exclude_unset=True)
    version = data.pop("version", None)
    return {"payload": data, "version": version}


@router.get("/{business_id}/bookings")
async def list_bookings(
    business_id: UUID,
    status: str | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=120),
    customer_contact_id: UUID | None = Query(default=None),
    location_id: UUID | None = Query(default=None),
    provider_id: UUID | None = Query(default=None),
    actor: BusinessActorContext = Depends(require_business_actor(BOOKINGS_READ, "bookings")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    bookings = await BookingService.list_for_business(
        session,
        business_id,
        status=status,
        search=search,
        customer_contact_id=customer_contact_id,
        location_id=location_id,
        provider_id=provider_id,
    )
    return {
        "data": [BookingService.serialize(b) for b in bookings],
        "meta": {"correlation_id": actor.request.correlation_id, "count": len(bookings)},
    }


@router.post("/{business_id}/bookings")
async def create_booking(
    business_id: UUID,
    body: CreateBookingRequest,
    actor: BusinessActorContext = Depends(require_business_actor(BOOKINGS_CREATE, "bookings")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    booking = await BookingService.create_booking(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(),
    )
    await session.commit()
    return {
        "data": BookingService.serialize(booking),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/bookings/{booking_id}")
async def get_booking(
    business_id: UUID,
    booking_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(BOOKINGS_READ, "bookings")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    booking = await BookingResolver.resolve(session, business_id=business_id, booking_id=booking_id)
    return {
        "data": BookingService.serialize(booking),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.patch("/{business_id}/bookings/{booking_id}")
async def patch_booking(
    business_id: UUID,
    booking_id: UUID,
    body: PatchBookingRequest,
    actor: BusinessActorContext = Depends(require_business_actor(BOOKINGS_UPDATE, "bookings")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    parsed = _patch_payload(body)
    booking = await BookingService.patch_booking(
        session,
        business_id=business_id,
        booking_id=booking_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=parsed["payload"],
        expected_version=parsed["version"],
    )
    await session.commit()
    return {
        "data": BookingService.serialize(booking),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/bookings/{booking_id}/status")
async def transition_booking_status(
    business_id: UUID,
    booking_id: UUID,
    body: StatusTransitionRequest,
    actor: BusinessActorContext = Depends(require_business_actor(BOOKINGS_UPDATE, "bookings")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    booking = await BookingLifecycleService.transition_status(
        session,
        business_id=business_id,
        booking_id=booking_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(exclude={"version"}),
        expected_version=body.version,
    )
    await session.commit()
    return {
        "data": BookingService.serialize(booking),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/bookings/{booking_id}/cancel")
async def cancel_booking(
    business_id: UUID,
    booking_id: UUID,
    body: CancelBookingRequest,
    actor: BusinessActorContext = Depends(require_business_actor(BOOKINGS_CANCEL, "bookings")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    booking = await BookingLifecycleService.transition_status(
        session,
        business_id=business_id,
        booking_id=booking_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload={"status": "cancelled", "reason": body.reason},
        expected_version=body.version,
    )
    await session.commit()
    return {
        "data": BookingService.serialize(booking),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/bookings/{booking_id}/reschedule")
async def reschedule_booking(
    business_id: UUID,
    booking_id: UUID,
    body: RescheduleRequest,
    actor: BusinessActorContext = Depends(require_business_actor(BOOKINGS_UPDATE, "bookings")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    booking = await BookingLifecycleService.reschedule(
        session,
        business_id=business_id,
        booking_id=booking_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(exclude={"version"}),
        expected_version=body.version,
    )
    await session.commit()
    return {
        "data": BookingService.serialize(booking),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/bookings/{booking_id}/history")
async def get_booking_history(
    business_id: UUID,
    booking_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(BOOKINGS_READ, "bookings")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    history = await BookingService.get_status_history(
        session, business_id=business_id, booking_id=booking_id
    )
    return {
        "data": [BookingResolver.serialize_status_history(h) for h in history],
        "meta": {"correlation_id": actor.request.correlation_id, "count": len(history)},
    }


@router.get("/{business_id}/bookings/{booking_id}/notes")
async def list_booking_notes(
    business_id: UUID,
    booking_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(BOOKINGS_READ, "bookings")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    notes = await BookingNoteService.list_for_booking(
        session, business_id=business_id, booking_id=booking_id
    )
    return {
        "data": [BookingNoteService.serialize(n) for n in notes],
        "meta": {"correlation_id": actor.request.correlation_id, "count": len(notes)},
    }


@router.post("/{business_id}/bookings/{booking_id}/notes")
async def create_booking_note(
    business_id: UUID,
    booking_id: UUID,
    body: CreateNoteRequest,
    actor: BusinessActorContext = Depends(require_business_actor(BOOKINGS_UPDATE, "bookings")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    note = await BookingNoteService.create_note(
        session,
        business_id=business_id,
        booking_id=booking_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        body=body.body,
    )
    await session.commit()
    return {
        "data": BookingNoteService.serialize(note),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/bookings/check-availability")
async def check_booking_availability(
    business_id: UUID,
    body: AvailabilityCheckRequest,
    actor: BusinessActorContext = Depends(require_business_actor(BOOKINGS_MANAGE_AVAILABILITY, "bookings")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    params = validate_availability_query(body.model_dump())
    result = await AvailabilityService.check_availability(
        session, business_id=business_id, params=params
    )
    return {
        "data": result,
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/bookings-policy")
async def get_bookings_policy(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(BOOKINGS_READ, "bookings")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    policy = await BookingService.get_or_create_policy(session, business_id)
    await session.commit()
    return {
        "data": {
            "require_deposit": policy.require_deposit,
            "deposit_amount": float(policy.deposit_amount)
            if policy.deposit_amount is not None
            else None,
            "deposit_percent": float(policy.deposit_percent)
            if policy.deposit_percent is not None
            else None,
            "cancel_window_hours": policy.cancel_window_hours,
            "version": policy.version,
        },
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.patch("/{business_id}/bookings-policy")
async def patch_bookings_policy(
    business_id: UUID,
    body: BookingsPolicyRequest,
    actor: BusinessActorContext = Depends(require_business_actor(BOOKINGS_UPDATE, "bookings")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    policy = await BookingService.update_policy(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        payload=body.model_dump(exclude_unset=True),
    )
    await session.commit()
    return {
        "data": {
            "require_deposit": policy.require_deposit,
            "deposit_amount": float(policy.deposit_amount)
            if policy.deposit_amount is not None
            else None,
            "deposit_percent": float(policy.deposit_percent)
            if policy.deposit_percent is not None
            else None,
            "cancel_window_hours": policy.cancel_window_hours,
            "version": policy.version,
        },
        "meta": {"correlation_id": actor.request.correlation_id},
    }
