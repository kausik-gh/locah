"""Public booking + management (WEB-009 / WEB-010)."""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import optional_customer_identity
from platform_core.services.public_booking import PublicBookingService

router = APIRouter(prefix="/v1/public", tags=["bookings-public"])


class GuestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    email: str | None = None  # required for guests; a signed-in customer uses their verified email
    phone: str | None = None


class AvailabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID
    provider_id: UUID | None = None
    offering_id: UUID | None = None
    reservation_mode: str = "appointment"
    starts_at: str
    ends_at: str
    party_size: int = Field(default=1, ge=1)
    resource_ids: list[UUID] = Field(default_factory=list, max_length=8)


class CreatePublicBookingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID
    offering_id: UUID | None = None
    provider_id: UUID | None = None
    reservation_mode: str = "appointment"
    title: str | None = None
    starts_at: str
    ends_at: str
    party_size: int = Field(default=1, ge=1)
    guest_count: int | None = None
    # No `capacity`. It is the limit availability is checked against, so an
    # anonymous caller supplying it made the check decorative. Capacity comes
    # from resource configuration; this picks which resources to consume.
    resource_ids: list[UUID] = Field(default_factory=list, max_length=8)
    payment_method: str = "cod"
    guest: GuestPayload
    idempotency_key: str | None = None


class WaitlistJoinPublicRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID
    offering_id: UUID | None = None
    provider_id: UUID | None = None
    reservation_mode: str = "appointment"
    starts_at: str
    ends_at: str
    party_size: int = Field(default=1, ge=1)
    guest: GuestPayload


class WaitlistClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str


class CancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    reason: str = "Customer cancelled"


class RescheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    starts_at: str
    ends_at: str
    reason: str | None = None


@router.get("/websites/{slug}/booking/options")
async def booking_options(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await PublicBookingService.booking_options(session, slug=slug)
    return {"data": data, "meta": {}}


@router.post("/websites/{slug}/booking/availability")
async def booking_availability(
    slug: str,
    body: AvailabilityRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await PublicBookingService.check_availability(
        session, slug=slug, payload=body.model_dump(mode="json")
    )
    return {"data": data, "meta": {}}


@router.post("/websites/{slug}/bookings")
async def create_public_booking(
    slug: str,
    body: CreatePublicBookingRequest,
    session: AsyncSession = Depends(get_db_session),
    identity_id: UUID | None = Depends(optional_customer_identity),
) -> dict[str, Any]:
    data = await PublicBookingService.create_public_booking(
        session,
        slug=slug,
        correlation_id=str(uuid.uuid4()),
        payload=body.model_dump(mode="json"),
        identity_id=identity_id,
    )
    await session.commit()
    return {"data": data, "meta": {}}


@router.get("/bookings/{booking_id}")
async def get_public_booking(
    booking_id: UUID,
    token: str = Query(..., min_length=8),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await PublicBookingService.get_by_token(
        session, booking_id=booking_id, token=token
    )
    return {"data": data, "meta": {}}


@router.post("/bookings/{booking_id}/cancel")
async def cancel_public_booking(
    booking_id: UUID,
    body: CancelRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await PublicBookingService.cancel_by_token(
        session,
        booking_id=booking_id,
        token=body.token,
        reason=body.reason,
        correlation_id=str(uuid.uuid4()),
    )
    await session.commit()
    return {"data": data, "meta": {}}


@router.post("/bookings/{booking_id}/reschedule")
async def reschedule_public_booking(
    booking_id: UUID,
    body: RescheduleRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await PublicBookingService.reschedule_by_token(
        session,
        booking_id=booking_id,
        token=body.token,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        reason=body.reason,
        correlation_id=str(uuid.uuid4()),
    )
    await session.commit()
    return {"data": data, "meta": {}}


@router.post("/websites/{slug}/waitlist")
async def join_waitlist(
    slug: str,
    body: WaitlistJoinPublicRequest,
    session: AsyncSession = Depends(get_db_session),
    identity_id: UUID | None = Depends(optional_customer_identity),
) -> dict[str, Any]:
    data = await PublicBookingService.join_waitlist(
        session, slug=slug, correlation_id=str(uuid.uuid4()), payload=body.model_dump(mode="json"),
        identity_id=identity_id)
    await session.commit()
    return {"data": data, "meta": {}}


@router.get("/websites/{slug}/waitlist/{entry_id}")
async def view_waitlist_offer(
    slug: str,
    entry_id: UUID,
    t: str = Query(default=""),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await PublicBookingService.waitlist_offer(session, slug=slug, entry_id=entry_id, token=t)
    return {"data": data, "meta": {}}


@router.post("/websites/{slug}/waitlist/{entry_id}/claim")
async def claim_waitlist_offer(
    slug: str,
    entry_id: UUID,
    body: WaitlistClaimRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await PublicBookingService.claim_waitlist(
        session, slug=slug, entry_id=entry_id, token=body.token, correlation_id=str(uuid.uuid4()))
    await session.commit()
    return {"data": data, "meta": {}}
