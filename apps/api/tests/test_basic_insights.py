"""Basic insights from real data only (IS-01; MD §26.3 P1-10; First Launch §12.1).

Sales, orders, bookings and money received for today / the last 7 days /
this month, counted from the records behind them; a tool that is off is named,
never shown as a zero; a viewer without the permission is told so; a
location-limited manager sees only their location, and money received (counted
business-wide) is not shown to them.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_core.insights.basic import rupees, window
from platform_testing.phase_b import billing_shop, create_business, new_identity, primary_location, sql

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)
IST = ZoneInfo("Asia/Kolkata")


def test_periods_and_rupees() -> None:
    now = datetime(2026, 10, 9, 20, 0, tzinfo=timezone.utc)  # 10 Oct, 1:30 am in India
    assert window("today", now) == (date(2026, 10, 10), date(2026, 10, 11))
    assert window("7d", now) == (date(2026, 10, 4), date(2026, 10, 11))
    assert window("month", now) == (date(2026, 10, 1), date(2026, 10, 11))
    assert rupees(123456) == "₹1,23,456" and rupees(-500) == "-₹500" and rupees(0) == "₹0"


def _insights(base: str, headers: dict[str, str], period: str = "today") -> dict[str, Any]:
    r = client.get(f"{base}/insights", params={"period": period}, headers=headers)
    assert r.status_code == 200, r.text
    return cast(dict[str, Any], r.json()["data"])


def _card(data: dict[str, Any], key: str) -> dict[str, Any]:
    return next(c for c in data["cards"] if c["key"] == key)


def _member(owner: dict[str, str], bid: str, monkeypatch: Any, role: str, locations: list[str]) -> dict[str, str]:
    person_id, headers = new_identity(monkeypatch)
    inv = client.post(f"/v1/b/{bid}/team/invitations", json={"identity_id": str(person_id), "role": "member"},
                      headers=owner).json()["data"]["id"]
    client.post(f"/v1/b/{bid}/team/members/{inv}/activate", headers=owner)
    r = client.put(f"/v1/platform/businesses/{bid}/members/{inv}/role",
                   json={"role": role, "location_ids": locations}, headers=owner)
    assert r.status_code == 200, r.text
    return cast(dict[str, str], headers)


@DB
def test_the_four_numbers_are_counted_from_real_records(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = billing_shop(client, owner, modules=("pos",))
    base = shop["base"]
    item = client.post(f"{base}/products", json={
        "status": "active", "offering_type": "product", "title": "Steel tiffin", "price_amount": 1000,
        "hsn_sac": "7323", "tax_rate": 0}, headers=owner).json()["data"]
    today_bill = client.post(f"{base}/invoices", json={"issue": True, "lines": [
        {"offering_id": item["id"], "quantity": 2}]}, headers=owner)
    assert today_bill.status_code == 200, today_bill.text
    paid = client.post(f"{base}/invoices/{today_bill.json()['data']['id']}/payments",
                       json={"amount": 2000, "method": "cash"}, headers=owner)
    assert paid.status_code == 200, paid.text
    older = client.post(f"{base}/invoices", json={"issue": True, "lines": [
        {"offering_id": item["id"], "quantity": 1}]}, headers=owner).json()["data"]
    three_days_ago = datetime.now(timezone.utc).astimezone(IST).date() - timedelta(days=3)
    sql("update invoicing_documents set issue_date = :d where id = :i", d=three_days_ago, i=older["id"])
    placed = []
    for _ in range(2):
        r = client.post(f"{base}/orders", json={
            "location_id": shop["loc"], "payment_method": "pay_at_business", "channel": "phone",
            "items": [{"offering_id": item["id"], "quantity": 1}]}, headers=owner)
        assert r.status_code == 200, r.text
        placed.append(r.json()["data"])
    cancelled = client.post(f"{base}/orders/{placed[1]['id']}/cancel", json={"reason": "Customer changed mind"},
                            headers=owner)
    assert cancelled.status_code == 200, cancelled.text

    today = _insights(base, owner)
    assert today["period"]["label"] == "Today"
    sales = _card(today, "sales")
    assert (sales["state"], sales["value"], sales["note"]) == ("ok", "₹2,000", "1 bill")
    orders = _card(today, "orders")
    assert (orders["value"], orders["note"]) == ("₹1,000", "1 order")
    assert {"label": "Phone", "value": "1 order"} in orders["detail"]
    assert {"label": "Cancelled or declined", "value": "1 order"} in orders["detail"]
    money = _card(today, "collections")
    overview = client.get(f"{base}/collect/overview", headers=owner)
    assert overview.status_code == 200, overview.text  # the Payments page and Insights count money the same way
    assert money["value"] == rupees(overview.json()["data"]["paid_today"]["total"])
    assert money["value"] == "₹2,000" and {"label": "Bills and the counter", "value": "₹2,000"} in money["detail"]
    assert [m["key"] for m in today["not_switched_on"]] == ["bookings"], "bookings are off: named, not a zero"
    assert "bookings" not in [c["key"] for c in today["cards"]]

    week = _card(_insights(base, owner, "7d"), "sales")
    assert (week["value"], week["note"]) == ("₹3,000", "2 bills"), "the bill from three days ago is in the week"
    month = _card(_insights(base, owner, "month"), "sales")
    in_month = three_days_ago.month == datetime.now(timezone.utc).astimezone(IST).month
    assert month["value"] == ("₹3,000" if in_month else "₹2,000")
    assert client.get(f"{base}/insights", params={"period": "year"}, headers=owner).status_code == 422


@DB
def test_empty_periods_say_so_and_nothing_is_invented(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("offerings-catalog", "orders", "bookings"))
    data = _insights(f"/v1/platform/businesses/{bid}", owner)
    orders = _card(data, "orders")
    assert (orders["state"], orders["value"], orders["note"]) == ("no_data", None, "No orders placed in this period.")
    assert _card(data, "bookings")["note"] == "No bookings in this period."
    assert {m["key"] for m in data["not_switched_on"]} == {"sales", "collections"}


@DB
def test_each_viewer_sees_only_what_they_may(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("offerings-catalog", "orders", "payments", "inventory"))
    base = f"/v1/platform/businesses/{bid}"
    a = primary_location(client, owner, bid)
    b = client.post(f"{base}/locations", json={"name": "Branch"}, headers=owner).json()["data"]["id"]
    item = client.post(f"{base}/products", json={"title": "Rice 5 kg", "status": "active", "price_amount": 400,
                                                  "sku": f"R-{uuid.uuid4().hex[:6]}"}, headers=owner).json()["data"]
    for loc, qty in ((a, 1), (b, 3)):
        r = client.post(f"{base}/orders", json={"location_id": loc, "payment_method": "cod",
                                                 "items": [{"offering_id": item["id"], "quantity": qty}]}, headers=owner)
        assert r.status_code == 200, r.text
    assert _card(_insights(base, owner), "orders")["value"] == "₹1,600"
    manager_a = _member(owner, bid, monkeypatch, "manager", [a])
    mine = _insights(base, manager_a)
    assert (_card(mine, "orders")["value"], _card(mine, "orders")["note"]) == ("₹400", "1 order")
    assert _card(mine, "collections")["state"] == "whole_business_only" and _card(mine, "collections")["value"] is None
    keeper = _member(owner, bid, monkeypatch, "store_keeper", [a, b])
    theirs = _insights(base, keeper)
    assert _card(theirs, "orders")["state"] == "no_permission" and _card(theirs, "orders")["value"] is None
    assert _card(theirs, "collections")["state"] == "no_permission"
    # another business's owner gets nothing
    _, other = new_identity(monkeypatch)
    create_business(client, other)
    assert client.get(f"{base}/insights", headers=other).status_code in (403, 404)


@DB
def test_bookings_count_who_came_who_is_waiting_and_who_did_not(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("offerings-catalog", "workforce", "bookings", "payments"))
    base = f"/v1/platform/businesses/{bid}"
    loc = primary_location(client, owner, bid)
    service = client.post(f"{base}/products", json={"title": "Haircut", "offering_type": "service",
                                                    "status": "active", "price_amount": 300}, headers=owner).json()["data"]
    now_ist = datetime.now(timezone.utc).astimezone(IST)
    ids = []
    for hour in (1, 2, 3, 4):  # four appointments today, early morning India time (always today)
        start = now_ist.replace(hour=hour, minute=0, second=0, microsecond=0)
        r = client.post(f"{base}/bookings", json={
            "location_id": loc, "offering_id": service["id"], "reservation_mode": "appointment",
            "starts_at": start.isoformat(), "ends_at": (start + timedelta(minutes=30)).isoformat()}, headers=owner)
        assert r.status_code == 200, r.text
        ids.append(r.json()["data"]["id"])
    for bk, status in ((0, "confirmed"), (0, "checked_in"), (0, "completed"), (1, "confirmed"), (1, "no_show"),
                       (2, "cancelled")):
        body = {"status": status} if status in ("confirmed", "checked_in", "completed") else {
            "status": status, "reason": "Did not come" if status == "no_show" else "Asked to cancel"}
        r = client.post(f"{base}/bookings/{ids[bk]}/status", json=body, headers=owner)
        assert r.status_code == 200, r.text
    card = _card(_insights(base, owner), "bookings")
    assert (card["value"], card["note"]) == ("2", "2 bookings in this period")
    detail = {d["label"]: d["value"] for d in card["detail"]}
    assert detail == {"Came in": "1", "Waiting for you to confirm": "1", "Did not come": "1",
                      "Cancelled or declined": "1"}, detail
