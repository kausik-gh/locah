"""Public consumer booking orchestration (WEB-009 / WEB-010).

Doc 11 §4.1 WEB-009/WEB-010 · Doc 09 required states · Stage 5 only.
My Activity UI is Stage 7 (Doc 11 §17.7) — not built here.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.context_resolver import bind_public_context
from platform_core.exceptions import ResourceNotFound, ValidationError
from platform_core.models import (
    Booking,
    BusinessModuleState,
    Offering,
    WorkforceLocationAssignment,
    WorkforceMember,
    WorkforceServiceAssociation,
)
from platform_core.resolvers.booking_resolver import BookingResolver
from platform_core.services.availability import AvailabilityService
from platform_core.services.booking import BookingService
from platform_core.services.booking_lifecycle import BookingLifecycleService
from platform_core.services.business import BusinessService
from platform_core.services.customer import CustomerService
from platform_core.services.location import LocationService
from platform_core.validation.booking import validate_availability_query

ACTIVE_MODULE_STATES = frozenset({"enabled", "ready", "active"})


class PublicBookingService:
    @staticmethod
    async def _resolve_business(session: AsyncSession, slug: str):
        business = await BusinessService.get_by_slug(session, slug)
        if business is None or business.deleted_at is not None:
            raise ResourceNotFound("Business")
        await bind_public_context(session, business.id)
        return business

    @staticmethod
    async def _bookings_active(session: AsyncSession, business_id: uuid.UUID) -> bool:
        state = (
            await session.execute(
                select(BusinessModuleState).where(
                    BusinessModuleState.business_id == business_id,
                    BusinessModuleState.module_id == "bookings",
                )
            )
        ).scalars().first()
        return state is not None and state.activation_state in ACTIVE_MODULE_STATES

    @staticmethod
    async def booking_options(session: AsyncSession, *, slug: str) -> dict[str, Any]:
        business = await PublicBookingService._resolve_business(session, slug)
        if not await PublicBookingService._bookings_active(session, business.id):
            raise ValidationError(
                "Bookings are not enabled for this Business",
                details={"code": "bookings_disabled"},
            )
        locations = await LocationService.list_for_business(
            session, business.id, status="active"
        )
        offerings = (
            await session.execute(
                select(Offering).where(
                    Offering.business_id == business.id,
                    Offering.deleted_at.is_(None),
                    Offering.status == "active",
                    Offering.visibility == "public",
                    Offering.offering_type.in_(("service", "experience", "rental")),
                ).order_by(Offering.title.asc())
            )
        ).scalars().all()
        members = (
            await session.execute(
                select(WorkforceMember).where(
                    WorkforceMember.business_id == business.id,
                    WorkforceMember.deleted_at.is_(None),
                    WorkforceMember.status == "active",
                ).order_by(WorkforceMember.display_name.asc())
            )
        ).scalars().all()
        assignments = (
            await session.execute(
                select(WorkforceLocationAssignment).where(
                    WorkforceLocationAssignment.business_id == business.id
                )
            )
        ).scalars().all()
        associations = (
            await session.execute(
                select(WorkforceServiceAssociation).where(
                    WorkforceServiceAssociation.business_id == business.id
                )
            )
        ).scalars().all()
        loc_map: dict[str, list[str]] = {}
        for a in assignments:
            loc_map.setdefault(str(a.member_id), []).append(str(a.location_id))
        svc_map: dict[str, list[str]] = {}
        for a in associations:
            svc_map.setdefault(str(a.member_id), []).append(str(a.offering_id))
        policy = await BookingService.get_or_create_policy(session, business.id)
        return {
            "business": {
                "id": str(business.id),
                "slug": business.slug,
                "display_name": business.display_name,
            },
            "locations": [
                {
                    "id": str(loc.id),
                    "name": loc.name,
                    "is_primary": loc.is_primary,
                    "status": loc.status,
                    "address": loc.address,
                }
                for loc in locations
            ],
            "services": [
                {
                    "id": str(o.id),
                    "title": o.title,
                    "description": o.description,
                    "offering_type": o.offering_type,
                    "price_amount": float(o.price_amount) if o.price_amount is not None else None,
                    "currency": o.currency,
                }
                for o in offerings
            ],
            "providers": [
                {
                    "id": str(m.id),
                    "display_name": m.display_name,
                    "designation": m.designation,
                    "location_ids": loc_map.get(str(m.id), []),
                    "offering_ids": svc_map.get(str(m.id), []),
                }
                for m in members
            ],
            "policy": {
                "require_deposit": policy.require_deposit,
                "deposit_amount": float(policy.deposit_amount)
                if policy.deposit_amount is not None
                else None,
                "deposit_percent": float(policy.deposit_percent)
                if policy.deposit_percent is not None
                else None,
                "cancel_window_hours": policy.cancel_window_hours,
            },
            "payment_methods": ["cod", "pay_at_business"],
        }

    @staticmethod
    async def check_availability(
        session: AsyncSession, *, slug: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        business = await PublicBookingService._resolve_business(session, slug)
        params = validate_availability_query(payload)
        location = await LocationService.get_by_id(
            session, business.id, params["location_id"]
        )
        if location is None or location.status != "active":
            return {
                "available": False,
                "reason": "Location is closed or inactive",
                "code": "location_closed",
            }
        result = await AvailabilityService.check_availability(
            session, business_id=business.id, params=params
        )
        if not result["available"]:
            result["code"] = "slot_conflict"
        return result

    @staticmethod
    async def create_public_booking(
        session: AsyncSession,
        *,
        slug: str,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        business = await PublicBookingService._resolve_business(session, slug)
        if not await PublicBookingService._bookings_active(session, business.id):
            raise ValidationError(
                "Bookings are not enabled for this Business",
                details={"code": "bookings_disabled"},
            )
        location_id = uuid.UUID(str(payload["location_id"]))
        location = await LocationService.get_by_id(session, business.id, location_id)
        if location is None or location.status != "active":
            raise ValidationError(
                "Location is closed or inactive",
                details={"code": "location_closed", "field": "location_id"},
            )

        guest = payload.get("guest") or {}
        display_name = str(guest.get("name") or "").strip()
        email = str(guest.get("email") or "").strip().lower()
        phone = (str(guest.get("phone")).strip() if guest.get("phone") else None) or None
        if not display_name or not email:
            raise ValidationError(
                "Guest name and email are required",
                details={"field": "guest", "code": "policy_restriction"},
            )

        # Doc 05 Part 7.1: a guest booking is bounded to the transaction and
        # never becomes a Platform Identity. Customer attribution is the
        # business-scoped CustomerContact; audit/actor attribution is the
        # storefront owner acting in a guest-checkout context.
        actor_id = business.primary_owner_identity_id
        contact = await CustomerService.find_or_create_contact(
            session,
            business_id=business.id,
            correlation_id=correlation_id,
            actor_id=actor_id,
            actor_context="guest_checkout",
            display_name=display_name,
            email=email,
            phone=phone,
        )

        booking = await BookingService.create_booking(
            session,
            business_id=business.id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            payload={
                "location_id": str(location_id),
                "customer_contact_id": str(contact.id),
                "offering_id": payload.get("offering_id"),
                "provider_id": payload.get("provider_id"),
                "reservation_mode": payload.get("reservation_mode") or "appointment",
                "title": payload.get("title"),
                "starts_at": payload["starts_at"],
                "ends_at": payload["ends_at"],
                "party_size": payload.get("party_size") or 1,
                "guest_count": payload.get("guest_count"),
                "capacity": payload.get("capacity"),
                "payment_method": payload.get("payment_method") or "cod",
                "idempotency_key": payload.get("idempotency_key"),
            },
        )
        data = BookingResolver.serialize_booking(booking)
        data["management_token"] = booking.management_token
        data["management_token_expires_at"] = (
            booking.management_token_expires_at.isoformat()
            if booking.management_token_expires_at
            else None
        )
        return data

    @staticmethod
    async def _resolve_by_token(
        session: AsyncSession, *, booking_id: uuid.UUID, token: str
    ) -> Booking:
        booking = (
            await session.execute(
                select(Booking).where(
                    Booking.id == booking_id,
                    Booking.deleted_at.is_(None),
                )
            )
        ).scalars().first()
        if booking is None:
            raise ResourceNotFound("Booking")
        if not booking.management_token or booking.management_token != token:
            raise ResourceNotFound("Booking")
        if (
            booking.management_token_expires_at is not None
            and booking.management_token_expires_at < datetime.now(timezone.utc)
        ):
            raise ValidationError(
                "Management link has expired",
                details={"code": "expired_link"},
            )
        return booking

    @staticmethod
    async def get_by_token(
        session: AsyncSession, *, booking_id: uuid.UUID, token: str
    ) -> dict[str, Any]:
        booking = await PublicBookingService._resolve_by_token(
            session, booking_id=booking_id, token=token
        )
        data = BookingResolver.serialize_booking(booking)
        data["contact"] = {
            "business_id": str(booking.business_id),
            "location_id": str(booking.location_id),
        }
        return data

    @staticmethod
    async def cancel_by_token(
        session: AsyncSession,
        *,
        booking_id: uuid.UUID,
        token: str,
        reason: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        booking = await PublicBookingService._resolve_by_token(
            session, booking_id=booking_id, token=token
        )
        policy = await BookingService.get_or_create_policy(session, booking.business_id)
        deadline = booking.starts_at - timedelta(hours=policy.cancel_window_hours)
        if datetime.now(timezone.utc) > deadline:
            raise ValidationError(
                "Cancellation window has closed",
                details={"code": "cancellation_window_closed"},
            )
        business = await BusinessService.get_by_id(session, booking.business_id)
        guest_actor = booking.cancelled_by or business.primary_owner_identity_id
        # Prefer linked customer identity for audit when present
        if booking.customer_contact_id:
            from platform_core.models import CustomerContact

            contact = (
                await session.execute(
                    select(CustomerContact).where(
                        CustomerContact.id == booking.customer_contact_id
                    )
                )
            ).scalars().first()
            if contact and contact.identity_id:
                guest_actor = contact.identity_id
        updated = await BookingLifecycleService.transition_status(
            session,
            business_id=booking.business_id,
            booking_id=booking.id,
            actor_id=guest_actor,
            correlation_id=correlation_id,
            payload={"status": "cancelled", "reason": reason or "Customer cancelled"},
        )
        return BookingResolver.serialize_booking(updated)

    @staticmethod
    async def reschedule_by_token(
        session: AsyncSession,
        *,
        booking_id: uuid.UUID,
        token: str,
        starts_at: str,
        ends_at: str,
        correlation_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        booking = await PublicBookingService._resolve_by_token(
            session, booking_id=booking_id, token=token
        )
        policy = await BookingService.get_or_create_policy(session, booking.business_id)
        deadline = booking.starts_at - timedelta(hours=policy.cancel_window_hours)
        if datetime.now(timezone.utc) > deadline:
            raise ValidationError(
                "Reschedule window has closed",
                details={"code": "cancellation_window_closed"},
            )
        business = await BusinessService.get_by_id(session, booking.business_id)
        actor_id = business.primary_owner_identity_id
        if booking.customer_contact_id:
            from platform_core.models import CustomerContact

            contact = (
                await session.execute(
                    select(CustomerContact).where(
                        CustomerContact.id == booking.customer_contact_id
                    )
                )
            ).scalars().first()
            if contact and contact.identity_id:
                actor_id = contact.identity_id
        updated = await BookingLifecycleService.reschedule(
            session,
            business_id=booking.business_id,
            booking_id=booking.id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            payload={"starts_at": starts_at, "ends_at": ends_at, "reason": reason},
        )
        return BookingResolver.serialize_booking(updated)
