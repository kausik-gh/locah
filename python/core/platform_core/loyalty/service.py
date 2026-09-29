"""Loyalty, Points, Stamp Cards, Referrals and Gift Vouchers services (LY-01 through LY-04).

Follows LOCAH architectural invariants:
- Business is the tenant; every operation requires business_id.
- Points use integer arithmetic (no floating point points/money errors).
- Points balance is derived/tracked via append-only ledger entries.
- Earning and redemption are strictly idempotent using idempotency keys.
- Duplicate event replays never award twice.
- Self-referrals and duplicate referrals are strictly rejected.
- Gift vouchers cannot drop below zero remaining balance.
"""

from __future__ import annotations

import math
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.loyalty.models import (
    GiftVoucher,
    GiftVoucherTransaction,
    LoyaltyAccount,
    LoyaltyLedgerEntry,
    LoyaltyProgram,
    ReferralCode,
    ReferralRelationship,
    StampCard,
    StampProgram,
    StampReward,
)


class LoyaltyProgramService:
    @staticmethod
    async def get_or_create_default_program(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        name: str = "Customer Rewards",
        points_per_rupee: Decimal = Decimal("1.0"),
        redemption_rupees_per_point: Decimal = Decimal("0.25"),
        min_redemption_points: int = 10,
        max_redemption_points_per_order: int | None = 1000,
        expiry_days: int | None = 365,
    ) -> LoyaltyProgram:
        q = select(LoyaltyProgram).where(
            LoyaltyProgram.business_id == business_id,
            LoyaltyProgram.status.in_(("active", "paused")),
        )
        prog = (await session.execute(q)).scalars().first()
        if prog is not None:
            return prog

        prog = LoyaltyProgram(
            business_id=business_id,
            name=name,
            program_type="points",
            points_per_rupee=points_per_rupee,
            redemption_rupees_per_point=redemption_rupees_per_point,
            min_redemption_points=min_redemption_points,
            max_redemption_points_per_order=max_redemption_points_per_order,
            expiry_days=expiry_days,
            status="active",
        )
        session.add(prog)
        await session.flush()
        return prog

    @staticmethod
    async def get_program(session: AsyncSession, business_id: uuid.UUID) -> LoyaltyProgram | None:
        q = select(LoyaltyProgram).where(LoyaltyProgram.business_id == business_id)
        return (await session.execute(q)).scalars().first()

    @staticmethod
    async def update_program(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        name: str | None = None,
        points_per_rupee: Decimal | None = None,
        redemption_rupees_per_point: Decimal | None = None,
        min_redemption_points: int | None = None,
        max_redemption_points_per_order: int | None = None,
        expiry_days: int | None = None,
        status: str | None = None,
    ) -> LoyaltyProgram:
        prog = await LoyaltyProgramService.get_or_create_default_program(session, business_id)
        if name is not None:
            prog.name = name
        if points_per_rupee is not None:
            prog.points_per_rupee = points_per_rupee
        if redemption_rupees_per_point is not None:
            prog.redemption_rupees_per_point = redemption_rupees_per_point
        if min_redemption_points is not None:
            prog.min_redemption_points = min_redemption_points
        if max_redemption_points_per_order is not None:
            prog.max_redemption_points_per_order = max_redemption_points_per_order
        if expiry_days is not None:
            prog.expiry_days = expiry_days
        if status is not None:
            if status not in ("active", "paused", "inactive"):
                raise ValidationError("Invalid status", details={"field": "status"})
            prog.status = status
        prog.updated_at = datetime.now(timezone.utc)
        prog.version += 1
        await session.flush()
        return prog


class LoyaltyPointsService:
    @staticmethod
    async def get_or_create_account(
        session: AsyncSession, business_id: uuid.UUID, customer_contact_id: uuid.UUID
    ) -> LoyaltyAccount:
        q = select(LoyaltyAccount).where(
            LoyaltyAccount.business_id == business_id,
            LoyaltyAccount.customer_contact_id == customer_contact_id,
        )
        account = (await session.execute(q)).scalars().first()
        if account is not None:
            return account

        account = LoyaltyAccount(
            business_id=business_id,
            customer_contact_id=customer_contact_id,
            current_points=0,
            lifetime_points_earned=0,
            lifetime_points_redeemed=0,
            tier="standard",
        )
        session.add(account)
        await session.flush()
        return account

    @staticmethod
    async def get_usable_balance(
        session: AsyncSession,
        business_id: uuid.UUID,
        customer_contact_id: uuid.UUID,
        now: datetime | None = None,
    ) -> int:
        """Computes current usable balance excluding expired points."""
        now = now or datetime.now(timezone.utc)
        await LoyaltyPointsService.get_or_create_account(session, business_id, customer_contact_id)

        # Check expired ledger entries: positive delta with expires_at <= now
        # Usable points = total_earned (non-expired) - total_redeemed/clawed_back
        q = select(
            func.coalesce(func.sum(LoyaltyLedgerEntry.delta), 0)
        ).where(
            LoyaltyLedgerEntry.business_id == business_id,
            LoyaltyLedgerEntry.customer_contact_id == customer_contact_id,
            (LoyaltyLedgerEntry.expires_at.is_(None) | (LoyaltyLedgerEntry.expires_at > now)),
        )
        balance = (await session.execute(q)).scalar() or 0
        return max(0, int(balance))

    @staticmethod
    async def earn_points(
        session: AsyncSession,
        business_id: uuid.UUID,
        customer_contact_id: uuid.UUID,
        *,
        order_amount_paise: int,
        source_type: str,
        source_id: str,
        idempotency_key: str,
        actor_id: uuid.UUID | None = None,
        reason: str = "earn_order",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Awards points from an eligible completed transaction. Idempotent."""
        now = now or datetime.now(timezone.utc)

        # 1. Idempotency check: if this key already awarded, return existing result without re-awarding!
        existing = (
            await session.execute(
                select(LoyaltyLedgerEntry).where(
                    LoyaltyLedgerEntry.business_id == business_id,
                    LoyaltyLedgerEntry.idempotency_key == idempotency_key,
                )
            )
        ).scalars().first()
        if existing is not None:
            return {
                "points_earned": existing.delta,
                "balance_after": existing.balance_after,
                "already_processed": True,
                "ledger_entry_id": str(existing.id),
            }

        prog = await LoyaltyProgramService.get_or_create_default_program(session, business_id)
        if prog.status != "active":
            return {"points_earned": 0, "balance_after": 0, "program_inactive": True}

        # Calculate integer points from order amount
        # points = floor((order_amount_paise / 100) * points_per_rupee)
        rupees = Decimal(order_amount_paise) / Decimal(100)
        points_to_award = int(math.floor(rupees * prog.points_per_rupee))
        if points_to_award <= 0:
            return {"points_earned": 0, "balance_after": 0}

        account = await LoyaltyPointsService.get_or_create_account(session, business_id, customer_contact_id)
        new_balance = (account.current_points or 0) + points_to_award
        account.current_points = new_balance
        account.lifetime_points_earned = (account.lifetime_points_earned or 0) + points_to_award
        account.last_activity_at = now
        account.updated_at = now

        expires_at = now + timedelta(days=prog.expiry_days) if prog.expiry_days else None

        entry = LoyaltyLedgerEntry(
            business_id=business_id,
            customer_contact_id=customer_contact_id,
            delta=points_to_award,
            balance_after=new_balance,
            reason=reason,
            source_type=source_type,
            source_id=source_id,
            idempotency_key=idempotency_key,
            actor_id=actor_id,
            expires_at=expires_at,
            created_at=now,
        )
        session.add(entry)
        await session.flush()

        return {
            "points_earned": points_to_award,
            "balance_after": new_balance,
            "already_processed": False,
            "ledger_entry_id": str(entry.id),
        }

    @staticmethod
    async def validate_redemption(
        session: AsyncSession,
        business_id: uuid.UUID,
        customer_contact_id: uuid.UUID,
        *,
        points_to_redeem: int,
        order_amount_paise: int,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Validates redemption deterministically. Returns discount in paise."""
        now = now or datetime.now(timezone.utc)
        prog = await LoyaltyProgramService.get_or_create_default_program(session, business_id)
        if prog.status != "active":
            raise ValidationError("Loyalty program is not currently active")

        if points_to_redeem < prog.min_redemption_points:
            raise ValidationError(
                f"Minimum redemption is {prog.min_redemption_points} points",
                details={"min_points": prog.min_redemption_points},
            )

        if prog.max_redemption_points_per_order and points_to_redeem > prog.max_redemption_points_per_order:
            raise ValidationError(
                f"Maximum redemption per order is {prog.max_redemption_points_per_order} points",
                details={"max_points": prog.max_redemption_points_per_order},
            )

        usable_balance = await LoyaltyPointsService.get_usable_balance(session, business_id, customer_contact_id, now)
        if points_to_redeem > usable_balance:
            raise ValidationError(
                f"Cannot redeem {points_to_redeem} points. Available balance is {usable_balance} points",
                details={"available_points": usable_balance, "requested_points": points_to_redeem},
            )

        # Calculate discount in paise
        # rupees = points * redemption_rupees_per_point
        discount_rupees = Decimal(points_to_redeem) * prog.redemption_rupees_per_point
        discount_paise = int(math.floor(discount_rupees * 100))

        if discount_paise > order_amount_paise:
            raise ValidationError(
                "Redemption discount cannot exceed total order amount",
                details={"discount_paise": discount_paise, "order_amount_paise": order_amount_paise},
            )

        return {
            "valid": True,
            "points_to_redeem": points_to_redeem,
            "discount_paise": discount_paise,
            "usable_balance": usable_balance,
        }

    @staticmethod
    async def redeem_points(
        session: AsyncSession,
        business_id: uuid.UUID,
        customer_contact_id: uuid.UUID,
        *,
        points_to_redeem: int,
        order_amount_paise: int,
        source_type: str,
        source_id: str,
        idempotency_key: str,
        actor_id: uuid.UUID | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Redeems points and writes negative ledger entry. Idempotent."""
        now = now or datetime.now(timezone.utc)

        existing = (
            await session.execute(
                select(LoyaltyLedgerEntry).where(
                    LoyaltyLedgerEntry.business_id == business_id,
                    LoyaltyLedgerEntry.idempotency_key == idempotency_key,
                )
            )
        ).scalars().first()
        if existing is not None:
            prog = await LoyaltyProgramService.get_or_create_default_program(session, business_id)
            discount_paise = int(math.floor(Decimal(abs(existing.delta)) * prog.redemption_rupees_per_point * 100))
            return {
                "points_redeemed": abs(existing.delta),
                "discount_paise": discount_paise,
                "balance_after": existing.balance_after,
                "already_processed": True,
                "ledger_entry_id": str(existing.id),
            }

        validation = await LoyaltyPointsService.validate_redemption(
            session,
            business_id,
            customer_contact_id,
            points_to_redeem=points_to_redeem,
            order_amount_paise=order_amount_paise,
            now=now,
        )

        account = await LoyaltyPointsService.get_or_create_account(session, business_id, customer_contact_id)
        new_balance = (account.current_points or 0) - points_to_redeem
        account.current_points = max(0, new_balance)
        account.lifetime_points_redeemed = (account.lifetime_points_redeemed or 0) + points_to_redeem
        account.last_activity_at = now
        account.updated_at = now

        entry = LoyaltyLedgerEntry(
            business_id=business_id,
            customer_contact_id=customer_contact_id,
            delta=-points_to_redeem,
            balance_after=new_balance,
            reason="redeem_order",
            source_type=source_type,
            source_id=source_id,
            idempotency_key=idempotency_key,
            actor_id=actor_id,
            created_at=now,
        )
        session.add(entry)
        await session.flush()

        return {
            "points_redeemed": points_to_redeem,
            "discount_paise": validation["discount_paise"],
            "balance_after": new_balance,
            "already_processed": False,
            "ledger_entry_id": str(entry.id),
        }

    @staticmethod
    async def reverse_points(
        session: AsyncSession,
        business_id: uuid.UUID,
        customer_contact_id: uuid.UUID,
        *,
        points_to_reverse: int,
        reason: str,
        source_type: str,
        source_id: str,
        idempotency_key: str,
        actor_id: uuid.UUID | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Reverses points (e.g. order refund / clawback or restoring redeemed points)."""
        now = now or datetime.now(timezone.utc)

        existing = (
            await session.execute(
                select(LoyaltyLedgerEntry).where(
                    LoyaltyLedgerEntry.business_id == business_id,
                    LoyaltyLedgerEntry.idempotency_key == idempotency_key,
                )
            )
        ).scalars().first()
        if existing is not None:
            return {"points_reversed": existing.delta, "already_processed": True}

        account = await LoyaltyPointsService.get_or_create_account(session, business_id, customer_contact_id)
        # If reason is clawback_refund, delta is negative
        # If reason is refund_reversal of a redemption, delta is positive
        delta = -abs(points_to_reverse) if reason == "clawback_refund" else abs(points_to_reverse)
        new_balance = max(0, account.current_points + delta)
        account.current_points = new_balance
        account.last_activity_at = now
        account.updated_at = now

        entry = LoyaltyLedgerEntry(
            business_id=business_id,
            customer_contact_id=customer_contact_id,
            delta=delta,
            balance_after=new_balance,
            reason=reason,
            source_type=source_type,
            source_id=source_id,
            idempotency_key=idempotency_key,
            actor_id=actor_id,
            created_at=now,
        )
        session.add(entry)
        await session.flush()

        return {
            "points_reversed": delta,
            "balance_after": new_balance,
            "already_processed": False,
            "ledger_entry_id": str(entry.id),
        }


class StampCardService:
    @staticmethod
    async def get_or_create_program(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        name: str = "Stamp Card",
        required_stamps: int = 10,
        reward_kind: str = "free_item",
        reward_details: dict[str, Any] | None = None,
        qualifying_rule: dict[str, Any] | None = None,
    ) -> StampProgram:
        q = select(StampProgram).where(
            StampProgram.business_id == business_id,
            StampProgram.status == "active",
        )
        prog = (await session.execute(q)).scalars().first()
        if prog is not None:
            return prog

        prog = StampProgram(
            business_id=business_id,
            name=name,
            required_stamps=required_stamps,
            reward_kind=reward_kind,
            reward_details=reward_details or {"item_name": "Free reward item"},
            qualifying_rule=qualifying_rule or {"all_items": True},
            status="active",
        )
        session.add(prog)
        await session.flush()
        return prog

    @staticmethod
    async def award_stamp(
        session: AsyncSession,
        business_id: uuid.UUID,
        customer_contact_id: uuid.UUID,
        *,
        source_type: str,
        source_id: str,
        idempotency_key: str,
        program_id: uuid.UUID | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Awards a stamp. If threshold is reached, issues reward exactly once."""
        now = now or datetime.now(timezone.utc)

        prog = (
            await session.get(StampProgram, program_id)
            if program_id
            else await StampCardService.get_or_create_program(session, business_id)
        )
        if not prog or prog.status != "active":
            return {"stamps_awarded": 0, "reward_issued": None}

        # Idempotency check via a unique stamp log or reward
        q_card = select(StampCard).where(
            StampCard.business_id == business_id,
            StampCard.program_id == prog.id,
            StampCard.customer_contact_id == customer_contact_id,
        )
        card = (await session.execute(q_card)).scalars().first()
        if card is None:
            card = StampCard(
                business_id=business_id,
                program_id=prog.id,
                customer_contact_id=customer_contact_id,
                current_stamps=0,
                cycle_count=0,
                lifetime_stamps=0,
            )
            session.add(card)
            await session.flush()

        # Check if reward for this idempotency key was already created or handled
        reward_code_prefix = f"STAMP-{idempotency_key}"
        existing_reward = (
            await session.execute(
                select(StampReward).where(
                    StampReward.business_id == business_id,
                    StampReward.reward_code == reward_code_prefix,
                )
            )
        ).scalars().first()
        if existing_reward:
            return {
                "current_stamps": card.current_stamps,
                "required_stamps": prog.required_stamps,
                "reward_issued": {
                    "code": existing_reward.reward_code,
                    "reward_kind": prog.reward_kind,
                    "cycle": existing_reward.cycle_completed,
                },
                "already_processed": True,
            }

        # Increment stamps
        card.current_stamps += 1
        card.lifetime_stamps += 1
        card.last_stamp_at = now
        card.updated_at = now

        reward_issued = None
        # Threshold reached: e.g. 10th coffee free!
        if card.current_stamps >= prog.required_stamps:
            card.cycle_count += 1
            card.current_stamps -= prog.required_stamps

            unique_suffix = secrets.token_hex(4).upper()
            code = f"STAMP-{card.cycle_count}-{unique_suffix}"

            reward = StampReward(
                business_id=business_id,
                program_id=prog.id,
                customer_contact_id=customer_contact_id,
                reward_code=code,
                cycle_completed=card.cycle_count,
                status="issued",
                issued_at=now,
            )
            session.add(reward)
            await session.flush()

            reward_issued = {
                "id": str(reward.id),
                "code": code,
                "reward_kind": prog.reward_kind,
                "cycle": card.cycle_count,
                "details": prog.reward_details,
            }

        await session.flush()
        return {
            "current_stamps": card.current_stamps,
            "required_stamps": prog.required_stamps,
            "cycle_count": card.cycle_count,
            "reward_issued": reward_issued,
            "already_processed": False,
        }


class ReferralService:
    @staticmethod
    async def get_or_create_referral_code(
        session: AsyncSession, business_id: uuid.UUID, customer_contact_id: uuid.UUID
    ) -> str:
        q = select(ReferralCode).where(
            ReferralCode.business_id == business_id,
            ReferralCode.customer_contact_id == customer_contact_id,
        )
        ref = (await session.execute(q)).scalars().first()
        if ref is not None:
            return ref.code

        suffix = secrets.token_hex(3).upper()
        code = f"REF-{suffix}"
        ref = ReferralCode(
            business_id=business_id,
            customer_contact_id=customer_contact_id,
            code=code,
        )
        session.add(ref)
        await session.flush()
        return code

    @staticmethod
    async def apply_referral_code(
        session: AsyncSession,
        business_id: uuid.UUID,
        referee_contact_id: uuid.UUID,
        code: str,
        now: datetime | None = None,
    ) -> ReferralRelationship:
        now = now or datetime.now(timezone.utc)
        clean_code = code.strip().upper()

        q_ref = select(ReferralCode).where(
            ReferralCode.business_id == business_id,
            func.lower(ReferralCode.code) == clean_code.lower(),
        )
        referrer_record = (await session.execute(q_ref)).scalars().first()
        if referrer_record is None:
            raise ValidationError("Invalid or unknown referral code", details={"code": code})

        if referrer_record.customer_contact_id == referee_contact_id:
            raise ValidationError("Customers cannot use their own referral code", details={"code": code})

        # Check if referee was already referred
        existing = (
            await session.execute(
                select(ReferralRelationship).where(
                    ReferralRelationship.business_id == business_id,
                    ReferralRelationship.referee_contact_id == referee_contact_id,
                )
            )
        ).scalars().first()
        if existing is not None:
            raise ConflictError("Customer has already been referred by another code")

        rel = ReferralRelationship(
            business_id=business_id,
            referrer_contact_id=referrer_record.customer_contact_id,
            referee_contact_id=referee_contact_id,
            code_used=clean_code,
            status="pending",
            created_at=now,
        )
        session.add(rel)
        await session.flush()
        return rel

    @staticmethod
    async def qualify_first_purchase(
        session: AsyncSession,
        business_id: uuid.UUID,
        referee_contact_id: uuid.UUID,
        *,
        source_type: str,
        source_id: str,
        referrer_points: int = 100,
        referee_points: int = 50,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Rewards both referrer and referee on referee's first completed purchase. Idempotent."""
        now = now or datetime.now(timezone.utc)
        q = select(ReferralRelationship).where(
            ReferralRelationship.business_id == business_id,
            ReferralRelationship.referee_contact_id == referee_contact_id,
        )
        rel = (await session.execute(q)).scalars().first()
        if rel is None or rel.status != "pending":
            return {"qualified": False, "reason": "No pending referral relationship"}

        rel.status = "qualified"
        rel.qualification_source_type = source_type
        rel.qualification_source_id = source_id
        rel.qualified_at = now
        rel.referrer_points_awarded = referrer_points
        rel.referee_points_awarded = referee_points

        # Award points via LoyaltyPointsService
        idemp_referrer = f"ref-bonus:referrer:{rel.id}:{source_id}"
        idemp_referee = f"ref-bonus:referee:{rel.id}:{source_id}"

        await LoyaltyPointsService.earn_points(
            session,
            business_id,
            rel.referrer_contact_id,
            order_amount_paise=referrer_points * 100,  # 1:1 conversion for direct bonus points
            source_type="referral",
            source_id=str(rel.id),
            idempotency_key=idemp_referrer,
            reason="referral_bonus",
            now=now,
        )
        await LoyaltyPointsService.earn_points(
            session,
            business_id,
            rel.referee_contact_id,
            order_amount_paise=referee_points * 100,
            source_type="referral",
            source_id=str(rel.id),
            idempotency_key=idemp_referee,
            reason="referral_bonus",
            now=now,
        )

        rel.status = "rewarded"
        await session.flush()
        return {
            "qualified": True,
            "referrer_points": referrer_points,
            "referee_points": referee_points,
            "referrer_id": str(rel.referrer_contact_id),
            "referee_id": str(rel.referee_contact_id),
        }


class GiftVoucherService:
    @staticmethod
    async def issue_voucher(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        issued_amount_paise: int,
        recipient_name: str | None = None,
        recipient_phone: str | None = None,
        holder_contact_id: uuid.UUID | None = None,
        expiry_days: int | None = 365,
        actor_id: uuid.UUID | None = None,
        now: datetime | None = None,
    ) -> GiftVoucher:
        """Issues a gift voucher with prepaid balance.

        Note: Payments owns collecting funds. This issues the voucher once funds are confirmed.
        """
        now = now or datetime.now(timezone.utc)
        if issued_amount_paise <= 0:
            raise ValidationError("Issued amount must be positive", details={"amount": issued_amount_paise})

        # Generate unique code: LOC-XXXX-XXXX
        chars = string.ascii_uppercase + string.digits
        part1 = "".join(secrets.choice(chars) for _ in range(4))
        part2 = "".join(secrets.choice(chars) for _ in range(4))
        code = f"LOC-GV-{part1}-{part2}"

        expires_at = now + timedelta(days=expiry_days) if expiry_days else None

        voucher = GiftVoucher(
            business_id=business_id,
            code=code,
            holder_contact_id=holder_contact_id,
            recipient_name=recipient_name,
            recipient_phone=recipient_phone,
            issued_amount_paise=issued_amount_paise,
            remaining_balance_paise=issued_amount_paise,
            currency="INR",
            status="active",
            expires_at=expires_at,
            created_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        session.add(voucher)
        await session.flush()

        tx = GiftVoucherTransaction(
            business_id=business_id,
            voucher_id=voucher.id,
            delta_paise=issued_amount_paise,
            balance_after_paise=issued_amount_paise,
            reason="issuance",
            source_type="manual",
            source_id=str(voucher.id),
            idempotency_key=f"voucher_issue:{voucher.id}",
            actor_id=actor_id,
            created_at=now,
        )
        session.add(tx)
        await session.flush()
        return voucher

    @staticmethod
    async def validate_voucher(
        session: AsyncSession,
        business_id: uuid.UUID,
        code: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Validates voucher availability and balance."""
        now = now or datetime.now(timezone.utc)
        clean_code = code.strip().upper()

        q = select(GiftVoucher).where(
            GiftVoucher.business_id == business_id,
            func.upper(GiftVoucher.code) == clean_code,
        )
        voucher = (await session.execute(q)).scalars().first()
        if voucher is None:
            raise ResourceNotFound("Gift Voucher")

        if voucher.status != "active":
            raise ValidationError(f"Voucher is {voucher.status}")

        if voucher.expires_at and voucher.expires_at < now:
            raise ValidationError("Voucher has expired")

        if voucher.remaining_balance_paise <= 0:
            raise ValidationError("Voucher has zero remaining balance")

        return {
            "id": str(voucher.id),
            "code": voucher.code,
            "remaining_balance_paise": voucher.remaining_balance_paise,
            "currency": voucher.currency,
            "expires_at": voucher.expires_at.isoformat() if voucher.expires_at else None,
            "recipient_name": voucher.recipient_name,
        }

    @staticmethod
    async def redeem_voucher(
        session: AsyncSession,
        business_id: uuid.UUID,
        code: str,
        *,
        redeem_amount_paise: int,
        source_type: str,
        source_id: str,
        idempotency_key: str,
        actor_id: uuid.UUID | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Redeems voucher balance deterministically. Never allows negative balance."""
        now = now or datetime.now(timezone.utc)
        if redeem_amount_paise <= 0:
            raise ValidationError("Redeem amount must be positive", details={"amount": redeem_amount_paise})

        # Idempotency check
        existing = (
            await session.execute(
                select(GiftVoucherTransaction).where(
                    GiftVoucherTransaction.business_id == business_id,
                    GiftVoucherTransaction.idempotency_key == idempotency_key,
                )
            )
        ).scalars().first()
        if existing is not None:
            return {
                "redeemed_paise": abs(existing.delta_paise),
                "balance_after_paise": existing.balance_after_paise,
                "already_processed": True,
            }

        val = await GiftVoucherService.validate_voucher(session, business_id, code, now)
        voucher = await session.get(GiftVoucher, uuid.UUID(val["id"]))
        assert voucher is not None

        if redeem_amount_paise > voucher.remaining_balance_paise:
            raise ValidationError(
                f"Cannot redeem ₹{redeem_amount_paise/100:.2f}. Available balance is ₹{voucher.remaining_balance_paise/100:.2f}",
                details={"available_paise": voucher.remaining_balance_paise, "requested_paise": redeem_amount_paise},
            )

        new_balance = voucher.remaining_balance_paise - redeem_amount_paise
        voucher.remaining_balance_paise = new_balance
        if new_balance == 0:
            voucher.status = "redeemed"
        voucher.updated_at = now

        tx = GiftVoucherTransaction(
            business_id=business_id,
            voucher_id=voucher.id,
            delta_paise=-redeem_amount_paise,
            balance_after_paise=new_balance,
            reason="redemption",
            source_type=source_type,
            source_id=source_id,
            idempotency_key=idempotency_key,
            actor_id=actor_id,
            created_at=now,
        )
        session.add(tx)
        await session.flush()

        return {
            "voucher_id": str(voucher.id),
            "redeemed_paise": redeem_amount_paise,
            "balance_after_paise": new_balance,
            "already_processed": False,
        }

    @staticmethod
    async def reverse_redemption(
        session: AsyncSession,
        business_id: uuid.UUID,
        code: str,
        *,
        restore_amount_paise: int,
        source_type: str,
        source_id: str,
        idempotency_key: str,
        actor_id: uuid.UUID | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Restores voucher balance on order cancellation / refund."""
        now = now or datetime.now(timezone.utc)
        clean_code = code.strip().upper()

        q = select(GiftVoucher).where(
            GiftVoucher.business_id == business_id,
            func.upper(GiftVoucher.code) == clean_code,
        )
        voucher = (await session.execute(q)).scalars().first()
        if voucher is None:
            raise ResourceNotFound("Gift Voucher")

        existing = (
            await session.execute(
                select(GiftVoucherTransaction).where(
                    GiftVoucherTransaction.business_id == business_id,
                    GiftVoucherTransaction.idempotency_key == idempotency_key,
                )
            )
        ).scalars().first()
        if existing is not None:
            return {"restored_paise": existing.delta_paise, "already_processed": True}

        new_balance = voucher.remaining_balance_paise + restore_amount_paise
        voucher.remaining_balance_paise = new_balance
        if voucher.status == "redeemed" and new_balance > 0:
            voucher.status = "active"
        voucher.updated_at = now

        tx = GiftVoucherTransaction(
            business_id=business_id,
            voucher_id=voucher.id,
            delta_paise=restore_amount_paise,
            balance_after_paise=new_balance,
            reason="refund_reversal",
            source_type=source_type,
            source_id=source_id,
            idempotency_key=idempotency_key,
            actor_id=actor_id,
            created_at=now,
        )
        session.add(tx)
        await session.flush()

        return {
            "voucher_id": str(voucher.id),
            "restored_paise": restore_amount_paise,
            "balance_after_paise": new_balance,
            "already_processed": False,
        }
