"""Approximate Last-Touch Attribution Foundation (MK-07; MD §18.2).

Captures marketing signals (UTM, CTWA ad id, coupon codes, referrals, campaigns)
and links them to conversions (orders, bookings, leads).
Strict rule: All attribution models in LOCAH are labelled "Approximate · last touch";
never claim causal attribution.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.marketing.models import MarketingConversion, MarketingTouchpoint


class AttributionService:
    @staticmethod
    async def record_touchpoint(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        touchpoint_kind: str,
        campaign_id: uuid.UUID | None = None,
        coupon_code: str | None = None,
        referral_code: str | None = None,
        utm_source: str | None = None,
        utm_medium: str | None = None,
        utm_campaign: str | None = None,
        customer_contact_id: uuid.UUID | None = None,
        session_id: str | None = None,
        metadata_snapshot: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> MarketingTouchpoint:
        """Records an incoming marketing touchpoint (UTM, ad click, coupon entry, referral link)."""
        now = now or datetime.now(timezone.utc)
        tp = MarketingTouchpoint(
            business_id=business_id,
            touchpoint_kind=touchpoint_kind,
            campaign_id=campaign_id,
            coupon_code=coupon_code.upper() if coupon_code else None,
            referral_code=referral_code.upper() if referral_code else None,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            customer_contact_id=customer_contact_id,
            session_id=session_id,
            metadata_snapshot=metadata_snapshot or {},
            created_at=now,
        )
        session.add(tp)
        await session.flush()
        return tp

    @staticmethod
    async def attribute_conversion(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        conversion_kind: str,
        conversion_id: str,
        revenue_paise: int,
        touchpoint_id: uuid.UUID | None = None,
        session_id: str | None = None,
        customer_contact_id: uuid.UUID | None = None,
        coupon_code: str | None = None,
        now: datetime | None = None,
    ) -> MarketingConversion | None:
        """Attributes an order, booking or lead to the approximate last touchpoint. Idempotent."""
        now = now or datetime.now(timezone.utc)

        # Idempotency check: already attributed this conversion?
        existing = (
            await session.execute(
                select(MarketingConversion).where(
                    MarketingConversion.business_id == business_id,
                    MarketingConversion.conversion_kind == conversion_kind,
                    MarketingConversion.conversion_id == conversion_id,
                )
            )
        ).scalars().first()
        if existing is not None:
            return existing

        # Resolve touchpoint
        tp = None
        if touchpoint_id:
            tp = await session.get(MarketingTouchpoint, touchpoint_id)
        elif coupon_code:
            tp = (
                await session.execute(
                    select(MarketingTouchpoint)
                    .where(
                        MarketingTouchpoint.business_id == business_id,
                        MarketingTouchpoint.coupon_code == coupon_code.upper(),
                    )
                    .order_by(MarketingTouchpoint.created_at.desc())
                    .limit(1)
                )
            ).scalars().first()
        elif customer_contact_id:
            tp = (
                await session.execute(
                    select(MarketingTouchpoint)
                    .where(
                        MarketingTouchpoint.business_id == business_id,
                        MarketingTouchpoint.customer_contact_id == customer_contact_id,
                    )
                    .order_by(MarketingTouchpoint.created_at.desc())
                    .limit(1)
                )
            ).scalars().first()
        elif session_id:
            tp = (
                await session.execute(
                    select(MarketingTouchpoint)
                    .where(
                        MarketingTouchpoint.business_id == business_id,
                        MarketingTouchpoint.session_id == session_id,
                    )
                    .order_by(MarketingTouchpoint.created_at.desc())
                    .limit(1)
                )
            ).scalars().first()

        if tp is None:
            return None

        conv = MarketingConversion(
            business_id=business_id,
            touchpoint_id=tp.id,
            conversion_kind=conversion_kind,
            conversion_id=conversion_id,
            revenue_paise=revenue_paise,
            attribution_model="approximate_last_touch",
            created_at=now,
        )
        session.add(conv)
        await session.flush()
        return conv
