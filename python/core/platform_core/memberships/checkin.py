"""Memberships' answer to Attendance's check-in question.

Attendance records the visit; it never decides whether the member may come in
(Founder refinement — Memberships §6). This adapter implements Attendance's
published `MembershipCheckinEligibility` protocol with Memberships' own
decision, so the lifecycle (active, grace policy, freeze, expiry, sessions left)
is computed in exactly one place.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.services.attendance_contracts import MembershipCheckinDecision


class MembershipsCheckinEligibility:
    async def decide(self, session: AsyncSession, business_id: uuid.UUID,
                     enrolment_id: uuid.UUID) -> MembershipCheckinDecision:
        from platform_core.memberships.service import MembershipCore

        answer = await MembershipCore.checkin_decision(session, business_id, enrolment_id)
        return MembershipCheckinDecision(
            enrolment_id=uuid.UUID(answer["enrolment_id"]),
            customer_contact_id=uuid.UUID(answer["customer_contact_id"]),
            state=answer["decision"],
            reason=answer["reason"],
        )

    async def resolve(self, session: AsyncSession, business_id: uuid.UUID, code: str) -> uuid.UUID:
        """The member's printed code or QR payload → their enrolment (Memberships owns the code)."""
        from platform_core.memberships.service import MembershipCore

        enrolment = await MembershipCore.resolve_code(session, business_id, code)
        return uuid.UUID(str(enrolment.id))
