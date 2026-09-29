"""Marketing & Campaigns models (MK-01 through MK-10; MS-26; MD §6.2, §18.1–§18.4, §25.1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
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


class MarketingOffer(Base):
    __tablename__ = "marketing_offers"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    discount_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    min_order_amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    max_discount_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    usage_limit_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_limit_per_customer: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    times_used: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketingCampaign(Base):
    __tablename__ = "marketing_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    audience_segment_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_relationships_segments.id"), nullable=True
    )
    audience_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    offer_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("marketing_offers.id"), nullable=True
    )
    creative: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    budget_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    estimated_cost_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    actual_cost_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    schedule_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'immediate'"))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'DRAFT'"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_record: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class MarketingBroadcastRecipient(Base):
    __tablename__ = "marketing_broadcast_recipients"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("marketing_campaigns.id"), nullable=False
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_relationships_contacts.id"), nullable=False
    )
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'queued'"))
    cost_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    error_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketingFrequencyLog(Base):
    __tablename__ = "marketing_frequency_log"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    contact_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_relationships_contacts.id"), nullable=False
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("marketing_campaigns.id"), nullable=True
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketingTouchpoint(Base):
    __tablename__ = "marketing_touchpoints"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    touchpoint_kind: Mapped[str] = mapped_column(Text, nullable=False)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("marketing_campaigns.id"), nullable=True
    )
    coupon_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    referral_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_relationships_contacts.id"), nullable=True
    )
    session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketingConversion(Base):
    __tablename__ = "marketing_conversions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    touchpoint_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("marketing_touchpoints.id"), nullable=False
    )
    conversion_kind: Mapped[str] = mapped_column(Text, nullable=False)
    conversion_id: Mapped[str] = mapped_column(Text, nullable=False)
    revenue_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    attribution_model: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'approximate_last_touch'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketingMetaConfiguration(Base):
    __tablename__ = "marketing_meta_configurations"

    business_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id"), primary_key=True
    )
    ad_account_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    pixel_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    monthly_spend_cap_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    current_month_spend_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    conversions_api_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'ACTIVATION_REQUIRED'"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
