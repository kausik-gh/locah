"""Attendance consumes these decisions; it never computes membership eligibility."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ServiceUnavailable


@dataclass(frozen=True)
class MembershipCheckinDecision:
    enrolment_id: uuid.UUID
    customer_contact_id: uuid.UUID
    state: Literal["allowed", "warning", "denied"]
    reason: str | None = None


class MembershipCheckinEligibility(Protocol):
    async def decide(self, session: AsyncSession, business_id: uuid.UUID,
                     enrolment_id: uuid.UUID) -> MembershipCheckinDecision: ...

    async def resolve(self, session: AsyncSession, business_id: uuid.UUID, code: str) -> uuid.UUID:
        """The member's printed code or QR payload → the enrolment it names."""
        ...


class UnconnectedMembershipEligibility:
    async def decide(self, session: AsyncSession, business_id: uuid.UUID,
                     enrolment_id: uuid.UUID) -> MembershipCheckinDecision:
        raise ServiceUnavailable("Membership eligibility is not connected; check-in was not recorded")

    async def resolve(self, session: AsyncSession, business_id: uuid.UUID, code: str) -> uuid.UUID:
        raise ServiceUnavailable("Membership eligibility is not connected; check-in was not recorded")
