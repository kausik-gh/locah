"""Buying, recipes, expenses, connectors, documents and donations.

One business, one stock record, one payment truth. This package does not
write inventory quantities itself: a goods receipt calls StockService.receive,
and a recipe consumption calls InventoryService.adjust_stock. Replaying the
same receipt or consumption key does not move stock again.

A counter-offer is its own row. It changes the purchase order only when the
buyer accepts it.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, PermissionDenied, ValidationError
from platform_core.procurement.demand import explain, explode_recipe, net_requirement, round_to_supplier
from platform_core.procurement.payable import ledger_posting_intent
from platform_core.services.inventory import InventoryService
from platform_core.services.outbox import OutboxService
from platform_core.stock.service import StockService

_OPEN_PO = ("sent", "acknowledged", "dispatched")


def _need(permissions: set[str] | None, permission: str) -> None:
    if permissions is not None and permission not in permissions:
        raise PermissionDenied(permission)


async def _as(session: AsyncSession, business_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.current_business_id', :bid, true)"),
        {"bid": str(business_id)},
    )


def _row(result: Any) -> dict[str, Any] | None:
    mapping = result.mappings().first()
    return dict(mapping) if mapping else None


def _rows(result: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in result.mappings().all()]


class SupplyService:
    @staticmethod
    async def create_supplier(
        session: AsyncSession,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        payload: dict[str, Any],
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        _need(permissions, "procurement.create")
        await _as(session, business_id)
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ValidationError("Supplier name is required")
        connection = payload.get("connection") or "off_network"
        if connection not in ("locah", "off_network"):
            raise ValidationError("Connection must be locah or off_network")
        linked = payload.get("linked_business_id")
        row = _row(await session.execute(
            text(
                """
                INSERT INTO procurement_suppliers (
                    business_id, name, contact_name, phone, email, connection,
                    linked_business_id, payment_terms, credit_days, preferred
                ) VALUES (
                    :business_id, :name, :contact_name, :phone, :email, :connection,
                    :linked, :terms, :credit_days, :preferred
                )
                RETURNING id, name, connection, linked_business_id, credit_days, preferred
                """
            ),
            {
                "business_id": business_id,
                "name": name,
                "contact_name": payload.get("contact_name"),
                "phone": payload.get("phone"),
                "email": payload.get("email"),
                "connection": connection,
                "linked": uuid.UUID(str(linked)) if linked else None,
                "terms": payload.get("payment_terms"),
                "credit_days": int(payload.get("credit_days") or 0),
                "preferred": bool(payload.get("preferred")),
            },
        ))
        assert row is not None
        return row

    @staticmethod
    async def map_item(
        session: AsyncSession,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        payload: dict[str, Any],
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        _need(permissions, "procurement.create")
        await _as(session, business_id)
        row = _row(await session.execute(
            text(
                """
                INSERT INTO procurement_supplier_items (
                    business_id, supplier_id, offering_id, supplier_sku, buy_unit,
                    pack_size, moq, lead_time_days, unit_price_paise, preferred
                ) VALUES (
                    :business_id, :supplier_id, :offering_id, :sku, :buy_unit,
                    :pack_size, :moq, :lead_time_days, :price, :preferred
                )
                RETURNING id, supplier_id, offering_id, pack_size, moq, unit_price_paise
                """
            ),
            {
                "business_id": business_id,
                "supplier_id": uuid.UUID(str(payload["supplier_id"])),
                "offering_id": uuid.UUID(str(payload["offering_id"])),
                "sku": payload.get("supplier_sku"),
                "buy_unit": payload.get("buy_unit"),
                "pack_size": int(payload.get("pack_size") or 1),
                "moq": int(payload.get("moq") or 1),
                "lead_time_days": int(payload.get("lead_time_days") or 0),
                "price": int(payload.get("unit_price_paise") or 0),
                "preferred": bool(payload.get("preferred", True)),
            },
        ))
        assert row is not None
        return row

    @staticmethod
    async def agree_price(
        session: AsyncSession,
        business_id: uuid.UUID,
        payload: dict[str, Any],
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        _need(permissions, "procurement.cost")
        await _as(session, business_id)
        row = _row(await session.execute(
            text(
                """
                INSERT INTO procurement_price_agreements (
                    business_id, supplier_item_id, unit_price_paise, pack_size, moq,
                    credit_days, effective_from, effective_to
                ) VALUES (
                    :business_id, :item, :price, :pack, :moq, :credit, :start, :end
                )
                RETURNING id, unit_price_paise, effective_from
                """
            ),
            {
                "business_id": business_id,
                "item": uuid.UUID(str(payload["supplier_item_id"])),
                "price": int(payload["unit_price_paise"]),
                "pack": int(payload.get("pack_size") or 1),
                "moq": int(payload.get("moq") or 1),
                "credit": int(payload.get("credit_days") or 0),
                "start": payload.get("effective_from") or date.today(),
                "end": payload.get("effective_to"),
            },
        ))
        assert row is not None
        return row

    @staticmethod
    async def plan_buy(
        session: AsyncSession,
        business_id: uuid.UUID,
        offering_id: uuid.UUID,
        *,
        demand: int,
        supplier_item_id: uuid.UUID | None,
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        """Show the arithmetic. Does not create a purchase order."""
        _need(permissions, "procurement.read")
        await _as(session, business_id)
        stock = _row(await session.execute(
            text(
                """
                SELECT COALESCE(SUM(GREATEST(quantity_on_hand - quantity_reserved, 0)), 0) AS usable,
                       COALESCE(MAX(low_stock_threshold), 0) AS safety
                FROM inventory_records
                WHERE business_id = :business_id AND offering_id = :offering_id
                """
            ),
            {"business_id": business_id, "offering_id": offering_id},
        ))
        inbound_row = _row(await session.execute(
            text(
                """
                SELECT COALESCE(SUM(l.quantity), 0) AS ordered
                FROM procurement_purchase_order_lines l
                JOIN procurement_purchase_orders p ON p.id = l.purchase_order_id
                WHERE p.business_id = :business_id
                  AND l.offering_id = :offering_id
                  AND p.status IN ('sent', 'acknowledged', 'dispatched')
                """
            ),
            {"business_id": business_id, "offering_id": offering_id},
        ))
        received_row = _row(await session.execute(
            text(
                """
                SELECT COALESCE(SUM(gl.received_quantity), 0) AS received
                FROM procurement_goods_receipt_lines gl
                JOIN procurement_goods_receipts g ON g.id = gl.receipt_id
                JOIN procurement_purchase_orders p ON p.id = g.purchase_order_id
                WHERE gl.business_id = :business_id
                  AND gl.offering_id = :offering_id
                  AND p.status IN ('sent', 'acknowledged', 'dispatched', 'received')
                """
            ),
            {"business_id": business_id, "offering_id": offering_id},
        ))
        usable = int(stock["usable"]) if stock else 0
        safety = int(stock["safety"]) if stock else 0
        inbound = max(0, int(inbound_row["ordered"] if inbound_row else 0) - int(received_row["received"] if received_row else 0))
        pack, moq, price = 1, 1, 0
        if supplier_item_id is not None:
            item = _row(await session.execute(
                text(
                    """
                    SELECT pack_size, moq, unit_price_paise
                    FROM procurement_supplier_items
                    WHERE business_id = :business_id AND id = :item
                    """
                ),
                {"business_id": business_id, "item": supplier_item_id},
            ))
            if item is None:
                raise ValidationError("That supplier item is not on this business")
            agreement = _row(await session.execute(
                text(
                    """
                    SELECT unit_price_paise, pack_size, moq
                    FROM procurement_price_agreements
                    WHERE business_id = :business_id AND supplier_item_id = :item
                      AND effective_from <= CURRENT_DATE
                      AND (effective_to IS NULL OR effective_to >= CURRENT_DATE)
                    ORDER BY effective_from DESC
                    LIMIT 1
                    """
                ),
                {"business_id": business_id, "item": supplier_item_id},
            ))
            pack = int((agreement or item)["pack_size"])
            moq = int((agreement or item)["moq"])
            price = int((agreement or item)["unit_price_paise"])
        net = net_requirement(demand=demand, safety=safety, usable=usable, inbound=inbound)
        buy = round_to_supplier(net=net, pack_size=pack, moq=moq)
        return {
            "demand": demand,
            "usable": usable,
            "safety": safety,
            "inbound": inbound,
            "net": net,
            "buy": buy,
            "pack_size": pack,
            "moq": moq,
            "unit_price_paise": price,
            "explanation": explain(
                demand=demand, safety=safety, usable=usable, inbound=inbound,
                net=net, buy=buy, pack_size=pack, moq=moq,
            ),
        }

    @staticmethod
    async def create_requisition(
        session: AsyncSession,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        payload: dict[str, Any],
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        _need(permissions, "procurement.create")
        await _as(session, business_id)
        plan = await SupplyService.plan_buy(
            session, business_id, uuid.UUID(str(payload["offering_id"])),
            demand=int(payload["demand"]),
            supplier_item_id=uuid.UUID(str(payload["supplier_item_id"])) if payload.get("supplier_item_id") else None,
            permissions=None,
        )
        if plan["buy"] <= 0:
            raise ValidationError("Nothing to buy: usable stock and inbound cover the demand", details=plan)
        header = _row(await session.execute(
            text(
                """
                INSERT INTO procurement_requisitions (
                    business_id, location_id, source, explanation, provenance, created_by
                ) VALUES (
                    :business_id, :location_id, :source, :explanation, CAST(:provenance AS jsonb), :actor
                )
                RETURNING id, status, explanation
                """
            ),
            {
                "business_id": business_id,
                "location_id": uuid.UUID(str(payload["location_id"])) if payload.get("location_id") else None,
                "source": payload.get("source") or "demand",
                "explanation": plan["explanation"],
                "provenance": json.dumps(plan),
                "actor": actor_id,
            },
        ))
        assert header is not None
        await session.execute(
            text(
                """
                INSERT INTO procurement_requisition_lines (
                    business_id, requisition_id, offering_id, supplier_id, quantity,
                    demand_quantity, usable_on_hand, confirmed_inbound, safety_stock
                ) VALUES (
                    :business_id, :requisition_id, :offering_id, :supplier_id, :quantity,
                    :demand, :usable, :inbound, :safety
                )
                """
            ),
            {
                "business_id": business_id,
                "requisition_id": header["id"],
                "offering_id": uuid.UUID(str(payload["offering_id"])),
                "supplier_id": uuid.UUID(str(payload["supplier_id"])) if payload.get("supplier_id") else None,
                "quantity": plan["buy"],
                "demand": plan["demand"],
                "usable": plan["usable"],
                "inbound": plan["inbound"],
                "safety": plan["safety"],
            },
        )
        await OutboxService.publish(
            session, event_type="procurement.requisition.created", business_id=business_id,
            payload={"requisition_id": str(header["id"]), "buy": plan["buy"]},
        )
        return {**header, "plan": plan}

    @staticmethod
    async def create_purchase_order(
        session: AsyncSession,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        payload: dict[str, Any],
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        """Pin the price that is current now. Later agreements do not rewrite it."""
        _need(permissions, "procurement.create")
        await _as(session, business_id)
        requisition_id = uuid.UUID(str(payload["requisition_id"]))
        line = _row(await session.execute(
            text(
                """
                SELECT offering_id, supplier_id, quantity
                FROM procurement_requisition_lines
                WHERE business_id = :business_id AND requisition_id = :requisition_id
                """
            ),
            {"business_id": business_id, "requisition_id": requisition_id},
        ))
        if line is None:
            raise ValidationError("Requisition has no line")
        price = int(payload.get("unit_price_paise") or 0)
        if payload.get("supplier_item_id"):
            agreed = _row(await session.execute(
                text(
                    """
                    SELECT a.unit_price_paise
                    FROM procurement_price_agreements a
                    WHERE a.business_id = :business_id
                      AND a.supplier_item_id = :item
                      AND a.effective_from <= CURRENT_DATE
                      AND (a.effective_to IS NULL OR a.effective_to >= CURRENT_DATE)
                    ORDER BY a.effective_from DESC
                    LIMIT 1
                    """
                ),
                {"business_id": business_id, "item": uuid.UUID(str(payload["supplier_item_id"]))},
            ))
            if agreed:
                price = int(agreed["unit_price_paise"])
            else:
                item = _row(await session.execute(
                    text("SELECT unit_price_paise FROM procurement_supplier_items WHERE id = :item AND business_id = :business_id"),
                    {"item": uuid.UUID(str(payload["supplier_item_id"])), "business_id": business_id},
                ))
                if item:
                    price = int(item["unit_price_paise"])
        reference = payload.get("reference") or f"PO-{uuid.uuid4().hex[:8].upper()}"
        po = _row(await session.execute(
            text(
                """
                INSERT INTO procurement_purchase_orders (
                    business_id, supplier_id, requisition_id, reference, created_by
                ) VALUES (
                    :business_id, :supplier_id, :requisition_id, :reference, :actor
                )
                RETURNING id, reference, status
                """
            ),
            {
                "business_id": business_id,
                "supplier_id": line["supplier_id"],
                "requisition_id": requisition_id,
                "reference": reference,
                "actor": actor_id,
            },
        ))
        assert po is not None
        await session.execute(
            text(
                """
                INSERT INTO procurement_purchase_order_lines (
                    business_id, purchase_order_id, offering_id, quantity, unit_price_paise
                ) VALUES (
                    :business_id, :po, :offering_id, :quantity, :price
                )
                """
            ),
            {
                "business_id": business_id,
                "po": po["id"],
                "offering_id": line["offering_id"],
                "quantity": line["quantity"],
                "price": price,
            },
        )
        await session.execute(
            text("UPDATE procurement_requisitions SET status = 'converted', updated_at = now() WHERE id = :id"),
            {"id": requisition_id},
        )
        await SupplyService._event(session, business_id, po["id"], actor_id, None, "draft", "prepared")
        return po

    @staticmethod
    async def approve_purchase_order(
        session: AsyncSession,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        _need(permissions, "procurement.approve")
        return await SupplyService._move(session, business_id, actor_id, purchase_order_id, "draft", "approved", "procurement.po.approved", "approved")

    @staticmethod
    async def send_purchase_order(
        session: AsyncSession,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        *,
        buyer_label: str,
        item_label: str,
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        _need(permissions, "procurement.approve")
        po = await SupplyService._move(
            session, business_id, actor_id, purchase_order_id, "approved", "sent",
            "procurement.po.sent", "sent",
        )
        supplier = _row(await session.execute(
            text(
                """
                SELECT connection, linked_business_id FROM procurement_suppliers
                WHERE id = :id AND business_id = :business_id
                """
            ),
            {"id": po["supplier_id"], "business_id": business_id},
        ))
        lines = _rows(await session.execute(
            text(
                """
                SELECT quantity, unit_price_paise FROM procurement_purchase_order_lines
                WHERE purchase_order_id = :po AND business_id = :business_id
                """
            ),
            {"po": purchase_order_id, "business_id": business_id},
        ))
        if supplier and supplier["connection"] == "locah" and supplier["linked_business_id"]:
            payload_lines = [
                {"item_label": item_label, "quantity": int(line["quantity"]), "unit_price_paise": int(line["unit_price_paise"])}
                for line in lines
            ]
            await session.execute(
                text(
                    """
                    SELECT procurement_post_trade(
                        CAST(:sender AS uuid), CAST(:recipient AS uuid), CAST(:po AS uuid),
                        :buyer, CAST(:lines AS jsonb), :key
                    )
                    """
                ),
                {
                    "sender": str(business_id),
                    "recipient": str(supplier["linked_business_id"]),
                    "po": str(purchase_order_id),
                    "buyer": buyer_label,
                    "lines": json.dumps(payload_lines),
                    "key": f"po:{purchase_order_id}",
                },
            )
            await OutboxService.publish(
                session, event_type="trade.message.received", business_id=supplier["linked_business_id"],
                payload={"source_po_id": str(purchase_order_id), "buyer_label": buyer_label},
            )
        return po

    @staticmethod
    async def counter(
        session: AsyncSession,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        payload: dict[str, Any],
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        """Record a proposal. The accepted line quantity and price stay as they are."""
        _need(permissions, "procurement.create")
        await _as(session, business_id)
        po = await SupplyService._po(session, business_id, purchase_order_id)
        if po["status"] not in ("sent", "acknowledged"):
            raise ConflictError("A counter-offer is only for a purchase order the supplier has been sent")
        line = _row(await session.execute(
            text(
                """
                SELECT id, quantity, unit_price_paise FROM procurement_purchase_order_lines
                WHERE purchase_order_id = :po AND business_id = :business_id
                ORDER BY created_at LIMIT 1
                """
            ),
            {"po": purchase_order_id, "business_id": business_id},
        ))
        assert line is not None
        before = {"quantity": int(line["quantity"]), "unit_price_paise": int(line["unit_price_paise"])}
        counter_row = _row(await session.execute(
            text(
                """
                INSERT INTO procurement_po_counters (
                    business_id, purchase_order_id, line_id, proposed_quantity, proposed_price_paise
                ) VALUES (
                    :business_id, :po, :line, :qty, :price
                )
                RETURNING id, proposed_quantity, proposed_price_paise, status
                """
            ),
            {
                "business_id": business_id,
                "po": purchase_order_id,
                "line": line["id"],
                "qty": int(payload["proposed_quantity"]),
                "price": int(payload["proposed_price_paise"]),
            },
        ))
        await session.execute(
            text("UPDATE procurement_purchase_orders SET status = 'countered', updated_at = now() WHERE id = :id"),
            {"id": purchase_order_id},
        )
        await SupplyService._event(session, business_id, purchase_order_id, actor_id, po["status"], "countered", "supplier proposed a change")
        await OutboxService.publish(
            session, event_type="procurement.po.countered", business_id=business_id,
            payload={"purchase_order_id": str(purchase_order_id)},
        )
        still = _row(await session.execute(
            text("SELECT quantity, unit_price_paise FROM procurement_purchase_order_lines WHERE id = :id"),
            {"id": line["id"]},
        ))
        assert still is not None
        if int(still["quantity"]) != before["quantity"] or int(still["unit_price_paise"]) != before["unit_price_paise"]:
            raise ConflictError("Counter-offer changed the accepted line")
        return {"counter": counter_row, "line": dict(still)}

    @staticmethod
    async def decide_counter(
        session: AsyncSession,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        counter_id: uuid.UUID,
        *,
        accept: bool,
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        _need(permissions, "procurement.approve")
        await _as(session, business_id)
        counter_row = _row(await session.execute(
            text(
                """
                SELECT id, purchase_order_id, line_id, proposed_quantity, proposed_price_paise, status
                FROM procurement_po_counters
                WHERE id = :id AND business_id = :business_id
                """
            ),
            {"id": counter_id, "business_id": business_id},
        ))
        if counter_row is None or counter_row["status"] != "pending":
            raise ConflictError("That counter-offer is not waiting for a decision")
        if accept:
            await session.execute(
                text(
                    """
                    UPDATE procurement_purchase_order_lines
                    SET quantity = :qty, unit_price_paise = :price
                    WHERE id = :line AND business_id = :business_id
                    """
                ),
                {
                    "qty": counter_row["proposed_quantity"],
                    "price": counter_row["proposed_price_paise"],
                    "line": counter_row["line_id"],
                    "business_id": business_id,
                },
            )
            next_status = "acknowledged"
            decision = "accepted"
        else:
            next_status = "sent"
            decision = "declined"
        await session.execute(
            text("UPDATE procurement_po_counters SET status = :decision WHERE id = :id"),
            {"decision": decision, "id": counter_id},
        )
        await session.execute(
            text("UPDATE procurement_purchase_orders SET status = :status, updated_at = now() WHERE id = :id"),
            {"status": next_status, "id": counter_row["purchase_order_id"]},
        )
        await SupplyService._event(
            session, business_id, counter_row["purchase_order_id"], actor_id, "countered", next_status,
            "buyer accepted the change" if accept else "buyer kept the original order",
        )
        return {"status": next_status, "decision": decision}

    @staticmethod
    async def receive_goods(
        session: AsyncSession,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        payload: dict[str, Any],
        permissions: set[str] | None,
        allowed_locations: list[uuid.UUID] | None,
    ) -> dict[str, Any]:
        """Actual delivery. A repeated idempotency key returns the first receipt."""
        _need(permissions, "procurement.receive")
        await _as(session, business_id)
        key = str(payload.get("idempotency_key") or "").strip()
        if not key:
            raise ValidationError("A receipt needs an idempotency key")
        existing = _row(await session.execute(
            text(
                """
                SELECT id, purchase_order_id FROM procurement_goods_receipts
                WHERE business_id = :business_id AND idempotency_key = :key
                """
            ),
            {"business_id": business_id, "key": key},
        ))
        if existing:
            return {"id": existing["id"], "replayed": True}
        po = await SupplyService._po(session, business_id, purchase_order_id)
        if po["status"] not in ("sent", "acknowledged", "dispatched", "received"):
            raise ConflictError("Stock moves when goods arrive against a sent purchase order, not before")
        received = int(payload["received_quantity"])
        damaged = int(payload.get("damaged_quantity") or 0)
        if received < 0 or damaged < 0:
            raise ValidationError("Quantities cannot be negative")
        good = received
        line = _row(await session.execute(
            text(
                """
                SELECT offering_id, quantity, unit_price_paise
                FROM procurement_purchase_order_lines
                WHERE purchase_order_id = :po AND business_id = :business_id
                ORDER BY created_at LIMIT 1
                """
            ),
            {"po": purchase_order_id, "business_id": business_id},
        ))
        assert line is not None
        receipt = _row(await session.execute(
            text(
                """
                INSERT INTO procurement_goods_receipts (
                    business_id, purchase_order_id, location_id, idempotency_key, notes, created_by
                ) VALUES (
                    :business_id, :po, :location_id, :key, :notes, :actor
                )
                RETURNING id
                """
            ),
            {
                "business_id": business_id,
                "po": purchase_order_id,
                "location_id": uuid.UUID(str(payload["location_id"])),
                "key": key,
                "notes": payload.get("notes"),
                "actor": actor_id,
            },
        ))
        assert receipt is not None
        await session.execute(
            text(
                """
                INSERT INTO procurement_goods_receipt_lines (
                    business_id, receipt_id, offering_id, ordered_quantity, received_quantity,
                    damaged_quantity, batch_code, expires_on
                ) VALUES (
                    :business_id, :receipt, :offering, :ordered, :received, :damaged, :batch, :expires
                )
                """
            ),
            {
                "business_id": business_id,
                "receipt": receipt["id"],
                "offering": line["offering_id"],
                "ordered": line["quantity"],
                "received": received,
                "damaged": damaged,
                "batch": payload.get("batch_code"),
                "expires": payload.get("expires_on"),
            },
        )
        if good > 0:
            await StockService.receive(
                session, business_id, actor_id,
                {
                    "location_id": payload["location_id"],
                    "offering_id": line["offering_id"],
                    "quantity": good,
                    "total_cost_paise": good * int(line["unit_price_paise"]),
                    "batch_code": payload.get("batch_code"),
                    "expires_on": payload.get("expires_on"),
                },
                allowed_locations,
            )
        total = _row(await session.execute(
            text(
                """
                SELECT COALESCE(SUM(received_quantity), 0) AS received
                FROM procurement_goods_receipt_lines
                WHERE business_id = :business_id AND receipt_id IN (
                    SELECT id FROM procurement_goods_receipts WHERE purchase_order_id = :po
                )
                """
            ),
            {"business_id": business_id, "po": purchase_order_id},
        ))
        complete = int(total["received"] if total else 0) >= int(line["quantity"])
        await session.execute(
            text("UPDATE procurement_purchase_orders SET status = :status, updated_at = now() WHERE id = :id"),
            {"status": "received" if complete else "dispatched", "id": purchase_order_id},
        )
        await SupplyService._event(session, business_id, purchase_order_id, actor_id, po["status"], "received" if complete else "dispatched", "goods received")
        await OutboxService.publish(
            session, event_type="procurement.goods_received", business_id=business_id,
            payload={"receipt_id": str(receipt["id"]), "quantity": good, "replayed": False},
        )
        return {"id": receipt["id"], "replayed": False, "stocked": good, "complete": complete}

    @staticmethod
    async def create_bill(
        session: AsyncSession,
        business_id: uuid.UUID,
        payload: dict[str, Any],
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        _need(permissions, "procurement.cost")
        await _as(session, business_id)
        row = _row(await session.execute(
            text(
                """
                INSERT INTO procurement_supplier_bills (
                    business_id, supplier_id, purchase_order_id, receipt_id,
                    invoice_reference, amount_paise, tax_paise, due_on
                ) VALUES (
                    :business_id, :supplier, :po, :receipt, :invoice, :amount, :tax, :due
                )
                RETURNING id, invoice_reference, amount_paise, status
                """
            ),
            {
                "business_id": business_id,
                "supplier": uuid.UUID(str(payload["supplier_id"])),
                "po": uuid.UUID(str(payload["purchase_order_id"])) if payload.get("purchase_order_id") else None,
                "receipt": uuid.UUID(str(payload["receipt_id"])) if payload.get("receipt_id") else None,
                "invoice": payload["invoice_reference"],
                "amount": int(payload["amount_paise"]),
                "tax": int(payload.get("tax_paise") or 0),
                "due": payload.get("due_on"),
            },
        ))
        assert row is not None
        await OutboxService.publish(
            session, event_type="supplier.bill.created", business_id=business_id,
            payload={"bill_id": str(row["id"]), "amount_paise": int(row["amount_paise"])},
        )
        row["supplier_id"] = payload["supplier_id"]
        row["ledger_intent"] = ledger_posting_intent(row)
        if row["status"] == "paid":
            raise ConflictError("A supplier bill is not paid until the shared ledger records the payment")
        return row

    @staticmethod
    async def settle_bill(
        session: AsyncSession,
        business_id: uuid.UUID,
        bill_id: uuid.UUID,
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        """Refuse a local paid flag. Settlement belongs to the shared ledger."""
        _need(permissions, "procurement.cost")
        await _as(session, business_id)
        raise ConflictError(
            "Record the payment on the shared ledger as payment_made. Buying does not mark a bill paid.",
            details={"bill_id": str(bill_id), "ledger_kind": "payment_made"},
        )

    @staticmethod
    async def save_bom(
        session: AsyncSession,
        business_id: uuid.UUID,
        payload: dict[str, Any],
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        _need(permissions, "procurement.create")
        await _as(session, business_id)
        bom = _row(await session.execute(
            text(
                """
                INSERT INTO recipe_boms (business_id, offering_id, name)
                VALUES (:business_id, :offering, :name)
                ON CONFLICT (business_id, offering_id) DO UPDATE SET name = EXCLUDED.name
                RETURNING id, name
                """
            ),
            {
                "business_id": business_id,
                "offering": uuid.UUID(str(payload["offering_id"])),
                "name": payload.get("name") or "Recipe",
            },
        ))
        assert bom is not None
        # One recipe per dish: saving again replaces its lines. Past consumptions
        # keep what they used (their event carries the exploded components).
        await session.execute(
            text("DELETE FROM recipe_bom_lines WHERE business_id = :business_id AND bom_id = :bom"),
            {"business_id": business_id, "bom": bom["id"]},
        )
        for line in payload.get("lines") or []:
            await session.execute(
                text(
                    """
                    INSERT INTO recipe_bom_lines (
                        business_id, bom_id, component_offering_id, quantity_per, yield_ratio
                    ) VALUES (
                        :business_id, :bom, :component, :per, :yield_ratio
                    )
                    """
                ),
                {
                    "business_id": business_id,
                    "bom": bom["id"],
                    "component": uuid.UUID(str(line["component_offering_id"])),
                    "per": line["quantity_per"],
                    "yield_ratio": line.get("yield_ratio") or 1,
                },
            )
        return bom

    @staticmethod
    async def list_boms(
        session: AsyncSession,
        business_id: uuid.UUID,
        permissions: set[str] | None,
    ) -> list[dict[str, Any]]:
        _need(permissions, "procurement.read")
        await _as(session, business_id)
        rows = _rows(await session.execute(
            text(
                """
                SELECT b.id AS bom_id, b.name, b.offering_id, o.title AS dish,
                       l.component_offering_id, c.title AS component, c.stock_unit,
                       l.quantity_per, l.yield_ratio
                FROM recipe_boms b
                JOIN offerings_catalog_offerings o ON o.id = b.offering_id
                LEFT JOIN recipe_bom_lines l ON l.bom_id = b.id AND l.business_id = b.business_id
                LEFT JOIN offerings_catalog_offerings c ON c.id = l.component_offering_id
                WHERE b.business_id = :business_id
                ORDER BY o.title, c.title
                """
            ),
            {"business_id": business_id},
        ))
        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            bom = out.setdefault(str(row["bom_id"]), {
                "id": str(row["bom_id"]), "name": row["name"], "offering_id": str(row["offering_id"]),
                "dish": row["dish"], "lines": [],
            })
            if row["component_offering_id"] is not None:
                bom["lines"].append({
                    "component_offering_id": str(row["component_offering_id"]), "component": row["component"],
                    "unit": row["stock_unit"], "quantity_per": float(row["quantity_per"]),
                    "yield_ratio": float(row["yield_ratio"]),
                })
        return list(out.values())

    @staticmethod
    async def consume_for_sale(
        session: AsyncSession,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        payload: dict[str, Any],
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        """Finished quantity becomes component movements. The same key consumes once."""
        _need(permissions, "procurement.create")
        await _as(session, business_id)
        key = str(payload["idempotency_key"])
        already = _row(await session.execute(
            text("SELECT id FROM recipe_consumptions WHERE business_id = :business_id AND idempotency_key = :key"),
            {"business_id": business_id, "key": key},
        ))
        if already:
            return {"replayed": True, "id": already["id"]}
        lines = _rows(await session.execute(
            text(
                """
                SELECT l.component_offering_id, l.quantity_per, l.yield_ratio
                FROM recipe_bom_lines l
                JOIN recipe_boms b ON b.id = l.bom_id
                WHERE b.business_id = :business_id AND b.offering_id = :offering
                """
            ),
            {"business_id": business_id, "offering": uuid.UUID(str(payload["offering_id"]))},
        ))
        exploded = explode_recipe(int(payload["quantity"]), [
            {
                "component_offering_id": row["component_offering_id"],
                "quantity_per": row["quantity_per"],
                "yield_ratio": row["yield_ratio"],
            }
            for row in lines
        ])
        location_id = uuid.UUID(str(payload["location_id"]))
        for component in exploded:
            if component["demand"] <= 0:
                continue
            record = _row(await session.execute(
                text(
                    """
                    SELECT version FROM inventory_records
                    WHERE business_id = :business_id AND offering_id = :offering AND location_id = :location
                    """
                ),
                {
                    "business_id": business_id,
                    "offering": uuid.UUID(component["component_offering_id"]),
                    "location": location_id,
                },
            ))
            await InventoryService.adjust_stock(
                session,
                business_id=business_id,
                actor_id=actor_id,
                correlation_id=str(uuid.uuid5(uuid.NAMESPACE_OID, key)),
                expected_version=int(record["version"]) if record else None,
                payload={
                    "offering_id": component["component_offering_id"],
                    "location_id": str(location_id),
                    "quantity_delta": -int(component["demand"]),
                    "movement_type": "adjustment",
                    "reason": f"recipe consumption {key}",
                },
            )
        stored = _row(await session.execute(
            text(
                """
                INSERT INTO recipe_consumptions (business_id, idempotency_key, offering_id, quantity)
                VALUES (:business_id, :key, :offering, :quantity)
                RETURNING id
                """
            ),
            {
                "business_id": business_id,
                "key": key,
                "offering": uuid.UUID(str(payload["offering_id"])),
                "quantity": int(payload["quantity"]),
            },
        ))
        assert stored is not None
        await OutboxService.publish(
            session, event_type="recipe.consumed", business_id=business_id,
            payload={"consumption_id": str(stored["id"]), "components": exploded},
        )
        return {"replayed": False, "id": stored["id"], "components": exploded}

    @staticmethod
    async def incoming_demand(
        session: AsyncSession,
        business_id: uuid.UUID,
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        _need(permissions, "procurement.read")
        await _as(session, business_id)
        rows = _rows(await session.execute(
            text(
                """
                SELECT buyer_label, item_label, quantity, unit_price_paise, source_business_id
                FROM procurement_incoming_demands
                WHERE business_id = :business_id AND status = 'incoming'
                ORDER BY created_at
                """
            ),
            {"business_id": business_id},
        ))
        totals: dict[str, int] = {}
        for row in rows:
            totals[row["item_label"]] = totals.get(row["item_label"], 0) + int(row["quantity"])
        return {"lines": rows, "totals": totals}

    @staticmethod
    async def record_expense(
        session: AsyncSession,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        payload: dict[str, Any],
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        _need(permissions, "expenses.write")
        await _as(session, business_id)
        category = payload.get("category")
        category_id = None
        if category:
            found = _row(await session.execute(
                text(
                    """
                    INSERT INTO expenses_categories (business_id, name)
                    VALUES (:business_id, :name)
                    ON CONFLICT (business_id, name) DO UPDATE SET name = EXCLUDED.name
                    RETURNING id
                    """
                ),
                {"business_id": business_id, "name": category},
            ))
            category_id = found["id"] if found else None
        row = _row(await session.execute(
            text(
                """
                INSERT INTO expenses_records (
                    business_id, category_id, payee, spent_on, amount_paise, tax_paise,
                    method, notes, petty_cash, created_by
                ) VALUES (
                    :business_id, :category, :payee, :spent_on, :amount, :tax,
                    :method, :notes, :petty, :actor
                )
                RETURNING id, amount_paise, method
                """
            ),
            {
                "business_id": business_id,
                "category": category_id,
                "payee": payload.get("payee"),
                "spent_on": payload.get("spent_on") or date.today(),
                "amount": int(payload["amount_paise"]),
                "tax": int(payload.get("tax_paise") or 0),
                "method": payload.get("method") or "cash",
                "notes": payload.get("notes"),
                "petty": bool(payload.get("petty_cash")),
                "actor": actor_id,
            },
        ))
        assert row is not None
        await OutboxService.publish(
            session, event_type="expense.created", business_id=business_id,
            payload={"expense_id": str(row["id"]), "amount_paise": int(row["amount_paise"])},
        )
        return row

    @staticmethod
    async def expense_totals(
        session: AsyncSession,
        business_id: uuid.UUID,
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        _need(permissions, "expenses.read")
        await _as(session, business_id)
        row = _row(await session.execute(
            text(
                """
                SELECT COALESCE(SUM(amount_paise), 0) AS total,
                       COALESCE(SUM(amount_paise) FILTER (WHERE method = 'cash'), 0) AS cash,
                       COALESCE(SUM(amount_paise) FILTER (WHERE method <> 'cash'), 0) AS bank
                FROM expenses_records
                WHERE business_id = :business_id
                """
            ),
            {"business_id": business_id},
        ))
        assert row is not None
        return {"total_paise": int(row["total"]), "cash_paise": int(row["cash"]), "bank_paise": int(row["bank"])}

    @staticmethod
    async def pair_connector(
        session: AsyncSession,
        business_id: uuid.UUID,
        payload: dict[str, Any],
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        _need(permissions, "connectors.manage")
        await _as(session, business_id)
        authority = payload.get("authority") or "locah"
        if authority not in ("locah", "external", "bidirectional"):
            raise ValidationError("Authority must be locah, external, or bidirectional")
        row = _row(await session.execute(
            text(
                """
                INSERT INTO connector_connections (
                    business_id, provider, state, direction, authority, secret_ref
                ) VALUES (
                    :business_id, :provider, 'paired', :direction, :authority, :secret
                )
                ON CONFLICT (business_id, provider) DO UPDATE SET
                    direction = EXCLUDED.direction,
                    authority = EXCLUDED.authority,
                    state = 'paired',
                    updated_at = now()
                RETURNING id, provider, authority, state
                """
            ),
            {
                "business_id": business_id,
                "provider": payload["provider"],
                "direction": payload.get("direction") or "export",
                "authority": authority,
                "secret": payload.get("secret_ref"),
            },
        ))
        assert row is not None
        return row

    @staticmethod
    async def run_connector(
        session: AsyncSession,
        business_id: uuid.UUID,
        connection_id: uuid.UUID,
        *,
        idempotency_key: str,
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        """Fixture sync. A repeated key does not create a second run."""
        _need(permissions, "connectors.manage")
        await _as(session, business_id)
        existing = _row(await session.execute(
            text(
                """
                SELECT id, status FROM connector_sync_runs
                WHERE connection_id = :connection AND idempotency_key = :key
                """
            ),
            {"connection": connection_id, "key": idempotency_key},
        ))
        if existing:
            return {"id": existing["id"], "replayed": True, "status": existing["status"]}
        connection = _row(await session.execute(
            text("SELECT authority FROM connector_connections WHERE id = :id AND business_id = :business_id"),
            {"id": connection_id, "business_id": business_id},
        ))
        if connection is None:
            raise ValidationError("Connector is not on this business")
        if connection["authority"] == "bidirectional":
            raise ConflictError("Bidirectional sync needs an explicit conflict policy before it can run")
        row = _row(await session.execute(
            text(
                """
                INSERT INTO connector_sync_runs (business_id, connection_id, idempotency_key, status, detail)
                VALUES (:business_id, :connection, :key, 'ok', :detail)
                RETURNING id, status
                """
            ),
            {
                "business_id": business_id,
                "connection": connection_id,
                "key": idempotency_key,
                "detail": f"fixture export under {connection['authority']} authority",
            },
        ))
        assert row is not None
        await session.execute(
            text("UPDATE connector_connections SET last_success_at = now(), last_error = NULL WHERE id = :id"),
            {"id": connection_id},
        )
        await OutboxService.publish(
            session, event_type="connector.sync.completed", business_id=business_id,
            payload={"run_id": str(row["id"]), "authority": connection["authority"]},
        )
        return {"id": row["id"], "replayed": False, "status": "ok", "authority": connection["authority"]}

    @staticmethod
    async def map_connector(
        session: AsyncSession,
        business_id: uuid.UUID,
        connection_id: uuid.UUID,
        payload: dict[str, Any],
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        _need(permissions, "connectors.manage")
        await _as(session, business_id)
        row = _row(await session.execute(
            text(
                """
                INSERT INTO connector_mappings (
                    business_id, connection_id, family, locah_key, external_key
                ) VALUES (
                    :business_id, :connection, :family, :locah_key, :external_key
                )
                RETURNING id, family, locah_key, external_key
                """
            ),
            {
                "business_id": business_id,
                "connection": connection_id,
                "family": payload["family"],
                "locah_key": payload["locah_key"],
                "external_key": payload["external_key"],
            },
        ))
        assert row is not None
        return row

    @staticmethod
    async def record_document(
        session: AsyncSession,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        payload: dict[str, Any],
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        _need(permissions, "documents.write")
        await _as(session, business_id)
        row = _row(await session.execute(
            text(
                """
                INSERT INTO documents_records (
                    business_id, document_type, title, storage_key, related_type, related_id,
                    expires_on, created_by
                ) VALUES (
                    :business_id, :kind, :title, :storage, :related_type, :related_id, :expires, :actor
                )
                RETURNING id, title, verification_status
                """
            ),
            {
                "business_id": business_id,
                "kind": payload["document_type"],
                "title": payload["title"],
                "storage": payload.get("storage_key"),
                "related_type": payload.get("related_type"),
                "related_id": uuid.UUID(str(payload["related_id"])) if payload.get("related_id") else None,
                "expires": payload.get("expires_on"),
                "actor": actor_id,
            },
        ))
        assert row is not None
        await OutboxService.publish(
            session, event_type="document.recorded", business_id=business_id,
            payload={"document_id": str(row["id"])},
        )
        return row

    @staticmethod
    async def open_cause(
        session: AsyncSession,
        business_id: uuid.UUID,
        name: str,
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        _need(permissions, "donations.write")
        await _as(session, business_id)
        row = _row(await session.execute(
            text(
                """
                INSERT INTO donations_causes (business_id, name)
                VALUES (:business_id, :name)
                RETURNING id, name, status
                """
            ),
            {"business_id": business_id, "name": name},
        ))
        assert row is not None
        return row

    @staticmethod
    async def receive_donation(
        session: AsyncSession,
        business_id: uuid.UUID,
        payload: dict[str, Any],
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        """A gift linked to a shared payment id. This does not collect money."""
        _need(permissions, "donations.write")
        await _as(session, business_id)
        receipt = payload.get("receipt_reference") or f"DN-{uuid.uuid4().hex[:8].upper()}"
        row = _row(await session.execute(
            text(
                """
                INSERT INTO donations_gifts (
                    business_id, cause_id, donor_name, amount_paise, payment_id, kind, receipt_reference
                ) VALUES (
                    :business_id, :cause, :donor, :amount, :payment, :kind, :receipt
                )
                RETURNING id, donor_name, amount_paise, payment_id, receipt_reference
                """
            ),
            {
                "business_id": business_id,
                "cause": uuid.UUID(str(payload["cause_id"])),
                "donor": payload["donor_name"],
                "amount": int(payload["amount_paise"]),
                "payment": uuid.UUID(str(payload["payment_id"])) if payload.get("payment_id") else None,
                "kind": payload.get("kind") or "one_time",
                "receipt": receipt,
            },
        ))
        assert row is not None
        await OutboxService.publish(
            session, event_type="donation.received", business_id=business_id,
            payload={"gift_id": str(row["id"]), "payment_id": str(row["payment_id"]) if row["payment_id"] else None},
        )
        return row

    @staticmethod
    async def supplier_scorecard(
        session: AsyncSession,
        business_id: uuid.UUID,
        supplier_id: uuid.UUID,
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        _need(permissions, "supplier.read")
        await _as(session, business_id)
        ordered = _row(await session.execute(
            text(
                """
                SELECT COALESCE(SUM(l.quantity), 0) AS quantity
                FROM procurement_purchase_order_lines l
                JOIN procurement_purchase_orders p ON p.id = l.purchase_order_id
                WHERE p.business_id = :business_id AND p.supplier_id = :supplier
                  AND p.status NOT IN ('draft', 'declined')
                """
            ),
            {"business_id": business_id, "supplier": supplier_id},
        ))
        received = _row(await session.execute(
            text(
                """
                SELECT COALESCE(SUM(gl.received_quantity), 0) AS quantity
                FROM procurement_goods_receipt_lines gl
                JOIN procurement_goods_receipts g ON g.id = gl.receipt_id
                JOIN procurement_purchase_orders p ON p.id = g.purchase_order_id
                WHERE p.business_id = :business_id AND p.supplier_id = :supplier
                """
            ),
            {"business_id": business_id, "supplier": supplier_id},
        ))
        ordered_qty = int(ordered["quantity"] if ordered else 0)
        received_qty = int(received["quantity"] if received else 0)
        fill = (received_qty / ordered_qty) if ordered_qty else None
        return {
            "ordered_quantity": ordered_qty,
            "received_quantity": received_qty,
            "fill_rate": fill,
        }

    @staticmethod
    async def list_causes(
        session: AsyncSession,
        business_id: uuid.UUID,
        permissions: set[str] | None,
    ) -> list[dict[str, Any]]:
        _need(permissions, "donations.read")
        await _as(session, business_id)
        return _rows(await session.execute(
            text(
                """
                SELECT id, name, status FROM donations_causes
                WHERE business_id = :business_id ORDER BY created_at DESC
                """
            ),
            {"business_id": business_id},
        ))

    @staticmethod
    async def list_gifts(
        session: AsyncSession,
        business_id: uuid.UUID,
        permissions: set[str] | None,
    ) -> list[dict[str, Any]]:
        _need(permissions, "donations.read")
        await _as(session, business_id)
        return _rows(await session.execute(
            text(
                """
                SELECT g.id, g.donor_name, g.amount_paise, g.receipt_reference, g.kind, c.name AS cause
                FROM donations_gifts g
                JOIN donations_causes c ON c.id = g.cause_id
                WHERE g.business_id = :business_id
                ORDER BY g.created_at DESC
                LIMIT 20
                """
            ),
            {"business_id": business_id},
        ))

    @staticmethod
    async def buying_home(
        session: AsyncSession,
        business_id: uuid.UUID,
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        _need(permissions, "procurement.read")
        await _as(session, business_id)
        counts = _rows(await session.execute(
            text(
                """
                SELECT status, COUNT(*) AS n
                FROM procurement_purchase_orders
                WHERE business_id = :business_id
                GROUP BY status
                """
            ),
            {"business_id": business_id},
        ))
        bills = _row(await session.execute(
            text(
                """
                SELECT COUNT(*) AS n FROM procurement_supplier_bills
                WHERE business_id = :business_id AND status = 'open'
                """
            ),
            {"business_id": business_id},
        ))
        needs = _row(await session.execute(
            text(
                """
                SELECT COUNT(*) AS n FROM procurement_requisitions
                WHERE business_id = :business_id AND status = 'draft'
                """
            ),
            {"business_id": business_id},
        ))
        orders = _rows(await session.execute(
            text(
                """
                SELECT p.id, p.reference, p.status, COALESCE(r.explanation, '') AS explanation,
                       l.quantity AS ordered_quantity,
                       COALESCE(SUM(gl.received_quantity), 0)::int AS received_quantity
                FROM procurement_purchase_orders p
                JOIN procurement_purchase_order_lines l ON l.purchase_order_id = p.id
                LEFT JOIN procurement_requisitions r ON r.id = p.requisition_id
                LEFT JOIN procurement_goods_receipts g ON g.purchase_order_id = p.id
                LEFT JOIN procurement_goods_receipt_lines gl ON gl.receipt_id = g.id
                WHERE p.business_id = :business_id
                  AND p.status IN ('draft', 'sent', 'acknowledged', 'dispatched', 'countered')
                GROUP BY p.id, p.reference, p.status, r.explanation, l.quantity, p.created_at
                ORDER BY p.created_at DESC
                """
            ),
            {"business_id": business_id},
        ))
        requisitions = _rows(await session.execute(
            text(
                """
                SELECT r.id, r.explanation, l.quantity, l.offering_id, l.demand_quantity,
                       l.usable_on_hand, l.confirmed_inbound, l.safety_stock
                FROM procurement_requisitions r
                JOIN procurement_requisition_lines l ON l.requisition_id = r.id
                WHERE r.business_id = :business_id AND r.status = 'draft'
                ORDER BY r.created_at DESC
                """
            ),
            {"business_id": business_id},
        ))
        suppliers = _rows(await session.execute(
            text(
                """
                SELECT id, name FROM procurement_suppliers
                WHERE business_id = :business_id AND status = 'active'
                ORDER BY name
                """
            ),
            {"business_id": business_id},
        ))
        return {
            "purchase_orders": {row["status"]: int(row["n"]) for row in counts},
            "bills_due": int(bills["n"] if bills else 0),
            "needs_buying": int(needs["n"] if needs else 0),
            "orders": orders,
            "requisitions": requisitions,
            "suppliers": suppliers,
        }

    @staticmethod
    async def prepare_order(
        session: AsyncSession,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        payload: dict[str, Any],
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        """Plan the requirement, keep the explanation, and leave a draft purchase order."""
        _need(permissions, "procurement.create")
        supplier_id = uuid.UUID(str(payload["supplier_id"]))
        offering_id = uuid.UUID(str(payload["offering_id"]))
        item = _row(await session.execute(
            text(
                """
                SELECT id FROM procurement_supplier_items
                WHERE business_id = :business_id AND supplier_id = :supplier AND offering_id = :offering
                """
            ),
            {"business_id": business_id, "supplier": supplier_id, "offering": offering_id},
        ))
        if item is None:
            item = await SupplyService.map_item(
                session, business_id, actor_id,
                {
                    "supplier_id": supplier_id,
                    "offering_id": offering_id,
                    "pack_size": int(payload.get("pack_size") or 1),
                    "moq": int(payload.get("moq") or 1),
                    "unit_price_paise": int(payload.get("unit_price_paise") or 0),
                },
                None,
            )
        requisition = await SupplyService.create_requisition(
            session, business_id, actor_id,
            {
                "offering_id": offering_id,
                "supplier_id": supplier_id,
                "supplier_item_id": item["id"],
                "demand": int(payload["demand"]),
                "location_id": payload.get("location_id"),
                "source": "demand",
            },
            None,
        )
        return {
            "requisition_id": requisition["id"],
            "explanation": requisition["explanation"],
            "plan": requisition["plan"],
        }

    @staticmethod
    async def approve_requisition(
        session: AsyncSession,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        requisition_id: uuid.UUID,
        *,
        buyer_label: str,
        item_label: str,
        permissions: set[str] | None,
    ) -> dict[str, Any]:
        _need(permissions, "procurement.approve")
        line = _row(await session.execute(
            text(
                """
                SELECT l.offering_id, l.supplier_id
                FROM procurement_requisition_lines l
                JOIN procurement_requisitions r ON r.id = l.requisition_id
                WHERE r.business_id = :business_id AND r.id = :requisition AND r.status = 'draft'
                """
            ),
            {"business_id": business_id, "requisition": requisition_id},
        ))
        if line is None:
            raise ConflictError("That requirement is not waiting for approval")
        item = _row(await session.execute(
            text(
                """
                SELECT id FROM procurement_supplier_items
                WHERE business_id = :business_id AND supplier_id = :supplier AND offering_id = :offering
                """
            ),
            {"business_id": business_id, "supplier": line["supplier_id"], "offering": line["offering_id"]},
        ))
        po = await SupplyService.create_purchase_order(
            session, business_id, actor_id,
            {"requisition_id": requisition_id, "supplier_item_id": item["id"] if item else None},
            None,
        )
        await SupplyService.approve_purchase_order(session, business_id, actor_id, po["id"], None)
        await SupplyService.send_purchase_order(
            session, business_id, actor_id, po["id"],
            buyer_label=buyer_label, item_label=item_label, permissions=None,
        )
        return {"purchase_order_id": po["id"], "status": "sent"}

    @staticmethod
    async def _po(session: AsyncSession, business_id: uuid.UUID, purchase_order_id: uuid.UUID) -> dict[str, Any]:
        row = _row(await session.execute(
            text("SELECT id, status, supplier_id FROM procurement_purchase_orders WHERE id = :id AND business_id = :business_id"),
            {"id": purchase_order_id, "business_id": business_id},
        ))
        if row is None:
            raise ValidationError("Purchase order not found")
        return row

    @staticmethod
    async def _move(
        session: AsyncSession,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        expected: str,
        nxt: str,
        event_type: str,
        reason: str,
    ) -> dict[str, Any]:
        await _as(session, business_id)
        po = await SupplyService._po(session, business_id, purchase_order_id)
        if po["status"] != expected:
            raise ConflictError(f"Purchase order is {po['status']}, so it cannot move to {nxt}")
        await session.execute(
            text("UPDATE procurement_purchase_orders SET status = :status, updated_at = now() WHERE id = :id"),
            {"status": nxt, "id": purchase_order_id},
        )
        await SupplyService._event(session, business_id, purchase_order_id, actor_id, expected, nxt, reason)
        await OutboxService.publish(
            session, event_type=event_type, business_id=business_id,
            payload={"purchase_order_id": str(purchase_order_id), "status": nxt},
        )
        po["status"] = nxt
        return po

    @staticmethod
    async def _event(
        session: AsyncSession,
        business_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        actor_id: uuid.UUID,
        frm: str | None,
        to: str,
        reason: str,
    ) -> None:
        await session.execute(
            text(
                """
                INSERT INTO procurement_po_events (
                    business_id, purchase_order_id, actor_id, from_status, to_status, reason
                ) VALUES (
                    :business_id, :po, :actor, :frm, :to, :reason
                )
                """
            ),
            {
                "business_id": business_id,
                "po": purchase_order_id,
                "actor": actor_id,
                "frm": frm,
                "to": to,
                "reason": reason,
            },
        )
