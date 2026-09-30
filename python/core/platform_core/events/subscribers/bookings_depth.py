"""Bookings' own timed work: unpaid holds, and the waitlist reacting to a freed place.

* booking.hold — when an online deposit's hold runs out unpaid, the booking is
  cancelled through the ordinary lifecycle, which releases its slot (and so
  wakes the waitlist). Paid in time: kept.
* A cancelled, rejected or moved booking - or a no-show before its start - frees
  a place; the first person waiting for an overlapping slot is offered it
  (booking.waitlist), one offer at a time, and the offer runs out after the
  owner's offer time (booking.waitlist_expiry) and passes on.

Every handler re-reads state first, so a replayed event or step does nothing twice.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.automation import StepOutcome, step_handler
from platform_core.automation.engine import DueStep
from platform_core.events.registry import EventContext, subscribe
from platform_core.models import Booking, BookingWaitlistEntry, Business
from platform_core.services.booking_waitlist import BookingWaitlistService


@step_handler("booking.hold")  # type: ignore[untyped-decorator, unused-ignore]
async def release_unpaid_hold(session: AsyncSession, step: DueStep) -> StepOutcome:
    from platform_core.services.booking_lifecycle import BookingLifecycleService
    from platform_core.services.outbox import OutboxService

    booking = await session.get(Booking, step.entity_id)
    if booking is None or booking.hold_expires_at is None:
        return StepOutcome("skipped", "No hold on this booking")
    if booking.hold_expires_at.isoformat(timespec="seconds") != step.period_key:
        return StepOutcome("skipped", "The hold was changed")
    if booking.payment_status in ("deposit_paid", "paid"):
        booking.hold_expires_at = None
        await session.flush()
        return StepOutcome("done", f"{booking.booking_number}: deposit paid in time; kept")
    if booking.status not in ("pending", "confirmed"):
        return StepOutcome("skipped", f"The booking is already {booking.status}")
    business = await session.get(Business, booking.business_id)
    assert business is not None
    await BookingLifecycleService.transition_status(
        session, business_id=booking.business_id, booking_id=booking.id,
        actor_id=business.primary_owner_identity_id, correlation_id=str(uuid.uuid4()),
        payload={"status": "cancelled", "reason": "The deposit was not paid in time; the slot was released"})
    await OutboxService.publish(session, event_type="booking.hold_released", business_id=booking.business_id,
                                correlation_id=str(uuid.uuid4()),
                                payload={"business_id": str(booking.business_id), "booking_id": str(booking.id)})
    return StepOutcome("done", f"{booking.booking_number}: not paid in time; slot released")


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "bookings.waitlist_place_opened", "booking.cancelled", "booking.rejected", "booking.rescheduled",
    "booking.no_show",
    description="When a place opens up, offer it to the first person on the waitlist (if the waitlist is on)",
)
async def place_opened(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    booking = await session.get(Booking, event.require_uuid("booking_id"))
    if booking is None:
        return
    p = event.payload
    if event.event_type == "booking.rescheduled":
        if not p.get("old_starts_at") or not p.get("old_ends_at"):
            return
        starts, ends = datetime.fromisoformat(str(p["old_starts_at"])), datetime.fromisoformat(str(p["old_ends_at"]))
    else:
        starts, ends = booking.starts_at, booking.ends_at
    await BookingWaitlistService.place_opened(
        session, business_id, location_id=booking.location_id, reservation_mode=booking.reservation_mode,
        starts_at=starts, ends_at=ends, offering_id=booking.offering_id)


async def _entry(session: AsyncSession, entity_id: uuid.UUID) -> BookingWaitlistEntry | None:
    return await session.get(BookingWaitlistEntry, entity_id, with_for_update=True)


@step_handler("booking.waitlist")  # type: ignore[untyped-decorator, unused-ignore]
async def offer_place(session: AsyncSession, step: DueStep) -> StepOutcome:
    entry = await _entry(session, step.entity_id)
    if entry is None:
        return StepOutcome("skipped", "The request no longer exists")
    made, said = await BookingWaitlistService.offer(session, entry)
    return StepOutcome("done" if made else "skipped", said)


@step_handler("booking.waitlist_expiry")  # type: ignore[untyped-decorator, unused-ignore]
async def expire_offer(session: AsyncSession, step: DueStep) -> StepOutcome:
    entry = await _entry(session, step.entity_id)
    if entry is None:
        return StepOutcome("skipped", "The request no longer exists")
    done, said = await BookingWaitlistService.expire(session, entry, step.period_key)
    return StepOutcome("done" if done else "skipped", said)

