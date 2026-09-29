"""Loyalty and marketing against local Postgres.

These tests fail if TEST_DATABASE_URL is missing. They are not skipped.
The session is the database owner, so they prove the services. Row Level
Security is proved separately in test_growth_rls.py.
"""

from __future__ import annotations

from typing import cast

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from platform_core.db import get_database_url
from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.loyalty.service import (
    GiftVoucherService,
    LoyaltyPointsService,
    LoyaltyProgramService,
    ReferralService,
    StampCardService,
)
from platform_core.marketing.attribution import AttributionService
from platform_core.marketing.broadcast import WhatsAppBroadcastOrchestrator
from platform_core.marketing.campaigns import CampaignService
from platform_core.marketing.frequency import FrequencyControlService
from platform_core.marketing.meta_ads import MetaAdsContractService
from platform_core.marketing.results import MarketingResultsService
from platform_core.models import CustomerContact, CustomerSegment
from platform_core.services.consent import ConsentService


def _url() -> str:
    url = get_database_url() or ""
    if not url:
        pytest.fail("Growth database tests require TEST_DATABASE_URL on local Postgres")
    return url.replace("postgresql://", "postgresql+asyncpg://", 1) if url.startswith("postgresql://") else url


async def _business(session: AsyncSession) -> uuid.UUID:
    business_id = uuid.uuid4()
    owner = uuid.uuid4()
    await session.execute(
        text("insert into auth.users (id, email) values (:id, :email)"),
        {"id": owner, "email": f"{owner.hex[:12]}@example.com"},
    )
    await session.execute(
        text(
            "insert into businesses (id, slug, display_name, state, primary_owner_identity_id, business_type) "
            "values (:id, :slug, :name, 'draft', :owner, 'other')"
        ),
        {
            "id": business_id,
            "slug": f"growth-{business_id.hex[:10]}",
            "name": "Growth test",
            "owner": owner,
        },
    )
    return business_id


async def _contact(session: AsyncSession, business_id: uuid.UUID, name: str, phone: str, tag: str | None = None) -> uuid.UUID:
    contact = CustomerContact(
        business_id=business_id,
        display_name=name,
        phone=phone,
        tags=[tag] if tag else [],
    )
    session.add(contact)
    await session.flush()
    return cast(uuid.UUID, contact.id)


@pytest.mark.asyncio
async def test_points_earn_once_redeem_and_expiry() -> None:
    engine = create_async_engine(_url(), poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            business_id = await _business(session)
            contact_id = await _contact(session, business_id, "Asha", "+919810000001")
            await LoyaltyProgramService.update_program(
                session, business_id, points_per_rupee=1, expiry_days=30, min_redemption_points=10
            )

            first = await LoyaltyPointsService.earn_points(
                session, business_id, contact_id,
                order_amount_paise=2000, source_type="order", source_id="sale-1", idempotency_key="earn-sale-1",
            )
            again = await LoyaltyPointsService.earn_points(
                session, business_id, contact_id,
                order_amount_paise=2000, source_type="order", source_id="sale-1", idempotency_key="earn-sale-1",
            )
            assert first["points_earned"] == 20
            assert again["already_processed"] is True
            assert await LoyaltyPointsService.get_usable_balance(session, business_id, contact_id) == 20

            redeemed = await LoyaltyPointsService.redeem_points(
                session, business_id, contact_id,
                points_to_redeem=10, order_amount_paise=5000,
                source_type="order", source_id="sale-2", idempotency_key="redeem-sale-2",
            )
            assert redeemed["points_redeemed"] == 10
            assert await LoyaltyPointsService.get_usable_balance(session, business_id, contact_id) == 10

            later = datetime.now(timezone.utc) + timedelta(days=31)
            assert await LoyaltyPointsService.get_usable_balance(session, business_id, contact_id, now=later) == 0
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_stamp_reward_and_referral_happen_once() -> None:
    engine = create_async_engine(_url(), poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            business_id = await _business(session)
            contact_id = await _contact(session, business_id, "Ravi", "+919810000002")
            card = await StampCardService.create_program(
                session, business_id, name="Coffee card", required_stamps=3, reward_kind="free_item",
                reward_details={"item_name": "Free coffee"},
            )
            rewards = 0
            for n in range(3):
                result = await StampCardService.award_stamp(
                    session, business_id, contact_id,
                    source_type="pos", source_id=f"visit-{n}", idempotency_key=f"visit-{n}",
                    program_id=card.id,
                )
                if result["reward_issued"]:
                    rewards += 1
            replay = await StampCardService.award_stamp(
                session, business_id, contact_id,
                source_type="pos", source_id="visit-2", idempotency_key="visit-2", program_id=card.id,
            )
            assert rewards == 1
            assert replay["already_processed"] is True

            referrer = await _contact(session, business_id, "Meena", "+919810000003")
            referee = await _contact(session, business_id, "Arun", "+919810000004")
            code = await ReferralService.get_or_create_referral_code(session, business_id, referrer)
            await ReferralService.apply_referral_code(session, business_id, referee, code)
            first = await ReferralService.qualify_first_purchase(
                session, business_id, referee, source_type="order", source_id="first-sale",
            )
            second = await ReferralService.qualify_first_purchase(
                session, business_id, referee, source_type="order", source_id="first-sale",
            )
            assert first["qualified"] is True
            assert second["qualified"] is False
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_voucher_and_campaign_stay_inside_one_business() -> None:
    engine = create_async_engine(_url(), poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            business_a = await _business(session)
            business_b = await _business(session)
            voucher = await GiftVoucherService.issue_voucher(session, business_a, issued_amount_paise=50000)
            with pytest.raises(ResourceNotFound):
                await GiftVoucherService.validate_voucher(session, business_b, voucher.code)
            own = await GiftVoucherService.validate_voucher(session, business_a, voucher.code)
            assert own["remaining_balance_paise"] == 50000

            campaign = await CampaignService.create_campaign(
                session, business_a, name="Weekday", goal="Fill quiet hours", budget_paise=10000,
            )
            with pytest.raises(ResourceNotFound):
                await CampaignService.get_campaign(session, business_b, campaign.id)
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_broadcast_consent_frequency_approval_and_attribution() -> None:
    engine = create_async_engine(_url(), poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            business_id = await _business(session)
            opted_in = await _contact(session, business_id, "Opted in", "+919810000011", "regular")
            # This contact stays in the segment and never receives marketing consent.
            await _contact(session, business_id, "No consent", "+919810000012", "regular")
            cooled = await _contact(session, business_id, "Recent message", "+919810000013", "regular")
            for contact_id in (opted_in, cooled):
                await ConsentService.grant(
                    session, business_id, contact_id,
                    purpose="marketing", channel="whatsapp", source="told_us",
                )
            await FrequencyControlService.record_promotional_send(
                session, business_id, cooled, channel="whatsapp",
            )
            segment = CustomerSegment(
                business_id=business_id, name="Regulars", rules=[{"kind": "tag", "tag": "regular"}],
            )
            session.add(segment)
            await session.flush()

            campaign = await CampaignService.create_campaign(
                session, business_id, name="Tuesday offer", goal="Bring regulars back",
                audience_segment_id=segment.id, budget_paise=100000,
            )
            with pytest.raises(ConflictError):
                await WhatsAppBroadcastOrchestrator.dispatch_campaign(session, business_id, campaign.id)

            prepared = await CampaignService.prepare_for_approval(session, business_id, campaign.id)
            assert prepared["audience_snapshot"]["consented_count"] == 2
            assert prepared["audience_snapshot"]["total_count"] == 3

            # approved_by references platform_identities. The business insert
            # creates that row through the auth user trigger.
            owner_id = (
                await session.execute(
                    text("select primary_owner_identity_id from businesses where id = :id"),
                    {"id": business_id},
                )
            ).scalar_one()
            await CampaignService.owner_approve_campaign(
                session, business_id, campaign.id, approver_identity_id=owner_id,
            )
            sent = await WhatsAppBroadcastOrchestrator.dispatch_campaign(session, business_id, campaign.id)
            assert sent["sent_count"] == 1
            assert sent["excluded_no_consent"] == 1
            assert sent["excluded_frequency"] == 1

            touch = await AttributionService.record_touchpoint(
                session, business_id, touchpoint_kind="campaign", campaign_id=campaign.id,
                customer_contact_id=opted_in,
            )
            conversion = await AttributionService.attribute_conversion(
                session, business_id, conversion_kind="order", conversion_id="ord-1",
                revenue_paise=25000, touchpoint_id=touch.id,
            )
            assert conversion is not None
            assert conversion.attribution_model == "approximate_last_touch"
            results = await MarketingResultsService.get_campaign_results(session, business_id, campaign.id)
            assert results["attribution_label"] == "Approximate · last touch"
            assert results["attributed_orders"] == 1

            await MetaAdsContractService.configure_spend_cap(
                session, business_id, monthly_spend_cap_paise=100000,
            )
            with pytest.raises(ValidationError):
                await MetaAdsContractService.prepare_campaign_spend_request(
                    session, business_id, requested_spend_paise=150000,
                )
            allowed = await MetaAdsContractService.prepare_campaign_spend_request(
                session, business_id, requested_spend_paise=40000,
            )
            assert allowed["provider_status"] == "ACTIVATION_REQUIRED"
            await session.rollback()
    finally:
        await engine.dispose()
