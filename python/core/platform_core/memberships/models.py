"""P2-02 recurring-relationship history (migration 20260930120000_p2_memberships).

Plans and enrolments stay in platform_core.models (the Stage 6 kernel); these
are the occurrence rows the engine reasons from: periods, freezes, session
uses, instalments, payment applications, delivery overrides, generated
deliveries and covered service visits.
"""
# mypy: allow-subclassing-any

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from platform_core.models import Base


def _pk() -> Mapped[UUID]:
    return mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


def _business() -> Mapped[UUID]:
    return mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))


def _enrolment() -> Mapped[UUID]:
    return mapped_column(PG_UUID(as_uuid=True), ForeignKey("memberships_enrolments.id"))


class MembershipPeriod(Base):
    __tablename__ = "memberships_periods"

    id: Mapped[UUID] = _pk()
    business_id: Mapped[UUID] = _business()
    enrolment_id: Mapped[UUID] = _enrolment()
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    base_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[Any] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    paid_amount: Mapped[Any] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    payment_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'unpaid'"))
    sessions_included: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'join'"))
    created_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MembershipFreeze(Base):
    __tablename__ = "memberships_freezes"

    id: Mapped[UUID] = _pk()
    business_id: Mapped[UUID] = _business()
    enrolment_id: Mapped[UUID] = _enrolment()
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'freeze'"))
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    extends_cover: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'confirmed'"))
    approved_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    channel: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MembershipSessionUse(Base):
    __tablename__ = "memberships_session_uses"

    id: Mapped[UUID] = _pk()
    business_id: Mapped[UUID] = _business()
    enrolment_id: Mapped[UUID] = _enrolment()
    period_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("memberships_periods.id"))
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'consumed'"))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MembershipInstalment(Base):
    __tablename__ = "memberships_instalments"

    id: Mapped[UUID] = _pk()
    business_id: Mapped[UUID] = _business()
    enrolment_id: Mapped[UUID] = _enrolment()
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Any] = mapped_column(Numeric(12, 2), nullable=False)
    due_on: Mapped[date] = mapped_column(Date, nullable=False)
    paid_amount: Mapped[Any] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'due'"))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MembershipPaymentApplication(Base):
    __tablename__ = "memberships_payment_applications"

    id: Mapped[UUID] = _pk()
    business_id: Mapped[UUID] = _business()
    enrolment_id: Mapped[UUID] = _enrolment()
    payment_attempt_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True),
                                                     ForeignKey("payments_payment_attempts.id"))
    charge_type: Mapped[str] = mapped_column(Text, nullable=False)
    charge_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    amount: Mapped[Any] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MembershipDeliveryOverride(Base):
    __tablename__ = "memberships_delivery_overrides"

    id: Mapped[UUID] = _pk()
    business_id: Mapped[UUID] = _business()
    enrolment_id: Mapped[UUID] = _enrolment()
    on_date: Mapped[date] = mapped_column(Date, nullable=False)
    slot: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Any | None] = mapped_column(Numeric(12, 3), nullable=True)
    channel: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MembershipDelivery(Base):
    __tablename__ = "memberships_deliveries"

    id: Mapped[UUID] = _pk()
    business_id: Mapped[UUID] = _business()
    enrolment_id: Mapped[UUID] = _enrolment()
    on_date: Mapped[date] = mapped_column(Date, nullable=False)
    slot: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    quantity: Mapped[Any] = mapped_column(Numeric(12, 3), nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    order_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    unit_price: Mapped[Any | None] = mapped_column(Numeric(12, 2), nullable=True)
    amount: Mapped[Any | None] = mapped_column(Numeric(12, 2), nullable=True)
    ledger_entry_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MembershipServiceVisit(Base):
    __tablename__ = "memberships_service_visits"

    id: Mapped[UUID] = _pk()
    business_id: Mapped[UUID] = _business()
    enrolment_id: Mapped[UUID] = _enrolment()
    period_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("memberships_periods.id"))
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    due_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'scheduled'"))
    job_ref: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
