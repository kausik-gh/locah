"""The daily run for AI employees that work on a schedule (collections, procurement).

One recurring chain (platform_scheduled_jobs, like memberships.sweep): booked
when the owner switches one of them on, re-booked by the worker after each
run. Each business runs in its own tenant binding and transaction; one
business's failure never stops the others. The receptionist needs no
schedule — it answers as messages arrive.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

RECURRENCE_KEY = "ai_employees.sweep"
SCHEDULED_KINDS = ("collections", "procurement")


async def ensure_scheduled(session: AsyncSession, *, minutes: int = 1440) -> bool:
    """Book the next run unless one is already waiting (one chain however many workers)."""
    pending = (await session.execute(text(
        "SELECT 1 FROM platform_scheduled_jobs WHERE recurrence_key = :k AND status = 'pending' LIMIT 1"),
        {"k": RECURRENCE_KEY})).first()
    if pending is not None:
        return False
    await session.execute(text(
        "INSERT INTO platform_scheduled_jobs (schedule_type, payload, run_at, recurrence_key) "
        "VALUES ('ai_employees.sweep', CAST(:p AS jsonb), now() + make_interval(mins => :m), :k)"),
        {"p": '{"recurring": true}', "m": max(1, int(minutes)), "k": RECURRENCE_KEY})
    return True


async def businesses_with_scheduled_employees(session: AsyncSession) -> list[uuid.UUID]:
    rows = (await session.execute(text(
        "SELECT DISTINCT business_id FROM ai_employees WHERE enabled AND kind = ANY(:k)"),
        {"k": list(SCHEDULED_KINDS)})).all()
    return [uuid.UUID(str(r[0])) for r in rows]


async def sweep_all(session: AsyncSession) -> dict[str, Any]:
    from platform_core.ai_employees import collections, procurement
    from platform_core.context_resolver import bind_public_context

    done: dict[str, Any] = {}
    for business_id in await businesses_with_scheduled_employees(session):
        await bind_public_context(session, business_id)
        try:
            done[str(business_id)] = {
                "collections": await collections.run(session, business_id, source="daily run"),
                "procurement": await procurement.run(session, business_id, source="daily run"),
            }
            await session.commit()
        except Exception as exc:  # noqa: BLE001 — one business's failure must not stop the others
            await session.rollback()
            done[str(business_id)] = {"error": str(exc)[:300]}
    return done
