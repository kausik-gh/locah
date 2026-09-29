"""Loyalty & Rewards models (LY-01, LY-02, LY-03, LY-04; MD §6.2, §18.2, §21.3)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from platform_core.models import Base


class LoyaltyProgram(Base):
    __tablename__ = "loyalty_programs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    program_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'points'"))
    points_per_rupee: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, server_default=text("1.0"))
    redemption_rupees_per_point: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, server_default=text("0.25"))
    min_redemption_points: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("10"))
    max_redemption_points_per_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expiry_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class LoyaltyAccount(Base):
    __tablename__ = "loyalty_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    customer_contact_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_relationships_contacts.id"), nullable=False
    )
    current_points: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    lifetime_points_earned: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    lifetime_points_redeemed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    tier: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'standard'"))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LoyaltyLedgerEntry(Base):
    __tablename__ = "loyalty_ledger"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    customer_contact_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_relationships_contacts.id"), nullable=False
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StampProgram(Base):
    __tablename__ = "stamp_programs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    qualifying_rule: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    required_stamps: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_kind: Mapped[str] = mapped_column(Text, nullable=False)
    reward_details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StampCard(Base):
    __tablename__ = "stamp_cards"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    program_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("stamp_programs.id"), nullable=False)
    customer_contact_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_relationships_contacts.id"), nullable=False
    )
    current_stamps: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    cycle_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    lifetime_stamps: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_stamp_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StampReward(Base):
    __tablename__ = "stamp_rewards"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    program_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("stamp_programs.id"), nullable=False)
    customer_contact_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_relationships_contacts.id"), nullable=False
    )
    reward_code: Mapped[str] = mapped_column(Text, nullable=False)
    cycle_completed: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'issued'"))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class ReferralCode(Base):
    __tablename__ = "referral_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    customer_contact_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_relationships_contacts.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReferralRelationship(Base):
    __tablename__ = "referral_relationships"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    referrer_contact_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_relationships_contacts.id"), nullable=False
    )
    referee_contact_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_relationships_contacts.id"), nullable=False
    )
    code_used: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    qualification_source_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    qualification_source_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    referrer_points_awarded: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    referee_points_awarded: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GiftVoucher(Base):
    __tablename__ = "gift_vouchers"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    holder_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_relationships_contacts.id"), nullable=True
    )
    recipient_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    recipient_phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    issued_amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    remaining_balance_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'INR'"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GiftVoucherTransaction(Base):
    __tablename__ = "gift_voucher_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    voucher_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("gift_vouchers.id"), nullable=False)
    delta_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
