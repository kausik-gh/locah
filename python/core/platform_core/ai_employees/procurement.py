"""Procurement assistant — shortages → draft requisitions; POs only with approval.

* find_shortages (T0): items at or below their reorder point.
* draft_requisition (T1): the same draft the low-stock automation makes —
  sized by the buying planner (pack size, minimum order, inbound), with the
  planner's own explanation. One open reorder requisition per item. Never a
  purchase order.
* request_po_send (T3): an approved purchase order that has not gone to the
  supplier becomes a request in "Needs your approval". It is sent only when
  the owner approves — the owner is the actor, through SupplyService.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.ai_employees.runtime import APPROVERS, AIRuntime, Outcome
from platform_core.exceptions import ValidationError
from platform_core.models import AIAction, AIEmployee


async def shortages(session: AsyncSession, business_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = (await session.execute(text("""
        SELECT r.offering_id, r.location_id, r.quantity_on_hand,
               COALESCE(r.low_stock_threshold, o.low_stock_threshold) AS threshold, o.title
        FROM inventory_records r JOIN offerings_catalog_offerings o ON o.id = r.offering_id
        WHERE r.business_id = :b AND o.deleted_at IS NULL
          AND COALESCE(r.low_stock_threshold, o.low_stock_threshold) IS NOT NULL
          AND r.quantity_on_hand <= COALESCE(r.low_stock_threshold, o.low_stock_threshold)
        ORDER BY o.title"""), {"b": str(business_id)})).mappings().all()
    return [dict(r) for r in rows]


async def _open_requisition(session: AsyncSession, business_id: uuid.UUID, offering_id: Any) -> bool:
    return (await session.execute(text("""
        SELECT 1 FROM procurement_requisitions r JOIN procurement_requisition_lines l ON l.requisition_id = r.id
        WHERE r.business_id = :b AND r.status IN ('draft', 'submitted', 'approved') AND l.offering_id = :o
        LIMIT 1"""), {"b": str(business_id), "o": str(offering_id)})).first() is not None


async def run(session: AsyncSession, business_id: uuid.UUID, *, source: str = "run") -> dict[str, Any]:
    from platform_core.procurement.service import SupplyService

    emp = await AIRuntime.active(session, business_id, "procurement")
    if emp is None:
        return {"ran": False, "reason": "The procurement assistant is off, paused, or AI staff is not switched on"}
    if not await _buying_on(session, business_id):
        return {"ran": False, "reason": "Switch on Buying (procurement) first"}
    cap = int((emp.limits or {}).get("max_drafts_per_run", 10))
    found: list[dict[str, Any]] = []

    async def look() -> Outcome:
        found.extend(await shortages(session, business_id))
        return Outcome(f"{len(found)} item(s) at or below the reorder point")

    await AIRuntime.act(session, emp, "find_shortages", look, input_summary="Stock against reorder points",
                        source=source)
    owner = (await session.execute(text("SELECT primary_owner_identity_id FROM businesses WHERE id = :b"),
                                   {"b": str(business_id)})).scalar()
    drafted = 0
    for row in found[:cap]:
        if await _open_requisition(session, business_id, row["offering_id"]):
            continue

        async def draft(row: dict[str, Any] = row) -> Outcome:
            try:
                made = await SupplyService.create_requisition(
                    session, business_id, owner,
                    {"offering_id": str(row["offering_id"]),
                     "location_id": str(row["location_id"]) if row["location_id"] else None,
                     "demand": max(int(row["threshold"] or 0), 1), "source": "reorder"},
                    permissions=None)
            except ValidationError as exc:
                return Outcome(f"{row['title']}: {exc}", status="done")
            return Outcome(f"Drafted a requisition for {row['title']}: {made.get('explanation') or ''}",
                           status="drafted", related_type="requisition", related_id=uuid.UUID(str(made["id"])))

        action, _ = await AIRuntime.act(
            session, emp, "draft_requisition", draft, source=source,
            input_summary=f"{row['title']}: {row['quantity_on_hand']} left, reorder point {row['threshold']}")
        drafted += action.status == "drafted"
    asked = await _ask_to_send(session, emp, source)
    return {"ran": True, "short": len(found), "drafted": drafted, "po_send_requests": asked}


async def _ask_to_send(session: AsyncSession, emp: AIEmployee, source: str) -> int:
    """Approved POs not yet sent → one approval request each (never sent by the AI)."""
    pos = (await session.execute(text("""
        SELECT p.id, p.reference AS number, s.name AS supplier FROM procurement_purchase_orders p
        LEFT JOIN procurement_suppliers s ON s.id = p.supplier_id
        WHERE p.business_id = :b AND p.status = 'approved' ORDER BY p.created_at"""),
        {"b": str(emp.business_id)})).mappings().all()
    asked = 0
    for po in pos:
        pending = (await session.execute(select(AIAction.id).where(
            AIAction.business_id == emp.business_id, AIAction.tool == "request_po_send",
            AIAction.related_id == po["id"], AIAction.approval_status == "pending"))).first()
        if pending is not None:
            continue

        async def never() -> Outcome:  # T3: the runtime never runs this without approval
            raise AssertionError("request_po_send runs only on approval")

        await AIRuntime.act(session, emp, "request_po_send", never, source=source,
                            input_summary=f"Send purchase order {po['number'] or ''} to {po['supplier'] or 'the supplier'}",
                            related=("purchase_order", po["id"]), pending_args={"purchase_order_id": str(po["id"])})
        asked += 1
    return asked


async def _approve_po_send(session: AsyncSession, action: AIAction, actor_id: uuid.UUID) -> str:
    from platform_core.procurement.service import SupplyService

    po_id = uuid.UUID(str((action.pending_args or {})["purchase_order_id"]))
    await SupplyService.send_purchase_order(session, action.business_id, actor_id, po_id,
                                            buyer_label="This business", item_label="Item", permissions=None)
    return "You approved it — the purchase order was sent to the supplier"


APPROVERS["request_po_send"] = _approve_po_send


async def _buying_on(session: AsyncSession, business_id: uuid.UUID) -> bool:
    row = (await session.execute(
        text("SELECT activation_state FROM business_module_states WHERE business_id = :b AND module_id = 'procurement'"),
        {"b": str(business_id)})).first()
    return row is not None and row[0] in ("enabled", "ready", "active")
