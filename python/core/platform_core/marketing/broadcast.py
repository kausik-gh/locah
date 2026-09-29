"""WhatsApp Broadcast Campaign Orchestration (MK-03, MK-09, MS-26; MD §18.2; PDF §7, §13).

Strict compliance pipeline:
1. Campaign MUST be in APPROVED state by owner.
2. Consent verified for every single recipient (`ConsentService.has`).
3. Frequency controls & cooldown verified (`FrequencyControlService.can_send`).
4. Replay-safe idempotency per (campaign_id, contact_id).
5. Exact actual spend recorded from sent messages.
6. Zero real Meta calls — uses fixture/adapter transport.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ValidationError
from platform_core.marketing.campaigns import (
    CONFIGURED_WHATSAPP_MARKETING_COST_PAISE,
    CampaignService,
)
from platform_core.marketing.frequency import FrequencyControlService
from platform_core.marketing.models import (
    MarketingBroadcastRecipient,
)
from platform_core.models import CustomerSegment
from platform_core.customers.segments import evaluate
from platform_core.services.consent import ConsentService


class WhatsAppBroadcastOrchestrator:
    @staticmethod
    async def dispatch_campaign(
        session: AsyncSession,
        business_id: uuid.UUID,
        campaign_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Dispatches an approved WhatsApp marketing campaign."""
        now = now or datetime.now(timezone.utc)
        campaign = await CampaignService.get_campaign(session, business_id, campaign_id)

        # 1. State check
        if campaign.status not in ("APPROVED", "SCHEDULED"):
            raise ConflictError(
                f"Campaign cannot be dispatched in '{campaign.status}' state. Owner approval is mandatory."
            )

        if not campaign.audience_segment_id:
            raise ValidationError("Campaign has no audience segment")

        campaign.status = "RUNNING"
        await session.flush()

        # 2. Fetch audience members from segment
        seg = await session.get(CustomerSegment, campaign.audience_segment_id)
        if not seg:
            raise ValidationError("Audience segment not found")

        eval_res = await evaluate(session, business_id, seg.rules, limit=5000, now=now)
        members = eval_res["members"]

        total_targeted = len(members)
        sent_count = 0
        excluded_no_consent = 0
        excluded_frequency = 0
        already_processed_count = 0

        for m in members:
            contact_id = uuid.UUID(m["id"])
            phone = m.get("phone")
            if not phone:
                continue

            idempotency_key = f"{business_id}:{campaign_id}:{contact_id}"

            # Check if this contact was already processed for this campaign (replay safety)
            existing = (
                await session.execute(
                    select(MarketingBroadcastRecipient).where(
                        MarketingBroadcastRecipient.business_id == business_id,
                        MarketingBroadcastRecipient.idempotency_key == idempotency_key,
                    )
                )
            ).scalars().first()

            if existing is not None:
                already_processed_count += 1
                if existing.status in ("dispatched", "delivered"):
                    sent_count += 1
                continue

            # Check 1: Marketing Consent (Hard Requirement!)
            has_consent = await ConsentService.has(
                session,
                business_id,
                contact_id,
                purpose="marketing",
                channel="whatsapp",
            )
            if not has_consent:
                excluded_no_consent += 1
                recipient_log = MarketingBroadcastRecipient(
                    business_id=business_id,
                    campaign_id=campaign_id,
                    contact_id=contact_id,
                    phone=phone,
                    status="excluded_no_consent",
                    cost_paise=0,
                    idempotency_key=idempotency_key,
                    error_reason="No marketing opt-in on WhatsApp",
                    created_at=now,
                )
                session.add(recipient_log)
                continue

            # Check 2: Frequency control (cooldown / spam protection)
            can_send, freq_reason = await FrequencyControlService.can_send_promotional_message(
                session,
                business_id,
                contact_id,
                channel="whatsapp",
                now=now,
            )
            if not can_send:
                excluded_frequency += 1
                recipient_log = MarketingBroadcastRecipient(
                    business_id=business_id,
                    campaign_id=campaign_id,
                    contact_id=contact_id,
                    phone=phone,
                    status="excluded_frequency",
                    cost_paise=0,
                    idempotency_key=idempotency_key,
                    error_reason=freq_reason,
                    created_at=now,
                )
                session.add(recipient_log)
                continue

            # Check 3: Budget check before dispatch
            new_spend = (sent_count + 1) * CONFIGURED_WHATSAPP_MARKETING_COST_PAISE
            if campaign.budget_paise > 0 and new_spend > campaign.budget_paise:
                recipient_log = MarketingBroadcastRecipient(
                    business_id=business_id,
                    campaign_id=campaign_id,
                    contact_id=contact_id,
                    phone=phone,
                    status="failed",
                    cost_paise=0,
                    idempotency_key=idempotency_key,
                    error_reason="Campaign budget cap reached",
                    created_at=now,
                )
                session.add(recipient_log)
                continue

            # Dispatch via fixture/adapter transport (No real Meta call!)
            # Record frequency touch
            await FrequencyControlService.record_promotional_send(
                session,
                business_id,
                contact_id,
                channel="whatsapp",
                campaign_id=campaign_id,
                now=now,
            )

            recipient_log = MarketingBroadcastRecipient(
                business_id=business_id,
                campaign_id=campaign_id,
                contact_id=contact_id,
                phone=phone,
                status="dispatched",
                cost_paise=CONFIGURED_WHATSAPP_MARKETING_COST_PAISE,
                idempotency_key=idempotency_key,
                dispatched_at=now,
                delivered_at=now,  # fixture auto-delivery
                created_at=now,
            )
            session.add(recipient_log)
            sent_count += 1

        campaign.actual_cost_paise = sent_count * CONFIGURED_WHATSAPP_MARKETING_COST_PAISE
        campaign.status = "COMPLETED"
        campaign.updated_at = now
        await session.flush()

        return {
            "campaign_id": str(campaign.id),
            "status": campaign.status,
            "total_targeted": total_targeted,
            "sent_count": sent_count,
            "excluded_no_consent": excluded_no_consent,
            "excluded_frequency": excluded_frequency,
            "already_processed_count": already_processed_count,
            "actual_cost_paise": campaign.actual_cost_paise,
        }
