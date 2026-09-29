"""Phone orders taken by staff and changes to an open order (FR-OR-13, FR-OR-18;
Founder: Orders — "Human phone order: staff creates the same Order using current
catalogue, stock, pricing, tax, delivery and payment rules"; "Order edits must
revalidate price, stock, tax, delivery, payment difference and preserve audit
history").
"""

from __future__ import annotations

import os
import uuid
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_testing.phase_b import create_business, new_identity, primary_location, sql

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)


def _shop(monkeypatch: Any) -> tuple[dict[str, str], str, str, str, dict[str, Any], dict[str, Any]]:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("offerings-catalog", "inventory", "orders", "payments", "fulfilment",
                                                  "customer-relationships"))
    base = f"/v1/platform/businesses/{bid}"
    loc = primary_location(client, owner, bid)
    client.patch(f"/v1/b/{bid}/fulfilment/settings", json={"pickup_enabled": True, "delivery_enabled": True},
                 headers=owner)
    client.post(f"/v1/b/{bid}/fulfilment/zones", json={"name": "Chennai", "match_type": "city", "city": "Chennai",
                                                       "charge_amount": 40}, headers=owner)
    rice = client.post(f"{base}/products", json={"title": "Ponni rice 5 kg", "status": "active", "price_amount": 450,
                                                  "sku": f"R-{uuid.uuid4().hex[:6]}", "track_inventory": True},
                       headers=owner).json()["data"]
    client.post(f"{base}/inventory/opening-stock", json={"offering_id": rice["id"], "location_id": loc, "quantity": 5},
                headers=owner)
    oil = client.post(f"{base}/products", json={"title": "Groundnut oil 1 l", "status": "active", "price_amount": 210,
                                                 "sku": f"O-{uuid.uuid4().hex[:6]}"}, headers=owner).json()["data"]
    return owner, bid, base, loc, rice, oil


def _staff(owner: dict[str, str], bid: str, base: str, loc: str, monkeypatch: Any, role: str = "manager") -> tuple[uuid.UUID, dict[str, str]]:
    person, headers = new_identity(monkeypatch)
    inv = client.post(f"/v1/b/{bid}/team/invitations", json={"identity_id": str(person), "role": "member"},
                      headers=owner).json()["data"]["id"]
    client.post(f"/v1/b/{bid}/team/members/{inv}/activate", headers=owner)
    client.put(f"{base}/members/{inv}/role", json={"role": role, "location_ids": [loc]}, headers=owner)
    return person, cast(dict[str, str], headers)


def _reserved(offering_id: str) -> int:
    return int(sql("select quantity_reserved from inventory_records where offering_id = :o", o=offering_id)[0][0])


@DB
def test_a_phone_order_goes_through_the_website_path_with_the_staff_member_as_actor(monkeypatch: Any) -> None:
    owner, bid, base, loc, rice, oil = _shop(monkeypatch)
    person, staff = _staff(owner, bid, base, loc, monkeypatch)
    items = [{"offering_id": rice["id"], "quantity": 2}, {"offering_id": oil["id"], "quantity": 1}]
    priced = client.post(f"{base}/orders/phone/price", json={
        "items": items, "fulfilment_mode": "delivery",
        "delivery_address": {"line1": "12 North St", "city": "Chennai", "postal_code": "600017"}}, headers=staff)
    assert priced.status_code == 200, priced.text
    p = priced.json()["data"]
    assert p["items_total"] == 1110.0 and p["delivery"]["charge"] == 40.0 and p["total"] == 1150.0
    placed = client.post(f"{base}/orders/phone", json={
        "customer": {"name": "Selvi", "phone": "98400 66001"}, "items": items, "fulfilment_mode": "delivery",
        "delivery_address": {"line1": "12 North St", "city": "Chennai", "postal_code": "600017"}}, headers=staff)
    assert placed.status_code == 200, placed.text
    d = placed.json()["data"]
    order_id = d["order"]["id"]
    assert d["confirmation"]["grand_total"] == 1150.0 and d["fulfilment"]["mode"] == "delivery"
    row = sql("select o.channel, c.display_name, c.phone from orders_orders o join customer_relationships_contacts c "
              "on c.id = o.customer_contact_id where o.id = :o", o=order_id)[0]
    assert row == ("phone", "Selvi", "+919840066001")
    assert sql("select actor_identity_id from orders_order_status_history where order_id = :o", o=order_id) == [(person,)]
    assert _reserved(rice["id"]) == 2
    # the same caller again is the same customer
    again = client.post(f"{base}/orders/phone", json={"customer": {"name": "Selvi M", "phone": "+91 98400-66001"},
                                                       "items": [{"offering_id": oil["id"], "quantity": 1}],
                                                       "fulfilment_mode": "pickup"}, headers=staff)
    assert again.status_code == 200, again.text
    assert sql("select count(distinct customer_contact_id) from orders_orders where business_id = :b", b=bid) == [(1,)]
    for bad, word in (({"customer": {"name": "X"}}, "phone number"), ({"customer": {"phone": "9840066002"}}, "name"),
                      ({"payment_method": "online"}, "paid at pickup")):
        r = client.post(f"{base}/orders/phone", json={"customer": {"name": "Ravi", "phone": "9840066003"}, "items": items,
                                                      "fulfilment_mode": "pickup", **bad}, headers=staff)
        assert r.status_code == 422 and word in r.text, (bad, r.text)
    _, keeper = _staff(owner, bid, base, loc, monkeypatch, role="store_keeper")
    assert client.post(f"{base}/orders/phone", json={"customer": {"name": "Ravi", "phone": "9840066003"},
                                                      "items": items, "fulfilment_mode": "pickup"},
                       headers=keeper).status_code == 403


@DB
def test_changing_an_order_revalidates_price_stock_tax_and_money(monkeypatch: Any) -> None:
    owner, bid, base, loc, rice, oil = _shop(monkeypatch)
    placed = client.post(f"{base}/orders/phone", json={
        "customer": {"name": "Kumar", "phone": "9840077001"}, "fulfilment_mode": "pickup",
        "items": [{"offering_id": rice["id"], "quantity": 2}, {"offering_id": oil["id"], "quantity": 1}]}, headers=owner)
    order = placed.json()["data"]["order"]
    rice_line = next(i for i in order["items"] if i["offering_id"] == rice["id"])
    oil_line = next(i for i in order["items"] if i["offering_id"] == oil["id"])
    assert _reserved(rice["id"]) == 2
    client.post(f"{base}/collect/record", json={"source_type": "order", "source_id": order["id"], "amount": 500,
                                                "method": "cash"}, headers=owner)
    # the shop's price goes up after the customer ordered
    client.patch(f"{base}/products/{rice['id']}", json={"price_amount": 480, "version": rice["version"]}, headers=owner)
    order = client.get(f"{base}/orders/{order['id']}", headers=owner).json()["data"]  # the payment moved its version

    change = {"lines": [{"line_id": rice_line["id"], "quantity": 3}, {"offering_id": rice["id"], "quantity": 1}],
              "reason": "Customer called to change", "version": order["version"]}
    preview = client.post(f"{base}/orders/{order['id']}/change", params={"preview": "true"}, json=change, headers=owner)
    assert preview.status_code == 200, preview.text
    pv = preview.json()["data"]
    # agreed line keeps ₹450; the added line is today's ₹480; oil removed
    assert pv["preview"] and pv["total"] == 1830.0 and pv["paid"] == 500.0 and pv["to_collect"] == 1330.0
    assert "removed Groundnut oil 1 l" in pv["changes"], pv["changes"]
    assert _reserved(rice["id"]) == 2, "a preview changes nothing"
    assert sql("select count(*) from orders_order_line_items where order_id = :o", o=order["id"]) == [(2,)]

    refused = client.post(f"{base}/orders/{order['id']}/change", json=change, headers=owner)
    assert refused.status_code == 422 and "customer agreed" in refused.text
    too_many = client.post(f"{base}/orders/{order['id']}/change", json={
        **change, "lines": [{"line_id": rice_line["id"], "quantity": 9}], "customer_agreed": True}, headers=owner)
    assert too_many.status_code == 422 and "stock" in too_many.text.lower()
    saved = client.post(f"{base}/orders/{order['id']}/change", json={**change, "customer_agreed": True}, headers=owner)
    assert saved.status_code == 200, saved.text
    assert _reserved(rice["id"]) == 4
    lines = sql("select title, quantity, unit_price from orders_order_line_items where order_id = :o order by sort_order",
                o=order["id"])
    assert [(t, q, float(p)) for t, q, p in lines] == [("Ponni rice 5 kg", 3, 450.0), ("Ponni rice 5 kg", 1, 480.0)]
    now = client.get(f"{base}/orders/{order['id']}", headers=owner).json()["data"]
    assert now["total_amount"] == 1830.0 and now["version"] == order["version"] + 1
    assert now["payment_status"] == "partially_paid"
    cod = sql("select amount, status from payments_payment_attempts where source_id = :o and payment_method = 'cod'",
              o=order["id"])
    assert [(float(a), s) for a, s in cod] == [(1330.0, "pending_offline")], "the cash still expected follows the balance"
    history = sql("select reason from orders_order_status_history where order_id = :o order by created_at", o=order["id"])
    assert history[-1][0].startswith("Changed: ") and "Customer called to change" in history[-1][0]
    assert sql("select count(*) from platform_audit_events where resource_id = :o and event_type = 'order.changed'",
               o=order["id"]) == [(1,)]
    stale = client.post(f"{base}/orders/{order['id']}/change", json={**change, "customer_agreed": True}, headers=owner)
    assert stale.status_code == 409 and "reload" in stale.text

    # cut it down below what was paid: a refund due appears in Payments
    now_line = sql("select id from orders_order_line_items where order_id = :o and unit_price = 480", o=order["id"])[0][0]
    down = client.post(f"{base}/orders/{order['id']}/change", json={
        "lines": [{"line_id": str(now_line), "quantity": 1}], "customer_agreed": True,
        "version": now["version"]}, headers=owner)
    assert down.status_code == 200 and down.json()["data"]["total"] == 480.0 and down.json()["data"]["paid"] == 500.0
    assert down.json()["data"]["refund_due"] == 20.0 and _reserved(rice["id"]) == 1
    assert sql("select attention from payments_payment_attempts where source_id = :o and status = 'succeeded'",
               o=order["id"]) == [("refund_due",)]
    assert sql("select status from payments_payment_attempts where source_id = :o and payment_method = 'cod'",
               o=order["id"]) == [("cancelled",)]


@DB
def test_orders_that_cannot_be_changed(monkeypatch: Any) -> None:
    owner, bid, base, loc, rice, oil = _shop(monkeypatch)
    placed = client.post(f"{base}/orders/phone", json={
        "customer": {"name": "Meena", "phone": "9840088001"}, "fulfilment_mode": "pickup",
        "items": [{"offering_id": oil["id"], "quantity": 1}]}, headers=owner).json()["data"]["order"]
    line = placed["items"][0]["id"]
    empty = client.post(f"{base}/orders/{placed['id']}/change", json={"lines": [], "customer_agreed": True}, headers=owner)
    assert empty.status_code == 422 and "cancel it instead" in empty.text
    foreign = client.post(f"{base}/orders/{placed['id']}/change", json={
        "lines": [{"line_id": str(uuid.uuid4()), "quantity": 1}], "customer_agreed": True}, headers=owner)
    assert foreign.status_code == 422
    zero = client.post(f"{base}/orders/{placed['id']}/change", json={
        "lines": [{"line_id": line, "quantity": 0}], "customer_agreed": True}, headers=owner)
    assert zero.status_code == 422
    sql("update orders_orders set status = 'completed' where id = :o", o=placed["id"])
    done = client.post(f"{base}/orders/{placed['id']}/change", json={
        "lines": [{"line_id": line, "quantity": 2}], "customer_agreed": True}, headers=owner)
    assert done.status_code == 409 and "completed" in done.text
    _, other = new_identity(monkeypatch)
    create_business(client, other)
    assert client.post(f"{base}/orders/{placed['id']}/change", json={"lines": [{"line_id": line, "quantity": 2}]},
                       headers=other).status_code in (403, 404)


@DB
def test_a_billed_order_is_changed_with_a_credit_note_not_an_edit(monkeypatch: Any) -> None:
    from platform_testing.phase_b import billing_shop

    _, owner = new_identity(monkeypatch)
    shop = billing_shop(client, owner, modules=("fulfilment", "customer-relationships"))
    base, bid = shop["base"], shop["bid"]
    client.patch(f"/v1/b/{bid}/fulfilment/settings", json={"pickup_enabled": True}, headers=owner)
    item = client.post(f"{base}/products", json={"title": "Sugar 1 kg", "status": "active", "price_amount": 50,
                                                  "hsn_sac": "1701", "tax_rate": 5}, headers=owner).json()["data"]
    placed = client.post(f"{base}/orders/phone", json={"customer": {"name": "Ravi", "phone": "9840099001"},
                                                       "fulfilment_mode": "pickup",
                                                       "items": [{"offering_id": item["id"], "quantity": 2}]},
                         headers=owner)
    assert placed.status_code == 200, placed.text
    order = placed.json()["data"]["order"]
    bill = client.post(f"{base}/invoices/from-order/{order['id']}", json={}, headers=owner)
    assert bill.status_code == 200, bill.text
    r = client.post(f"{base}/orders/{order['id']}/change", json={
        "lines": [{"line_id": order["items"][0]["id"], "quantity": 3}], "customer_agreed": True}, headers=owner)
    assert r.status_code == 409 and "credit note" in r.text


@DB
def test_a_change_rechecks_the_delivery_charge(monkeypatch: Any) -> None:
    owner, bid, base, loc, rice, oil = _shop(monkeypatch)
    placed = client.post(f"{base}/orders/phone", json={
        "customer": {"name": "Anbu", "phone": "9840011222"}, "fulfilment_mode": "delivery",
        "delivery_address": {"line1": "3 Beach Rd", "city": "Chennai", "postal_code": "600004"},
        "items": [{"offering_id": oil["id"], "quantity": 1}]}, headers=owner)
    assert placed.status_code == 200, placed.text
    order = placed.json()["data"]["order"]
    assert order["total_amount"] == 250.0
    sql("update fulfilment_zones set charge_amount = 60 where business_id = :b", b=bid)
    oil_line = next(i for i in order["items"] if i["offering_id"] == oil["id"])
    r = client.post(f"{base}/orders/{order['id']}/change", json={
        "lines": [{"line_id": oil_line["id"], "quantity": 2}], "customer_agreed": True, "version": order["version"]},
        headers=owner)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert "delivery ₹40 → ₹60" in d["changes"] and d["total"] == 480.0
