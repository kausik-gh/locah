"""Meta Ads & Conversions API neutral contract (MK-04, MK-05, MK-09; MD §18.2).

Enforces:
- Monthly spend cap is strictly verified and enforced BEFORE any provider adapter call.
- Conversions API: No raw personal data leaves unhashed (SHA-256 for phone/email); verified marketing consent.
- Provider integration remains ACTIVATION_REQUIRED; zero real Meta API calls.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ValidationError
from platform_core.marketing.models import MarketingMetaConfiguration
from platform_core.services.consent import ConsentService


class MetaAdsContractService:
    @staticmethod
    async def get_or_create_config(
        session: AsyncSession, business_id: uuid.UUID
    ) -> MarketingMetaConfiguration:
        cfg = await session.get(MarketingMetaConfiguration, business_id)
        if cfg is None:
            cfg = MarketingMetaConfiguration(
                business_id=business_id,
                monthly_spend_cap_paise=0,
                current_month_spend_paise=0,
                conversions_api_enabled=False,
                status="ACTIVATION_REQUIRED",
            )
            session.add(cfg)
            await session.flush()
        return cfg

    @staticmethod
    async def configure_spend_cap(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        monthly_spend_cap_paise: int,
        ad_account_id: str | None = None,
        pixel_id: str | None = None,
        conversions_api_enabled: bool = False,
    ) -> MarketingMetaConfiguration:
        if monthly_spend_cap_paise < 0:
            raise ValidationError("Monthly spend cap cannot be negative")

        cfg = await MetaAdsContractService.get_or_create_config(session, business_id)
        cfg.monthly_spend_cap_paise = monthly_spend_cap_paise
        if ad_account_id:
            cfg.ad_account_id = ad_account_id
        if pixel_id:
            cfg.pixel_id = pixel_id
        cfg.conversions_api_enabled = conversions_api_enabled
        cfg.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return cfg

    @staticmethod
    async def prepare_campaign_spend_request(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        requested_spend_paise: int,
    ) -> dict[str, Any]:
        """Validates spend against monthly cap BEFORE invoking provider. Over-cap requests are rejected."""
        cfg = await MetaAdsContractService.get_or_create_config(session, business_id)

        if cfg.monthly_spend_cap_paise <= 0:
            raise ValidationError(
                "A monthly spend cap must be set by the owner before running Meta ad campaigns."
            )

        projected_spend = cfg.current_month_spend_paise + requested_spend_paise
        if projected_spend > cfg.monthly_spend_cap_paise:
            overage_paise = projected_spend - cfg.monthly_spend_cap_paise
            raise ValidationError(
                f"Campaign blocked: requested spend of ₹{requested_spend_paise/100:.2f} exceeds remaining monthly cap by ₹{overage_paise/100:.2f}.",
                details={
                    "current_month_spend_paise": cfg.current_month_spend_paise,
                    "monthly_spend_cap_paise": cfg.monthly_spend_cap_paise,
                    "requested_spend_paise": requested_spend_paise,
                },
            )

        # Provider invocation contract
        return {
            "status": "APPROVED_LOCALLY",
            "provider_status": "ACTIVATION_REQUIRED",
            "business_id": str(business_id),
            "ad_account_id": cfg.ad_account_id,
            "approved_spend_paise": requested_spend_paise,
            "projected_monthly_spend_paise": projected_spend,
        }

    @staticmethod
    async def prepare_conversion_payload(
        session: AsyncSession,
        business_id: uuid.UUID,
        contact_id: uuid.UUID,
        *,
        event_name: str,
        event_time: datetime,
        revenue_paise: int,
        phone: str | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        """Prepares a Conversions API payload with hashed personal data and consent validation.

        MD §18.2: 'no raw personal data leaves unhashed'.
        """
        # Verify marketing consent
        has_consent = await ConsentService.has(
            session,
            business_id,
            contact_id,
            purpose="marketing",
            channel="any",
        )
        if not has_consent:
            raise ValidationError("Cannot send conversion event to Meta without customer marketing consent")

        user_data: dict[str, str] = {}
        if phone:
            norm_phone = "".join(filter(str.isdigit, phone))
            user_data["ph"] = hashlib.sha256(norm_phone.encode("utf-8")).hexdigest()
        if email:
            norm_email = email.strip().lower()
            user_data["em"] = hashlib.sha256(norm_email.encode("utf-8")).hexdigest()

        return {
            "event_name": event_name,
            "event_time": int(event_time.timestamp()),
            "user_data": user_data,
            "custom_data": {
                "currency": "INR",
                "value": float(Decimal(revenue_paise) / Decimal(100)),
            },
            "action_source": "system_server",
            "provider_status": "ACTIVATION_REQUIRED",
        }
