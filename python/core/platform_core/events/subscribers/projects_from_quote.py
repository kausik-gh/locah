"""Projects takes an accepted quote handed to it (locah.quote.conversion.v1).

Quotes never inserts the project; it publishes `quote.conversion_requested`.
Projects decides the record: `ProjectService.create_from_quote`, which is one
project per quote through the unique `source_quote_id`, so a replay returns
the project that exists.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.events.registry import EventContext, subscribe
from platform_core.models import Business


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "projects.from_quote", "quote.conversion_requested",
    description="An accepted quote handed to Projects becomes its project, once",
)
async def project_from_quote(session: AsyncSession, event: EventContext) -> None:
    if event.payload.get("target") != "project":
        return
    from platform_core.services.project import ProjectService

    business_id = event.require_business_id()
    owner = (await session.execute(select(Business.primary_owner_identity_id).where(
        Business.id == business_id))).scalar_one()
    await ProjectService.create_from_quote(
        session, business_id=business_id, quote_id=event.require_uuid("quote_id"),
        actor_id=uuid.UUID(str(owner)), correlation_id=event.correlation_id or str(event.event_id))
