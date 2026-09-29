"""Platform Loyalty, Points, Stamps, Referrals & Vouchers API (LY-01 through LY-04)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.loyalty.service import (
    GiftVoucherService,
    LoyaltyPointsService,
    LoyaltyProgramService,
    ReferralService,
    StampCardService,
)

router = APIRouter(prefix="/v1/platform/businesses", tags=["loyalty"])


# -----------------------------------------------------------------------------
# Request & Response Models
# -----------------------------------------------------------------------------

class UpdateProgramRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    points_per_rupee: Decimal | None = None
    redemption_rupees_per_point: Decimal | None = None
    min_redemption_points: int | None = None
    max_redemption_points_per_order: int | None = None
    expiry_days: int | None = None
    status: str | None = None


class EarnPointsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_amount_paise: int = Field(..., ge=0)
    source_type: str = "order"
    source_id: str
    idempotency_key: str
    reason: str = "earn_order"


class ValidateRedemptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    points_to_redeem: int = Field(..., ge=1)
    order_amount_paise: int = Field(..., ge=0)


class RedeemPointsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    points_to_redeem: int = Field(..., ge=1)
    order_amount_paise: int = Field(..., ge=0)
    source_type: str = "order"
    source_id: str
    idempotency_key: str


class AwardStampRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str = "order"
    source_id: str
    idempotency_key: str
    program_id: uuid.UUID | None = None


class ApplyReferralRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str


class QualifyReferralRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str = "order"
    source_id: str
    referrer_points: int = 100
    referee_points: int = 50


class IssueVoucherRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issued_amount_paise: int = Field(..., ge=1)
    recipient_name: str | None = None
    recipient_phone: str | None = None
    holder_contact_id: uuid.UUID | None = None
    expiry_days: int | None = 365


class RedeemVoucherRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    redeem_amount_paise: int = Field(..., ge=1)
    source_type: str = "order"
    source_id: str
    idempotency_key: str


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.get("/{business_id}/loyalty/program")
async def get_loyalty_program(
    business_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(require_business_actor()),
) -> dict[str, Any]:
    prog = await LoyaltyProgramService.get_or_create_default_program(session, business_id)
    return {
        "id": str(prog.id),
        "name": prog.name,
        "program_type": prog.program_type,
        "points_per_rupee": float(prog.points_per_rupee),
        "redemption_rupees_per_point": float(prog.redemption_rupees_per_point),
        "min_redemption_points": prog.min_redemption_points,
        "max_redemption_points_per_order": prog.max_redemption_points_per_order,
        "expiry_days": prog.expiry_days,
        "status": prog.status,
    }


@router.put("/{business_id}/loyalty/program")
async def update_loyalty_program(
    business_id: uuid.UUID,
    body: UpdateProgramRequest,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(require_business_actor()),
) -> dict[str, Any]:
    prog = await LoyaltyProgramService.update_program(
        session,
        business_id,
        name=body.name,
        points_per_rupee=body.points_per_rupee,
        redemption_rupees_per_point=body.redemption_rupees_per_point,
        min_redemption_points=body.min_redemption_points,
        max_redemption_points_per_order=body.max_redemption_points_per_order,
        expiry_days=body.expiry_days,
        status=body.status,
    )
    return {
        "id": str(prog.id),
        "name": prog.name,
        "points_per_rupee": float(prog.points_per_rupee),
        "redemption_rupees_per_point": float(prog.redemption_rupees_per_point),
        "status": prog.status,
    }


@router.get("/{business_id}/loyalty/customers/{contact_id}/balance")
async def get_customer_points_balance(
    business_id: uuid.UUID,
    contact_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(require_business_actor()),
) -> dict[str, Any]:
    account = await LoyaltyPointsService.get_or_create_account(session, business_id, contact_id)
    usable = await LoyaltyPointsService.get_usable_balance(session, business_id, contact_id)
    return {
        "customer_contact_id": str(contact_id),
        "usable_points": usable,
        "current_points": account.current_points,
        "lifetime_earned": account.lifetime_points_earned,
        "lifetime_redeemed": account.lifetime_points_redeemed,
        "tier": account.tier,
    }


@router.post("/{business_id}/loyalty/customers/{contact_id}/earn")
async def earn_customer_points(
    business_id: uuid.UUID,
    contact_id: uuid.UUID,
    body: EarnPointsRequest,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(require_business_actor()),
) -> dict[str, Any]:
    return await LoyaltyPointsService.earn_points(
        session,
        business_id,
        contact_id,
        order_amount_paise=body.order_amount_paise,
        source_type=body.source_type,
        source_id=body.source_id,
        idempotency_key=body.idempotency_key,
        reason=body.reason,
    )


@router.post("/{business_id}/loyalty/customers/{contact_id}/validate-redemption")
async def validate_points_redemption(
    business_id: uuid.UUID,
    contact_id: uuid.UUID,
    body: ValidateRedemptionRequest,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(require_business_actor()),
) -> dict[str, Any]:
    return await LoyaltyPointsService.validate_redemption(
        session,
        business_id,
        contact_id,
        points_to_redeem=body.points_to_redeem,
        order_amount_paise=body.order_amount_paise,
    )


@router.post("/{business_id}/loyalty/customers/{contact_id}/redeem")
async def redeem_customer_points(
    business_id: uuid.UUID,
    contact_id: uuid.UUID,
    body: RedeemPointsRequest,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(require_business_actor()),
) -> dict[str, Any]:
    return await LoyaltyPointsService.redeem_points(
        session,
        business_id,
        contact_id,
        points_to_redeem=body.points_to_redeem,
        order_amount_paise=body.order_amount_paise,
        source_type=body.source_type,
        source_id=body.source_id,
        idempotency_key=body.idempotency_key,
    )


@router.post("/{business_id}/loyalty/customers/{contact_id}/stamps/award")
async def award_customer_stamp(
    business_id: uuid.UUID,
    contact_id: uuid.UUID,
    body: AwardStampRequest,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(require_business_actor()),
) -> dict[str, Any]:
    return await StampCardService.award_stamp(
        session,
        business_id,
        contact_id,
        source_type=body.source_type,
        source_id=body.source_id,
        idempotency_key=body.idempotency_key,
        program_id=body.program_id,
    )


@router.get("/{business_id}/loyalty/customers/{contact_id}/referral")
async def get_referral_code(
    business_id: uuid.UUID,
    contact_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(require_business_actor()),
) -> dict[str, Any]:
    code = await ReferralService.get_or_create_referral_code(session, business_id, contact_id)
    return {"code": code}


@router.post("/{business_id}/loyalty/customers/{contact_id}/referral/apply")
async def apply_referral_code(
    business_id: uuid.UUID,
    contact_id: uuid.UUID,
    body: ApplyReferralRequest,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(require_business_actor()),
) -> dict[str, Any]:
    rel = await ReferralService.apply_referral_code(session, business_id, contact_id, body.code)
    return {
        "relationship_id": str(rel.id),
        "code_used": rel.code_used,
        "status": rel.status,
    }


@router.post("/{business_id}/loyalty/customers/{contact_id}/referral/qualify")
async def qualify_referral(
    business_id: uuid.UUID,
    contact_id: uuid.UUID,
    body: QualifyReferralRequest,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(require_business_actor()),
) -> dict[str, Any]:
    return await ReferralService.qualify_first_purchase(
        session,
        business_id,
        contact_id,
        source_type=body.source_type,
        source_id=body.source_id,
        referrer_points=body.referrer_points,
        referee_points=body.referee_points,
    )


@router.post("/{business_id}/loyalty/vouchers")
async def issue_gift_voucher(
    business_id: uuid.UUID,
    body: IssueVoucherRequest,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(require_business_actor()),
) -> dict[str, Any]:
    v = await GiftVoucherService.issue_voucher(
        session,
        business_id,
        issued_amount_paise=body.issued_amount_paise,
        recipient_name=body.recipient_name,
        recipient_phone=body.recipient_phone,
        holder_contact_id=body.holder_contact_id,
        expiry_days=body.expiry_days,
        actor_id=context.identity_id if hasattr(context, "identity_id") else None,
    )
    return {
        "id": str(v.id),
        "code": v.code,
        "issued_amount_paise": v.issued_amount_paise,
        "remaining_balance_paise": v.remaining_balance_paise,
        "status": v.status,
        "expires_at": v.expires_at.isoformat() if v.expires_at else None,
    }


@router.get("/{business_id}/loyalty/vouchers/{code}")
async def validate_gift_voucher(
    business_id: uuid.UUID,
    code: str,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(require_business_actor()),
) -> dict[str, Any]:
    return await GiftVoucherService.validate_voucher(session, business_id, code)


@router.post("/{business_id}/loyalty/vouchers/{code}/redeem")
async def redeem_gift_voucher(
    business_id: uuid.UUID,
    code: str,
    body: RedeemVoucherRequest,
    session: AsyncSession = Depends(get_db_session),
    context: BusinessActorContext = Depends(require_business_actor()),
) -> dict[str, Any]:
    return await GiftVoucherService.redeem_voucher(
        session,
        business_id,
        code,
        redeem_amount_paise=body.redeem_amount_paise,
        source_type=body.source_type,
        source_id=body.source_id,
        idempotency_key=body.idempotency_key,
    )
