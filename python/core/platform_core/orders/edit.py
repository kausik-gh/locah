"""Changing an order after it was placed (FR-OR-18; Founder: Orders — "Order
edits must revalidate price, stock, tax, delivery, payment difference and
preserve audit history"; MD §12.3).

Staff change what the customer asked to change — a quantity, a line removed,
an item added — while the order is still open and not yet billed. The change
goes through the same steps as placing: added lines are priced from today's
catalogue (lines the customer already agreed keep their price), stock is
reserved or released for the difference, tax and the total are worked out
again by the billing engine, a dated order's day, notice, daily limit and
advance are checked again, and the money already taken is compared with the
new total — more to collect, or a refund due in Payments. The customer's
agreement is recorded, and the before/after is kept in the order's history
and the audit.

A preview runs exactly the same code inside a savepoint that is rolled back,
so what the owner sees before saving is what saving does.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ValidationError
from platform_core.models import InvoicingDocument, OrderLineItem, OrderStatusHistory, PaymentAttempt
from platform_core.resolvers.order_resolver import OrderResolver
from platform_core.services.audit import AuditService
from platform_core.services.inventory import InventoryService
from platform_core.services.order_calculation import calculate_line, calculate_order_totals
from platform_core.services.outbox import OutboxService

EDITABLE = ("pending", "accepted", "preparing")
DELIVERY = "Delivery fee"
PAID = ("succeeded", "partially_refunded")


class _Preview(Exception):
    """Raised inside the savepoint to roll a preview back after measuring it."""

    def __init__(self, result: dict[str, Any]) -> None:
        super().__init__("preview")
        self.result = result


def _bad(message: str, fld: str = "lines") -> ValidationError:
    return ValidationError(message, details={"field": fld, "errors": [{"field": fld, "message": message}]})


def _summary(before: list[tuple[str, int]], after: list[OrderLineItem]) -> list[str]:
    """What changed, in words: "added 1 × Buns", "Plum cake: 1 → 2", "removed Murukku"."""
    old = {title: q for title, q in before if title != DELIVERY}
    new = {ln.title: ln.quantity for ln in after if ln.title != DELIVERY}
    out = []
    for title, q in new.items():
        if title not in old:
            out.append(f"added {q} × {title}")
        elif old[title] != q:
            out.append(f"{title}: {old[title]} → {q}")
    out += [f"removed {title}" for title in old if title not in new]
    return out


async def change(session: AsyncSession, *, business_id: uuid.UUID, order_id: uuid.UUID, actor_id: uuid.UUID,
                 correlation_id: str, lines: list[dict[str, Any]], reason: str | None, customer_agreed: bool,
                 expected_version: int | None, preview: bool) -> dict[str, Any]:
    from platform_core.services.order import OrderService
    from platform_core.services.payment_collect import PaymentCollectService

    order = await OrderResolver.resolve(session, business_id=business_id, order_id=order_id)
    if order.status not in EDITABLE:
        raise ConflictError("This order can no longer be changed — it is "
                            + {"ready": "ready", "completed": "completed", "cancelled": "cancelled",
                               "rejected": "declined"}.get(order.status, order.status))
    if expected_version is not None and order.version != expected_version:
        raise ConflictError("Someone changed this order a moment ago — reload it and try again")
    billed = (await session.execute(select(InvoicingDocument.number).where(
        InvoicingDocument.business_id == business_id, InvoicingDocument.order_id == order.id,
        InvoicingDocument.status == "issued"))).scalars().first()
    if billed:
        raise ConflictError(f"This order is already billed ({billed}) — change it with a credit note or a new bill")
    if not lines:
        raise _bad("An order needs at least one item — cancel it instead")
    if len(lines) > 100:
        raise _bad("At most 100 lines on one order")
    if not preview and not customer_agreed:
        raise _bad("Confirm the customer agreed to this change", "customer_agreed")

    current = await OrderResolver.load_line_items(session, order_id=order.id)
    by_id = {ln.id: ln for ln in current}
    delivery = [ln for ln in current if ln.title == DELIVERY]
    before_detail = OrderResolver.serialize_order_detail(order, line_items=current)
    before_total = Decimal(str(order.total_amount))
    snapshot = [(ln.title, ln.quantity) for ln in current]

    try:
        async with session.begin_nested():
            kept: list[OrderLineItem] = []
            added_or_more = False
            seen: set[uuid.UUID] = set()
            for idx, raw in enumerate(lines):
                try:
                    qty = int(str(raw.get("quantity")))
                except (TypeError, ValueError):
                    raise _bad("Enter a whole number for the quantity", f"lines.{idx}.quantity") from None
                if not 1 <= qty <= 999:
                    raise _bad("Quantities are 1 to 999 — remove the line to take it off", f"lines.{idx}.quantity")
                line_id = raw.get("line_id")
                if line_id:
                    ln = by_id.get(uuid.UUID(str(line_id)))
                    if ln is None or ln.title == DELIVERY or ln.id in seen:
                        raise _bad("That line is not on this order", f"lines.{idx}.line_id")
                    seen.add(ln.id)
                    if qty != ln.quantity:
                        per = (ln.stock_quantity // ln.quantity) if ln.quantity else 1
                        if qty > ln.quantity:
                            added_or_more = True
                        # Agreed lines keep their agreed price; only the quantity changes.
                        t = calculate_line(unit_price=Decimal(str(ln.unit_price)), quantity=qty,
                                           tax_rate=Decimal(str(ln.tax_rate)) if ln.tax_rate is not None else None)
                        ln.quantity = qty
                        ln.stock_quantity = qty * per
                        ln.line_subtotal = float(t["line_subtotal"])
                        ln.line_tax = float(t["line_tax"])
                        ln.line_total = float(t["line_total"])
                    ln.sort_order = idx
                    kept.append(ln)
                else:
                    added_or_more = True
                    item = await OrderService._build_line_item(
                        session, business_id=business_id, order_id=order.id, sort_order=idx,
                        raw={"offering_id": uuid.UUID(str(raw["offering_id"])),
                             "variant_id": uuid.UUID(str(raw["variant_id"])) if raw.get("variant_id") else None,
                             "quantity": qty, "options": raw.get("options") or {}})
                    session.add(item)
                    kept.append(item)
            removed = [ln for ln in current if ln.title != DELIVERY and ln.id not in seen]
            await session.flush()

            # Stock: release what is no longer needed, reserve what is newly needed.
            for ln in removed:
                pending = ln.quantity_reserved - ln.quantity_deducted
                if ln.track_inventory and pending > 0:
                    await InventoryService.release_reservation_for_order(
                        session, business_id=business_id, offering_id=ln.offering_id, location_id=order.location_id,
                        variant_id=ln.variant_id, quantity=pending, actor_id=actor_id, correlation_id=correlation_id,
                        order_id=order.id, reason=f"Order {order.order_number} changed")
                await session.delete(ln)
            for ln in kept:
                if not ln.track_inventory:
                    continue
                delta = ln.stock_quantity - (ln.quantity_reserved or 0)
                if delta > 0:
                    await InventoryService.reserve_for_order(
                        session, business_id=business_id, offering_id=ln.offering_id, location_id=order.location_id,
                        variant_id=ln.variant_id, quantity=delta, actor_id=actor_id, correlation_id=correlation_id,
                        order_id=order.id, reason=f"Order {order.order_number} changed")
                elif delta < 0:
                    await InventoryService.release_reservation_for_order(
                        session, business_id=business_id, offering_id=ln.offering_id, location_id=order.location_id,
                        variant_id=ln.variant_id, quantity=-delta, actor_id=actor_id, correlation_id=correlation_id,
                        order_id=order.id, reason=f"Order {order.order_number} changed")
                ln.quantity_reserved = ln.stock_quantity
            await session.flush()

            # Delivery: the charge for the order's address under today's zones.
            delivery_note = await _recheck_delivery(session, business_id, order, delivery)
            await session.flush()
            delivery = [ln for ln in delivery if ln in session]  # a line whose charge fell to ₹0 was removed

            # Tax and total again, by the same engine as the bill.
            all_lines = kept + delivery
            from platform_core.services.invoicing_pricing import price_order

            if not await price_order(session, business_id=business_id, order=order, lines=all_lines,
                                     discount=Decimal(str(order.discount_amount or 0)), place_of_supply=None):
                totals = calculate_order_totals([OrderResolver.serialize_line_item(i) for i in all_lines],
                                                discount_amount=Decimal(str(order.discount_amount or 0)))
                order.subtotal = float(totals["subtotal"])
                order.tax_amount = float(totals["tax_amount"])
                order.total_amount = float(totals["total_amount"])

            # A dated order: the day, notice, daily limit and advance, checked again for what was added.
            if order.due_at is not None and added_or_more:
                await OrderService._apply_preorder(session, business_id=business_id, order=order,
                                                   line_items=list(kept), requested=order.due_at.isoformat())

            new_total = Decimal(str(order.total_amount))
            paid = await PaymentCollectService.net_paid(session, business_id, "order", order.id)
            difference = new_total - paid
            result: dict[str, Any] = {
                "before_total": float(before_total), "total": float(new_total), "paid": float(paid),
                "to_collect": float(difference) if difference > 0 else 0.0,
                "refund_due": float(-difference) if difference < 0 else 0.0,
                "tax_amount": float(order.tax_amount or 0),
                "advance_amount": float(order.advance_amount) if order.advance_amount is not None else None,
                "lines": [OrderResolver.serialize_line_item(i) for i in sorted(all_lines, key=lambda x: x.sort_order)],
                "changes": _summary(snapshot, all_lines) + ([delivery_note] if delivery_note else []),
            }
            if preview:
                raise _Preview(result)

            # The cash still expected on the order follows the new balance (nothing left → no cash expected).
            expected = update(PaymentAttempt).where(
                PaymentAttempt.business_id == business_id, PaymentAttempt.source_type == "order",
                PaymentAttempt.source_id == order.id, PaymentAttempt.deleted_at.is_(None),
                PaymentAttempt.status.in_(("pending", "pending_offline")), PaymentAttempt.payment_method == "cod")
            await session.execute(expected.values(amount=float(difference), status="pending_offline")
                                  if difference > 0 else expected.values(status="cancelled"))
            if paid > 0:
                order.payment_status = "paid" if paid >= new_total else "partially_paid"
            if difference < 0:
                # More was taken than the order now costs: Payments shows the refund to make.
                await session.execute(update(PaymentAttempt).where(
                    PaymentAttempt.business_id == business_id, PaymentAttempt.source_type == "order",
                    PaymentAttempt.source_id == order.id, PaymentAttempt.deleted_at.is_(None),
                    PaymentAttempt.status.in_(PAID), PaymentAttempt.attention.is_(None)).values(attention="refund_due"))
            order.version += 1
            words = "; ".join(result["changes"]) or "no change to the items"
            session.add(OrderStatusHistory(business_id=business_id, order_id=order.id, from_status=order.status,
                                           to_status=order.status, actor_identity_id=actor_id,
                                           reason=f"Changed: {words}" + (f" — {reason.strip()}" if reason else "")))
            await session.flush()
            after = await OrderResolver.load_line_items(session, order_id=order.id)
            after_detail = OrderResolver.serialize_order_detail(order, line_items=after)
            await AuditService.record(session, event_type="order.changed", actor_identity_id=actor_id,
                                      actor_context="business", business_id=business_id, resource_type="order",
                                      resource_id=order.id, action="changed", before_state=before_detail,
                                      after_state={**after_detail, "customer_agreed": True,
                                                   "reason": (reason or "").strip()[:300] or None})
            await OutboxService.publish(session, event_type="order.updated", business_id=business_id,
                                        correlation_id=correlation_id,
                                        payload={"business_id": str(business_id), "order_id": str(order.id),
                                                 "after": after_detail, "changes": result["changes"]})
    except _Preview as p:
        await session.refresh(order)
        return {**p.result, "preview": True}
    return {**result, "preview": False, "version": order.version}


async def _recheck_delivery(session: AsyncSession, business_id: uuid.UUID, order: Any,
                            lines: list[OrderLineItem]) -> str | None:
    """A delivered order's charge under the zones as they are now; returns what changed, in words."""
    from platform_core.models import FulfilmentJob
    from platform_core.services.fulfilment import FulfilmentService

    job = (await session.execute(select(FulfilmentJob).where(
        FulfilmentJob.business_id == business_id, FulfilmentJob.order_id == order.id))).scalars().first()
    if job is None or job.mode != "delivery" or not isinstance(job.delivery_address, dict):
        return None
    zone, charge = await FulfilmentService.match_zone(session, business_id=business_id, address=job.delivery_address)
    if zone is None:
        return None  # zones changed and no longer cover it: the placed charge stands; the owner decides
    current = Decimal(str(lines[0].unit_price)) if lines else Decimal("0")
    if charge == current:
        return None
    if lines and charge > 0:
        t = calculate_line(unit_price=charge, quantity=1, tax_rate=None)
        lines[0].unit_price = float(charge)
        lines[0].line_subtotal, lines[0].line_tax, lines[0].line_total = (
            float(t["line_subtotal"]), float(t["line_tax"]), float(t["line_total"]))
    elif lines:
        await session.delete(lines[0])
    elif charge > 0:
        from platform_core.services.order import OrderService

        fee = await FulfilmentService._ensure_delivery_fee_offering(session, business_id=business_id)
        item = await OrderService._build_line_item(session, business_id=business_id, order_id=order.id, sort_order=999,
                                                   raw={"offering_id": fee, "quantity": 1, "unit_price": float(charge)})
        session.add(item)
        lines.append(item)
    return f"delivery ₹{current:,.0f} → ₹{charge:,.0f}"
