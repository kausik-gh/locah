"""Structured WhatsApp journeys (Capability Universe §12.3, P1 column).

The router (services.messaging.MessagingService.route) offers every message
here before handing it to a person. Journeys — order, book, enquire, pay,
track, reorder, change/cancel with buttons and lists — are packet P1-08;
until they exist nothing is handled here, so every message reaches a person.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import MessagingConversation


async def handle(session: AsyncSession, conv: MessagingConversation, kind: str, body: str,
                 extra: dict[str, Any]) -> bool:
    """True when a structured journey answered the message."""
    return False
