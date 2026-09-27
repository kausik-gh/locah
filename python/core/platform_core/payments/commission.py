"""Versioned, tenant-scoped fee policy for merchant payments."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ValidationError
from platform_core.models import PlatformFeeRule


def calculate_split(gross: Decimal, rule: PlatformFeeRule) -> tuple[Decimal, Decimal]:
    if gross <= 0:
        raise ValidationError("Payment amount must be positive")
    fee = (
        gross * Decimal(rule.percentage_bps) / Decimal(10000) + Decimal(str(rule.fixed_amount))
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rule.minimum_amount is not None:
        fee = max(fee, Decimal(str(rule.minimum_amount)))
    if rule.maximum_amount is not None:
        fee = min(fee, Decimal(str(rule.maximum_amount)))
    if fee < 0 or fee >= gross:
        raise ValidationError("Configured commission leaves no vendor amount")
    return fee, gross - fee


async def active_rule(session: AsyncSession, business_id: uuid.UUID) -> PlatformFeeRule:
    now = datetime.now(timezone.utc)
    rule = (
        (
            await session.execute(
                select(PlatformFeeRule)
                .where(
                    PlatformFeeRule.business_id == business_id,
                    PlatformFeeRule.effective_from <= now,
                    or_(PlatformFeeRule.effective_to.is_(None), PlatformFeeRule.effective_to > now),
                )
                .order_by(PlatformFeeRule.effective_from.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if rule is None:
        raise ValidationError("Online payments require an active commission rule")
    return rule
