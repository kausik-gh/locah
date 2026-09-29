"""P1-10D2b: formula-priced offerings and the rate board (OK-15; MD §21.2
jewellery "price = today's metal rate × weight + making charge + GST from a
daily rate board"; Business OS Guide p.22).

Pure tests pin the arithmetic and validation. Database tests take a jeweller
through it: a 22K rate, a chain priced from it (10 g + 12% making), a phone
order and its bill, then a new rate — the chain re-prices for the next sale,
while the order and bill already made keep the rate they were sold at.
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal as D
from typing import Any

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_core.exceptions import ValidationError
from platform_core.pricing.formula import basis_words, clean_formula, compute
from platform_testing.phase_b import assert_tenant_isolated, billing_shop, create_business, new_identity, sql
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)
CHAIN = {"rate_key": "22k_gold", "quantity": "10", "making": {"type": "percent", "value": 12}}


# ---------------------------------------------------------------- pure
def test_the_price_is_rate_times_quantity_plus_making_and_extras() -> None:
    f = clean_formula("cart", CHAIN)
    assert f is not None and f["quantity"] == "10.000" and f["making"] == {"type": "percent", "value": "12.00"}
    price, basis = compute(f, D("6450"), label="22K gold", unit="g")
    assert price == D("72240") and basis["base"] == "64500.00" and basis["making"] == "7740.00"
    assert basis_words(basis) == "10 g × ₹6,450 (22K gold) + making ₹7,740 (12%)"
    stones = clean_formula("cart", {**CHAIN, "extra": "500", "extra_label": "stones"})
    assert stones is not None
    assert compute(stones, D("6450"))[0] == D("72740")
    per_gram = clean_formula("cart", {"rate_key": "silver", "quantity": "52.5",
                                      "making": {"type": "per_unit", "value": "18"}, "round": "paise"})
    assert per_gram is not None
    price, basis = compute(per_gram, D("92.35"), unit="g")
    assert price == D("5793.38"), "52.5 × 92.35 + 52.5 × 18, to the paisa"
    flat = clean_formula("cart", {"rate_key": "22k_gold", "quantity": "2.345", "making": {"type": "flat", "value": 800}})
    assert flat is not None
    assert compute(flat, D("6450"))[0] == D("15925"), "15,125.25 + 800, rounded to the rupee"


def test_formulas_are_validated() -> None:
    assert clean_formula("cart", None) is None and clean_formula("cart", {"rate_key": ""}) is None
    for bad in ({**CHAIN, "quantity": "0"}, {**CHAIN, "quantity": "ten"},
                {**CHAIN, "making": {"type": "discount", "value": 5}},
                {**CHAIN, "making": {"type": "percent", "value": 900}}, {**CHAIN, "extra": "-5"},
                {**CHAIN, "round": "ten"}):
        with pytest.raises(ValidationError):
            clean_formula("cart", bad)
    with pytest.raises(ValidationError, match="basket or at the counter"):
        clean_formula("booking", CHAIN)


# ---------------------------------------------------------------- database
def _jeweller(monkeypatch: Any) -> tuple[dict[str, str], dict[str, Any], dict[str, Any], dict[str, Any]]:
    _, owner = new_identity(monkeypatch)
    shop: dict[str, Any] = dict(billing_shop(client, owner, modules=("pos", "customer-relationships")))
    rate = client.post(f"{shop['base']}/pricing/rates", json={"label": "22K gold", "unit": "g", "value": 6450},
                       headers=owner)
    assert rate.status_code == 200, rate.text
    chain = client.post(f"{shop['base']}/products", json={
        "status": "active", "offering_type": "product", "title": "Gold chain 22K", "hsn_sac": "7113",
        "tax_rate": 3, "visibility": "public", "price_formula": CHAIN}, headers=owner)
    assert chain.status_code == 200, chain.text
    return owner, shop, rate.json()["data"], chain.json()["data"]


@DB
def test_a_chain_is_priced_from_todays_rate_and_a_sale_keeps_the_rate_it_was_made_at(monkeypatch: Any) -> None:
    owner, shop, rate, chain = _jeweller(monkeypatch)
    base = shop["base"]
    assert rate["key"] == "22k_gold" and rate["value"] == 6450.0
    assert chain["price_amount"] == 72240.0 and chain["price_type"] == "fixed"
    assert chain["price_formula"]["last"]["rate"] == "6450.0000"
    assert chain["price_formula"]["last_words"] == "10 g × ₹6,450 (22K gold) + making ₹7,740 (12%)"
    # a typed price never overrides a rate-priced item
    typed = client.patch(f"{base}/products/{chain['id']}", json={"price_amount": 100, "version": chain["version"]},
                         headers=owner)
    assert typed.status_code == 200 and typed.json()["data"]["price_amount"] == 72240.0

    # a phone order and its bill, at today's rate
    order = client.post(f"{base}/orders", json={
        "location_id": shop["loc"], "payment_method": "pay_at_business", "channel": "phone",
        "items": [{"offering_id": chain["id"], "quantity": 1}]}, headers=owner)
    assert order.status_code == 200, order.text
    o = order.json()["data"]
    [line] = [ln for ln in o["items"] if ln["offering_id"] == chain["id"]]
    assert line["unit_price"] == 72240.0 and line["options"]["formula"]["rate"] == "6450.0000"
    bill = client.post(f"{base}/invoices/from-order/{o['id']}", json={}, headers=owner)
    assert bill.status_code == 200, bill.text
    [bl] = bill.json()["data"]["lines"]
    assert bl["unit_price"] == 72240.0 and bl["basis_words"].startswith("10 g × ₹6,450")

    # tomorrow's rate: the chain re-prices, the order and bill already made do not
    board = client.get(f"{base}/pricing/rates", headers=owner).json()["data"]
    assert [i["title"] for i in board[0]["items"]] == ["Gold chain 22K"]
    new = client.post(f"{base}/pricing/rates/{rate['id']}/values", json={"value": 6600, "note": "Morning rate"},
                      headers=owner)
    assert new.status_code == 200, new.text
    assert new.json()["data"]["repriced"] == [chain["id"]]
    now = client.get(f"{base}/products/{chain['id']}", headers=owner).json()["data"]
    assert now["price_amount"] == 73920.0 and now["version"] > typed.json()["data"]["version"]
    again = client.get(f"{base}/orders/{o['id']}", headers=owner).json()["data"]
    [line2] = [ln for ln in again["items"] if ln["offering_id"] == chain["id"]]
    assert line2["unit_price"] == 72240.0 and line2["options"]["formula"]["rate"] == "6450.0000"
    kept = client.get(f"{base}/invoices/{bill.json()['data']['id']}", headers=owner).json()["data"]
    assert kept["lines"][0]["unit_price"] == 72240.0 and "₹6,450" in kept["lines"][0]["basis_words"]
    history = client.get(f"{base}/pricing/rates", headers=owner).json()["data"][0]["history"]
    assert [h["value"] for h in history] == [6600.0, 6450.0] and history[0]["note"] == "Morning rate"

    # a counter bill today uses today's rate and keeps its working; a changed price keeps none
    counter = client.post(f"{base}/invoices", json={"lines": [{"offering_id": chain["id"], "quantity": 1}]},
                          headers=owner)
    assert counter.status_code == 200, counter.text
    cl = counter.json()["data"]["lines"][0]
    assert cl["unit_price"] == 73920.0 and "₹6,600" in cl["basis_words"]
    haggled = client.post(f"{base}/invoices", json={"lines": [
        {"offering_id": chain["id"], "quantity": 1, "unit_price": 73000}]}, headers=owner).json()["data"]
    assert haggled["lines"][0]["basis_words"] is None
    # history is append-only for the API role
    assert sql("select count(*) from pricing_rate_values where rate_id = :r", r=rate["id"]) == [(2,)]


@DB
def test_an_item_needs_a_rate_on_the_board_and_a_rate_is_the_owners_alone(monkeypatch: Any) -> None:
    owner, shop, rate, chain = _jeweller(monkeypatch)
    base = shop["base"]
    missing = client.post(f"{base}/products", json={
        "status": "active", "offering_type": "product", "title": "Silver anklet",
        "price_formula": {"rate_key": "silver", "quantity": "40"}}, headers=owner)
    assert missing.status_code == 422 and "rate board first" in missing.text
    dup = client.post(f"{base}/pricing/rates", json={"label": "22K gold"}, headers=owner)
    assert dup.status_code == 409
    # a rate added without today's value leaves its items unpriced until it is entered
    silver = client.post(f"{base}/pricing/rates", json={"label": "Silver"}, headers=owner).json()["data"]
    anklet = client.post(f"{base}/products", json={
        "status": "active", "offering_type": "product", "title": "Silver anklet",
        "price_formula": {"rate_key": "silver", "quantity": "40", "making": {"type": "per_unit", "value": 20}}},
        headers=owner).json()["data"]
    assert anklet["price_amount"] is None
    client.post(f"{base}/pricing/rates/{silver['id']}/values", json={"value": 95}, headers=owner)
    assert client.get(f"{base}/products/{anklet['id']}", headers=owner).json()["data"]["price_amount"] == 4600.0
    # dropping the formula makes it an ordinary item again
    cur = client.get(f"{base}/products/{anklet['id']}", headers=owner).json()["data"]
    plain = client.patch(f"{base}/products/{anklet['id']}", json={
        "price_formula": None, "price_amount": 4500, "version": cur["version"]}, headers=owner).json()["data"]
    assert plain["price_formula"] is None and plain["price_amount"] == 4500.0

    # another business cannot read or change this board
    _, other = new_identity(monkeypatch)
    create_business(client, other)
    assert client.get(f"{base}/pricing/rates", headers=other).status_code in (403, 404)
    assert client.post(f"{base}/pricing/rates/{rate['id']}/values", json={"value": 1},
                       headers=other).status_code in (403, 404)
    assert client.get(f"{base}/products/{chain['id']}", headers=owner).json()["data"]["price_amount"] == 72240.0


@pytest.mark.asyncio
@DB
@pytest.mark.parametrize("table", ["pricing_rates", "pricing_rate_values"])
async def test_the_rate_board_is_tenant_isolated(table: str) -> None:
    async def insert(session: AsyncSession, business_id: uuid.UUID) -> None:
        key = f"r{uuid.uuid4().hex[:8]}"
        rid = (await session.execute(text(
            "INSERT INTO pricing_rates (business_id, key, label) VALUES (:b, :k, 'Gold') RETURNING id"),
            {"b": business_id, "k": key})).scalar()
        if table == "pricing_rate_values":
            await session.execute(text(
                "INSERT INTO pricing_rate_values (business_id, rate_id, value) VALUES (:b, :r, 6450)"),
                {"b": business_id, "r": rid})

    # rate history is append-only (no UPDATE grant at all), so "cannot change B's"
    # is checked as "cannot even reach B's rows" there
    await assert_tenant_isolated(table, insert, update_sql=None if table == "pricing_rates" else
                                 "select business_id from pricing_rate_values where business_id = :b")


@pytest.mark.asyncio
@DB
async def test_rate_history_cannot_be_rewritten_by_the_api_role() -> None:
    from platform_testing.phase_b import db_url
    from sqlalchemy.exc import DBAPIError
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(db_url(), poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            await session.execute(text("set local role platform_api"))
            for stmt in ("update pricing_rate_values set value = 1", "delete from pricing_rate_values",
                         "delete from pricing_rates"):
                await session.execute(text("savepoint s"))
                with pytest.raises(DBAPIError, match="permission denied"):
                    await session.execute(text(stmt))
                await session.execute(text("rollback to savepoint s"))
            await session.rollback()
    finally:
        await engine.dispose()
