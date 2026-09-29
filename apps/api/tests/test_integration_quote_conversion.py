"""Integration: an accepted quote becomes the owning module's record, once.

Quotes publishes quote.conversion_requested (locah.quote.conversion.v1) and
inserts nothing. Through the real API, customer acceptance and the worker on
local PostgreSQL: a service quote handed to Projects becomes one project; a
catalogue quote at a negotiated price handed to Orders becomes one order at the
accepted price, not the catalogue price; a free-text quote handed to Orders is
refused and creates nothing. Replays change nothing.
"""

from __future__ import annotations

import os
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_testing.phase_b import drain_events, sql

from test_quotes import TEST_JWT_SECRET, _accept_from_share, _business, _headers, _quote, _reachable_customer, _seed

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)


@pytest.fixture
def owner(monkeypatch: Any) -> dict[str, str]:
    import uuid

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed(user_id, email)
    return cast(dict[str, str], _headers(user_id, email))


def _accepted(owner: dict[str, str], bid: str, **quote: Any) -> str:
    quote.setdefault("customer_contact_id", _reachable_customer(client, owner, bid))
    q = _quote(client, owner, bid, **quote)
    issued = client.post(f"/v1/platform/businesses/{bid}/quotes/{q['id']}/issue", json={"valid_days": 10},
                         headers=owner)
    assert issued.status_code == 200, issued.text
    accepted = _accept_from_share(client, issued.json()["data"]["share_token"], q["id"], name="Ravi")
    assert accepted.status_code == 200, accepted.text
    return str(q["id"])


def _hand(owner: dict[str, str], bid: str, quote_id: str, target: str) -> None:
    r = client.post(f"/v1/platform/businesses/{bid}/quotes/{quote_id}/conversion", json={"target": target},
                    headers=owner)
    assert r.status_code == 200, r.text
    drain_events(bid)
    drain_events(bid)


def _enable(owner: dict[str, str], bid: str, *modules: str) -> None:
    for module in modules:
        r = client.post(f"/v1/b/{bid}/modules/{module}/enable", headers=owner)
        assert r.status_code == 200, r.text


def test_a_service_quote_handed_to_projects_becomes_one_project(owner: dict[str, str]) -> None:
    bid = _business(client, owner)
    _enable(owner, bid, "projects")
    quote_id = _accepted(owner, bid)
    _hand(owner, bid, quote_id, "project")
    rows = sql("select id::text from projects_projects where business_id = :b and source_quote_id = :q",
               b=bid, q=quote_id)
    assert len(rows) == 1, "one project from one accepted quote"
    drain_events(bid)
    assert int(sql("select count(*) from projects_projects where business_id = :b", b=bid)[0][0]) == 1


def test_a_catalogue_quote_handed_to_orders_is_one_order_at_the_accepted_price(owner: dict[str, str]) -> None:
    bid = _business(client, owner)
    _enable(owner, bid, "orders")
    base = f"/v1/platform/businesses/{bid}"
    bracket = client.post(f"{base}/products", json={
        "title": "Steel bracket", "status": "active", "price_amount": 100, "tax_rate": 18}, headers=owner)
    assert bracket.status_code == 200, bracket.text
    offering = bracket.json()["data"]["id"]
    quote_id = _accepted(owner, bid, title="Brackets for Plant 2", items=[
        {"offering_id": offering, "title": "Steel bracket", "quantity": 50, "unit_price": 90, "tax_rate": 18}])
    _hand(owner, bid, quote_id, "order")

    orders = sql("select id::text, subtotal::text, internal_reference from orders_orders "
                 "where business_id = :b and idempotency_key = :k", b=bid, k=f"quote:{quote_id}")
    assert len(orders) == 1, "one order from one accepted quote"
    order_id, subtotal, reference = orders[0]
    assert float(subtotal) == 4500.0, "50 × ₹90 as accepted, not the ₹100 catalogue price"
    assert reference.startswith("Quote ")
    lines = sql("select quantity, unit_price::text from orders_order_line_items where order_id = :o", o=order_id)
    assert [(int(q), float(p)) for q, p in lines] == [(50, 90.0)]

    drain_events(bid)
    assert int(sql("select count(*) from orders_orders where business_id = :b", b=bid)[0][0]) == 1


def test_a_free_text_quote_is_not_turned_into_an_order(owner: dict[str, str]) -> None:
    bid = _business(client, owner)
    _enable(owner, bid, "orders")
    quote_id = _accepted(owner, bid)  # "Design" and "Build": no catalogue items
    _hand(owner, bid, quote_id, "order")
    assert int(sql("select count(*) from orders_orders where business_id = :b", b=bid)[0][0]) == 0


def test_the_accepted_token_is_the_orders_advance_and_payments_asks_for_it_once(owner: dict[str, str]) -> None:
    """quote.payment_handoff lands in the one payment system: the token is the
    converted order's advance, collected by Payment Collect on the order."""
    bid = _business(client, owner)
    _enable(owner, bid, "orders", "payments")
    base = f"/v1/platform/businesses/{bid}"
    bracket = client.post(f"{base}/products", json={
        "title": "Steel bracket", "status": "active", "price_amount": 100, "tax_rate": 18}, headers=owner)
    assert bracket.status_code == 200, bracket.text
    quote_id = _accepted(owner, bid, title="Brackets, 20% token", deposit_type="percent", deposit_value=20, items=[
        {"offering_id": bracket.json()["data"]["id"], "title": "Steel bracket", "quantity": 50, "unit_price": 90,
         "tax_rate": 18}])
    token = float(client.get(f"{base}/quotes/{quote_id}", headers=owner).json()["data"]["deposit_amount"])
    assert token > 0
    _hand(owner, bid, quote_id, "order")
    order_id, advance = sql("select id::text, advance_amount::text from orders_orders "
                            "where business_id = :b and idempotency_key = :k", b=bid, k=f"quote:{quote_id}")[0]
    assert float(advance) == token, "the token the customer accepted is the order's advance"

    due = client.get(f"{base}/collect/due", params={"source_type": "order", "source_id": order_id}, headers=owner)
    assert due.status_code == 200, due.text
    assert due.json()["data"]["advance"] == token and due.json()["data"]["paid"] == 0
    asked = client.post(f"{base}/collect/requests", json={
        "source_type": "order", "source_id": order_id, "amount": token, "purpose": "advance"}, headers=owner)
    assert asked.status_code == 200, asked.text

    # A replayed handoff changes nothing: one order, the same advance, no request made by the system.
    again = client.post(f"{base}/quotes/{quote_id}/conversion", json={"target": "order"}, headers=owner)
    assert again.status_code == 200, again.text
    drain_events(bid)
    assert sql("select count(*), max(advance_amount)::text from orders_orders where business_id = :b", b=bid) == [
        (1, advance)]
    assert int(sql("select count(*) from payments_requests where business_id = :b", b=bid)[0][0]) == 1
