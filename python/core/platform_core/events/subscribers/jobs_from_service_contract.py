"""Jobs does the covered AMC visit Memberships asks for.

Memberships owns the service contract and its coverage; when a covered visit
falls due it publishes `membership.service_visit_due`. Jobs owns the work: it
opens one job card per visit (source `service_contract`, the visit id opaque),
which the unique (source_type, source_id) holds to once under replay.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.events.registry import EventContext, subscribe
from platform_core.jobs.models import JobCard
from platform_core.models import Business, BusinessLocation

IST = ZoneInfo("Asia/Kolkata")


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "jobs.from_service_contract", "membership.service_visit_due",
    description="A covered AMC visit that falls due becomes one job card",
)
async def job_for_visit(session: AsyncSession, event: EventContext) -> None:
    from platform_core.events.subscribers.automation_triggers import _module_on
    from platform_core.jobs.service import JobService

    business_id = event.require_business_id()
    if not await _module_on(session, business_id, "jobs"):
        return
    visit_id = event.require_uuid("visit_id")
    exists = (await session.execute(select(JobCard.id).where(
        JobCard.business_id == business_id, JobCard.source_type == "service_contract",
        JobCard.source_id == visit_id))).scalar_one_or_none()
    if exists is not None:
        return
    owner = (await session.execute(select(Business.primary_owner_identity_id).where(
        Business.id == business_id))).scalar_one()
    location = (await session.execute(select(BusinessLocation.id).where(
        BusinessLocation.business_id == business_id, BusinessLocation.is_primary.is_(True),
        BusinessLocation.deleted_at.is_(None)))).scalars().first()
    plan = event.payload.get("plan_name") or "Service contract"
    due = date.fromisoformat(str(event.payload["due_on"]))
    await JobService.create(session, business_id, uuid.UUID(str(owner)),
                            event.correlation_id or str(event.event_id), {
        "title": f"{plan} — covered visit {event.payload.get('seq')}",
        "customer_contact_id": event.require_uuid("customer_contact_id"),
        "location_id": location, "source_type": "service_contract", "source_id": visit_id,
        "scheduled_at": datetime.combine(due, time(10, 0), IST).isoformat(),
    })
