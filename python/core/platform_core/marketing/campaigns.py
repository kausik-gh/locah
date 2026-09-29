"""Marketing Campaign Domain & Owner Approval Workflow (MK-08; MD §18.1–§18.2; PDF §13).

Campaign flow:
Goal -> Audience -> Offer -> Creative -> Channel + Budget -> Owner Approves -> Scheduled/Running -> Results.
Owner approval is mandatory before any live broadcast or rupee spent.
Mutation after approval invalidates approval and returns to DRAFT.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.marketing.audiences import MarketingAudienceService
from platform_core.marketing.models import MarketingCampaign
from platform_core.marketing.regulated import RegulatedCategoryPolicyService

# Configured WhatsApp Marketing template cost per message (in paise)
# E.g. ₹0.80 = 80 paise
CONFIGURED_WHATSAPP_MARKETING_COST_PAISE = 80


def _compute_content_hash(
    name: str,
    goal: str,
    channel: str,
    audience_segment_id: uuid.UUID | None,
    offer_id: uuid.UUID | None,
    creative: dict[str, Any],
    budget_paise: int,
) -> str:
    content = json.dumps(
        {
            "name": name,
            "goal": goal,
            "channel": channel,
            "audience_segment_id": str(audience_segment_id) if audience_segment_id else None,
            "offer_id": str(offer_id) if offer_id else None,
            "creative": creative,
            "budget_paise": budget_paise,
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class CampaignService:
    @staticmethod
    async def create_campaign(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        name: str,
        goal: str,
        channel: str = "whatsapp",
        audience_segment_id: uuid.UUID | None = None,
        offer_id: uuid.UUID | None = None,
        creative: dict[str, Any] | None = None,
        budget_paise: int = 0,
        schedule_type: str = "immediate",
        scheduled_at: datetime | None = None,
        created_by: uuid.UUID | None = None,
    ) -> MarketingCampaign:
        if channel not in ("whatsapp", "meta_ads"):
            raise ValidationError(f"Invalid channel: {channel}")

        creative_payload = creative or {}
        content_hash = _compute_content_hash(
            name, goal, channel, audience_segment_id, offer_id, creative_payload, budget_paise
        )

        now = datetime.now(timezone.utc)
        campaign = MarketingCampaign(
            business_id=business_id,
            name=name,
            goal=goal,
            channel=channel,
            audience_segment_id=audience_segment_id,
            audience_snapshot={},
            offer_id=offer_id,
            creative=creative_payload,
            budget_paise=budget_paise,
            estimated_cost_paise=0,
            actual_cost_paise=0,
            schedule_type=schedule_type,
            scheduled_at=scheduled_at,
            status="DRAFT",
            content_hash=content_hash,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        session.add(campaign)
        await session.flush()
        return campaign

    @staticmethod
    async def get_campaign(
        session: AsyncSession, business_id: uuid.UUID, campaign_id: uuid.UUID
    ) -> MarketingCampaign:
        q = select(MarketingCampaign).where(
            MarketingCampaign.business_id == business_id,
            MarketingCampaign.id == campaign_id,
        )
        c = (await session.execute(q)).scalars().first()
        if c is None:
            raise ResourceNotFound("Marketing Campaign")
        return c

    @staticmethod
    async def update_campaign(
        session: AsyncSession,
        business_id: uuid.UUID,
        campaign_id: uuid.UUID,
        *,
        name: str | None = None,
        goal: str | None = None,
        channel: str | None = None,
        audience_segment_id: uuid.UUID | None = None,
        offer_id: uuid.UUID | None = None,
        creative: dict[str, Any] | None = None,
        budget_paise: int | None = None,
        schedule_type: str | None = None,
        scheduled_at: datetime | None = None,
    ) -> MarketingCampaign:
        campaign = await CampaignService.get_campaign(session, business_id, campaign_id)

        if campaign.status in ("RUNNING", "COMPLETED", "CANCELLED"):
            raise ConflictError(f"Cannot edit campaign in {campaign.status} status")

        changed_significant = False

        if name is not None and name != campaign.name:
            campaign.name = name
            changed_significant = True
        if goal is not None and goal != campaign.goal:
            campaign.goal = goal
            changed_significant = True
        if channel is not None and channel != campaign.channel:
            campaign.channel = channel
            changed_significant = True
        if audience_segment_id is not None and audience_segment_id != campaign.audience_segment_id:
            campaign.audience_segment_id = audience_segment_id
            changed_significant = True
        if offer_id is not None and offer_id != campaign.offer_id:
            campaign.offer_id = offer_id
            changed_significant = True
        if creative is not None and creative != campaign.creative:
            campaign.creative = creative
            changed_significant = True
        if budget_paise is not None and budget_paise != campaign.budget_paise:
            campaign.budget_paise = budget_paise
            changed_significant = True
        if schedule_type is not None:
            campaign.schedule_type = schedule_type
        if scheduled_at is not None:
            campaign.scheduled_at = scheduled_at

        # If campaign was already approved, but changed: INVALIDATE APPROVAL!
        if campaign.status in ("APPROVED", "SCHEDULED", "READY_FOR_APPROVAL") and changed_significant:
            campaign.status = "DRAFT"
            campaign.approved_by = None
            campaign.approved_at = None
            campaign.approval_record = None

        campaign.content_hash = _compute_content_hash(
            campaign.name,
            campaign.goal,
            campaign.channel,
            campaign.audience_segment_id,
            campaign.offer_id,
            campaign.creative,
            campaign.budget_paise,
        )
        campaign.updated_at = datetime.now(timezone.utc)
        campaign.version += 1
        await session.flush()
        return campaign

    @staticmethod
    async def prepare_for_approval(
        session: AsyncSession,
        business_id: uuid.UUID,
        campaign_id: uuid.UUID,
        *,
        business_category: str | None = None,
        business_subcategory: str | None = None,
        business_traits: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Calculates audience snapshot, estimated cost, and checks regulated category policy."""
        campaign = await CampaignService.get_campaign(session, business_id, campaign_id)

        if not campaign.audience_segment_id:
            raise ValidationError("An audience segment must be selected before submitting for approval")

        # 1. Regulated Category Guard
        policy = RegulatedCategoryPolicyService.evaluate(
            category_key=business_category,
            subcategory_key=business_subcategory,
            business_traits=business_traits,
        )
        if not policy.allowed and policy.status == "prohibited":
            raise ValidationError(f"Campaign prohibited: {policy.reason}")

        # 2. Audience & Cost Estimation
        aud = await MarketingAudienceService.resolve_segment_audience(
            session, business_id, campaign.audience_segment_id, channel=campaign.channel
        )
        consented_count = aud["consented_count"]
        estimated_cost = consented_count * CONFIGURED_WHATSAPP_MARKETING_COST_PAISE

        campaign.audience_snapshot = aud
        campaign.estimated_cost_paise = estimated_cost
        campaign.status = "READY_FOR_APPROVAL"
        campaign.updated_at = datetime.now(timezone.utc)
        await session.flush()

        return {
            "campaign_id": str(campaign.id),
            "status": campaign.status,
            "audience_snapshot": aud,
            "estimated_cost_paise": estimated_cost,
            "budget_paise": campaign.budget_paise,
            "policy": {
                "status": policy.status,
                "reason": policy.reason,
                "requires_declaration": policy.requires_declaration,
            },
        }

    @staticmethod
    async def owner_approve_campaign(
        session: AsyncSession,
        business_id: uuid.UUID,
        campaign_id: uuid.UUID,
        approver_identity_id: uuid.UUID,
        *,
        is_owner: bool = True,
        override_declaration: bool = False,
        now: datetime | None = None,
    ) -> MarketingCampaign:
        """Owner approval is mandatory before any broadcast or rupee spent."""
        now = now or datetime.now(timezone.utc)
        campaign = await CampaignService.get_campaign(session, business_id, campaign_id)

        if not is_owner:
            raise ValidationError("Only the business owner or authorized administrator can approve marketing campaigns")

        if campaign.status not in ("READY_FOR_APPROVAL", "DRAFT"):
            raise ConflictError(f"Cannot approve campaign in {campaign.status} status")

        # Must have positive budget or estimated cost within budget
        if campaign.budget_paise > 0 and campaign.estimated_cost_paise > campaign.budget_paise:
            raise ValidationError(
                f"Estimated send cost (₹{campaign.estimated_cost_paise/100:.2f}) exceeds configured budget cap (₹{campaign.budget_paise/100:.2f})",
                details={
                    "estimated_cost_paise": campaign.estimated_cost_paise,
                    "budget_paise": campaign.budget_paise,
                },
            )

        # Freeze approval record
        approval_rec = {
            "approved_by": str(approver_identity_id),
            "approved_at": now.isoformat(),
            "audience_snapshot": campaign.audience_snapshot,
            "estimated_cost_paise": campaign.estimated_cost_paise,
            "budget_cap_paise": campaign.budget_paise,
            "content_hash": campaign.content_hash,
            "channel": campaign.channel,
            "override_declaration": override_declaration,
        }

        campaign.approved_by = approver_identity_id
        campaign.approved_at = now
        campaign.approval_record = approval_rec
        campaign.status = "APPROVED"
        campaign.updated_at = now
        await session.flush()
        return campaign
