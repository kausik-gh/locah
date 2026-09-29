"""Supply lane: demand math, purchase flow, tenant isolation.

A purchase order does not change stock. A goods receipt does, once.
A counter-offer does not rewrite the line until the buyer accepts it.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from platform_api.main import app
from platform_core.exceptions import ConflictError, PermissionDenied
from platform_core.procurement.demand import explode_recipe, net_requirement, round_to_supplier
from platform_core.procurement.service import SupplyService
from platform_core.stock.service import StockService
from platform_testing.phase_b import (
    assert_tenant_isolated,
    create_business,
    db_url,
    new_identity,
    primary_location,
    sql,
)

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)


def test_net_requirement_keeps_the_arithmetic() -> None:
    assert net_requirement(demand=100, safety=0, usable=70, inbound=0) == 30
    assert net_requirement(demand=100, safety=10, usable=70, inbound=15) == 25
    assert net_requirement(demand=10, safety=0, usable=70, inbound=0) == 0


def test_pack_and_minimum_order_round_up() -> None:
    assert round_to_supplier(net=25, pack_size=10, moq=1) == 30
    assert round_to_supplier(net=4, pack_size=1, moq=12) == 12
    assert round_to_supplier(net=0, pack_size=10, moq=12) == 0


def test_recipe_turns_finished_demand_into_components() -> None:
    lines = explode_recipe(10, [
        {"component_offering_id": "chicken", "quantity_per": 0.2, "yield_ratio": 1},
        {"component_offering_id": "bread", "quantity_per": 1, "yield_ratio": 0.5},
    ])
    assert lines[0]["demand"] == 2
    assert lines[1]["demand"] == 20


def test_roles_keep_approval_with_the_manager() -> None:
    from platform_core.authorization.role_templates import ROLE_TEMPLATES

    keeper = ROLE_TEMPLATES["store_keeper"].permissions
    assert "procurement.receive" in keeper
    assert "procurement.create" in keeper
    assert "procurement.approve" not in keeper
    assert "procurement.cost" not in keeper
    cashier = ROLE_TEMPLATES["cashier"].permissions
    assert "procurement.approve" not in cashier
    assert "procurement.read" not in cashier
    assert "procurement.approve" in ROLE_TEMPLATES["manager"].permissions
    accountant = ROLE_TEMPLATES["accountant"].permissions
    assert "expenses.write" in accountant
    assert "procurement.cost" in accountant
    assert "procurement.approve" not in accountant
    assert "procurement.receive" not in accountant


def test_supplier_bill_is_not_a_payment() -> None:
    from platform_core.procurement.payable import ledger_posting_intent

    intent = ledger_posting_intent({"id": "bill-1", "supplier_id": "sup-1", "amount_paise": 500, "invoice_reference": "INV"})
    assert intent["kind"] == "purchase"
    assert intent["settlement_kind"] == "payment_made"
    assert intent["status_until_settled"] == "open"


def test_aggregate_keeps_each_buyer() -> None:
    buyers = {"A": 40, "B": 35, "C": 25}
    total = sum(buyers.values())
    shortage = net_requirement(demand=total, safety=0, usable=70, inbound=0)
    assert total == 100
    assert shortage == 30
    assert buyers["A"] == 40


@DB
def test_supplier_rows_are_isolated() -> None:
    async def insert(session: AsyncSession, business_id: uuid.UUID) -> None:
        await session.execute(
            text("INSERT INTO procurement_suppliers (business_id, name) VALUES (:b, :n)"),
            {"b": business_id, "n": f"Supplier {business_id.hex[:6]}"},
        )

    asyncio.run(assert_tenant_isolated("procurement_suppliers", insert))


@DB
def test_expenses_are_isolated() -> None:
    async def insert(session: AsyncSession, business_id: uuid.UUID) -> None:
        await session.execute(
            text(
                """
                INSERT INTO expenses_records (business_id, spent_on, amount_paise, method)
                VALUES (:b, CURRENT_DATE, 100, 'cash')
                """
            ),
            {"b": business_id},
        )

    asyncio.run(assert_tenant_isolated("expenses_records", insert))


@DB
def test_buy_receive_and_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    _owner, headers = new_identity(monkeypatch)
    buyer = create_business(client, headers, name=f"Buyer {uuid.uuid4().hex[:6]}", modules=("offerings-catalog", "inventory"))
    supplier_biz = create_business(client, headers, name=f"Mill {uuid.uuid4().hex[:6]}")
    location = primary_location(client, headers, buyer)
    item = client.post(
        f"/v1/platform/businesses/{buyer}/products",
        json={"title": "Rice", "status": "active", "offering_type": "product", "track_inventory": True, "price_amount": 5000},
        headers=headers,
    )
    assert item.status_code == 200, item.text
    offering = item.json()["data"]["id"]
    actor = _owner

    async def _run() -> dict[str, Any]:
        engine = create_async_engine(db_url(), poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as session:
                await StockService.receive(
                    session, uuid.UUID(buyer), actor,
                    {"location_id": location, "offering_id": offering, "quantity": 70, "total_cost_paise": 7000},
                    None,
                )
                supplier = await SupplyService.create_supplier(
                    session, uuid.UUID(buyer), actor,
                    {
                        "name": "Upstream mill",
                        "connection": "locah",
                        "linked_business_id": supplier_biz,
                        "credit_days": 7,
                    },
                    None,
                )
                mapped = await SupplyService.map_item(
                    session, uuid.UUID(buyer), actor,
                    {
                        "supplier_id": supplier["id"],
                        "offering_id": offering,
                        "pack_size": 10,
                        "moq": 1,
                        "unit_price_paise": 1000,
                    },
                    None,
                )
                await SupplyService.agree_price(
                    session, uuid.UUID(buyer),
                    {"supplier_item_id": mapped["id"], "unit_price_paise": 1000, "pack_size": 10, "moq": 1},
                    None,
                )
                plan = await SupplyService.plan_buy(
                    session, uuid.UUID(buyer), uuid.UUID(offering),
                    demand=100, supplier_item_id=mapped["id"], permissions=None,
                )
                requisition = await SupplyService.create_requisition(
                    session, uuid.UUID(buyer), actor,
                    {
                        "offering_id": offering,
                        "supplier_id": supplier["id"],
                        "supplier_item_id": mapped["id"],
                        "demand": 100,
                        "location_id": location,
                        "source": "demand",
                    },
                    None,
                )
                po = await SupplyService.create_purchase_order(
                    session, uuid.UUID(buyer), actor,
                    {"requisition_id": requisition["id"], "supplier_item_id": mapped["id"]},
                    None,
                )
                await SupplyService.agree_price(
                    session, uuid.UUID(buyer),
                    {"supplier_item_id": mapped["id"], "unit_price_paise": 2500, "pack_size": 10, "moq": 1},
                    None,
                )
                with pytest.raises(ConflictError):
                    await SupplyService.receive_goods(
                        session, uuid.UUID(buyer), actor, po["id"],
                        {"location_id": location, "received_quantity": 10, "idempotency_key": "too-soon"},
                        None, None,
                    )
                await SupplyService.approve_purchase_order(session, uuid.UUID(buyer), actor, po["id"], None)
                with pytest.raises(PermissionDenied):
                    await SupplyService.approve_purchase_order(
                        session, uuid.UUID(buyer), actor, po["id"], {"procurement.read"},
                    )
                await SupplyService.send_purchase_order(
                    session, uuid.UUID(buyer), actor, po["id"],
                    buyer_label="Buyer shop", item_label="Rice", permissions=None,
                )
                incoming = await SupplyService.incoming_demand(session, uuid.UUID(supplier_biz), None)
                countered = await SupplyService.counter(
                    session, uuid.UUID(buyer), actor, po["id"],
                    {"proposed_quantity": 99, "proposed_price_paise": 1},
                    None,
                )
                declined = await SupplyService.decide_counter(
                    session, uuid.UUID(buyer), actor, countered["counter"]["id"],
                    accept=False, permissions=None,
                )

                async def on_hand() -> int:
                    value = (await session.execute(
                        text("SELECT quantity_on_hand FROM inventory_records WHERE offering_id = :o"),
                        {"o": offering},
                    )).scalar()
                    return int(value or 0)

                async def receipt_moves() -> int:
                    value = (await session.execute(
                        text(
                            """
                            SELECT COUNT(*) FROM inventory_movements
                            WHERE offering_id = :o AND movement_type = 'receipt'
                            """
                        ),
                        {"o": offering},
                    )).scalar()
                    return int(value or 0)

                stock_before_receipt = await on_hand()
                first = await SupplyService.receive_goods(
                    session, uuid.UUID(buyer), actor, po["id"],
                    {
                        "location_id": location,
                        "received_quantity": 10,
                        "damaged_quantity": 2,
                        "idempotency_key": "grn-1",
                    },
                    None, None,
                )
                replay = await SupplyService.receive_goods(
                    session, uuid.UUID(buyer), actor, po["id"],
                    {"location_id": location, "received_quantity": 10, "idempotency_key": "grn-1"},
                    None, None,
                )
                stock_after_first = await on_hand()
                moves_after_replay = await receipt_moves()
                bill = await SupplyService.create_bill(
                    session, uuid.UUID(buyer),
                    {
                        "supplier_id": supplier["id"],
                        "purchase_order_id": po["id"],
                        "receipt_id": first["id"],
                        "invoice_reference": "INV-1",
                        "amount_paise": 10000,
                    },
                    None,
                )
                with pytest.raises(ConflictError):
                    await SupplyService.settle_bill(session, uuid.UUID(buyer), bill["id"], None)
                stock_after_bill = await on_hand()
                second = await SupplyService.receive_goods(
                    session, uuid.UUID(buyer), actor, po["id"],
                    {"location_id": location, "received_quantity": 20, "idempotency_key": "grn-2"},
                    None, None,
                )
                stock_after_second = await on_hand()
                moves_after_second = await receipt_moves()
                card = await SupplyService.supplier_scorecard(session, uuid.UUID(buyer), supplier["id"], None)
                expense = await SupplyService.record_expense(
                    session, uuid.UUID(buyer), actor,
                    {"category": "Fuel", "amount_paise": 5000, "method": "cash", "payee": "Pump"},
                    None,
                )
                totals = await SupplyService.expense_totals(session, uuid.UUID(buyer), None)
                other = await SupplyService.expense_totals(session, uuid.UUID(supplier_biz), None)
                cause = await SupplyService.open_cause(session, uuid.UUID(buyer), "School meal", None)
                payment = uuid.uuid4()
                gift = await SupplyService.receive_donation(
                    session, uuid.UUID(buyer),
                    {"cause_id": cause["id"], "donor_name": "Ravi", "amount_paise": 25000, "payment_id": str(payment)},
                    None,
                )
                connection = await SupplyService.pair_connector(
                    session, uuid.UUID(buyer),
                    {"provider": "tally", "direction": "export", "authority": "locah", "secret_ref": "vault:tally"},
                    None,
                )
                await SupplyService.map_connector(
                    session, uuid.UUID(buyer), connection["id"],
                    {"family": "ledger", "locah_key": "sales", "external_key": "Sales"},
                    None,
                )
                sync = await SupplyService.run_connector(
                    session, uuid.UUID(buyer), connection["id"], idempotency_key="tally-1", permissions=None,
                )
                sync_again = await SupplyService.run_connector(
                    session, uuid.UUID(buyer), connection["id"], idempotency_key="tally-1", permissions=None,
                )
                both = await SupplyService.pair_connector(
                    session, uuid.UUID(buyer),
                    {"provider": "tally-both", "direction": "both", "authority": "bidirectional"},
                    None,
                )
                with pytest.raises(ConflictError):
                    await SupplyService.run_connector(
                        session, uuid.UUID(buyer), both["id"], idempotency_key="nope", permissions=None,
                    )
                home = await SupplyService.buying_home(session, uuid.UUID(buyer), None)
                await session.commit()
                return {
                    "plan": plan,
                    "line_price": None,
                    "po": po["id"],
                    "incoming": incoming,
                    "counter_line": countered["line"],
                    "declined": declined,
                    "stock_before_receipt": stock_before_receipt,
                    "stock_after_first": stock_after_first,
                    "moves_after_replay": moves_after_replay,
                    "stock_after_bill": stock_after_bill,
                    "second": second,
                    "stock_after_second": stock_after_second,
                    "moves_after_second": moves_after_second,
                    "first": first,
                    "replay": replay,
                    "bill": bill,
                    "card": card,
                    "expense": expense,
                    "totals": totals,
                    "other": other,
                    "gift": gift,
                    "payment": payment,
                    "sync": sync,
                    "sync_again": sync_again,
                    "home": home,
                    "offering": offering,
                }
        finally:
            await engine.dispose()

    result = asyncio.run(_run())
    assert result["plan"]["net"] == 30
    assert result["plan"]["buy"] == 30
    pinned = sql(
        "SELECT unit_price_paise, quantity FROM procurement_purchase_order_lines WHERE purchase_order_id = :po",
        po=result["po"],
    )
    assert pinned[0][0] == 1000
    assert pinned[0][1] == 30
    assert result["incoming"]["totals"]["Rice"] == 30
    assert {row["buyer_label"] for row in result["incoming"]["lines"]} == {"Buyer shop"}
    assert "customer" not in result["incoming"]["lines"][0]
    assert result["counter_line"]["quantity"] == 30
    assert result["counter_line"]["unit_price_paise"] == 1000
    assert result["declined"]["decision"] == "declined"
    assert result["stock_before_receipt"] == 70
    assert result["first"]["replayed"] is False
    assert result["first"]["stocked"] == 10
    assert result["stock_after_first"] == 80
    assert result["replay"]["replayed"] is True
    assert result["moves_after_replay"] == 2
    assert result["bill"]["status"] == "open"
    assert result["bill"]["ledger_intent"]["kind"] == "purchase"
    assert result["stock_after_bill"] == 80
    assert result["second"]["stocked"] == 20
    assert result["second"]["complete"] is True
    assert result["stock_after_second"] == 100
    assert result["moves_after_second"] == 3
    on_hand = sql(
        "SELECT quantity_on_hand FROM inventory_records WHERE offering_id = :o",
        o=result["offering"],
    )
    assert on_hand[0][0] == 100
    assert result["bill"]["amount_paise"] == 10000
    assert result["card"]["ordered_quantity"] == 30
    assert result["card"]["received_quantity"] == 30
    assert result["totals"]["cash_paise"] == 5000
    assert result["other"]["total_paise"] == 0
    assert result["gift"]["payment_id"] == result["payment"]
    assert result["sync"]["replayed"] is False
    assert result["sync_again"]["replayed"] is True
    assert result["home"]["bills_due"] == 1


@DB
def test_supplier_sees_only_the_sealed_demand(monkeypatch: pytest.MonkeyPatch) -> None:
    """Buyer A owns the purchase order. Supplier B receives a copy and cannot read A's tables."""
    owner, headers = new_identity(monkeypatch)
    buyer = create_business(client, headers, name=f"Buyer {uuid.uuid4().hex[:6]}", modules=("offerings-catalog", "inventory"))
    supplier_biz = create_business(client, headers, name=f"Mill {uuid.uuid4().hex[:6]}", modules=("offerings-catalog",))
    item = client.post(
        f"/v1/platform/businesses/{buyer}/products",
        json={"title": "Atta", "status": "active", "offering_type": "product", "track_inventory": True, "price_amount": 1000},
        headers=headers,
    )
    assert item.status_code == 200, item.text
    offering = item.json()["data"]["id"]

    async def _run() -> None:
        engine = create_async_engine(db_url(), poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as session:
                supplier = await SupplyService.create_supplier(
                    session, uuid.UUID(buyer), owner,
                    {"name": "Mill", "connection": "locah", "linked_business_id": supplier_biz},
                    None,
                )
                mapped = await SupplyService.map_item(
                    session, uuid.UUID(buyer), owner,
                    {"supplier_id": supplier["id"], "offering_id": offering, "unit_price_paise": 400},
                    None,
                )
                requisition = await SupplyService.create_requisition(
                    session, uuid.UUID(buyer), owner,
                    {"offering_id": offering, "supplier_id": supplier["id"], "supplier_item_id": mapped["id"], "demand": 10, "source": "demand"},
                    None,
                )
                po = await SupplyService.create_purchase_order(
                    session, uuid.UUID(buyer), owner,
                    {"requisition_id": requisition["id"], "supplier_item_id": mapped["id"]},
                    None,
                )
                await SupplyService.approve_purchase_order(session, uuid.UUID(buyer), owner, po["id"], None)
                await SupplyService.send_purchase_order(
                    session, uuid.UUID(buyer), owner, po["id"],
                    buyer_label="Buyer shop", item_label="Atta", permissions=None,
                )
                await SupplyService.record_expense(
                    session, uuid.UUID(supplier_biz), owner,
                    {"category": "Rent", "amount_paise": 900, "method": "bank", "payee": "Landlord"},
                    None,
                )
                await session.commit()
            async with factory() as session:
                await session.execute(text("set local role platform_api"))
                await session.execute(text("select set_config('app.current_business_id', :b, true)"), {"b": supplier_biz})
                buyer_orders = (await session.execute(text("select id from procurement_purchase_orders"))).all()
                assert buyer_orders == []
                incoming = (await session.execute(text(
                    "select buyer_label, item_label, quantity, unit_price_paise from procurement_incoming_demands"
                ))).mappings().all()
                assert len(incoming) == 1
                assert dict(incoming[0])["buyer_label"] == "Buyer shop"
                assert "customer" not in dict(incoming[0])
                payload = (await session.execute(text("select payload::text from procurement_trade_messages"))).scalar()
                assert payload is not None
                assert "customer" not in payload
                await session.execute(text("select set_config('app.current_business_id', :a, true)"), {"a": buyer})
                foreign_demand = (await session.execute(text("select id from procurement_incoming_demands"))).all()
                assert foreign_demand == []
                foreign_expense = (await session.execute(text("select id from expenses_records"))).all()
                assert foreign_expense == []
                await session.rollback()
        finally:
            await engine.dispose()

    asyncio.run(_run())


@DB
def test_recipe_consumption_is_once(monkeypatch: pytest.MonkeyPatch) -> None:
    _owner, headers = new_identity(monkeypatch)
    buyer = create_business(client, headers, name=f"Kitchen {uuid.uuid4().hex[:6]}", modules=("offerings-catalog", "inventory"))
    location = primary_location(client, headers, buyer)

    def product(title: str) -> str:
        response = client.post(
            f"/v1/platform/businesses/{buyer}/products",
            json={"title": title, "status": "active", "offering_type": "product", "track_inventory": True, "price_amount": 1000},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        return str(response.json()["data"]["id"])

    plate = product("Shawarma")
    chicken = product("Chicken")
    actor = _owner

    async def _run() -> None:
        engine = create_async_engine(db_url(), poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as session:
                await StockService.receive(
                    session, uuid.UUID(buyer), actor,
                    {"location_id": location, "offering_id": chicken, "quantity": 20, "total_cost_paise": 2000},
                    None,
                )
                await SupplyService.save_bom(
                    session, uuid.UUID(buyer),
                    {
                        "offering_id": plate,
                        "name": "Shawarma",
                        "lines": [{"component_offering_id": chicken, "quantity_per": 1, "yield_ratio": 1}],
                    },
                    None,
                )
                await SupplyService.consume_for_sale(
                    session, uuid.UUID(buyer), actor,
                    {"offering_id": plate, "quantity": 3, "location_id": location, "idempotency_key": "sale-1"},
                    None,
                )
                again = await SupplyService.consume_for_sale(
                    session, uuid.UUID(buyer), actor,
                    {"offering_id": plate, "quantity": 3, "location_id": location, "idempotency_key": "sale-1"},
                    None,
                )
                assert again["replayed"] is True
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(_run())
    left = sql("SELECT quantity_on_hand FROM inventory_records WHERE offering_id = :o", o=chicken)
    assert left[0][0] == 17
