"""P1-10B one customer identity across businesses (Founder §12–13; Guide §1; Doc 12 l.848).

A signed-in customer's website order joins their own record; My Activity
shows it with its tracking link; each business's website shows "My account"
with that customer's orders, bills and bookings — never another customer's.
Guest history joins an account only through a verified email.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from platform_api.main import app
from platform_testing.phase_b import create_business, drain_events, new_identity, sql

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)


def _shop(owner: dict[str, str], name: str) -> tuple[str, str, dict[str, Any]]:
    bid = create_business(client, owner, modules=("offerings-catalog", "orders", "payments", "fulfilment"),
                          name=name)
    assert client.post(f"/v1/b/{bid}/marketplace/visibility", json={"visibility": "unlisted"},
                       headers=owner).status_code == 200
    client.patch(f"/v1/b/{bid}/fulfilment/settings", json={"pickup_enabled": True}, headers=owner)
    slug = client.get(f"/v1/b/{bid}", headers=owner).json()["data"]["slug"]
    item = client.post(f"/v1/platform/businesses/{bid}/products", json={
        "status": "active", "offering_type": "product", "title": "Filter coffee powder 500 g",
        "price_amount": 240}, headers=owner).json()["data"]
    return bid, slug, item


def _checkout(slug: str, item: dict[str, Any], headers: dict[str, str] | None = None,
              email: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"items": [{"offering_id": item["id"], "quantity": 2}], "fulfilment_mode": "pickup",
                            "payment_method": "cod", "guest": {"name": "Meena"}}
    if email:
        body["guest"]["email"] = email
    r = client.post(f"/v1/public/websites/{slug}/checkout", json=body, headers=headers or {})
    assert r.status_code == 200, r.text
    return dict(r.json()["data"])


def _order_id(placed: dict[str, Any]) -> str:
    return str(placed.get("order_id") or placed["order"]["id"])


@DB
def test_signed_in_order_joins_the_customer_and_shows_on_both_surfaces(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, slug, item = _shop(owner, "Kumbakonam Coffee Works")
    me, customer = new_identity(monkeypatch)
    placed = _checkout(slug, item, headers=customer)
    order_id = _order_id(placed)
    linked = sql("SELECT c.identity_id FROM orders_orders o JOIN customer_relationships_contacts c "
                 "ON c.id = o.customer_contact_id WHERE o.id = :o", o=order_id)
    assert linked == [(me,)]
    drain_events(bid)

    feed = client.get("/v1/me/activity", headers=customer).json()
    orders = [a for a in feed["data"] if a["resource_type"] == "order"]
    assert orders and orders[0]["summary"]["order_number"] and orders[0]["action_url"].startswith(f"/{slug}/track/")
    assert "tracking_token" not in orders[0]["summary"]  # the link is given, the raw token is not echoed
    assert orders[0]["account_url"] == f"/{slug}/account"
    assert "order" in feed["meta"]["covered_resource_types"]

    account = client.get(f"/v1/me/businesses/{slug}/account", headers=customer)
    assert account.status_code == 200, account.text
    data = account.json()["data"]
    assert data["linked"] is True and [o["id"] for o in data["orders"]] == [order_id]
    assert data["orders"][0]["track_url"].startswith(f"/{slug}/track/{order_id}?token=")
    assert data["orders"][0]["items"] == [{"title": "Filter coffee powder 500 g", "quantity": 2.0}]

    # Another LOCAH customer sees nothing of this one's, and cannot reorder it.
    _, stranger = new_identity(monkeypatch)
    theirs = client.get(f"/v1/me/businesses/{slug}/account", headers=stranger).json()["data"]
    assert theirs["linked"] is False and theirs["orders"] == []
    assert client.get(f"/v1/me/businesses/{slug}/orders/{order_id}/reorder", headers=stranger).status_code == 404

    # Order again: today's price, not the old one.
    client.patch(f"/v1/platform/businesses/{bid}/products/{item['id']}", json={"price_amount": 260}, headers=owner)
    again = client.get(f"/v1/me/businesses/{slug}/orders/{order_id}/reorder", headers=customer)
    assert again.status_code == 200, again.text
    line = again.json()["data"][0]
    assert line["available"] is True and line["unit_price"] == 260.0 and line["was_unit_price"] == 240.0
    assert client.post(f"/v1/platform/businesses/{bid}/products/{item['id']}/archive", json={},
                       headers=owner).status_code == 200
    gone = client.get(f"/v1/me/businesses/{slug}/orders/{order_id}/reorder", headers=customer).json()["data"][0]
    assert gone["available"] is False and gone["reason"] == "No longer sold"


@DB
def test_guest_history_joins_only_through_a_verified_email(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid_a, slug_a, item_a = _shop(owner, "Anna Stores")
    bid_b, slug_b, item_b = _shop(owner, "Bala Bakery")
    me, customer = new_identity(monkeypatch)
    email = f"{me}@example.com"
    # Earlier, as a guest, with the same email in two shops — and someone else's email in a third order.
    first = _order_id(_checkout(slug_a, item_a, email=email.upper()))
    second = _order_id(_checkout(slug_b, item_b, email=email))
    other = _order_id(_checkout(slug_a, item_a, email=f"someone-{uuid.uuid4().hex[:6]}@example.com"))

    # An unverified email links nothing.
    sql("UPDATE platform_identities SET email_verified = false WHERE id = :i", i=me)
    assert [a for a in client.get("/v1/me/activity", headers=customer).json()["data"]
            if a["resource_type"] == "order"] == []
    assert sql("SELECT count(*) FROM customer_relationships_contacts WHERE identity_id = :i", i=me) == [(0,)]

    sql("UPDATE platform_identities SET email_verified = true WHERE id = :i", i=me)
    feed = client.get("/v1/me/activity", headers=customer).json()["data"]
    seen = {a["resource_id"] for a in feed if a["resource_type"] == "order"}
    assert seen == {first, second} and other not in seen
    names = {a["business_name"] for a in feed if a["resource_type"] == "order"}
    assert names == {"Anna Stores", "Bala Bakery"}
    # Linking is idempotent: a second visit adds nothing.
    again = client.get("/v1/me/activity", headers=customer).json()["data"]
    assert len([a for a in again if a["resource_type"] == "order"]) == 2
    # A contact once claimed stays with its identity.
    assert sql("SELECT count(*) FROM customer_relationships_contacts WHERE identity_id = :i", i=me) == [(2,)]
    drain_events(bid_a)
    drain_events(bid_b)


@DB
def test_invalid_token_is_refused_not_treated_as_a_guest(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    _, slug, item = _shop(owner, "Chennai Spices")
    bad = client.post(f"/v1/public/websites/{slug}/checkout", json={
        "items": [{"offering_id": item["id"], "quantity": 1}], "fulfilment_mode": "pickup",
        "payment_method": "cod", "guest": {"name": "X", "email": "x@example.com"}},
        headers={"Authorization": "Bearer not-a-real-token"})
    assert bad.status_code == 401
