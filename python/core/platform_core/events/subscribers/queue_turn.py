"""queue.turn_soon → one notice per token visit.

Messaging sends the WhatsApp from this event. This handler does not import
Messaging. A redelivery inserts nothing the second time.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.events.registry import EventContext, subscribe


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "queue.turn_soon",
    "queue.turn_soon",
    description="Record one your-turn-soon notice per token visit for Messaging",
)
async def record_turn_soon(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    entry_id = event.require_uuid("entry_id")
    try:
        cycle = int(event.payload["visit_cycle"])
        ahead = int(event.payload["ahead"])
        token = int(event.payload["token_number"])
    except (KeyError, TypeError, ValueError) as exc:
        from platform_core.events.registry import PermanentEventError

        raise PermanentEventError("queue.turn_soon is missing visit_cycle, ahead, or token_number") from exc
    await session.execute(
        text("""
            INSERT INTO queue_turn_notices
                (business_id, entry_id, visit_cycle, ahead, token_number, customer_contact_id, booking_id)
            VALUES (:b, :e, :c, :a, :t,
                    NULLIF(:contact, '')::uuid, NULLIF(:booking, '')::uuid)
            ON CONFLICT (entry_id, visit_cycle) DO NOTHING
        """),
        {
            "b": str(business_id),
            "e": str(entry_id),
            "c": cycle,
            "a": ahead,
            "t": token,
            "contact": event.payload.get("customer_contact_id") or "",
            "booking": event.payload.get("booking_id") or "",
        },
    )
