"""Integration: a completed sale earns loyalty once and qualifies a referral once.

Orders owns the sale; Loyalty owns points. Through the real API and worker on
local PostgreSQL: Priya refers Ravi, Ravi's first completed ₹500 order earns
him 500 points plus the referee bonus and Priya the referrer bonus; delivering
the event again changes nothing; his second order earns its points but no
second referral reward. A business without Loyalty on earns nothing.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_testing.phase_b import create_business, drain_events, new_identity, primary_location, sql

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)


def _shop(monkeypatch: Any, *extra: str) -> tuple[dict[str, str], str, str, str]:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("offerings-catalog", "orders", "customer-relationships"))
    base = f"/v1/platform/businesses/{bid}"
    if extra:  # loyalty is on the Growth plan
        plan = client.patch(f"{base}/entitlements/plan", json={"plan_id": "growth"}, headers=owner)
        assert plan.status_code == 200, plan.text
        for module in extra:
            on = client.post(f"/v1/b/{bid}/modules/{module}/enable", headers=owner)
            assert on.status_code == 200, on.text
    product = client.post(f"{base}/products", json={
        "status": "active", "offering_type": "product", "title": "Sweets box", "price_amount": 500}, headers=owner)
    assert product.status_code == 200, product.text
    return owner, bid, base, str(product.json()["data"]["id"])


def _customer(owner: dict[str, str], base: str, name: str, phone: str) -> str:
    r = client.post(f"{base}/customers", json={"display_name": name, "phone": phone}, headers=owner)
    assert r.status_code == 200, r.text
    return str(r.json()["data"]["id"])


def _completed_sale(owner: dict[str, str], bid: str, base: str, product: str, contact: str) -> str:
    created = client.post(f"{base}/orders", json={
        "location_id": primary_location(client, owner, bid), "customer_contact_id": contact,
        "items": [{"offering_id": product, "quantity": 1}]}, headers=owner)
    assert created.status_code == 200, created.text
    order_id = str(created.json()["data"]["id"])
    for status in ("accepted", "preparing", "ready", "completed"):
        r = client.post(f"{base}/orders/{order_id}/status", json={"status": status}, headers=owner)
        assert r.status_code == 200, r.text
    drain_events(bid)
    drain_events(bid)
    return order_id


def test_a_completed_sale_earns_once_and_qualifies_the_referral_once(monkeypatch: Any) -> None:
    owner, bid, base, product = _shop(monkeypatch, "loyalty")
    program = client.put(f"{base}/loyalty/program", json={"points_per_rupee": 1, "status": "active"}, headers=owner)
    assert program.status_code == 200, program.text
    priya = _customer(owner, base, "Priya", "+919840033333")
    ravi = _customer(owner, base, "Ravi", "+919840044444")
    code = client.get(f"{base}/loyalty/customers/{priya}/referral", headers=owner).json()["code"]
    applied = client.post(f"{base}/loyalty/customers/{ravi}/referral/apply", json={"code": code}, headers=owner)
    assert applied.status_code == 200 and applied.json()["status"] == "pending", applied.text

    def points(contact: str) -> int:
        r = client.get(f"{base}/loyalty/customers/{contact}/balance", headers=owner)
        assert r.status_code == 200, r.text
        return int(r.json()["current_points"])

    _completed_sale(owner, bid, base, product, ravi)
    first_ravi, first_priya = points(ravi), points(priya)
    assert first_ravi == 500 + 50, "₹500 at 1 point per rupee, plus the referee bonus"
    assert first_priya == 100, "the referrer bonus, once"

    drain_events(bid)
    assert (points(ravi), points(priya)) == (first_ravi, first_priya), "a replayed event earns nothing more"

    _completed_sale(owner, bid, base, product, ravi)
    assert points(ravi) == first_ravi + 500, "the next sale earns its own points"
    assert points(priya) == first_priya, "a referral qualifies on the first purchase only"


def test_no_loyalty_module_no_points(monkeypatch: Any) -> None:
    owner, bid, base, product = _shop(monkeypatch)
    ravi = _customer(owner, base, "Ravi", "+919840055555")
    _completed_sale(owner, bid, base, product, ravi)
    assert sql("select count(*) from loyalty_ledger where business_id = :b", b=bid)[0][0] == 0
