"""Where customers start a WhatsApp journey (Capability Universe §12.2).

Counter and packaging QR, the website's "Order on WhatsApp" button and the
Marketplace profile all open the business's own connected number with the
word "menu" already typed, which the router answers with the structured menu
(journeys.menu). Offered only when it works right now: the number is
connected, messaging is on, and at least one journey has something to do.
"""

from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import BusinessModuleState, MessagingChannel

LIVE = ("enabled", "ready", "active")


def wa_link(number: str, text: str = "menu") -> str:
    digits = "".join(ch for ch in number if ch.isdigit())
    return f"https://wa.me/{digits}?text={quote(text)}"


async def whatsapp_entry(session: AsyncSession, business_id: uuid.UUID) -> dict[str, Any] | None:
    states = {m: s for m, s in (await session.execute(select(
        BusinessModuleState.module_id, BusinessModuleState.activation_state).where(
        BusinessModuleState.business_id == business_id))).all()}
    if states.get("messaging") not in LIVE:
        return None
    channel = (await session.execute(select(MessagingChannel).where(
        MessagingChannel.business_id == business_id, MessagingChannel.status == "connected"))).scalars().first()
    if channel is None or not channel.display_phone:
        return None
    does = [k for k, module in (("order", "orders"), ("book", "bookings"), ("enquire", "leads"))
            if states.get(module) in LIVE]
    if not does:
        return None
    label = {"order": "Order on WhatsApp", "book": "Book on WhatsApp"}.get(does[0], "Ask us on WhatsApp")
    if states.get("ledger") in LIVE or states.get("invoicing") in LIVE:
        does.append("dues")
    return {"number": channel.display_phone, "href": wa_link(channel.display_phone), "label": label,
            "journeys": does, "test_number": channel.provider == "sandbox"}
