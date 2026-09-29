"""Offers and Coupons domain (MK-02; MD §18.2).

Coupon codes, auto-applied offers, first-order, win-back, usage limits, expiry, per-customer caps.
Provides a clean evaluation contract without mutating or hijacking Checkout.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ValidationError
from platform_core.marketing.models import MarketingOffer
from platform_core.models import SalesOrder


class OfferService:
    @staticmethod
    async def create_offer(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        code: str,
        name: str,
        kind: str,
        discount_value: Decimal,
        min_order_amount_paise: int = 0,
        max_discount_paise: int | None = None,
        usage_limit_total: int | None = None,
        usage_limit_per_customer: int = 1,
        starts_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> MarketingOffer:
        clean_code = code.strip().upper()
        if not clean_code:
            raise ValidationError("Coupon code cannot be empty")

        if kind not in ("percentage_discount", "fixed_amount", "free_delivery", "first_order", "win_back"):
            raise ValidationError(f"Invalid offer kind: {kind}")

        # Check unique code within business
        q = select(MarketingOffer).where(
            MarketingOffer.business_id == business_id,
            func.upper(MarketingOffer.code) == clean_code,
        )
        if (await session.execute(q)).scalars().first() is not None:
            raise ConflictError(f"Coupon code '{clean_code}' already exists for this business")

        now = datetime.now(timezone.utc)
        offer = MarketingOffer(
            business_id=business_id,
            code=clean_code,
            name=name,
            kind=kind,
            discount_value=discount_value,
            min_order_amount_paise=min_order_amount_paise,
            max_discount_paise=max_discount_paise,
            usage_limit_total=usage_limit_total,
            usage_limit_per_customer=usage_limit_per_customer,
            times_used=0,
            starts_at=starts_at or now,
            expires_at=expires_at,
            status="active",
            created_at=now,
            updated_at=now,
        )
        session.add(offer)
        await session.flush()
        return offer

    @staticmethod
    async def get_offer_by_code(
        session: AsyncSession, business_id: uuid.UUID, code: str
    ) -> MarketingOffer | None:
        clean_code = code.strip().upper()
        q = select(MarketingOffer).where(
            MarketingOffer.business_id == business_id,
            func.upper(MarketingOffer.code) == clean_code,
        )
        return (await session.execute(q)).scalars().first()

    @staticmethod
    async def evaluate_offer(
        session: AsyncSession,
        business_id: uuid.UUID,
        code: str,
        *,
        cart_total_paise: int,
        customer_contact_id: uuid.UUID | None = None,
        delivery_fee_paise: int = 0,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Evaluates offer deterministically against cart/order context.

        Returns:
            {
                "eligible": bool,
                "discount_paise": int,
                "code": str,
                "offer_id": str | None,
                "reason": str,
            }
        """
        now = now or datetime.now(timezone.utc)
        clean_code = code.strip().upper()

        offer = await OfferService.get_offer_by_code(session, business_id, clean_code)
        if offer is None:
            return {
                "eligible": False,
                "discount_paise": 0,
                "code": clean_code,
                "offer_id": None,
                "reason": "Coupon code not found",
            }

        if offer.status != "active":
            return {
                "eligible": False,
                "discount_paise": 0,
                "code": clean_code,
                "offer_id": str(offer.id),
                "reason": f"Offer is {offer.status}",
            }

        if offer.starts_at and offer.starts_at > now:
            return {
                "eligible": False,
                "discount_paise": 0,
                "code": clean_code,
                "offer_id": str(offer.id),
                "reason": "Offer has not started yet",
            }

        if offer.expires_at and offer.expires_at < now:
            return {
                "eligible": False,
                "discount_paise": 0,
                "code": clean_code,
                "offer_id": str(offer.id),
                "reason": "Offer has expired",
            }

        if cart_total_paise < offer.min_order_amount_paise:
            min_rs = offer.min_order_amount_paise / 100
            return {
                "eligible": False,
                "discount_paise": 0,
                "code": clean_code,
                "offer_id": str(offer.id),
                "reason": f"Minimum order amount of ₹{min_rs:.2f} required",
            }

        if offer.usage_limit_total and offer.times_used >= offer.usage_limit_total:
            return {
                "eligible": False,
                "discount_paise": 0,
                "code": clean_code,
                "offer_id": str(offer.id),
                "reason": "Offer usage limit has been reached",
            }

        # First order check
        if offer.kind == "first_order":
            if not customer_contact_id:
                return {
                    "eligible": False,
                    "discount_paise": 0,
                    "code": clean_code,
                    "offer_id": str(offer.id),
                    "reason": "Login required for first-order discount",
                }
            prior_count = (
                await session.execute(
                    select(func.count(SalesOrder.id)).where(
                        SalesOrder.business_id == business_id,
                        SalesOrder.customer_contact_id == customer_contact_id,
                        SalesOrder.deleted_at.is_(None),
                        SalesOrder.status.notin_(("cancelled", "rejected")),
                    )
                )
            ).scalar() or 0
            if prior_count > 0:
                return {
                    "eligible": False,
                    "discount_paise": 0,
                    "code": clean_code,
                    "offer_id": str(offer.id),
                    "reason": "Valid only on your first purchase",
                }

        # Win-back check: customer hasn't purchased in >= 60 days
        if offer.kind == "win_back":
            if not customer_contact_id:
                return {
                    "eligible": False,
                    "discount_paise": 0,
                    "code": clean_code,
                    "offer_id": str(offer.id),
                    "reason": "Customer identity required for win-back offer",
                }
            recent_order = (
                await session.execute(
                    select(SalesOrder.id).where(
                        SalesOrder.business_id == business_id,
                        SalesOrder.customer_contact_id == customer_contact_id,
                        SalesOrder.deleted_at.is_(None),
                        SalesOrder.created_at >= now - timedelta(days=60),
                        SalesOrder.status.notin_(("cancelled", "rejected")),
                    )
                )
            ).scalars().first()
            if recent_order is not None:
                return {
                    "eligible": False,
                    "discount_paise": 0,
                    "code": clean_code,
                    "offer_id": str(offer.id),
                    "reason": "Valid only for returning customers with no orders in 60 days",
                }

        # Calculate discount
        discount_paise = 0
        if offer.kind in ("percentage_discount", "first_order", "win_back"):
            # discount_value is percentage (e.g. 10.0 for 10%)
            discount_paise = int(math.floor(Decimal(cart_total_paise) * (offer.discount_value / Decimal(100))))
            if offer.max_discount_paise:
                discount_paise = min(discount_paise, offer.max_discount_paise)
        elif offer.kind == "fixed_amount":
            # discount_value is in rupees
            fixed_paise = int(offer.discount_value * 100)
            discount_paise = min(cart_total_paise, fixed_paise)
        elif offer.kind == "free_delivery":
            discount_paise = delivery_fee_paise

        # Ensure discount does not exceed cart
        discount_paise = min(discount_paise, cart_total_paise)

        return {
            "eligible": True,
            "discount_paise": discount_paise,
            "code": clean_code,
            "offer_id": str(offer.id),
            "reason": "Offer applied successfully",
        }

    @staticmethod
    async def record_offer_use(session: AsyncSession, offer_id: uuid.UUID) -> None:
        """Increments times_used on offer."""
        offer = await session.get(MarketingOffer, offer_id)
        if offer:
            offer.times_used += 1
            await session.flush()
