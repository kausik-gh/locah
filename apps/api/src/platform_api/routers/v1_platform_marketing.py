"""Platform Marketing, Campaigns, Audiences, Offers & Attribution API (MK-01 through MK-10; MS-26)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.marketing.audiences import MarketingAudienceService
from platform_core.marketing.broadcast import WhatsAppBroadcastOrchestrator
from platform_core.marketing.campaigns import CampaignService
from platform_core.marketing.meta_ads import MetaAdsContractService
from platform_core.marketing.models import MarketingCampaign, MarketingOffer
from platform_core.marketing.offers import OfferService
from platform_core.marketing.regulated import RegulatedCategoryPolicyService
from platform_core.marketing.results import MarketingResultsService
from platform_core.models import Business
from platform_core.permissions import (
    MARKETING_APPROVE,
    MARKETING_CREATE,
    MARKETING_READ,
    MARKETING_SEND,
)

# marketing.approve and marketing.send stay with the owner.
# A marketer may read and draft. Approval is not the same permission.
_MODULE = "marketing"
_READ = require_business_actor(MARKETING_READ, _MODULE)
_CREATE = require_business_actor(MARKETING_CREATE, _MODULE)
_APPROVE = require_business_actor(MARKETING_APPROVE, _MODULE)
_SEND = require_business_actor(MARKETING_SEND, _MODULE)

router = APIRouter(prefix="/v1/platform/businesses", tags=["marketing"])


async def _keep(session: AsyncSession) -> None:
    """The request session rolls back on the way out unless the handler commits."""
    await session.commit()


async def _enabled_traits(session: AsyncSession, business: Business | None) -> frozenset[str]:
    """Enabled operating traits. Marketing rules read these, not a free-form bag."""
    if business is None:
        return frozenset()
    from platform_core.services.business_classification import BusinessClassificationService

    return await BusinessClassificationService.effective_traits(session, business)


# -----------------------------------------------------------------------------
# Request & Response Models
# -----------------------------------------------------------------------------

class CreateCampaignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., max_length=100)
    goal: str = Field(..., max_length=60)
    channel: str = "whatsapp"
    audience_segment_id: uuid.UUID | None = None
    offer_id: uuid.UUID | None = None
    creative: dict[str, Any] = Field(default_factory=dict)
    budget_paise: int = Field(default=0, ge=0)
    schedule_type: str = "immediate"


class PatchCampaignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    goal: str | None = None
    channel: str | None = None
    audience_segment_id: uuid.UUID | None = None
    offer_id: uuid.UUID | None = None
    creative: dict[str, Any] | None = None
    budget_paise: int | None = None
    schedule_type: str | None = None


class CreateOfferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    name: str
    kind: str = "percentage_discount"
    discount_value: Decimal = Field(..., gt=0)
    min_order_amount_paise: int = 0
    max_discount_paise: int | None = None
    usage_limit_total: int | None = None
    usage_limit_per_customer: int = 1


class EvaluateOfferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    cart_total_paise: int = Field(..., ge=0)
    customer_contact_id: uuid.UUID | None = None
    delivery_fee_paise: int = 0


class MetaSpendCapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monthly_spend_cap_paise: int = Field(..., ge=0)
    ad_account_id: str | None = None
    pixel_id: str | None = None
    conversions_api_enabled: bool = False


class MetaSpendTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_spend_paise: int = Field(..., ge=1)


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.get("/{business_id}/marketing/campaigns")
async def list_campaigns(
    business_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(_READ),
) -> dict[str, Any]:
    q = select(MarketingCampaign).where(MarketingCampaign.business_id == business_id).order_by(MarketingCampaign.created_at.desc())
    items = (await session.execute(q)).scalars().all()
    return {
        "campaigns": [
            {
                "id": str(c.id),
                "name": c.name,
                "goal": c.goal,
                "channel": c.channel,
                "status": c.status,
                "budget_paise": c.budget_paise,
                "estimated_cost_paise": c.estimated_cost_paise,
                "actual_cost_paise": c.actual_cost_paise,
                "audience_segment_id": str(c.audience_segment_id) if c.audience_segment_id else None,
                "offer_id": str(c.offer_id) if c.offer_id else None,
                "approved_at": c.approved_at.isoformat() if c.approved_at else None,
                "created_at": c.created_at.isoformat(),
            }
            for c in items
        ]
    }


@router.post("/{business_id}/marketing/campaigns")
async def create_campaign(
    business_id: uuid.UUID,
    body: CreateCampaignRequest,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(_CREATE),
) -> dict[str, Any]:
    c = await CampaignService.create_campaign(
        session,
        business_id,
        name=body.name,
        goal=body.goal,
        channel=body.channel,
        audience_segment_id=body.audience_segment_id,
        offer_id=body.offer_id,
        creative=body.creative,
        budget_paise=body.budget_paise,
        schedule_type=body.schedule_type,
        created_by=context.request.identity_id,
    )
    await _keep(session)
    return {
        "id": str(c.id),
        "name": c.name,
        "goal": c.goal,
        "status": c.status,
        "channel": c.channel,
        "budget_paise": c.budget_paise,
    }


@router.get("/{business_id}/marketing/campaigns/{campaign_id}")
async def get_campaign(
    business_id: uuid.UUID,
    campaign_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(_READ),
) -> dict[str, Any]:
    c = await CampaignService.get_campaign(session, business_id, campaign_id)
    return {
        "id": str(c.id),
        "name": c.name,
        "goal": c.goal,
        "channel": c.channel,
        "status": c.status,
        "budget_paise": c.budget_paise,
        "estimated_cost_paise": c.estimated_cost_paise,
        "actual_cost_paise": c.actual_cost_paise,
        "audience_segment_id": str(c.audience_segment_id) if c.audience_segment_id else None,
        "audience_snapshot": c.audience_snapshot,
        "offer_id": str(c.offer_id) if c.offer_id else None,
        "creative": c.creative,
        "approved_by": str(c.approved_by) if c.approved_by else None,
        "approved_at": c.approved_at.isoformat() if c.approved_at else None,
        "approval_record": c.approval_record,
        "version": c.version,
    }


@router.patch("/{business_id}/marketing/campaigns/{campaign_id}")
async def patch_campaign(
    business_id: uuid.UUID,
    campaign_id: uuid.UUID,
    body: PatchCampaignRequest,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(_CREATE),
) -> dict[str, Any]:
    c = await CampaignService.update_campaign(
        session,
        business_id,
        campaign_id,
        name=body.name,
        goal=body.goal,
        channel=body.channel,
        audience_segment_id=body.audience_segment_id,
        offer_id=body.offer_id,
        creative=body.creative,
        budget_paise=body.budget_paise,
        schedule_type=body.schedule_type,
    )
    await _keep(session)
    return {
        "id": str(c.id),
        "name": c.name,
        "status": c.status,
        "version": c.version,
    }


@router.post("/{business_id}/marketing/campaigns/{campaign_id}/prepare")
async def prepare_campaign(
    business_id: uuid.UUID,
    campaign_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(_CREATE),
) -> dict[str, Any]:
    biz = await session.get(Business, business_id)
    traits = await _enabled_traits(session, biz)
    result = await CampaignService.prepare_for_approval(
        session,
        business_id,
        campaign_id,
        business_category=getattr(biz, "category_key", None) if biz else None,
        business_subcategory=getattr(biz, "subcategory_key", None) if biz else None,
        business_traits=traits,
    )
    await _keep(session)
    return result


@router.post("/{business_id}/marketing/campaigns/{campaign_id}/approve")
async def approve_campaign(
    business_id: uuid.UUID,
    campaign_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(_APPROVE),
) -> dict[str, Any]:
    # marketing.approve is the owner's permission. A marketer template does not hold it.
    c = await CampaignService.owner_approve_campaign(
        session,
        business_id,
        campaign_id,
        approver_identity_id=context.request.identity_id,
    )
    await _keep(session)
    return {
        "id": str(c.id),
        "status": c.status,
        "approved_at": c.approved_at.isoformat() if c.approved_at else None,
        "approval_record": c.approval_record,
    }


@router.post("/{business_id}/marketing/campaigns/{campaign_id}/dispatch")
async def dispatch_campaign(
    business_id: uuid.UUID,
    campaign_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(_SEND),
) -> dict[str, Any]:
    result = await WhatsAppBroadcastOrchestrator.dispatch_campaign(
        session, business_id, campaign_id
    )
    await _keep(session)
    return result


@router.get("/{business_id}/marketing/campaigns/{campaign_id}/results")
async def get_campaign_results(
    business_id: uuid.UUID,
    campaign_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(_READ),
) -> dict[str, Any]:
    return await MarketingResultsService.get_campaign_results(
        session, business_id, campaign_id
    )


@router.get("/{business_id}/marketing/offers")
async def list_offers(
    business_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(_READ),
) -> dict[str, Any]:
    q = select(MarketingOffer).where(MarketingOffer.business_id == business_id).order_by(MarketingOffer.created_at.desc())
    items = (await session.execute(q)).scalars().all()
    return {
        "offers": [
            {
                "id": str(o.id),
                "code": o.code,
                "name": o.name,
                "kind": o.kind,
                "discount_value": float(o.discount_value),
                "min_order_amount_paise": o.min_order_amount_paise,
                "max_discount_paise": o.max_discount_paise,
                "times_used": o.times_used,
                "status": o.status,
            }
            for o in items
        ]
    }


@router.post("/{business_id}/marketing/offers")
async def create_offer(
    business_id: uuid.UUID,
    body: CreateOfferRequest,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(_CREATE),
) -> dict[str, Any]:
    o = await OfferService.create_offer(
        session,
        business_id,
        code=body.code,
        name=body.name,
        kind=body.kind,
        discount_value=body.discount_value,
        min_order_amount_paise=body.min_order_amount_paise,
        max_discount_paise=body.max_discount_paise,
        usage_limit_total=body.usage_limit_total,
        usage_limit_per_customer=body.usage_limit_per_customer,
    )
    await _keep(session)
    return {
        "id": str(o.id),
        "code": o.code,
        "name": o.name,
        "status": o.status,
    }


@router.post("/{business_id}/marketing/offers/evaluate")
async def evaluate_offer_code(
    business_id: uuid.UUID,
    body: EvaluateOfferRequest,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(_READ),
) -> dict[str, Any]:
    return await OfferService.evaluate_offer(
        session,
        business_id,
        body.code,
        cart_total_paise=body.cart_total_paise,
        customer_contact_id=body.customer_contact_id,
        delivery_fee_paise=body.delivery_fee_paise,
    )


@router.get("/{business_id}/marketing/audiences/{segment_id}")
async def get_audience_counts(
    business_id: uuid.UUID,
    segment_id: uuid.UUID,
    channel: str = "whatsapp",
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(_READ),
) -> dict[str, Any]:
    return await MarketingAudienceService.resolve_segment_audience(
        session, business_id, segment_id, channel=channel
    )


@router.get("/{business_id}/marketing/policy")
async def check_marketing_policy(
    business_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(_READ),
) -> dict[str, Any]:
    biz = await session.get(Business, business_id)
    traits = await _enabled_traits(session, biz)
    res = RegulatedCategoryPolicyService.evaluate(
        category_key=getattr(biz, "category_key", None) if biz else None,
        subcategory_key=getattr(biz, "subcategory_key", None) if biz else None,
        traits=traits,
    )
    return {
        "allowed": res.allowed,
        "status": res.status,
        "reason": res.reason,
        "meta_targeting_check": res.meta_targeting_check,
    }


@router.post("/{business_id}/marketing/meta/spend-cap")
async def configure_meta_spend_cap(
    business_id: uuid.UUID,
    body: MetaSpendCapRequest,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(_APPROVE),
) -> dict[str, Any]:
    cfg = await MetaAdsContractService.configure_spend_cap(
        session,
        business_id,
        monthly_spend_cap_paise=body.monthly_spend_cap_paise,
        ad_account_id=body.ad_account_id,
        pixel_id=body.pixel_id,
        conversions_api_enabled=body.conversions_api_enabled,
    )
    await _keep(session)
    return {
        "business_id": str(cfg.business_id),
        "monthly_spend_cap_paise": cfg.monthly_spend_cap_paise,
        "status": cfg.status,
    }


@router.post("/{business_id}/marketing/meta/spend-request")
async def test_meta_spend_request(
    business_id: uuid.UUID,
    body: MetaSpendTestRequest,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(_APPROVE),
) -> dict[str, Any]:
    result = await MetaAdsContractService.prepare_campaign_spend_request(
        session, business_id, requested_spend_paise=body.requested_spend_paise
    )
    await _keep(session)
    return result
