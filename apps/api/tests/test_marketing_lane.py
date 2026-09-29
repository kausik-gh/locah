"""Tests for Marketing Campaigns, Audiences, Offers, Broadcast, Consent, Frequency, Policy, Attribution (MK-01 through MK-10).

Covers:
11. Audience resolves existing segment count
12. No consent -> excluded from broadcast
13. Opted-out -> excluded from broadcast
14. Owner approval required before live campaign action
15. Approved campaign mutation requires re-approval (invalidates approved status)
16. Frequency cap excludes repeat recipient (cooldown + weekly cap)
17. Same campaign/contact dispatch idempotent
18. Regulated marketing policy blocks/restricts as required (minors prohibited, lawyers off by default, finance restricted)
19. Over-budget / over-cap blocked before provider adapter (Meta spend cap)
20. Attribution is explicitly marked "approximate_last_touch"
21. Cross-business isolation
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from platform_core.exceptions import ConflictError, ValidationError
from platform_core.marketing.attribution import AttributionService
from platform_core.marketing.broadcast import WhatsAppBroadcastOrchestrator
from platform_core.marketing.campaigns import CampaignService
from platform_core.marketing.frequency import FrequencyControlService
from platform_core.marketing.meta_ads import MetaAdsContractService
from platform_core.marketing.models import (
    MarketingBroadcastRecipient,
    MarketingCampaign,
    MarketingMetaConfiguration,
    MarketingTouchpoint,
)
from platform_core.marketing.offers import OfferService
from platform_core.marketing.regulated import RegulatedCategoryPolicyService
from platform_core.marketing.results import MarketingResultsService
from platform_core.models import CustomerSegment


# =============================================================================
# MARKETING TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_audience_resolves_existing_segment_count() -> None:
    """11. Audience resolves existing segment count without rebuilding segmentation."""
    from platform_core.marketing.audiences import MarketingAudienceService

    b_id = uuid.uuid4()
    s_id = uuid.uuid4()

    mock_segment = CustomerSegment(
        id=s_id,
        business_id=b_id,
        name="VIP Customers",
        rules=[{"kind": "bought", "times": 3, "days": 30}],
    )

    session = AsyncMock()
    session.execute.return_value = MagicMock(scalars=lambda: MagicMock(first=lambda: mock_segment))

    with patch("platform_core.marketing.audiences.evaluate", new_callable=AsyncMock) as mock_eval:
        mock_eval.return_value = {
            "count": 45,
            "whatsapp_offers": 32,
            "members": [],
        }

        aud = await MarketingAudienceService.resolve_segment_audience(
            session, b_id, s_id, channel="whatsapp"
        )

        assert aud["segment_id"] == str(s_id)
        assert aud["total_count"] == 45
        assert aud["consented_count"] == 32
        assert aud["excluded_no_consent_count"] == 13


@pytest.mark.asyncio
async def test_no_consent_and_opted_out_excluded_from_broadcast() -> None:
    """12 & 13. No consent and opted-out contacts are excluded from promotional broadcast."""
    b_id = uuid.uuid4()
    c_id = uuid.uuid4()
    contact_consented = uuid.uuid4()
    contact_no_consent = uuid.uuid4()
    contact_opted_out = uuid.uuid4()

    mock_campaign = MarketingCampaign(
        id=c_id,
        business_id=b_id,
        name="Festive Promo",
        goal="repeat_orders",
        channel="whatsapp",
        audience_segment_id=uuid.uuid4(),
        status="APPROVED",  # Owner already approved
        budget_paise=100000,
    )
    mock_segment = CustomerSegment(
        id=mock_campaign.audience_segment_id,
        business_id=b_id,
        name="All Customers",
        rules=[{"kind": "tag", "tag": "customer"}],
    )

    session = AsyncMock()
    session.get.side_effect = lambda model, ident: mock_segment if model == CustomerSegment else mock_campaign
    session.execute.side_effect = [
        # 1. Campaign lookup in CampaignService.get_campaign
        MagicMock(scalars=lambda: MagicMock(first=lambda: mock_campaign)),
        # 2, 3, 4: recipient idempotency checks for the 3 members (None = not yet dispatched)
        MagicMock(scalars=lambda: MagicMock(first=lambda: None)),
        MagicMock(scalars=lambda: MagicMock(first=lambda: None)),
        MagicMock(scalars=lambda: MagicMock(first=lambda: None)),
    ]

    # Mock evaluate returning 3 contacts
    members = [
        {"id": str(contact_consented), "display_name": "Alice", "phone": "+919876543210"},
        {"id": str(contact_no_consent), "display_name": "Bob", "phone": "+919876543211"},
        {"id": str(contact_opted_out), "display_name": "Charlie", "phone": "+919876543212"},
    ]

    with patch("platform_core.marketing.broadcast.evaluate", new_callable=AsyncMock) as mock_eval, \
         patch("platform_core.marketing.broadcast.ConsentService.has", new_callable=AsyncMock) as mock_consent, \
         patch("platform_core.marketing.broadcast.FrequencyControlService.can_send_promotional_message", new_callable=AsyncMock) as mock_freq, \
         patch("platform_core.marketing.broadcast.FrequencyControlService.record_promotional_send", new_callable=AsyncMock):

        mock_eval.return_value = {"count": 3, "whatsapp_offers": 1, "members": members}

        # Consent responses: Alice=True, Bob=False (never consented), Charlie=False (opted-out)
        async def consent_check(sess, biz, contact, purpose, channel):
            return contact == contact_consented

        mock_consent.side_effect = consent_check
        mock_freq.return_value = (True, "Eligible")

        res = await WhatsAppBroadcastOrchestrator.dispatch_campaign(session, b_id, c_id)

        assert res["total_targeted"] == 3
        assert res["sent_count"] == 1
        assert res["excluded_no_consent"] == 2  # Bob and Charlie excluded
        assert res["actual_cost_paise"] == 80  # 1 message at ₹0.80
        assert mock_campaign.status == "COMPLETED"


@pytest.mark.asyncio
async def test_owner_approval_required_before_dispatch() -> None:
    """14. Owner approval is mandatory before live campaign action; draft campaign cannot dispatch."""
    b_id = uuid.uuid4()
    c_id = uuid.uuid4()

    mock_campaign = MarketingCampaign(
        id=c_id,
        business_id=b_id,
        name="Unapproved Promo",
        goal="win_back",
        channel="whatsapp",
        status="DRAFT",  # Not approved!
    )

    session = AsyncMock()
    session.execute.return_value = MagicMock(scalars=lambda: MagicMock(first=lambda: mock_campaign))

    with pytest.raises(ConflictError, match="Owner approval is mandatory"):
        await WhatsAppBroadcastOrchestrator.dispatch_campaign(session, b_id, c_id)


@pytest.mark.asyncio
async def test_approved_campaign_mutation_requires_reapproval() -> None:
    """15. Mutating significant fields on an approved campaign invalidates approval."""
    b_id = uuid.uuid4()
    c_id = uuid.uuid4()
    approver = uuid.uuid4()

    mock_campaign = MarketingCampaign(
        id=c_id,
        business_id=b_id,
        name="Diwali 2026",
        goal="festive_sale",
        channel="whatsapp",
        status="APPROVED",
        approved_by=approver,
        approved_at=datetime.now(timezone.utc),
        approval_record={"approved_by": str(approver)},
        budget_paise=50000,
        version=1,
    )

    session = AsyncMock()
    session.execute.return_value = MagicMock(scalars=lambda: MagicMock(first=lambda: mock_campaign))

    # Marketer modifies budget from ₹500 to ₹5000
    updated = await CampaignService.update_campaign(
        session,
        b_id,
        c_id,
        budget_paise=500000,
    )

    # Status must drop back to DRAFT and approval cleared!
    assert updated.status == "DRAFT"
    assert updated.approved_by is None
    assert updated.approved_at is None
    assert updated.approval_record is None
    assert updated.budget_paise == 500000


@pytest.mark.asyncio
async def test_frequency_cap_excludes_repeat_recipient() -> None:
    """16. Frequency controls: customer in 48h cooldown is excluded."""
    b_id = uuid.uuid4()
    c_id = uuid.uuid4()
    now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=timezone.utc)

    # Last promotional message sent 12 hours ago (within 48h cooldown)
    sent_12h_ago = now - timedelta(hours=12)

    session = AsyncMock()
    session.execute.return_value = MagicMock(scalar=lambda: sent_12h_ago)

    can_send, reason = await FrequencyControlService.can_send_promotional_message(
        session, b_id, c_id, channel="whatsapp", now=now
    )

    assert can_send is False
    assert "48h cooldown" in reason


@pytest.mark.asyncio
async def test_same_campaign_contact_dispatch_idempotent() -> None:
    """17. Same campaign + contact dispatch is idempotent; replay does not re-send."""
    b_id = uuid.uuid4()
    camp_id = uuid.uuid4()
    contact_id = uuid.uuid4()

    mock_campaign = MarketingCampaign(
        id=camp_id,
        business_id=b_id,
        name="Test Camp",
        channel="whatsapp",
        status="APPROVED",
        audience_segment_id=uuid.uuid4(),
    )
    mock_segment = CustomerSegment(id=mock_campaign.audience_segment_id, rules=[])
    existing_recipient = MarketingBroadcastRecipient(
        id=uuid.uuid4(),
        business_id=b_id,
        campaign_id=camp_id,
        contact_id=contact_id,
        phone="+919876543210",
        status="delivered",
        cost_paise=80,
        idempotency_key=f"{b_id}:{camp_id}:{contact_id}",
    )

    session = AsyncMock()
    session.get.side_effect = lambda m, ident: mock_segment if m == CustomerSegment else mock_campaign
    # 1st call: CampaignService.get_campaign -> mock_campaign
    # 2nd call: Idempotency check returns existing dispatched recipient
    session.execute.side_effect = [
        MagicMock(scalars=lambda: MagicMock(first=lambda: mock_campaign)),
        MagicMock(scalars=lambda: MagicMock(first=lambda: existing_recipient)),
    ]

    with patch("platform_core.marketing.broadcast.evaluate", new_callable=AsyncMock) as mock_eval:
        mock_eval.return_value = {
            "members": [{"id": str(contact_id), "display_name": "Alice", "phone": "+919876543210"}]
        }

        res = await WhatsAppBroadcastOrchestrator.dispatch_campaign(session, b_id, camp_id)

        assert res["already_processed_count"] == 1
        assert res["sent_count"] == 1
        # No new recipient record was inserted
        session.add.assert_not_called()


def test_regulated_marketing_policy_guards() -> None:
    """18. Regulated marketing policy blocks/restricts according to source rules."""
    # A. Minors: Strictly prohibited under DPDP Act 2023 §9
    policy_minors = RegulatedCategoryPolicyService.evaluate(
        target_tags=["minors", "students"],
    )
    assert policy_minors.allowed is False
    assert policy_minors.status == "prohibited"
    assert "DPDP Act 2023 §9" in policy_minors.reason

    # B. Legal profession: Marketing off by default under Bar Council rules
    policy_legal = RegulatedCategoryPolicyService.evaluate(
        category_key="legal_services",
        subcategory_key="advocate",
        owner_override=False,
    )
    assert policy_legal.allowed is False
    assert policy_legal.status == "requires_owner_override"
    assert "Bar Council of India" in policy_legal.reason

    # Legal with owner override permitted
    policy_legal_override = RegulatedCategoryPolicyService.evaluate(
        category_key="legal_services",
        owner_override=True,
    )
    assert policy_legal_override.allowed is True

    # C. Finance: Restricted category requiring disclosures
    policy_finance = RegulatedCategoryPolicyService.evaluate(
        category_key="financial_services",
    )
    assert policy_finance.allowed is True
    assert policy_finance.status == "restricted"
    assert policy_finance.requires_declaration is True


@pytest.mark.asyncio
async def test_over_budget_blocked_before_meta_provider_call() -> None:
    """19. Meta monthly spend cap enforced in DB before any adapter call."""
    b_id = uuid.uuid4()

    mock_cfg = MarketingMetaConfiguration(
        business_id=b_id,
        monthly_spend_cap_paise=1000000,   # ₹10,000 monthly cap
        current_month_spend_paise=800000,  # ₹8,000 already spent (₹2,000 remaining)
        status="ACTIVATION_REQUIRED",
    )

    session = AsyncMock()
    session.get.return_value = mock_cfg

    # Attempt to request ₹3,000 spend (exceeds ₹2,000 remaining)
    with pytest.raises(ValidationError, match="requested spend of ₹3000.00 exceeds remaining monthly cap by ₹1000.00"):
        await MetaAdsContractService.prepare_campaign_spend_request(
            session, b_id, requested_spend_paise=300000
        )


@pytest.mark.asyncio
async def test_attribution_is_marked_approximate_last_touch() -> None:
    """20. Attribution is explicitly labelled 'approximate_last_touch'."""
    b_id = uuid.uuid4()
    tp_id = uuid.uuid4()

    mock_tp = MarketingTouchpoint(
        id=tp_id,
        business_id=b_id,
        touchpoint_kind="utm",
        utm_source="instagram",
        utm_campaign="summer_fest",
    )

    session = AsyncMock()
    session.execute.return_value = MagicMock(scalars=lambda: MagicMock(first=lambda: None))
    session.get.return_value = mock_tp

    conv = await AttributionService.attribute_conversion(
        session,
        b_id,
        conversion_kind="order",
        conversion_id="ord-999",
        revenue_paise=45000,
        touchpoint_id=tp_id,
    )

    assert conv is not None
    assert conv.attribution_model == "approximate_last_touch"
    assert conv.conversion_id == "ord-999"
    assert conv.revenue_paise == 45000


@pytest.mark.asyncio
async def test_cross_business_isolation_marketing_offers() -> None:
    """21. Cross-business isolation: Business B cannot evaluate or use Business A coupons."""
    biz_a = uuid.uuid4()
    biz_b = uuid.uuid4()
    assert biz_a != biz_b

    session = AsyncMock()
    # Query for coupon 'BIZA-CODE' within biz_b returns None
    session.execute.return_value = MagicMock(scalars=lambda: MagicMock(first=lambda: None))

    res = await OfferService.evaluate_offer(
        session,
        biz_b,
        "BIZA-CODE",
        cart_total_paise=10000,
    )

    assert res["eligible"] is False
    assert res["reason"] == "Coupon code not found"


@pytest.mark.asyncio
async def test_marketing_results_never_estimated() -> None:
    """Marketing results are computed strictly from real records and never estimated."""
    b_id = uuid.uuid4()
    c_id = uuid.uuid4()

    mock_campaign = MarketingCampaign(
        id=c_id,
        business_id=b_id,
        name="Real Records Test",
        channel="whatsapp",
        status="COMPLETED",
        actual_cost_paise=160,  # 2 messages sent
        offer_id=None,
    )

    session = AsyncMock()
    session.execute.side_effect = [
        # Campaign lookup
        MagicMock(scalars=lambda: MagicMock(first=lambda: mock_campaign)),
        # Recipient stats: total=2, sent=2, delivered=2, excluded_consent=0, excluded_frequency=0
        MagicMock(first=lambda: (2, 2, 2, 0, 0)),
        # Conversion stats: attributed_orders=1, attributed_revenue=50000 paise (₹500.00)
        MagicMock(first=lambda: (1, 50000)),
    ]

    res = await MarketingResultsService.get_campaign_results(session, b_id, c_id)

    assert res["campaign_id"] == str(c_id)
    assert res["recipients_targeted"] == 2
    assert res["recipients_sent"] == 2
    assert res["recipients_delivered"] == 2
    assert res["attributed_orders"] == 1
    assert res["attributed_revenue_paise"] == 50000
    assert res["actual_cost_paise"] == 160
    assert res["cost_per_order_paise"] == 160
    # ROAS = 50000 / 160 = 312.5
    assert res["roas"] == 312.5
    assert res["attribution_label"] == "Approximate · last touch"
    assert "zero estimated revenue" in res["data_source"]

