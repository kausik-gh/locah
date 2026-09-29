"""Marketing frequency controls and spam protection (MK-03; MS-26; Capability Universe §18.2).

Prevents promotional fatigue:
- Cooldown period between promotional messages (default 48 hours).
- Maximum promotional messages per customer per rolling window (default 2 in 7 days).
- Idempotent log of sends.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.marketing.models import MarketingFrequencyLog


class FrequencyControlService:
    DEFAULT_COOLDOWN_HOURS = 48
    DEFAULT_MAX_PER_WEEK = 2

    @staticmethod
    async def can_send_promotional_message(
        session: AsyncSession,
        business_id: uuid.UUID,
        contact_id: uuid.UUID,
        *,
        channel: str = "whatsapp",
        cooldown_hours: int = DEFAULT_COOLDOWN_HOURS,
        max_per_week: int = DEFAULT_MAX_PER_WEEK,
        now: datetime | None = None,
    ) -> tuple[bool, str]:
        """Checks if promotional send is permitted under frequency rules."""
        now = now or datetime.now(timezone.utc)

        # 1. Cooldown check: when was last message sent?
        q_last = (
            select(MarketingFrequencyLog.sent_at)
            .where(
                MarketingFrequencyLog.business_id == business_id,
                MarketingFrequencyLog.contact_id == contact_id,
                MarketingFrequencyLog.channel == channel,
            )
            .order_by(MarketingFrequencyLog.sent_at.desc())
            .limit(1)
        )
        last_sent = (await session.execute(q_last)).scalar()
        if last_sent is not None and (now - last_sent) < timedelta(hours=cooldown_hours):
            remaining_hours = int((timedelta(hours=cooldown_hours) - (now - last_sent)).total_seconds() / 3600)
            return False, f"Customer is in {cooldown_hours}h cooldown ({remaining_hours}h remaining)"

        # 2. Rolling 7-day cap
        seven_days_ago = now - timedelta(days=7)
        q_count = select(func.count(MarketingFrequencyLog.id)).where(
            MarketingFrequencyLog.business_id == business_id,
            MarketingFrequencyLog.contact_id == contact_id,
            MarketingFrequencyLog.channel == channel,
            MarketingFrequencyLog.sent_at >= seven_days_ago,
        )
        count_7d = (await session.execute(q_count)).scalar() or 0
        if count_7d >= max_per_week:
            return False, f"Maximum frequency cap reached ({count_7d}/{max_per_week} promotional messages in 7 days)"

        return True, "Eligible"

    @staticmethod
    async def record_promotional_send(
        session: AsyncSession,
        business_id: uuid.UUID,
        contact_id: uuid.UUID,
        *,
        channel: str,
        campaign_id: uuid.UUID | None = None,
        now: datetime | None = None,
    ) -> MarketingFrequencyLog:
        """Appends promotional send to frequency log."""
        now = now or datetime.now(timezone.utc)
        log = MarketingFrequencyLog(
            business_id=business_id,
            contact_id=contact_id,
            channel=channel,
            campaign_id=campaign_id,
            sent_at=now,
        )
        session.add(log)
        await session.flush()
        return log
