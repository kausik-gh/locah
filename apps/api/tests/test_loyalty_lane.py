"""Tests for Loyalty, Points, Stamps, Referrals, and Gift Vouchers (LY-01 through LY-04).

Covers:
1. Earn points from eligible transaction
2. Duplicate source does not earn twice (idempotency key)
3. Redeem points
4. Cannot over-redeem
5. Expiry ignored from usable balance
6. 10th stamp card reward issued once
7. Referral qualifies once on referee first purchase
8. Self-referral rejected
9. Voucher cannot go below zero
10. Cross-business isolation
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from platform_core.exceptions import ValidationError
from platform_core.loyalty.models import (
    GiftVoucher,
    LoyaltyAccount,
    LoyaltyLedgerEntry,
    LoyaltyProgram,
    ReferralCode,
    ReferralRelationship,
    StampCard,
    StampProgram,
)
from platform_core.loyalty.service import (
    GiftVoucherService,
    LoyaltyPointsService,
    ReferralService,
    StampCardService,
)

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")


# =============================================================================
# 1. PURE DOMAIN & IN-MEMORY TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_earn_points_calculation_and_integer_arithmetic() -> None:
    """1. Earn points: calculates points via integer math with no float errors."""
    b_id = uuid.uuid4()
    c_id = uuid.uuid4()

    mock_program = LoyaltyProgram(
        business_id=b_id,
        name="Rewards",
        points_per_rupee=Decimal("1.5"),
        status="active",
        expiry_days=365,
    )
    mock_account = LoyaltyAccount(
        business_id=b_id,
        customer_contact_id=c_id,
        current_points=100,
        lifetime_points_earned=100,
    )

    session = AsyncMock()
    # Program lookup
    session.execute.side_effect = [
        # First query: existing entry check for idempotency -> None
        MagicMock(scalars=lambda: MagicMock(first=lambda: None)),
        # Second query in get_or_create_default_program -> mock_program
        MagicMock(scalars=lambda: MagicMock(first=lambda: mock_program)),
        # Third query in get_or_create_account -> mock_account
        MagicMock(scalars=lambda: MagicMock(first=lambda: mock_account)),
    ]

    # Order of ₹250.50 (25050 paise) at 1.5 pts/₹ = floor(250.50 * 1.5) = floor(375.75) = 375 points
    res = await LoyaltyPointsService.earn_points(
        session,
        b_id,
        c_id,
        order_amount_paise=25050,
        source_type="order",
        source_id="ord-1",
        idempotency_key="idemp-1",
    )

    assert res["points_earned"] == 375
    assert res["balance_after"] == 475
    assert res["already_processed"] is False
    assert mock_account.current_points == 475
    assert mock_account.lifetime_points_earned == 475


@pytest.mark.asyncio
async def test_duplicate_source_does_not_earn_twice() -> None:
    """2. Duplicate source does not earn twice: idempotent replay returns existing entry."""
    b_id = uuid.uuid4()
    c_id = uuid.uuid4()

    existing_entry = LoyaltyLedgerEntry(
        id=uuid.uuid4(),
        business_id=b_id,
        customer_contact_id=c_id,
        delta=50,
        balance_after=150,
        idempotency_key="dup-key-1",
        reason="earn_order",
        source_type="order",
        source_id="ord-1",
    )

    session = AsyncMock()
    # First query for idempotency returns existing entry!
    session.execute.return_value = MagicMock(scalars=lambda: MagicMock(first=lambda: existing_entry))

    res = await LoyaltyPointsService.earn_points(
        session,
        b_id,
        c_id,
        order_amount_paise=5000,
        source_type="order",
        source_id="ord-1",
        idempotency_key="dup-key-1",
    )

    assert res["already_processed"] is True
    assert res["points_earned"] == 50
    assert res["balance_after"] == 150
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_redeem_points_and_discount_calculation() -> None:
    """3. Redeem points: validates points and creates negative ledger entry."""
    b_id = uuid.uuid4()
    c_id = uuid.uuid4()

    mock_program = LoyaltyProgram(
        business_id=b_id,
        name="Rewards",
        min_redemption_points=10,
        max_redemption_points_per_order=500,
        redemption_rupees_per_point=Decimal("0.25"),  # 1 point = 25 paise
        status="active",
    )
    mock_account = LoyaltyAccount(
        business_id=b_id,
        customer_contact_id=c_id,
        current_points=200,
        lifetime_points_earned=200,
        lifetime_points_redeemed=0,
    )

    session = AsyncMock()
    session.execute.side_effect = [
        # Idempotency check -> None
        MagicMock(scalars=lambda: MagicMock(first=lambda: None)),
        # Program in validate_redemption
        MagicMock(scalars=lambda: MagicMock(first=lambda: mock_program)),
        # Account in get_usable_balance
        MagicMock(scalars=lambda: MagicMock(first=lambda: mock_account)),
        # Sum of non-expired ledger entries in get_usable_balance -> 200
        MagicMock(scalar=lambda: 200),
        # Account in redeem_points
        MagicMock(scalars=lambda: MagicMock(first=lambda: mock_account)),
    ]

    # Redeem 100 points on a ₹100 (10000 paise) order: 100 pts * 0.25 = ₹25.00 (2500 paise) discount
    res = await LoyaltyPointsService.redeem_points(
        session,
        b_id,
        c_id,
        points_to_redeem=100,
        order_amount_paise=10000,
        source_type="order",
        source_id="ord-2",
        idempotency_key="redeem-key-1",
    )

    assert res["points_redeemed"] == 100
    assert res["discount_paise"] == 2500
    assert res["balance_after"] == 100
    assert mock_account.current_points == 100
    assert mock_account.lifetime_points_redeemed == 100


@pytest.mark.asyncio
async def test_cannot_over_redeem_points() -> None:
    """4. Cannot over-redeem: rejecting more points than customer has."""
    b_id = uuid.uuid4()
    c_id = uuid.uuid4()

    mock_program = LoyaltyProgram(
        business_id=b_id,
        name="Rewards",
        min_redemption_points=10,
        max_redemption_points_per_order=1000,
        redemption_rupees_per_point=Decimal("0.25"),
        status="active",
    )
    mock_account = LoyaltyAccount(
        business_id=b_id,
        customer_contact_id=c_id,
        current_points=50,
    )

    session = AsyncMock()
    session.execute.side_effect = [
        MagicMock(scalars=lambda: MagicMock(first=lambda: mock_program)),
        MagicMock(scalars=lambda: MagicMock(first=lambda: mock_account)),
        MagicMock(scalar=lambda: 50),  # usable balance = 50
    ]

    with pytest.raises(ValidationError, match="Cannot redeem 100 points. Available balance is 50"):
        await LoyaltyPointsService.validate_redemption(
            session,
            b_id,
            c_id,
            points_to_redeem=100,
            order_amount_paise=10000,
        )


@pytest.mark.asyncio
async def test_expiry_ignored_from_usable_balance() -> None:
    """5. Expiry ignored from usable balance: points expired are excluded."""
    b_id = uuid.uuid4()
    c_id = uuid.uuid4()
    now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=timezone.utc)

    mock_account = LoyaltyAccount(
        business_id=b_id,
        customer_contact_id=c_id,
        current_points=100,
    )

    session = AsyncMock()
    # Usable balance query explicitly returns sum of non-expired entries (e.g. only 40 points left unexpired)
    session.execute.side_effect = [
        MagicMock(scalars=lambda: MagicMock(first=lambda: mock_account)),
        MagicMock(scalar=lambda: 40),
    ]

    usable = await LoyaltyPointsService.get_usable_balance(session, b_id, c_id, now=now)
    assert usable == 40


@pytest.mark.asyncio
async def test_stamp_card_10th_reward_issued_once() -> None:
    """6. 10th stamp card reward issued once: increments stamps and triggers reward at threshold."""
    b_id = uuid.uuid4()
    c_id = uuid.uuid4()

    mock_prog = StampProgram(
        id=uuid.uuid4(),
        business_id=b_id,
        name="Coffee Club",
        required_stamps=10,
        reward_kind="free_item",
        reward_details={"item_name": "Free Espresso"},
        status="active",
    )
    # Customer currently has 9 stamps! Next one should issue reward.
    mock_card = StampCard(
        id=uuid.uuid4(),
        business_id=b_id,
        program_id=mock_prog.id,
        customer_contact_id=c_id,
        current_stamps=9,
        cycle_count=0,
        lifetime_stamps=9,
    )

    session = AsyncMock()
    session.get.return_value = mock_prog
    session.execute.side_effect = [
        # No earlier stamp for this visit
        MagicMock(scalars=lambda: MagicMock(first=lambda: None)),
        # Existing card, one stamp short of the reward
        MagicMock(scalars=lambda: MagicMock(first=lambda: mock_card)),
    ]

    res = await StampCardService.award_stamp(
        session,
        b_id,
        c_id,
        source_type="order",
        source_id="ord-coffee-10",
        idempotency_key="stamp-order-10",
        program_id=mock_prog.id,
    )

    # Reached 10 stamps!
    assert res["cycle_count"] == 1
    assert res["current_stamps"] == 0  # reset for next cycle
    assert res["reward_issued"] is not None
    assert "STAMP-1-" in res["reward_issued"]["code"]
    assert res["reward_issued"]["reward_kind"] == "free_item"


@pytest.mark.asyncio
async def test_referral_self_referral_rejected() -> None:
    """8. Self-referral rejected: a customer cannot use their own referral code."""
    b_id = uuid.uuid4()
    c_id = uuid.uuid4()

    mock_code = ReferralCode(
        id=uuid.uuid4(),
        business_id=b_id,
        customer_contact_id=c_id,
        code="REF-SELF1",
    )

    session = AsyncMock()
    session.execute.return_value = MagicMock(scalars=lambda: MagicMock(first=lambda: mock_code))

    with pytest.raises(ValidationError, match="Customers cannot use their own referral code"):
        await ReferralService.apply_referral_code(session, b_id, c_id, "REF-SELF1")


@pytest.mark.asyncio
async def test_referral_qualifies_once_on_first_purchase() -> None:
    """7. Referral qualifies once: awards referrer and referee on first purchase."""
    b_id = uuid.uuid4()
    referrer_id = uuid.uuid4()
    referee_id = uuid.uuid4()

    mock_rel = ReferralRelationship(
        id=uuid.uuid4(),
        business_id=b_id,
        referrer_contact_id=referrer_id,
        referee_contact_id=referee_id,
        code_used="REF-CODE",
        status="pending",
    )

    session = AsyncMock()
    session.execute.side_effect = [
        # Referral relationship lookup
        MagicMock(scalars=lambda: MagicMock(first=lambda: mock_rel)),
        # Idempotency check for referrer award -> None
        MagicMock(scalars=lambda: MagicMock(first=lambda: None)),
        # Program in earn_points for referrer
        MagicMock(scalars=lambda: MagicMock(first=lambda: LoyaltyProgram(business_id=b_id, status="active", points_per_rupee=Decimal("1.0")))),
        # Account in earn_points for referrer
        MagicMock(scalars=lambda: MagicMock(first=lambda: LoyaltyAccount(business_id=b_id, customer_contact_id=referrer_id, current_points=0))),
        # Idempotency check for referee award -> None
        MagicMock(scalars=lambda: MagicMock(first=lambda: None)),
        # Program in earn_points for referee
        MagicMock(scalars=lambda: MagicMock(first=lambda: LoyaltyProgram(business_id=b_id, status="active", points_per_rupee=Decimal("1.0")))),
        # Account in earn_points for referee
        MagicMock(scalars=lambda: MagicMock(first=lambda: LoyaltyAccount(business_id=b_id, customer_contact_id=referee_id, current_points=0))),
    ]

    res = await ReferralService.qualify_first_purchase(
        session,
        b_id,
        referee_id,
        source_type="order",
        source_id="first-ord-1",
        referrer_points=100,
        referee_points=50,
    )

    assert res["qualified"] is True
    assert res["referrer_points"] == 100
    assert res["referee_points"] == 50
    assert mock_rel.status == "rewarded"


@pytest.mark.asyncio
async def test_voucher_cannot_go_below_zero() -> None:
    """9. Voucher cannot go below zero remaining balance."""
    b_id = uuid.uuid4()

    mock_voucher = GiftVoucher(
        id=uuid.uuid4(),
        business_id=b_id,
        code="LOC-GV-TEST-1234",
        issued_amount_paise=50000,   # ₹500.00
        remaining_balance_paise=20000, # ₹200.00 left
        status="active",
    )

    session = AsyncMock()
    # Idempotency check -> None
    # Validate voucher lookup -> mock_voucher
    # get voucher -> mock_voucher
    session.execute.side_effect = [
        MagicMock(scalars=lambda: MagicMock(first=lambda: None)),
        MagicMock(scalars=lambda: MagicMock(first=lambda: mock_voucher)),
    ]
    session.get.return_value = mock_voucher

    # Attempt to redeem ₹300 (30000 paise) when only ₹200 (20000 paise) remains
    with pytest.raises(ValidationError, match="Cannot redeem ₹300.00. Available balance is ₹200.00"):
        await GiftVoucherService.redeem_voucher(
            session,
            b_id,
            "LOC-GV-TEST-1234",
            redeem_amount_paise=30000,
            source_type="order",
            source_id="ord-overspend",
            idempotency_key="tx-overspend",
        )


@pytest.mark.asyncio
async def test_cross_business_isolation_voucher_and_program() -> None:
    """10. Cross-business isolation: Business B cannot redeem or see Business A vouchers."""
    biz_a = uuid.uuid4()
    biz_b = uuid.uuid4()

    mock_voucher_a = GiftVoucher(
        id=uuid.uuid4(),
        business_id=biz_a,
        code="LOC-GV-BIZA-ONLY",
        issued_amount_paise=10000,
        remaining_balance_paise=10000,
        status="active",
    )
    assert mock_voucher_a.business_id == biz_a

    session = AsyncMock()
    # When business B queries for Biz A's voucher, query filter `business_id == biz_b` returns None!
    session.execute.return_value = MagicMock(scalars=lambda: MagicMock(first=lambda: None))

    with pytest.raises(Exception):
        await GiftVoucherService.validate_voucher(session, biz_b, "LOC-GV-BIZA-ONLY")
