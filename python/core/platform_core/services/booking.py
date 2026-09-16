"""Booking domain service (Stage 7 kernel + Stage 5 provider/deposit completion)."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ValidationError
from platform_core.gates import assert_business_accepts_commerce, assert_business_mutable
from platform_core.models import Booking, BookingStatusHistory, BookingsPolicy
from platform_core.resolvers.customer_resolver import CustomerResolver
from platform_core.resolvers.location_resolver import LocationResolver
from platform_core.resolvers.offering_resolver import OfferingResolver
from platform_core.resolvers.booking_resolver import BookingResolver
from platform_core.services.audit import AuditService
from platform_core.services.availability import AvailabilityService
from platform_core.services.business import BusinessService
from platform_core.services.consumer_activity import ConsumerActivityService
from platform_core.services.customer_timeline import CustomerTimelineService
from platform_core.services.outbox import OutboxService
from platform_core.services.payment_attempt import PaymentAttemptService
from platform_core.validation.booking import (
    RESERVABLE_OFFERING_TYPES,
    validate_create_payload,
    validate_patch_payload,
)


class BookingService:
    @staticmethod
    def serialize(booking: Booking) -> dict[str, Any]:
        return cast(dict[str, Any], BookingResolver.serialize_booking(booking))

    @staticmethod
    def _generate_booking_number() -> str:
        return f"BKG-{uuid.uuid4().hex[:8].upper()}"

    @staticmethod
    async def list_for_business(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        status: str | None = None,
        search: str | None = None,
        customer_contact_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        provider_id: uuid.UUID | None = None,
    ) -> list[Booking]:
        query = select(Booking).where(
            Booking.business_id == business_id,
            Booking.deleted_at.is_(None),
        )
        if status:
            query = query.where(Booking.status == status)
        if customer_contact_id:
            query = query.where(Booking.customer_contact_id == customer_contact_id)
        if location_id:
            query = query.where(Booking.location_id == location_id)
        if provider_id:
            query = query.where(Booking.provider_id == provider_id)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Booking.booking_number.ilike(pattern),
                    Booking.title.ilike(pattern),
                    Booking.internal_reference.ilike(pattern),
                )
            )
        query = query.order_by(Booking.starts_at.desc())
        return list((await session.execute(query)).scalars().all())

    @staticmethod
    async def create_booking(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> Booking:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="create booking")
        # Doc 04 §6.1: a suspended Business cannot receive orders. Standing
        # (`status`) is a separate axis from lifecycle (`state`) — both apply.
        assert_business_accepts_commerce(business.status, action="create booking")
        validated = validate_create_payload(payload)

        if validated["idempotency_key"]:
            existing = await session.execute(
                select(Booking).where(
                    Booking.business_id == business_id,
                    Booking.idempotency_key == validated["idempotency_key"],
                    Booking.deleted_at.is_(None),
                )
            )
            found = existing.scalars().first()
            if found:
                return found

        await LocationResolver.resolve(
            session, business_id=business_id, location_id=validated["location_id"]
        )
        if validated["customer_contact_id"]:
            await CustomerResolver.resolve(
                session,
                business_id=business_id,
                contact_id=validated["customer_contact_id"],
            )

        title = validated["title"]
        capacity = validated["capacity"]
        offering_price: float | None = None
        if validated["offering_id"]:
            offering = await OfferingResolver.resolve(
                session,
                business_id=business_id,
                offering_id=validated["offering_id"],
            )
            if offering.status != "active":
                raise ValidationError(
                    "Offering is not active",
                    details={"offering_id": str(offering.id)},
                )
            if offering.offering_type not in RESERVABLE_OFFERING_TYPES:
                raise ValidationError(
                    "Offering type is not reservable",
                    details={"offering_type": offering.offering_type},
                )
            title = title or offering.title
            if offering.price_amount is not None:
                offering_price = float(offering.price_amount)

            # Stage 6 membership gate (Doc 11 §17.6): if this class/session
            # offering is mapped to one or more membership plans, the customer
            # must hold an active enrolment in one of them. Offerings with no
            # mapping keep the Stage 5 capacity-only path unchanged.
            if validated["reservation_mode"] == "class_session":
                from platform_core.resolvers.membership_resolver import MembershipResolver

                gating_plan_ids = await MembershipResolver.offering_requires_membership(
                    session, business_id=business_id, offering_id=offering.id
                )
                if gating_plan_ids:
                    if not validated["customer_contact_id"]:
                        raise ValidationError(
                            "This class requires an active membership",
                            details={
                                "code": "membership_required",
                                "offering_id": str(offering.id),
                            },
                        )
                    has_enrolment = await MembershipResolver.has_active_enrolment(
                        session,
                        business_id=business_id,
                        customer_contact_id=validated["customer_contact_id"],
                        plan_ids=gating_plan_ids,
                    )
                    if not has_enrolment:
                        raise ValidationError(
                            "This class requires an active membership",
                            details={
                                "code": "membership_required",
                                "offering_id": str(offering.id),
                                "eligible_plan_ids": [str(p) for p in gating_plan_ids],
                            },
                        )

        if not title:
            raise ValidationError(
                "Booking title is required",
                details={"field": "title"},
            )

        await AvailabilityService.assert_available(
            session,
            business_id=business_id,
            location_id=validated["location_id"],
            provider_id=validated["provider_id"],
            offering_id=validated["offering_id"],
            reservation_mode=validated["reservation_mode"],
            starts_at=validated["starts_at"],
            ends_at=validated["ends_at"],
            party_size=validated["party_size"],
            capacity=capacity,
        )

        policy = await BookingService.get_or_create_policy(session, business_id)
        deposit_required = bool(policy.require_deposit)
        deposit_amount = Decimal("0")
        if deposit_required:
            deposit_amount = BookingService._compute_deposit_amount(
                policy, offering_price=offering_price
            )

        booking = Booking(
            business_id=business_id,
            location_id=validated["location_id"],
            customer_contact_id=validated["customer_contact_id"],
            offering_id=validated["offering_id"],
            provider_id=validated["provider_id"],
            booking_number=BookingService._generate_booking_number(),
            reservation_mode=validated["reservation_mode"],
            title=title,
            starts_at=validated["starts_at"],
            ends_at=validated["ends_at"],
            party_size=validated["party_size"],
            guest_count=validated["guest_count"],
            capacity=capacity,
            payment_method=validated["payment_method"],
            payment_status=(
                "pending_offline"
                if validated["payment_method"] in {"cod", "pay_at_business", "pay_later"}
                else "pending"
            ),
            deposit_required=deposit_required,
            deposit_amount=float(deposit_amount),
            management_token=secrets.token_urlsafe(24),
            management_token_expires_at=datetime.now(timezone.utc) + timedelta(days=90),
            internal_reference=validated["internal_reference"],
            idempotency_key=validated["idempotency_key"],
        )
        session.add(booking)
        await session.flush()

        history = BookingStatusHistory(
            business_id=business_id,
            booking_id=booking.id,
            from_status=None,
            to_status="pending",
            actor_identity_id=actor_id,
            reason="Booking created",
        )
        session.add(history)
        await session.flush()

        if deposit_required and deposit_amount > 0:
            payment = await PaymentAttemptService.create_attempt(
                session,
                business_id=business_id,
                actor_id=actor_id,
                correlation_id=correlation_id,
                payload={
                    "source_type": "booking",
                    "source_id": str(booking.id),
                    "amount": float(deposit_amount),
                    "currency": "INR",
                    "payment_method": validated["payment_method"],
                    "customer_contact_id": (
                        str(validated["customer_contact_id"])
                        if validated["customer_contact_id"]
                        else None
                    ),
                    "idempotency_key": f"deposit-{validated['idempotency_key'] or booking.id}",
                },
            )
            payment.provider_metadata = {**(payment.provider_metadata or {}), "purpose": "deposit"}
            await session.flush()
            # Re-sync after purpose is stamped so later succeed paths mark deposit_paid.
            await PaymentAttemptService._sync_source_payment_status(session, payment)
            if payment.status == "succeeded":
                booking.payment_status = "deposit_paid"
            elif payment.status == "pending_offline":
                booking.payment_status = "pending_offline"
            await session.flush()
            await AuditService.record(
                session,
                event_type="booking.deposit_collected",
                actor_identity_id=actor_id,
                actor_context="business",
                business_id=business_id,
                resource_type="booking",
                resource_id=booking.id,
                action="deposit_collected",
                after_state={
                    "payment_id": str(payment.id),
                    "amount": float(deposit_amount),
                    "payment_status": booking.payment_status,
                },
            )
            await OutboxService.publish(
                session,
                event_type="booking.deposit_collected",
                payload={
                    "business_id": str(business_id),
                    "booking_id": str(booking.id),
                    "payment_id": str(payment.id),
                    "amount": float(deposit_amount),
                },
                business_id=business_id,
                correlation_id=correlation_id,
            )

        after = BookingResolver.serialize_booking(booking)
        await OutboxService.publish(
            session,
            event_type="booking.created",
            payload={
                "business_id": str(business_id),
                "booking_id": str(booking.id),
                "booking_number": booking.booking_number,
                "customer_contact_id": (
                    str(booking.customer_contact_id) if booking.customer_contact_id else None
                ),
                "starts_at": booking.starts_at.isoformat(),
                "ends_at": booking.ends_at.isoformat(),
                "after": after,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="booking.created",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="booking",
            resource_id=booking.id,
            action="created",
            before_state=None,
            after_state=after,
        )
        if booking.customer_contact_id:
            await CustomerTimelineService.record_entry(
                session,
                business_id=business_id,
                contact_id=booking.customer_contact_id,
                activity_type="booking.created",
                resource_type="booking",
                resource_id=booking.id,
                location_id=booking.location_id,
                summary={
                    "booking_number": booking.booking_number,
                    "starts_at": booking.starts_at.isoformat(),
                    "status": booking.status,
                },
            )
            await ConsumerActivityService.record_for_customer_contact(
                session,
                business_id=business_id,
                customer_contact_id=booking.customer_contact_id,
                activity_type="booking.created",
                resource_type="booking",
                resource_id=booking.id,
                summary={
                    "booking_number": booking.booking_number,
                    "starts_at": booking.starts_at.isoformat(),
                    "status": booking.status,
                },
            )
        return booking

    @staticmethod
    async def get_or_create_policy(
        session: AsyncSession, business_id: uuid.UUID
    ) -> BookingsPolicy:
        policy = (
            await session.execute(
                select(BookingsPolicy).where(BookingsPolicy.business_id == business_id)
            )
        ).scalars().first()
        if policy is None:
            policy = BookingsPolicy(business_id=business_id)
            session.add(policy)
            await session.flush()
        return policy

    @staticmethod
    def _compute_deposit_amount(
        policy: BookingsPolicy, *, offering_price: float | None
    ) -> Decimal:
        if policy.deposit_amount is not None:
            return Decimal(str(policy.deposit_amount))
        if policy.deposit_percent is not None and offering_price is not None:
            return (
                Decimal(str(offering_price)) * Decimal(str(policy.deposit_percent)) / Decimal("100")
            ).quantize(Decimal("0.01"))
        if policy.deposit_amount is None and policy.deposit_percent is None:
            raise ValidationError(
                "Deposit is required but Business has no deposit amount configured",
                details={"field": "deposit"},
            )
        raise ValidationError(
            "Deposit percent requires a priced offering",
            details={"field": "deposit"},
        )

    @staticmethod
    async def update_policy(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        payload: dict[str, Any],
    ) -> BookingsPolicy:
        policy = await BookingService.get_or_create_policy(session, business_id)
        if "require_deposit" in payload:
            policy.require_deposit = bool(payload["require_deposit"])
        if "deposit_amount" in payload:
            policy.deposit_amount = payload["deposit_amount"]
        if "deposit_percent" in payload:
            policy.deposit_percent = payload["deposit_percent"]
        if "cancel_window_hours" in payload:
            policy.cancel_window_hours = int(payload["cancel_window_hours"])
        policy.version += 1
        policy.updated_at = datetime.now(timezone.utc)
        await session.flush()
        await AuditService.record(
            session,
            event_type="booking.policy_updated",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="bookings_policy",
            resource_id=business_id,
            action="updated",
            after_state={
                "require_deposit": policy.require_deposit,
                "deposit_amount": float(policy.deposit_amount)
                if policy.deposit_amount is not None
                else None,
                "cancel_window_hours": policy.cancel_window_hours,
            },
        )
        return policy

    @staticmethod
    async def patch_booking(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        booking_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
        expected_version: int | None = None,
    ) -> Booking:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="update booking")
        booking = await BookingResolver.resolve_mutable(
            session, business_id=business_id, booking_id=booking_id
        )
        if expected_version is not None and booking.version != expected_version:
            raise ConflictError(
                "Stale booking version",
                details={
                    "expected_version": expected_version,
                    "current_version": booking.version,
                },
            )
        before = BookingResolver.serialize_booking(booking)
        patch = validate_patch_payload(payload)
        for key, value in patch.items():
            setattr(booking, key, value)
        booking.version += 1
        await session.flush()
        after = BookingResolver.serialize_booking(booking)
        await OutboxService.publish(
            session,
            event_type="booking.updated",
            payload={
                "business_id": str(business_id),
                "booking_id": str(booking.id),
                "after": after,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="booking.updated",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="booking",
            resource_id=booking.id,
            action="updated",
            before_state=before,
            after_state=after,
        )
        return booking

    @staticmethod
    async def get_status_history(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        booking_id: uuid.UUID,
    ) -> list[BookingStatusHistory]:
        await BookingResolver.resolve(session, business_id=business_id, booking_id=booking_id)
        return await BookingResolver.load_status_history(session, booking_id=booking_id)
