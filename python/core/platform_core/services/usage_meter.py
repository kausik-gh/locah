"""Usage meters (Capability Universe §24 #9, §2 rule 13, §8.4, §11.6).

Every metered cost — WhatsApp/SMS/email messages, voice minutes, Maps calls,
model tokens — is counted per business per calendar month, idempotently, with
an optional hard cap. `check` answers "may I spend this?" before a provider is
called; `record` counts after. Crossing 80 % and 100 % of a cap tells the owner
once each month.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ValidationError

RESOURCES = ("whatsapp_message", "sms_message", "email_message", "voice_minute", "maps_call", "model_tokens")
LABELS = {
    "whatsapp_message": "WhatsApp messages", "sms_message": "SMS messages", "email_message": "Emails",
    "voice_minute": "Call minutes", "maps_call": "Maps lookups", "model_tokens": "AI usage (tokens)",
}
ALERT_STEPS = (80, 100)
# Resources something actually counts today. Messaging, calls and maps join as
# their providers are connected; until then the owner can still set a limit.
COUNTED_NOW = frozenset({"model_tokens", "whatsapp_message"})


class CapReached(Exception):
    def __init__(self, resource: str, used: int | None = None, cap: int | None = None) -> None:
        label = LABELS.get(resource, resource)
        super().__init__(f"{label}: this month's limit is reached"
                         + (f" ({used:,} of {cap:,})" if used is not None and cap is not None else ""))
        self.resource, self.used, self.cap = resource, used, cap


def period_of(moment: datetime | None = None) -> str:
    local = (moment or datetime.now(timezone.utc)).astimezone(ZoneInfo("Asia/Kolkata"))
    return f"{local.year:04d}-{local.month:02d}"


class UsageMeterService:
    @staticmethod
    def _resource(resource: str) -> None:
        if resource not in RESOURCES:
            raise ValidationError("Unknown metered resource", details={"field": "resource"})

    @staticmethod
    async def _row(session: AsyncSession, business_id: uuid.UUID, resource: str, period: str) -> tuple[int, int | None, int]:
        await session.execute(
            text("""INSERT INTO usage_meters (business_id, resource, period) VALUES (:b, :r, :p)
                    ON CONFLICT (business_id, resource, period) DO NOTHING"""),
            {"b": str(business_id), "r": resource, "p": period},
        )
        # A cap set in an earlier month carries forward until changed.
        await session.execute(
            text("""
                UPDATE usage_meters m SET cap = prev.cap
                FROM (SELECT cap FROM usage_meters WHERE business_id = :b AND resource = :r AND period < :p
                      AND cap IS NOT NULL ORDER BY period DESC LIMIT 1) prev
                WHERE m.business_id = :b AND m.resource = :r AND m.period = :p AND m.cap IS NULL
            """),
            {"b": str(business_id), "r": resource, "p": period},
        )
        row = (await session.execute(
            text("SELECT used, cap, alerted_pct FROM usage_meters WHERE business_id = :b AND resource = :r "
                 "AND period = :p FOR UPDATE"),
            {"b": str(business_id), "r": resource, "p": period},
        )).one()
        return int(row[0]), (int(row[1]) if row[1] is not None else None), int(row[2])

    @staticmethod
    async def check(session: AsyncSession, business_id: uuid.UUID, resource: str, quantity: int = 1) -> None:
        """Raise CapReached before spending past the cap."""
        UsageMeterService._resource(resource)
        used, cap, _ = await UsageMeterService._row(session, business_id, resource, period_of())
        if cap is not None and used + quantity > cap:
            raise CapReached(resource, used, cap)

    @staticmethod
    async def record(
        session: AsyncSession,
        business_id: uuid.UUID,
        resource: str,
        quantity: int,
        *,
        idempotency_key: str,
        context: dict[str, Any] | None = None,
        enforce_cap: bool = True,
    ) -> dict[str, Any]:
        """Count usage once per idempotency key. Returns the meter after counting."""
        UsageMeterService._resource(resource)
        if quantity <= 0:
            raise ValidationError("Quantity must be positive", details={"field": "quantity"})
        period = period_of()
        used, cap, alerted = await UsageMeterService._row(session, business_id, resource, period)
        inserted = (await session.execute(
            text("""
                INSERT INTO usage_events (business_id, resource, period, quantity, idempotency_key, context)
                VALUES (:b, :r, :p, :q, :k, CAST(:c AS jsonb))
                ON CONFLICT (business_id, idempotency_key) DO NOTHING RETURNING id
            """),
            {"b": str(business_id), "r": resource, "p": period, "q": quantity, "k": idempotency_key,
             "c": json.dumps(context or {})},
        )).all()
        if not inserted:
            return {"resource": resource, "period": period, "used": used, "cap": cap, "counted": False}
        if enforce_cap and cap is not None and used + quantity > cap:
            raise CapReached(resource, used, cap)
        used += quantity
        crossed = [s for s in ALERT_STEPS if cap and alerted < s <= used * 100 // cap]
        await session.execute(
            text("""UPDATE usage_meters SET used = :u, alerted_pct = :a, updated_at = now()
                    WHERE business_id = :b AND resource = :r AND period = :p"""),
            {"u": used, "a": max([alerted, *crossed]), "b": str(business_id), "r": resource, "p": period},
        )
        if crossed:
            await UsageMeterService._alert(session, business_id, resource, used, cap, max(crossed))
        return {"resource": resource, "period": period, "used": used, "cap": cap, "counted": True,
                "alerts": crossed}

    @staticmethod
    async def _alert(
        session: AsyncSession, business_id: uuid.UUID, resource: str, used: int, cap: int | None, pct: int
    ) -> None:
        """Tell whoever manages settings once a cap is 80% or fully used."""
        from platform_core.permissions import SETTINGS_READ
        from platform_core.services.notification import NotificationService

        label = LABELS[resource]
        full = pct >= 100
        await NotificationService.fan_out(
            session, business_id=business_id, notification_type="usage.cap_alert",
            title=f"{label}: {'this month’s limit is reached' if full else f'{pct}% of this month’s limit used'}",
            body=(f"{used:,} of {cap:,} used. " + ("New use stops until next month or until you raise the limit."
                                                   if full else "You can raise the limit in Settings › Usage.")),
            required_permission=SETTINGS_READ, severity="warning" if not full else "critical",
            resource_type="usage_meter", payload={"resource": resource, "used": used, "cap": cap, "pct": pct},
        )

    @staticmethod
    async def over_cap(session: AsyncSession, business_id: uuid.UUID, resource: str) -> bool:
        """A read without locks, for checks made just before a slow provider
        call (the caller must not hold a transaction across that call)."""
        UsageMeterService._resource(resource)
        row = (await session.execute(
            text("""
                SELECT COALESCE((SELECT used FROM usage_meters WHERE business_id = :b AND resource = :r
                                 AND period = :p), 0),
                       COALESCE((SELECT cap FROM usage_meters WHERE business_id = :b AND resource = :r
                                 AND period = :p),
                                (SELECT cap FROM usage_meters WHERE business_id = :b AND resource = :r
                                 AND period < :p AND cap IS NOT NULL ORDER BY period DESC LIMIT 1))
            """),
            {"b": str(business_id), "r": resource, "p": period_of()},
        )).one()
        return row[1] is not None and int(row[0]) >= int(row[1])

    @staticmethod
    async def record_model_usage(
        session: AsyncSession, business_id: uuid.UUID, usage: dict[str, Any] | None, *, key: str, feature: str
    ) -> None:
        """Count the tokens a model call already spent (never refused after the
        fact — the cap is honoured by `over_cap` before the call)."""
        usage = usage or {}
        total = usage.get("total_tokens")
        if not isinstance(total, int):
            parts = [usage.get(k) for k in ("prompt_tokens", "completion_tokens")]
            total = sum(v for v in parts if isinstance(v, int))
        if total and total > 0:
            await UsageMeterService.record(session, business_id, "model_tokens", total, idempotency_key=key,
                                           context={"feature": feature, "model": usage.get("model")},
                                           enforce_cap=False)

    @staticmethod
    async def set_cap(session: AsyncSession, business_id: uuid.UUID, resource: str, cap: int | None) -> None:
        UsageMeterService._resource(resource)
        if cap is not None and cap < 0:
            raise ValidationError("Cap cannot be negative", details={"field": "cap"})
        period = period_of()
        await UsageMeterService._row(session, business_id, resource, period)
        await session.execute(
            text("UPDATE usage_meters SET cap = :c, alerted_pct = 0 WHERE business_id = :b AND resource = :r "
                 "AND period = :p"),
            {"c": cap, "b": str(business_id), "r": resource, "p": period},
        )

    @staticmethod
    async def summary(session: AsyncSession, business_id: uuid.UUID) -> list[dict[str, Any]]:
        period = period_of()
        # A limit carries forward month to month until the owner changes it.
        rows = {r[0]: (int(r[1]), r[2]) for r in (await session.execute(
            text("""
                SELECT DISTINCT ON (resource) resource,
                       CASE WHEN period = :p THEN used ELSE 0 END, cap
                FROM usage_meters
                WHERE business_id = :b AND (period = :p OR (period < :p AND cap IS NOT NULL))
                ORDER BY resource, period DESC
            """),
            {"b": str(business_id), "p": period},
        )).all()}
        return [
            {"resource": r, "label": LABELS[r], "period": period, "used": rows.get(r, (0, None))[0],
             "cap": rows.get(r, (0, None))[1], "counting": r in COUNTED_NOW}
            for r in RESOURCES
        ]
