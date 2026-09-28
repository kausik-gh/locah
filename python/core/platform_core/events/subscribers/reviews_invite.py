"""Ask for a verified review after an eligible order or booking completes."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.automation import StepOutcome, step_handler
from platform_core.automation.engine import DueStep
from platform_core.events.registry import EventContext, subscribe
from platform_core.events.subscribers.automation_triggers import _module_on
from platform_core.models import (
    Booking,
    BookingStatusHistory,
    Business,
    CustomerContact,
    OrderStatusHistory,
    Review,
    ReviewInvitation,
    SalesOrder,
)
from platform_core.services.messaging import MessagingService, NotSent
from platform_core.services.reviews import ReviewService

IST = ZoneInfo("Asia/Kolkata")


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "reviews.invite_completed",
    "order.completed",
    "booking.completed",
    description="Invite the customer once after a completed order or booking",
)
async def invite_completed(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    if not await _module_on(session, business_id, "reviews"):
        return

    if event.event_type == "order.completed":
        source_id = event.require_uuid("order_id")
        order = await session.get(SalesOrder, source_id)
        if order is None or order.business_id != business_id or order.status != "completed" or order.deleted_at:
            return
        completed_at = (await session.execute(
            select(OrderStatusHistory.created_at).where(
                OrderStatusHistory.business_id == business_id,
                OrderStatusHistory.order_id == source_id,
                OrderStatusHistory.to_status == "completed",
            ).order_by(OrderStatusHistory.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        source_type = "order"
        contact_id = order.customer_contact_id
        label = f"Order {order.order_number}"
    else:
        source_id = event.require_uuid("booking_id")
        booking = await session.get(Booking, source_id)
        if booking is None or booking.business_id != business_id or booking.status != "completed" or booking.deleted_at:
            return
        completed_at = (await session.execute(
            select(BookingStatusHistory.created_at).where(
                BookingStatusHistory.business_id == business_id,
                BookingStatusHistory.booking_id == source_id,
                BookingStatusHistory.to_status == "completed",
            ).order_by(BookingStatusHistory.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        source_type = "booking"
        contact_id = booking.customer_contact_id
        day = booking.starts_at.astimezone(IST).strftime("%d %b %Y")
        label = f"{booking.title} on {day}"

    if completed_at is None:
        return  # A status without completion history is not verified evidence.
    await ReviewService.invite(
        session, business_id, source_type=source_type, source_id=source_id,
        contact_id=contact_id, label=label, completed_at=completed_at,
    )


@step_handler("review.request")  # type: ignore[untyped-decorator, unused-ignore]
async def send_review_request(session: AsyncSession, step: DueStep) -> StepOutcome:
    invitation = await session.get(ReviewInvitation, step.entity_id)
    if invitation is None or invitation.business_id != step.business_id:
        return StepOutcome("skipped", "The review invitation no longer exists")
    if invitation.declined_at is not None:
        return StepOutcome("skipped", "The customer said no thanks")
    if datetime.now(timezone.utc) > invitation.expires_at:
        return StepOutcome("skipped", "The review window has closed")
    review = (await session.execute(select(Review.id).where(
        Review.business_id == step.business_id,
        Review.invitation_id == invitation.id,
    ))).scalar_one_or_none()
    if review is not None:
        return StepOutcome("skipped", "The customer has already reviewed")
    if not await ReviewService.source_completed(session, invitation):
        return StepOutcome("skipped", "The order or booking is no longer completed")
    if not await _module_on(session, step.business_id, "reviews"):
        return StepOutcome("skipped", "Reviews are switched off")
    if not await _module_on(session, step.business_id, "messaging"):
        return StepOutcome("skipped", "WhatsApp is switched off")

    contact = await session.get(CustomerContact, invitation.customer_contact_id)
    business = await session.get(Business, step.business_id)
    if contact is None or not contact.phone or business is None:
        return StepOutcome("skipped", "No WhatsApp number for this customer")
    try:
        message = await MessagingService.send_template(
            session, step.business_id, to=contact.phone, key="review_request",
            params=[business.display_name, invitation.label, await ReviewService.link(session, invitation)],
            contact_id=contact.id, idempotency_key=f"ladder:{step.id}",
        )
    except NotSent as exc:
        return StepOutcome("skipped", str(exc))
    if message.status != "sent":
        return StepOutcome("skipped", f"Review request not sent: {message.error or message.status}")
    return StepOutcome("done", f"Asked for a review of {invitation.label} on WhatsApp")
