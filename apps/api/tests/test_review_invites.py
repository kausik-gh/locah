"""P1-09 review invitations follow real completion events, with no AI or provider spend."""

from __future__ import annotations

import os
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from platform_api.main import app
from platform_testing.phase_b import create_business, drain_events, new_identity, primary_location, run_automation, sql

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)
IST = ZoneInfo("Asia/Kolkata")


def _enable_reviews_in_test(business_id: str) -> None:
    # The module stays unavailable to owners until the rest of P1-09 ships.
    sql("""INSERT INTO business_module_states (business_id, module_id, activation_state)
           VALUES (:b, 'reviews', 'enabled')
           ON CONFLICT (business_id, module_id) DO UPDATE SET activation_state = 'enabled'""", b=business_id)


def _due_daytime() -> datetime:
    day = datetime.now(IST).date() + timedelta(days=1)
    return datetime.combine(day, time(10, 0), IST).astimezone(timezone.utc)


@DB
def test_completed_order_invites_once_and_decline_stops_the_message(monkeypatch: Any) -> None:
    monkeypatch.setenv("MESSAGING_SANDBOX", "1")
    _, owner = new_identity(monkeypatch)
    business_id = create_business(client, owner, modules=(
        "offerings-catalog", "orders", "payments", "customer-relationships", "messaging",
    ))
    _enable_reviews_in_test(business_id)
    base = f"/v1/platform/businesses/{business_id}"
    connected = client.post(f"{base}/messaging/channel/sandbox", json={"display_phone": "+919840000101"},
                            headers=owner)
    assert connected.status_code == 200, connected.text
    product = client.post(f"{base}/products", json={"status": "active", "offering_type": "product",
                                                       "title": "Coffee beans", "price_amount": 320},
                          headers=owner).json()["data"]
    contact = client.post(f"{base}/customers", json={"display_name": "Anika", "phone": "+919876500111"},
                          headers=owner).json()["data"]
    location_id = primary_location(client, owner, business_id)

    def complete_order() -> dict[str, Any]:
        created = client.post(f"{base}/orders", json={"location_id": location_id,
                                                        "customer_contact_id": contact["id"],
                                                        "items": [{"offering_id": product["id"], "quantity": 1}]},
                              headers=owner)
        assert created.status_code == 200, created.text
        order = dict(created.json()["data"])
        for status in ("accepted", "preparing", "ready", "completed"):
            changed = client.post(f"{base}/orders/{order['id']}/status", json={"status": status}, headers=owner)
            assert changed.status_code == 200, changed.text
        return order

    first = complete_order()
    drain_events(business_id)
    invited = sql("""SELECT source_id, label, token_hash FROM reviews_invitations
                     WHERE business_id = :b ORDER BY created_at""", b=business_id)
    assert len(invited) == 1 and str(invited[0][0]) == first["id"]
    assert invited[0][1] == f"Order {first['order_number']}" and len(invited[0][2]) == 64
    assert sql("""SELECT count(*) FROM automation_steps WHERE business_id = :b
                  AND ladder_key = 'review.request' AND status = 'pending'""", b=business_id) == [(1,)]
    sql("""INSERT INTO platform_outbox_events (business_id, event_type, payload)
           VALUES (CAST(:b AS uuid), 'order.completed',
                   jsonb_build_object('business_id', CAST(:b_payload AS text), 'order_id', CAST(:source AS text)))""",
        b=business_id, b_payload=business_id, source=first["id"])
    drain_events(business_id)
    assert sql("SELECT count(*) FROM reviews_invitations WHERE business_id = :b", b=business_id) == [(1,)]
    assert sql("""SELECT count(*) FROM automation_steps WHERE business_id = :b
                  AND ladder_key = 'review.request'""", b=business_id) == [(1,)]

    run_automation(business_id, now=_due_daytime())
    sent = sql("""SELECT status, body FROM messaging_messages
                  WHERE business_id = :b AND template_key = 'review_request'""", b=business_id)
    assert len(sent) == 1 and sent[0][0] == "sent"
    assert f"Order {first['order_number']}" in sent[0][1] and "/review/" in sent[0][1]

    second = complete_order()
    drain_events(business_id)
    sql("""UPDATE reviews_invitations SET declined_at = now()
           WHERE business_id = :b AND source_id = :source""", b=business_id, source=second["id"])
    run_automation(business_id, now=_due_daytime())
    assert sql("""SELECT count(*) FROM messaging_messages
                  WHERE business_id = :b AND template_key = 'review_request'""", b=business_id) == [(1,)]


@DB
def test_completed_booking_invites_but_confirmed_booking_does_not(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    business_id = create_business(client, owner, modules=(
        "workforce", "bookings", "offerings-catalog", "payments", "customer-relationships",
    ))
    _enable_reviews_in_test(business_id)
    base = f"/v1/platform/businesses/{business_id}"
    service = client.post(f"{base}/products", json={"title": "Haircut", "offering_type": "service",
                                                       "status": "active", "price_amount": 300},
                          headers=owner).json()["data"]
    contact = client.post(f"{base}/customers", json={"display_name": "Meena", "phone": "+919876500112"},
                          headers=owner).json()["data"]
    starts = datetime.combine(datetime.now(IST).date() + timedelta(days=2), time(11, 0), IST)
    booking = client.post(f"{base}/bookings", json={
        "location_id": primary_location(client, owner, business_id), "offering_id": service["id"],
        "customer_contact_id": contact["id"], "reservation_mode": "appointment",
        "starts_at": starts.isoformat(), "ends_at": (starts + timedelta(hours=1)).isoformat(),
    }, headers=owner)
    assert booking.status_code == 200, booking.text
    booking_id = booking.json()["data"]["id"]
    for status in ("confirmed", "checked_in"):
        changed = client.post(f"{base}/bookings/{booking_id}/status", json={"status": status}, headers=owner)
        assert changed.status_code == 200, changed.text
    drain_events(business_id)
    assert sql("SELECT count(*) FROM reviews_invitations WHERE business_id = :b", b=business_id) == [(0,)]
    changed = client.post(f"{base}/bookings/{booking_id}/status", json={"status": "completed"}, headers=owner)
    assert changed.status_code == 200, changed.text
    drain_events(business_id)
    invited = sql("SELECT source_type, label FROM reviews_invitations WHERE business_id = :b", b=business_id)
    assert len(invited) == 1 and invited[0][0] == "booking" and "Haircut" in invited[0][1]
