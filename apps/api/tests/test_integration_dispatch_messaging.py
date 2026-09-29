"""Integration: the customer hears what the delivery really did, once.

A website order chosen for delivery has a fulfilment record (what the customer
tracks). Dispatch executes it; Fulfilment follows dispatch's real state through
the worker, and the existing Messaging contract speaks from the fulfilment
events. Real API, worker, automation lane and sandbox WhatsApp on local
PostgreSQL: nothing is said while the parcel is only picked up, "on its way"
goes out once after out_for_delivery, "delivered" once after delivery, and
replays add nothing.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_testing.phase_b import create_business, drain_events, new_identity, primary_location, run_automation, sql

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)
IST = ZoneInfo("Asia/Kolkata")


def _messages(bid: str, key: str) -> list[Any]:
    return list(sql("select status from messaging_messages where business_id = :b and template_key = :k",
                    b=bid, k=key))


def _fulfilment(order_id: str) -> str:
    return str(sql("select status from fulfilment_jobs where order_id = :o", o=order_id)[0][0])


def test_dispatch_state_drives_the_customer_record_and_messages_once(monkeypatch: Any) -> None:
    monkeypatch.setenv("MESSAGING_SANDBOX", "1")
    owner_id, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=(
        "offerings-catalog", "orders", "payments", "fulfilment", "dispatch", "workforce",
        "customer-relationships", "messaging"))
    slug = str(sql("select slug from businesses where id = :b", b=bid)[0][0])
    loc = primary_location(client, owner, bid)
    base = f"/v1/platform/businesses/{bid}"
    assert client.post(f"{base}/messaging/channel/sandbox", json={
        "display_phone": "+919840011111", "display_name": "Anna Stores"}, headers=owner).status_code == 200
    assert client.patch(f"/v1/b/{bid}/fulfilment/settings", json={
        "pickup_enabled": True, "delivery_enabled": True}, headers=owner).status_code == 200
    assert client.post(f"/v1/b/{bid}/fulfilment/zones", json={
        "name": "Coimbatore", "match_type": "city", "city": "Coimbatore", "charge_amount": 30},
        headers=owner).status_code == 200
    product = client.post(f"{base}/products", json={
        "title": "Filter coffee powder", "sku": f"FC-{uuid.uuid4().hex[:6]}", "status": "active",
        "price_amount": 220, "visibility": "public"}, headers=owner)
    assert product.status_code == 200, product.text

    checkout = client.post(f"/v1/public/websites/{slug}/checkout", json={
        "items": [{"offering_id": product.json()["data"]["id"], "quantity": 1}],
        "fulfilment_mode": "delivery", "payment_method": "cod", "location_id": loc,
        "delivery_address": {"city": "Coimbatore", "line1": "12 Temple Street"},
        "guest": {"name": "Lakshmi", "email": f"{uuid.uuid4()}@example.com", "phone": "+919840022222"},
        "idempotency_key": str(uuid.uuid4())})
    assert checkout.status_code == 200, checkout.text
    order_id = checkout.json()["data"]["order"]["id"]
    drain_events(bid)

    crew = client.post(f"{base}/workforce/members", json={
        "display_name": "Anbu", "identity_id": str(owner_id), "location_ids": [loc], "primary_location_id": loc},
        headers=owner)
    assert crew.status_code == 200, crew.text
    job = client.post(f"/v1/b/{bid}/dispatch/jobs", json={
        "order_id": order_id, "kind": "delivery", "idempotency_key": f"d-{order_id}"}, headers=owner)
    assert job.status_code == 200, job.text
    job_id = job.json()["data"]["id"]
    assert job.json()["data"]["fulfilment_job_id"], "dispatch runs the customer's delivery record"
    assert client.post(f"/v1/b/{bid}/dispatch/jobs/{job_id}/assign", json={
        "member_id": crew.json()["data"]["id"]}, headers=owner).status_code == 200

    def move(status: str) -> None:
        body = {"status": status, "idempotency_key": f"{status}-{job_id}"}
        if status == "delivered":
            body["proof_note"] = "Handed to Lakshmi"
        r = client.post(f"/v1/b/{bid}/dispatch/jobs/{job_id}/status", json=body, headers=owner)
        assert r.status_code == 200, r.text
        drain_events(bid)
        drain_events(bid)

    tomorrow_morning = datetime.combine(datetime.now(IST).date() + timedelta(days=1), time(10, 30), IST)

    move("picked_up")
    assert _fulfilment(order_id) == "ready"
    run_automation(bid, now=tomorrow_morning)
    assert _messages(bid, "order_out_for_delivery") == [], "not on its way until it really is"

    move("out_for_delivery")
    assert _fulfilment(order_id) == "out_for_delivery"
    run_automation(bid, now=tomorrow_morning)
    run_automation(bid, now=tomorrow_morning + timedelta(minutes=5))
    assert [m[0] for m in _messages(bid, "order_out_for_delivery")] == ["sent"]

    move("out_for_delivery")  # the same tap again
    run_automation(bid, now=tomorrow_morning + timedelta(minutes=10))
    assert len(_messages(bid, "order_out_for_delivery")) == 1

    move("delivered")
    assert _fulfilment(order_id) == "delivered"
    assert [m[0] for m in _messages(bid, "order_delivered")] == ["sent"]
    drain_events(bid)
    assert len(_messages(bid, "order_delivered")) == 1
    assert len(_messages(bid, "order_out_for_delivery")) == 1
