"""Expiry alerts for batches (Capability Universe §15.1 "expiry alerts").

A batch received with an expiry date schedules the `inventory.expiry` ladder;
each step tells whoever may see stock at that location, and stops by itself
once the batch is sold out or written off.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.automation import AutomationEngine, StepOutcome, step_handler
from platform_core.automation.engine import DueStep
from platform_core.events.registry import EventContext, subscribe
from platform_core.events.subscribers.automation_triggers import _module_on
from platform_core.models import InventoryBatch, Offering
from platform_core.permissions import INVENTORY_READ
from platform_core.services.notification import NotificationService
from platform_core.stock.service import StockService, display_quantity


@subscribe(  # type: ignore[untyped-decorator, unused-ignore]
    "inventory.expiry_alerts", "inventory.received",
    description="Schedule expiry alerts for a batch received with an expiry date",
)
async def schedule(session: AsyncSession, event: EventContext) -> None:
    business_id = event.require_business_id()
    raw_batch, raw_expiry = event.payload.get("batch_id"), event.payload.get("expires_on")
    if not raw_batch or not raw_expiry:
        return
    if not await _module_on(session, business_id, "inventory"):
        return
    batch = await session.get(InventoryBatch, uuid.UUID(str(raw_batch)))
    if batch is None or batch.business_id != business_id or batch.expires_on is None:
        return
    await AutomationEngine.schedule(session, business_id, ladder_key="inventory.expiry", entity_id=batch.id,
                                    anchor=StockService.expiry_anchor(batch.expires_on),
                                    period_key=batch.expires_on.isoformat(),
                                    context={"batch_code": batch.batch_code}, now=datetime.now(timezone.utc))


@step_handler("inventory.expiry")  # type: ignore[untyped-decorator, unused-ignore]
async def alert(session: AsyncSession, step: DueStep) -> StepOutcome:
    batch = await session.get(InventoryBatch, step.entity_id)
    if batch is None or batch.business_id != step.business_id:
        return StepOutcome("skipped", "The batch no longer exists")
    if batch.status != "active" or batch.quantity_on_hand <= 0:
        return StepOutcome("skipped", "The batch is sold out or written off")
    if batch.expires_on is None or batch.expires_on.isoformat() != step.period_key:
        return StepOutcome("skipped", "The expiry date changed")
    if not await _module_on(session, step.business_id, "inventory"):
        return StepOutcome("skipped", "Stock is switched off")
    offering = await session.get(Offering, batch.offering_id)
    title = offering.title if offering else "An item"
    qty = display_quantity(batch.quantity_on_hand, offering.stock_unit if offering else "piece")
    expired = batch.expires_on <= date.today()
    await NotificationService.fan_out(
        session, business_id=step.business_id, notification_type="inventory.expiry",
        title=(f"{title} batch {batch.batch_code} expires today" if expired
               else f"{title} batch {batch.batch_code} expires on {batch.expires_on:%d %b %Y}"),
        body=f"{qty} left in this batch. Sell it first, return it to the supplier, or write it off.",
        required_permission=INVENTORY_READ, severity="warning", resource_type="inventory_batch",
        resource_id=batch.id, location_id=batch.location_id,
    )
    return StepOutcome("done", f"Told the team about batch {batch.batch_code} ({batch.expires_on.isoformat()})")
