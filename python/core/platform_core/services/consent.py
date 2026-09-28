"""Consent store (Capability Universe §24 #8, §12.4, §25.1; DPDP Act).

Transactional messages follow the customer's own action (an order, a
booking). Marketing needs explicit opt-in recorded here with a timestamp and
source. A grant is a row; a withdrawal closes it; a re-grant opens a new one,
so the history of what a person agreed to is never overwritten.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ResourceNotFound, ValidationError

PURPOSES = ("transactional", "marketing", "reminders", "photos_public", "data_processing", "forecast_sharing")
CHANNELS = ("whatsapp", "sms", "email", "call", "any")
PURPOSE_LABELS = {
    "transactional": "Order, booking and payment messages",
    "marketing": "Offers and promotions",
    "reminders": "Reminders (renewals, appointments)",
    "photos_public": "Photos may appear publicly",
    "data_processing": "Keep and use their details",
    "forecast_sharing": "Share forecasts with suppliers",
}


class ConsentService:
    @staticmethod
    def _check(purpose: str, channel: str) -> None:
        if purpose not in PURPOSES:
            raise ValidationError("Unknown consent purpose", details={"field": "purpose"})
        if channel not in CHANNELS:
            raise ValidationError("Unknown channel", details={"field": "channel"})

    @staticmethod
    async def _contact_exists(session: AsyncSession, business_id: uuid.UUID, contact_id: uuid.UUID) -> None:
        found = (await session.execute(
            text("SELECT 1 FROM customer_relationships_contacts WHERE business_id = :b AND id = :c "
                 "AND deleted_at IS NULL"),
            {"b": str(business_id), "c": str(contact_id)},
        )).first()
        if found is None:
            raise ResourceNotFound("Customer")

    @staticmethod
    async def grant(
        session: AsyncSession,
        business_id: uuid.UUID,
        contact_id: uuid.UUID,
        *,
        purpose: str,
        channel: str,
        source: str,
        evidence: dict[str, Any] | None = None,
        recorded_by: uuid.UUID | None = None,
    ) -> bool:
        """Record a grant. Returns False if an open grant already existed."""
        ConsentService._check(purpose, channel)
        await ConsentService._contact_exists(session, business_id, contact_id)
        res = await session.execute(
            text("""
                INSERT INTO customer_consents (business_id, contact_id, purpose, channel, source, evidence, recorded_by)
                VALUES (:b, :c, :p, :ch, :s, CAST(:e AS jsonb), :r)
                ON CONFLICT (business_id, contact_id, purpose, channel) WHERE withdrawn_at IS NULL DO NOTHING
                RETURNING id
            """),
            {"b": str(business_id), "c": str(contact_id), "p": purpose, "ch": channel, "s": source,
             "e": json.dumps(evidence or {}), "r": str(recorded_by) if recorded_by else None},
        )
        return bool(res.all())

    @staticmethod
    async def withdraw(
        session: AsyncSession, business_id: uuid.UUID, contact_id: uuid.UUID, *, purpose: str, channel: str,
        source: str,
    ) -> bool:
        ConsentService._check(purpose, channel)
        res = await session.execute(
            text("""
                UPDATE customer_consents SET withdrawn_at = :now, withdrawn_source = :s
                WHERE business_id = :b AND contact_id = :c AND purpose = :p AND channel = :ch
                  AND withdrawn_at IS NULL
                RETURNING id
            """),
            {"now": datetime.now(timezone.utc), "s": source, "b": str(business_id), "c": str(contact_id),
             "p": purpose, "ch": channel},
        )
        return bool(res.all())

    @staticmethod
    async def has(
        session: AsyncSession, business_id: uuid.UUID, contact_id: uuid.UUID, *, purpose: str, channel: str
    ) -> bool:
        """An open grant for this purpose on this channel (or on 'any')."""
        ConsentService._check(purpose, channel)
        row = (await session.execute(
            text("""
                SELECT 1 FROM customer_consents
                WHERE business_id = :b AND contact_id = :c AND purpose = :p
                  AND channel IN (:ch, 'any') AND withdrawn_at IS NULL
                LIMIT 1
            """),
            {"b": str(business_id), "c": str(contact_id), "p": purpose, "ch": channel},
        )).first()
        return row is not None

    @staticmethod
    async def history(session: AsyncSession, business_id: uuid.UUID, contact_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (await session.execute(
            text("""
                SELECT id, purpose, channel, source, granted_at, withdrawn_at, withdrawn_source
                FROM customer_consents WHERE business_id = :b AND contact_id = :c
                ORDER BY granted_at DESC
            """),
            {"b": str(business_id), "c": str(contact_id)},
        )).all()
        return [
            {"id": str(r[0]), "purpose": r[1], "purpose_label": PURPOSE_LABELS[r[1]], "channel": r[2],
             "source": r[3], "granted_at": r[4].isoformat(),
             "withdrawn_at": r[5].isoformat() if r[5] else None, "withdrawn_source": r[6],
             "open": r[5] is None}
            for r in rows
        ]
