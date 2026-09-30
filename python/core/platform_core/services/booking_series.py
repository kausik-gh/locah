"""Recurring bookings (Founder refinement — Bookings §15; Master Doc §6.1 BK-10).

A series links ordinary bookings - a weekly class seat, a standing
consultation. Every occurrence is created through the booking path with its
own availability check, so an occurrence that would collide is reported and
left out rather than double-booked. Afterwards:

* edit or cancel one occurrence - the booking's own reschedule / cancel;
* change this and later occurrences - moved together, all or none;
* end the series - later occurrences cancelled, the series marked ended.

Past and finished occurrences are never rewritten.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, PlatformError, ResourceNotFound, ValidationError
from platform_core.models import Booking, BookingAllocation, BookingSeries
from platform_core.resolvers.booking_resolver import BookingResolver
from platform_core.services.audit import AuditService
from platform_core.services.booking import BookingService
from platform_core.services.booking_lifecycle import BookingLifecycleService
from platform_core.services.outbox import OutboxService

LIVE = ("pending", "confirmed")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _reason(exc: PlatformError) -> str:
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return str(detail.get("message") or exc.code)


class BookingSeriesService:
    @staticmethod
    async def occurrences(session: AsyncSession, series: BookingSeries) -> list[Booking]:
        return list((await session.execute(select(Booking).where(
            Booking.business_id == series.business_id, Booking.series_id == series.id,
            Booking.deleted_at.is_(None),
        ).order_by(Booking.occurrence_index))).scalars().all())

    @staticmethod
    async def serialize(session: AsyncSession, series: BookingSeries) -> dict[str, Any]:
        return {
            "id": str(series.id), "status": series.status, "interval_weeks": series.interval_weeks,
            "occurrences_planned": series.occurrences,
            "ended_at": series.ended_at.isoformat() if series.ended_at else None,
            "occurrences": [BookingResolver.serialize_booking(b)
                            for b in await BookingSeriesService.occurrences(session, series)],
        }

    @staticmethod
    async def get(session: AsyncSession, business_id: uuid.UUID, series_id: uuid.UUID,
                  *, lock: bool = False) -> BookingSeries:
        q = select(BookingSeries).where(BookingSeries.id == series_id, BookingSeries.business_id == business_id)
        series = (await session.execute(q.with_for_update() if lock else q)).scalars().first()
        if series is None:
            raise ResourceNotFound("Booking series")
        return series

    @staticmethod
    async def repeat(
        session: AsyncSession, *, business_id: uuid.UUID, booking_id: uuid.UUID, actor_id: uuid.UUID,
        correlation_id: str, interval_weeks: int, occurrences: int,
    ) -> dict[str, Any]:
        """Make this booking the first of a weekly series."""
        if not 1 <= interval_weeks <= 4:
            raise ValidationError("Repeat every 1 to 4 weeks", details={"field": "interval_weeks"})
        if not 2 <= occurrences <= 52:
            raise ValidationError("A series has 2 to 52 bookings", details={"field": "occurrences"})
        first = await BookingResolver.resolve(session, business_id=business_id, booking_id=booking_id)
        if first.series_id is not None:
            raise ConflictError("This booking is already part of a series")
        if first.status not in LIVE:
            raise ConflictError("Only a pending or confirmed booking can be repeated")
        series = BookingSeries(business_id=business_id, location_id=first.location_id, interval_weeks=interval_weeks,
                               occurrences=occurrences, provider_id=first.provider_id, created_by=actor_id)
        session.add(series)
        await session.flush()
        first.series_id, first.occurrence_index = series.id, 1
        first.version += 1
        resource_ids = [str(r) for r in (await session.execute(select(BookingAllocation.resource_id).where(
            BookingAllocation.booking_id == first.id, BookingAllocation.released_at.is_(None),
            BookingAllocation.resource_id.is_not(None)))).scalars()]
        created, skipped = [first], []
        for index in range(2, occurrences + 1):
            shift = timedelta(weeks=interval_weeks * (index - 1))
            starts, ends = first.starts_at + shift, first.ends_at + shift
            try:
                async with session.begin_nested():
                    booking = await BookingService.create_booking(
                        session, business_id=business_id, actor_id=actor_id, correlation_id=correlation_id,
                        payload={"location_id": str(first.location_id),
                                 "customer_contact_id": str(first.customer_contact_id)
                                 if first.customer_contact_id else None,
                                 "offering_id": str(first.offering_id) if first.offering_id else None,
                                 "provider_id": str(first.provider_id) if first.provider_id else None,
                                 "reservation_mode": first.reservation_mode, "title": first.title,
                                 "starts_at": starts.isoformat(), "ends_at": ends.isoformat(),
                                 "party_size": first.party_size, "guest_count": first.guest_count,
                                 "capacity": first.capacity, "resource_ids": resource_ids or None,
                                 "payment_method": first.payment_method, "channel": first.channel,
                                 "idempotency_key": f"series-{series.id}-{index}"})
                    booking.series_id, booking.occurrence_index = series.id, index
                    await session.flush()
                created.append(booking)
            except PlatformError as exc:
                skipped.append({"occurrence": index, "starts_at": starts.isoformat(), "reason": _reason(exc)})
        await OutboxService.publish(session, event_type="booking.series_created", business_id=business_id,
                                    correlation_id=correlation_id,
                                    payload={"business_id": str(business_id), "series_id": str(series.id),
                                             "created": len(created), "skipped": len(skipped)})
        await AuditService.record(session, event_type="booking.series_created", actor_identity_id=actor_id,
                                  actor_context="business", business_id=business_id, resource_type="booking_series",
                                  resource_id=series.id, action="created",
                                  after_state={"first_booking_id": str(first.id), "interval_weeks": interval_weeks,
                                               "occurrences": occurrences, "skipped": skipped})
        return {**await BookingSeriesService.serialize(session, series), "skipped": skipped}

    @staticmethod
    async def _later(session: AsyncSession, series: BookingSeries, from_booking_id: uuid.UUID) -> list[Booking]:
        """This occurrence and the later ones still to come - never past or finished ones."""
        occurrences = await BookingSeriesService.occurrences(session, series)
        pivot = next((b for b in occurrences if b.id == from_booking_id), None)
        if pivot is None:
            raise ResourceNotFound("Booking in this series")
        now = _now()
        return [b for b in occurrences if (b.occurrence_index or 0) >= (pivot.occurrence_index or 0)
                and b.status in LIVE and b.starts_at > now]

    @staticmethod
    async def change_future(
        session: AsyncSession, *, business_id: uuid.UUID, series_id: uuid.UUID, from_booking_id: uuid.UUID,
        starts_at: datetime, ends_at: datetime, actor_id: uuid.UUID, correlation_id: str,
    ) -> dict[str, Any]:
        """Move this occurrence to starts_at–ends_at and every later one by the
        same shift. All or none: one collision and nothing moves."""
        if ends_at <= starts_at:
            raise ValidationError("A booking must end after it starts")
        series = await BookingSeriesService.get(session, business_id, series_id, lock=True)
        if series.status != "active":
            raise ConflictError("This series has ended")
        later = await BookingSeriesService._later(session, series, from_booking_id)
        pivot = next((b for b in later if b.id == from_booking_id), None)
        if pivot is None:
            raise ConflictError("That occurrence has passed or is finished; choose a later one")
        shift, duration = starts_at - pivot.starts_at, ends_at - starts_at
        clashes = []
        # Move the far end first when shifting later (and the near end when
        # earlier), so an occurrence never collides with its own neighbour's
        # old slot on the way.
        for booking in sorted(later, key=lambda b: b.starts_at, reverse=shift > timedelta(0)):
            new_start = booking.starts_at + shift
            try:
                async with session.begin_nested():
                    await BookingLifecycleService.reschedule(
                        session, business_id=business_id, booking_id=booking.id, actor_id=actor_id,
                        correlation_id=correlation_id,
                        payload={"starts_at": new_start.isoformat(), "ends_at": (new_start + duration).isoformat(),
                                 "reason": "Series changed from this occurrence on"})
            except PlatformError as exc:
                clashes.append({"occurrence": booking.occurrence_index, "starts_at": new_start.isoformat(),
                                "reason": _reason(exc)})
        if clashes:
            raise ConflictError("Some of the later bookings cannot move to that time; nothing was changed",
                                details={"code": "series_conflict", "clashes": clashes})
        series.version += 1
        await OutboxService.publish(session, event_type="booking.series_changed", business_id=business_id,
                                    correlation_id=correlation_id,
                                    payload={"business_id": str(business_id), "series_id": str(series.id),
                                             "moved": len(later)})
        await AuditService.record(session, event_type="booking.series_changed", actor_identity_id=actor_id,
                                  actor_context="business", business_id=business_id, resource_type="booking_series",
                                  resource_id=series.id, action="changed_future",
                                  after_state={"from_booking_id": str(from_booking_id), "moved": len(later),
                                               "shift_minutes": int(shift.total_seconds() // 60)})
        return await BookingSeriesService.serialize(session, series)

    @staticmethod
    async def end(
        session: AsyncSession, *, business_id: uuid.UUID, series_id: uuid.UUID, from_booking_id: uuid.UUID,
        actor_id: uuid.UUID, correlation_id: str,
    ) -> dict[str, Any]:
        """Cancel this occurrence and every later one; earlier ones stay."""
        series = await BookingSeriesService.get(session, business_id, series_id, lock=True)
        if series.status != "active":
            raise ConflictError("This series has already ended")
        later = await BookingSeriesService._later(session, series, from_booking_id)
        for booking in later:
            await BookingLifecycleService.transition_status(
                session, business_id=business_id, booking_id=booking.id, actor_id=actor_id,
                correlation_id=correlation_id, payload={"status": "cancelled", "reason": "The series was ended"})
        series.status, series.ended_at = "ended", _now()
        series.version += 1
        await session.flush()
        await OutboxService.publish(session, event_type="booking.series_ended", business_id=business_id,
                                    correlation_id=correlation_id,
                                    payload={"business_id": str(business_id), "series_id": str(series.id),
                                             "cancelled": len(later)})
        await AuditService.record(session, event_type="booking.series_ended", actor_identity_id=actor_id,
                                  actor_context="business", business_id=business_id, resource_type="booking_series",
                                  resource_id=series.id, action="ended",
                                  after_state={"from_booking_id": str(from_booking_id), "cancelled": len(later)})
        return await BookingSeriesService.serialize(session, series)
