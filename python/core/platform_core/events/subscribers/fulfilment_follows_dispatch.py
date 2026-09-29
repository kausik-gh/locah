"""The fulfilment record follows what dispatch actually did.

Order = the sale. Fulfilment = the customer's pickup/delivery choice and the
record they track. Dispatch = the execution (Capability Universe §13). Dispatch
never edits the fulfilment record; Fulfilment listens to dispatch's real state
changes and walks its own record along its legal transitions, so its genuine
`fulfilment.*` events drive the customer's messages and tracking page. The
customer hears "on the way" only after dispatch reached out_for_delivery.
Replays are no-ops: a record already at (or past) the target is left alone.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.events.registry import EventContext, subscribe
from platform_core.models import Business, FulfilmentJob

_PATH = ("pending", "preparing", "ready", "out_for_delivery", "delivered")
_TARGET = {"dispatch.picked_up": "ready", "dispatch.out_for_delivery": "out_for_delivery",
           "dispatch.delivered": "delivered", "dispatch.failed": "failed"}
_DONE = frozenset({"delivered", "failed", "cancelled"})


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "fulfilment.follows_dispatch",
    "dispatch.picked_up", "dispatch.out_for_delivery", "dispatch.delivered", "dispatch.failed",
    description="Move the customer's delivery record to where the delivery really is",
)
async def follow_dispatch(session: AsyncSession, event: EventContext) -> None:
    from platform_core.services.fulfilment import FulfilmentService

    business_id = event.require_business_id()
    job_id, dispatch_id = event.payload.get("job_id"), event.payload.get("dispatch_job_id")
    if not job_id or job_id == dispatch_id:
        return  # an execution with no fulfilment record behind it
    job = (await session.execute(select(FulfilmentJob).where(
        FulfilmentJob.business_id == business_id, FulfilmentJob.id == uuid.UUID(str(job_id)))
        .with_for_update())).scalars().first()
    if job is None or job.status in _DONE:
        return
    owner = (await session.execute(select(Business.primary_owner_identity_id).where(
        Business.id == business_id))).scalar_one()
    target = _TARGET[event.event_type]

    async def move(status: str, reason: str | None = None) -> None:
        await FulfilmentService.transition_status(
            session, business_id=business_id, job_id=job.id, actor_id=uuid.UUID(str(owner)),
            correlation_id=event.correlation_id or str(event.event_id),
            payload={"status": status, "reason": reason})

    if target == "failed":
        await move("failed", str(event.payload.get("reason") or "The delivery could not be completed"))
        return
    path = [s for s in _PATH if not (job.mode == "pickup" and s == "out_for_delivery")]
    if job.status not in path or target not in path or path.index(job.status) >= path.index(target):
        return
    for status in path[path.index(job.status) + 1: path.index(target) + 1]:
        await move(status)
