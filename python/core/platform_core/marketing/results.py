"""Marketing Results derived strictly from real data (MK-09; MD §18.2, §18.4).

Invariants:
- Every result figure is computed from LOCAH orders, conversions, or real delivery records.
- Never estimated or invented metrics.
- If data is unavailable, it is explicitly shown as unavailable.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ResourceNotFound
from platform_core.marketing.models import (
    MarketingBroadcastRecipient,
    MarketingCampaign,
    MarketingConversion,
    MarketingOffer,
    MarketingTouchpoint,
)


class MarketingResultsService:
    @staticmethod
    async def get_campaign_results(
        session: AsyncSession, business_id: uuid.UUID, campaign_id: uuid.UUID
    ) -> dict[str, Any]:
        """Aggregates campaign results strictly from recorded database rows."""
        campaign = (
            await session.execute(
                select(MarketingCampaign).where(
                    MarketingCampaign.business_id == business_id,
                    MarketingCampaign.id == campaign_id,
                )
            )
        ).scalars().first()
        if campaign is None:
            raise ResourceNotFound("Marketing Campaign")

        # 1. Broadcast recipient metrics from real recipient rows
        q_recipients = select(
            func.count(MarketingBroadcastRecipient.id).label("total_recipients"),
            func.count(MarketingBroadcastRecipient.id).filter(
                MarketingBroadcastRecipient.status.in_(("dispatched", "delivered"))
            ).label("sent_count"),
            func.count(MarketingBroadcastRecipient.id).filter(
                MarketingBroadcastRecipient.status == "delivered"
            ).label("delivered_count"),
            func.count(MarketingBroadcastRecipient.id).filter(
                MarketingBroadcastRecipient.status == "excluded_no_consent"
            ).label("excluded_no_consent"),
            func.count(MarketingBroadcastRecipient.id).filter(
                MarketingBroadcastRecipient.status == "excluded_frequency"
            ).label("excluded_frequency"),
        ).where(
            MarketingBroadcastRecipient.business_id == business_id,
            MarketingBroadcastRecipient.campaign_id == campaign_id,
        )
        rec_stats = (await session.execute(q_recipients)).first() or (0, 0, 0, 0, 0)

        total_targeted = rec_stats[0] or 0
        sent_count = rec_stats[1] or 0
        delivered_count = rec_stats[2] or 0
        excluded_consent = rec_stats[3] or 0
        excluded_frequency = rec_stats[4] or 0

        # 2. Coupon redemptions if campaign has an offer
        coupon_uses = 0
        if campaign.offer_id:
            offer = await session.get(MarketingOffer, campaign.offer_id)
            if offer:
                coupon_uses = offer.times_used

        # 3. Attributed conversions and revenue from marketing_conversions
        q_conversions = select(
            func.count(MarketingConversion.id).label("attributed_orders"),
            func.coalesce(func.sum(MarketingConversion.revenue_paise), 0).label("attributed_revenue"),
        ).select_from(MarketingConversion).join(
            MarketingTouchpoint, MarketingConversion.touchpoint_id == MarketingTouchpoint.id
        ).where(
            MarketingConversion.business_id == business_id,
            MarketingTouchpoint.campaign_id == campaign_id,
        )
        conv_stats = (await session.execute(q_conversions)).first()

        attributed_orders = conv_stats[0] or 0
        attributed_revenue_paise = int(conv_stats[1] or 0)
        actual_cost_paise = campaign.actual_cost_paise

        cost_per_order_paise = (
            int(actual_cost_paise / attributed_orders) if attributed_orders > 0 else None
        )
        roas = (
            round(attributed_revenue_paise / actual_cost_paise, 2)
            if actual_cost_paise > 0
            else None
        )

        return {
            "campaign_id": str(campaign.id),
            "campaign_name": campaign.name,
            "channel": campaign.channel,
            "status": campaign.status,
            "actual_cost_paise": actual_cost_paise,
            "recipients_targeted": total_targeted,
            "recipients_sent": sent_count,
            "recipients_delivered": delivered_count,
            "excluded_no_consent": excluded_consent,
            "excluded_frequency": excluded_frequency,
            "coupon_uses": coupon_uses,
            "attributed_orders": attributed_orders,
            "attributed_revenue_paise": attributed_revenue_paise,
            "cost_per_order_paise": cost_per_order_paise,
            "roas": roas,
            "attribution_label": "Approximate · last touch",
            "data_source": "Computed from real LOCAH records only; zero estimated revenue.",
        }
