"""WhatsApp foundation (Capability Universe §9.1, §12.1, §12.4, §12.5, §12.6;
§26.3 P1-07 "owner connects a number and receives order notifications").

Zero live provider calls: the sandbox number records what would be sent, and
inbound traffic is WhatsApp's own webhook format (messaging.fixtures) through
the same code path a real delivery takes. The real Meta connection is
activation-required and is checked here only for refusing to run unconfigured.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.messaging.fixtures import status_payload, webhook_payload
from platform_core.messaging.templates import check_library, render
from platform_core.services.messaging import normalise_phone
from platform_testing.phase_b import (
    assert_tenant_isolated,
    billing_shop,
    create_business,
    drain_events,
    new_identity,
    primary_location,
    run_automation,
    sql,
)

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)


# ---------------------------------------------------------------- no DB
def test_the_template_library_would_pass_whatsapps_checks() -> None:
    assert check_library() == []
    assert render("order_confirmed", "hi", ["ORD-1", "Sri Stores", "₹450.00"]).startswith("आपका ऑर्डर ORD-1")


def test_phone_numbers_become_whatsapp_ids() -> None:
    assert normalise_phone("98401 23456") == "919840123456"
    assert normalise_phone("+91 98401-23456") == "919840123456"
    assert normalise_phone("098401 23456") == "919840123456"
    assert normalise_phone("12345") is None


# ---------------------------------------------------------------- helpers
@pytest.fixture(autouse=True)
def _sandbox(monkeypatch: Any) -> None:
    monkeypatch.setenv("MESSAGING_SANDBOX", "1")


def _connect(owner: dict[str, str], bid: str, phone: str = "+919840000001") -> dict[str, Any]:
    r = client.post(f"/v1/platform/businesses/{bid}/messaging/channel/sandbox",
                    json={"display_phone": phone, "display_name": "Sri Stores"}, headers=owner)
    assert r.status_code == 200, r.text
    return dict(r.json()["data"])


def _inbound(owner: dict[str, str], bid: str, **body: Any) -> dict[str, Any]:
    r = client.post(f"/v1/platform/businesses/{bid}/messaging/sandbox/inbound",
                    json={"from_phone": "919876500001", "name": "Kavya", **body}, headers=owner)
    assert r.status_code == 200, r.text
    return dict(r.json()["data"])


def _messages(bid: str, **where: str) -> list[Any]:
    clause = " and ".join(f"m.{k} = :{k}" for k in where)
    rows: list[Any] = sql("select m.direction, m.kind, m.template_key, m.status, m.body, c.kind, c.wa_id, m.error "
                          "from messaging_messages m join messaging_conversations c on c.id = m.conversation_id "
                          f"where m.business_id = :b {'and ' + clause if clause else ''} order by m.created_at",
                          b=bid, **where)
    return rows


def _join(owner: dict[str, str], bid: str, monkeypatch: Any, role: str, locs: list[str]) -> dict[str, str]:
    person_id, headers = new_identity(monkeypatch)
    inv = client.post(f"/v1/b/{bid}/team/invitations", json={"identity_id": str(person_id), "role": "member"},
                      headers=owner)
    mid = inv.json()["data"]["id"]
    assert client.post(f"/v1/b/{bid}/team/members/{mid}/activate", headers=owner).status_code == 200
    given = client.put(f"/v1/platform/businesses/{bid}/members/{mid}/role", json={"role": role, "location_ids": locs},
                       headers=owner)
    assert given.status_code == 200, given.text
    return dict(headers)


def _readiness(bid: str) -> dict[str, Any]:
    import asyncio

    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    from platform_core.services.module_readiness import readiness
    from platform_testing.phase_b import db_url

    async def run() -> dict[str, Any]:
        engine = create_async_engine(db_url(), poolclass=NullPool)
        try:
            async with AsyncSession(engine) as s:
                return dict((await readiness(s, uuid.UUID(bid), ["messaging"]))["messaging"])
        finally:
            await engine.dispose()

    return asyncio.run(run())


# ---------------------------------------------------------------- connecting
@DB
def test_meta_connection_is_activation_required_and_the_sandbox_is_test_only(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("messaging",))
    base = f"/v1/platform/businesses/{bid}/messaging"
    setup = client.get(f"{base}/setup", headers=owner).json()["data"]
    assert setup["channel"] is None and setup["meta_ready"] is False and setup["meta"] is None
    signup = client.post(f"{base}/channel/embedded-signup", json={"code": "abcd", "waba_id": "123",
                                                                "phone_number_id": "456"}, headers=owner)
    assert signup.status_code == 503 and signup.json()["error"]["details"]["activation_required"] is True
    monkeypatch.setenv("MESSAGING_SANDBOX", "0")
    assert client.post(f"{base}/channel/sandbox", json={"display_phone": "+919840000001"},
                       headers=owner).status_code == 409
    monkeypatch.setenv("MESSAGING_SANDBOX", "1")
    ch = _connect(owner, bid)
    assert ch["status"] == "connected" and ch["sandbox"] is True and ch["display_phone"] == "+919840000001"
    setup = client.get(f"{base}/setup", headers=owner).json()["data"]
    approved = {t["key"]: t["status"] for t in setup["templates"]}
    assert approved["order_confirmed"] == {"en": "approved", "ta": "approved", "hi": "approved"}
    assert approved["offer_announcement"] == {"en": None, "ta": None, "hi": None}, "P3 templates wait for P3"
    assert _readiness(bid)["steps"] == [{"key": "channel_connected", "label": "Connect your WhatsApp number",
                                         "done": True}]
    assert client.post(f"{base}/channel/sandbox", json={"display_phone": "+919840000002"},
                       headers=owner).status_code == 409, "one number per business"


# ---------------------------------------------------------------- the done-when
@DB
def test_owner_connects_a_number_and_receives_order_notifications(monkeypatch: Any) -> None:
    """§26.3 P1-07: the owner connects the business number, asks for new-order
    alerts on their own WhatsApp; a customer orders and hears back at each step."""
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("offerings-catalog", "orders", "payments", "customer-relationships",
                                                  "messaging"))
    base = f"/v1/platform/businesses/{bid}"
    _connect(owner, bid)
    alerts = client.put(f"{base}/messaging/alerts/me", json={"enabled": True, "phone": "98401 99999",
                                                             "kinds": ["order.new", "chat.waiting"]}, headers=owner)
    assert alerts.status_code == 200, alerts.text
    item = client.post(f"{base}/products", json={"status": "active", "offering_type": "product", "title": "Ghee 500 ml",
                                                 "price_amount": 320}, headers=owner).json()["data"]
    contact = client.post(f"{base}/customers", json={"display_name": "Kavya", "phone": "98765 00001"},
                          headers=owner).json()["data"]
    loc = primary_location(client, owner, bid)
    order = client.post(f"{base}/orders", json={"location_id": loc, "customer_contact_id": contact["id"],
                                                "items": [{"offering_id": item["id"], "quantity": 2}]}, headers=owner)
    assert order.status_code == 200, order.text
    o = order.json()["data"]
    drain_events(bid)
    staff = _messages(bid, template_key="staff_alert")
    assert len(staff) == 1 and staff[0][3] == "sent" and staff[0][5] == "staff" and staff[0][6] == "919840199999"
    assert f"New order {o['order_number']} for ₹640.00 from Kavya" in staff[0][4]
    received = _messages(bid, template_key="order_received")
    assert len(received) == 1 and received[0][6] == "919876500001" and received[0][3] == "sent"
    accepted = client.post(f"{base}/orders/{o['id']}/status", json={"status": "accepted", "version": o["version"]},
                           headers=owner)
    assert accepted.status_code == 200, accepted.text
    drain_events(bid)
    drain_events(bid)
    assert [m[2] for m in _messages(bid, direction="out") if m[5] == "customer"] == ["order_received", "order_confirmed"]
    # Staff alerts never show as customer chats.
    inbox = client.get(f"{base}/messaging/conversations", headers=owner).json()["data"]
    assert [c["phone"] for c in inbox["conversations"]] == ["+919876500001"]
    meter = next(m for m in client.get(f"{base}/usage", headers=owner).json()["data"]
                 if m["resource"] == "whatsapp_message")
    assert meter["used"] == 3 and meter["counting"] is True
    # The owner switches "order confirmed" off: the next acceptance says nothing.
    client.put(f"{base}/messaging/settings", json={"customer_updates": {"order_confirmed": False}}, headers=owner)
    o2 = client.post(f"{base}/orders", json={"location_id": loc, "customer_contact_id": contact["id"],
                                             "items": [{"offering_id": item["id"], "quantity": 1}]}, headers=owner)
    client.post(f"{base}/orders/{o2.json()['data']['id']}/status",
                json={"status": "accepted", "version": o2.json()["data"]["version"]}, headers=owner)
    drain_events(bid)
    drain_events(bid)
    assert len(_messages(bid, template_key="order_confirmed")) == 1


# ---------------------------------------------------------------- inbound, the inbox, §12.6
@DB
def test_duplicate_webhooks_create_one_message_and_a_person_pauses_automation(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("customer-relationships", "messaging"))
    base = f"/v1/platform/businesses/{bid}/messaging"
    _connect(owner, bid)
    first = _inbound(owner, bid, text="Do you deliver to Adyar?", message_id="wamid.dup.1")
    again = _inbound(owner, bid, text="Do you deliver to Adyar?", message_id="wamid.dup.1")
    assert first["messages"] == 1 and again == {**again, "messages": 0, "duplicates": 1}
    inbound = _messages(bid, direction="in")
    assert len(inbound) == 1, "§12.6: duplicate webhook deliveries create one message"
    contact = sql("select display_name, phone from customer_relationships_contacts where business_id = :b", b=bid)
    assert contact == [("Kavya", "+919876500001")], "a new number becomes a customer"
    conv = client.get(f"{base}/conversations?view=waiting", headers=owner).json()["data"]
    assert conv["counts"]["waiting"] == 1
    c = conv["conversations"][0]
    assert c["needs_person"] and c["window_open"] and c["unread"] == 1
    acks = [m for m in _messages(bid, direction="out")]
    assert len(acks) == 1 and "will reply here soon" in acks[0][4] and acks[0][2] is None

    # A person replies: the chat is theirs, automation keeps out for 12 hours.
    reply = client.post(f"{base}/conversations/{c['id']}/messages", json={"body": "Yes, free above ₹500."},
                        headers=owner)
    assert reply.status_code == 200, reply.text
    thread = reply.json()["data"]
    assert thread["needs_person"] is False and thread["bot_paused_until"] is not None
    assert thread["messages"][-1]["sent_by_name"] is not None
    _inbound(owner, bid, text="talk to a person please")
    outs = _messages(bid, direction="out")
    assert len(outs) == 2, "§12.6: no automatic message in a thread a person answered in the last 12 hours"
    # Handing back to LOCAH lifts the pause.
    client.post(f"{base}/conversations/{c['id']}/state", json={"handler": "bot"}, headers=owner)
    _inbound(owner, bid, text="human")
    assert len(_messages(bid, direction="out")) == 3

    # Outside the 24-hour window only templates may go.
    sql("update messaging_conversations set last_inbound_at = now() - interval '25 hours' where id = :c", c=c["id"])
    late = client.post(f"{base}/conversations/{c['id']}/messages", json={"body": "Hello?"}, headers=owner)
    assert late.status_code == 409 and "24 hours" in late.text


@DB
def test_delivery_statuses_and_the_owners_app_replies(monkeypatch: Any) -> None:
    from platform_core.services.messaging import MessagingService

    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("customer-relationships", "messaging"))
    base = f"/v1/platform/businesses/{bid}/messaging"
    ch = _connect(owner, bid)
    _inbound(owner, bid, text="hi, is the shop open?")
    [(pid,)] = sql("select phone_number_id from messaging_channels where id = :c", c=ch["id"])
    [(ack_id,)] = sql("select provider_message_id from messaging_messages where business_id = :b and direction = 'out'",
                      b=bid)

    async def deliver(payload: dict[str, Any]) -> dict[str, int]:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.pool import NullPool

        from platform_testing.phase_b import db_url

        engine = create_async_engine(db_url(), poolclass=NullPool)
        try:
            async with AsyncSession(engine) as s, s.begin():
                return dict(await MessagingService.process_webhook(s, payload))
        finally:
            await engine.dispose()

    import asyncio

    asyncio.run(deliver(status_payload(pid, ack_id, "read", "919876500001")))
    asyncio.run(deliver(status_payload(pid, ack_id, "delivered", "919876500001")))
    assert sql("select status from messaging_messages where provider_message_id = :p", p=ack_id) == [("read",)], \
        "statuses only move forward"
    unknown = asyncio.run(deliver(status_payload("not-a-number", ack_id, "failed", "1")))
    assert unknown["unknown_number"] == 1
    # Coexistence: the owner answered from the WhatsApp Business app.
    _inbound(owner, bid, text="Open till 9", echo=True)
    conv = client.get(f"{base}/conversations", headers=owner).json()["data"]["conversations"][0]
    assert conv["needs_person"] is False and conv["bot_paused_until"] is not None
    echo = _messages(bid, direction="out")[-1]
    assert echo[4] == "Open till 9"


@DB
def test_marketing_needs_an_opt_in_and_stop_withdraws_it(monkeypatch: Any) -> None:
    """§12.6: a customer without marketing consent never receives a marketing template."""
    import asyncio

    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    from platform_core.services.messaging import MessagingService
    from platform_testing.phase_b import db_url

    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("customer-relationships", "messaging"))
    base = f"/v1/platform/businesses/{bid}"
    _connect(owner, bid)
    assert client.post(f"{base}/messaging/templates/submit?keys=offer_announcement", headers=owner).status_code == 200
    contact = client.post(f"{base}/customers", json={"display_name": "Anu", "phone": "+919876500002"},
                          headers=owner).json()["data"]

    async def offer() -> str:
        engine = create_async_engine(db_url(), poolclass=NullPool)
        try:
            async with AsyncSession(engine) as s, s.begin():
                msg = await MessagingService.send_template(
                    s, uuid.UUID(bid), to="+919876500002", key="offer_announcement",
                    params=["Sri Stores", "10% off this weekend"], contact_id=uuid.UUID(contact["id"]))
                return str(msg.status)
        finally:
            await engine.dispose()

    assert asyncio.run(offer()) == "blocked"
    client.post(f"{base}/customers/{contact['id']}/consents",
                json={"purpose": "marketing", "channel": "whatsapp", "granted": True, "source": "counter_form"},
                headers=owner)
    assert asyncio.run(offer()) == "sent"
    _inbound(owner, bid, from_phone="919876500002", name="Anu", text="STOP")
    assert asyncio.run(offer()) == "blocked", "STOP withdraws the marketing opt-in"
    statuses = [m[3] for m in _messages(bid, template_key="offer_announcement")]
    assert statuses == ["blocked", "sent", "blocked"]


@DB
def test_the_monthly_cap_stops_sending(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("customer-relationships", "messaging"))
    base = f"/v1/platform/businesses/{bid}"
    _connect(owner, bid)
    assert client.put(f"{base}/usage/whatsapp_message/cap", json={"cap": 1}, headers=owner).status_code == 200
    _inbound(owner, bid, text="hello")  # the acknowledgement uses the one message
    conv = client.get(f"{base}/messaging/conversations", headers=owner).json()["data"]["conversations"][0]
    over = client.post(f"{base}/messaging/conversations/{conv['id']}/messages", json={"body": "Hi!"}, headers=owner)
    assert over.status_code == 409 and "limit" in over.text
    assert _messages(bid, direction="out")[-1][3] == "blocked"


# ---------------------------------------------------------------- reminders and waiting chats
@DB
def test_khata_and_bill_reminders_go_out_on_whatsapp_when_due(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = billing_shop(client, owner, modules=("ledger", "customer-relationships", "messaging"))
    base, bid = shop["base"], shop["bid"]
    _connect(owner, bid)
    client.post(f"{base}/messaging/templates/submit", headers=owner)
    acct = client.post(f"{base}/ledger/accounts", json={"party_type": "customer", "display_name": "Devi",
                                                        "phone": "+919876500003", "credit_days": 7},
                       headers=owner).json()["data"]
    client.post(f"{base}/ledger/accounts/{acct['id']}/entries", json={
        "kind": "opening_balance", "amount": 900, "note": "From the notebook",
        "entry_date": (date.today() - timedelta(days=3)).isoformat()}, headers=owner)
    bill = client.post(f"{base}/invoices", json={
        "lines": [{"title": "Site visit", "hsn_sac": "998719", "rate": 18, "unit_price": 1000}],
        "buyer": {"name": "Kaveri Builders", "phone": "+919876500004"},
        "due_date": (date.today() + timedelta(days=2)).isoformat()}, headers=owner).json()["data"]
    drain_events(bid)
    steps = sql("select ladder_key, step_key from automation_steps where business_id = :b order by ladder_key, due_at",
                b=bid)
    assert ("ledger.statement", "due_day") in steps and ("invoice.overdue", "due_day") in steps
    later = datetime.now(timezone.utc) + timedelta(days=9)
    run_automation(bid, now=later.replace(hour=6, minute=0))  # 11:30 IST: outside quiet hours
    due = _messages(bid, template_key="payment_due")
    bodies = {m[6]: m[4] for m in due}
    assert "₹900.00 is due" in bodies["919876500003"] and "/khata/" in bodies["919876500003"]
    assert "₹1,180.00 is due" in bodies["919876500004"] and "/bill/" in bodies["919876500004"]
    # Paid bills stop reminding.
    client.post(f"{base}/invoices/{bill['id']}/payments", json={"amount": 1180, "method": "upi"}, headers=owner)
    drain_events(bid)
    pending = sql("select count(*) from automation_steps where business_id = :b and ladder_key = 'invoice.overdue' "
                  "and status = 'pending'", b=bid)
    assert pending == [(0,)]


@DB
def test_out_for_delivery_sends_the_tracking_link_and_delivered_says_so(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("offerings-catalog", "orders", "payments", "fulfilment",
                                                  "customer-relationships", "messaging"))
    base = f"/v1/platform/businesses/{bid}"
    _connect(owner, bid)
    item = client.post(f"{base}/products", json={"status": "active", "offering_type": "product", "title": "Cake",
                                                 "price_amount": 600}, headers=owner).json()["data"]
    contact = client.post(f"{base}/customers", json={"display_name": "Latha", "phone": "+919876500007"},
                          headers=owner).json()["data"]
    loc = primary_location(client, owner, bid)
    order = client.post(f"{base}/orders", json={"location_id": loc, "customer_contact_id": contact["id"],
                                                "items": [{"offering_id": item["id"], "quantity": 1}]},
                        headers=owner).json()["data"]
    tok = f"tok-{uuid.uuid4().hex[:12]}"
    [(job_id,)] = sql("insert into fulfilment_jobs (business_id, order_id, location_id, mode, status, tracking_token, "
                      "tracking_expires_at) values (:b, :o, :l, 'delivery', 'ready', :t, now() + interval "
                      "'7 days') returning id", b=bid, o=order["id"], l=loc, t=tok)
    moved = client.patch(f"/v1/b/{bid}/fulfilment/jobs/{job_id}/status", json={"status": "out_for_delivery"}, headers=owner)
    assert moved.status_code == 200, moved.text
    drain_events(bid)
    run_automation(bid, now=datetime.now(timezone.utc).replace(hour=6, minute=0) + timedelta(days=1))
    [tracking] = _messages(bid, template_key="order_out_for_delivery")
    assert tracking[3] == "sent" and f"/track/{order['id']}?token={tok}" in tracking[4]
    done = client.patch(f"/v1/b/{bid}/fulfilment/jobs/{job_id}/status", json={"status": "delivered"}, headers=owner)
    assert done.status_code == 200, done.text
    drain_events(bid)
    assert [m[2] for m in _messages(bid, template_key="order_delivered")] == ["order_delivered"]


@DB
def test_bookings_are_confirmed_and_reminded_and_a_cancel_stops_it(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("workforce", "bookings", "offerings-catalog", "payments",
                                                  "customer-relationships", "messaging"))
    base = f"/v1/platform/businesses/{bid}"
    _connect(owner, bid)
    service = client.post(f"{base}/products", json={"title": "Haircut", "offering_type": "service", "status": "active",
                                                    "price_amount": 300}, headers=owner).json()["data"]
    contact = client.post(f"{base}/customers", json={"display_name": "Meena", "phone": "+919876500006"},
                          headers=owner).json()["data"]
    from zoneinfo import ZoneInfo

    ist = ZoneInfo("Asia/Kolkata")
    starts = datetime.combine(datetime.now(ist).date() + timedelta(days=2), datetime.min.time().replace(hour=11),
                              ist).astimezone(timezone.utc)  # 11 am, the day after tomorrow
    booking = client.post(f"{base}/bookings", json={
        "location_id": primary_location(client, owner, bid), "offering_id": service["id"],
        "customer_contact_id": contact["id"], "reservation_mode": "appointment",
        "starts_at": starts.isoformat(), "ends_at": (starts + timedelta(hours=1)).isoformat()}, headers=owner)
    assert booking.status_code == 200, booking.text
    bk = booking.json()["data"]
    assert client.post(f"{base}/bookings/{bk['id']}/status", json={"status": "confirmed"},
                       headers=owner).status_code == 200
    drain_events(bid)
    confirmed = _messages(bid, template_key="booking_confirmed")
    assert len(confirmed) == 1 and "Haircut" in confirmed[0][4]
    steps = sql("select step_key, status from automation_steps where business_id = :b and ladder_key = 'booking.reminder' "
                "order by due_at", b=bid)
    assert steps == [("day_before", "pending"), ("two_hours", "pending")]
    # The day before, at 11:30 am, the reminder goes.
    run_automation(bid, now=starts - timedelta(hours=23, minutes=30))
    reminded = _messages(bid, template_key="booking_reminder")
    assert len(reminded) == 1 and reminded[0][3] == "sent"
    # Cancelled: the 2-hour reminder never goes.
    assert client.post(f"{base}/bookings/{bk['id']}/status", json={"status": "cancelled", "reason": "Unwell"},
                       headers=owner).status_code == 200
    drain_events(bid)
    assert sql("select status from automation_steps where business_id = :b and step_key = 'two_hours'",
               b=bid) == [("cancelled",)]


@DB
def test_a_rescheduled_booking_is_reminded_for_its_new_time_only_once(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("workforce", "bookings", "offerings-catalog", "payments",
                                                  "customer-relationships", "messaging"))
    base = f"/v1/platform/businesses/{bid}"
    _connect(owner, bid)
    service = client.post(f"{base}/products", json={"title": "Facial", "offering_type": "service", "status": "active",
                                                    "price_amount": 900}, headers=owner).json()["data"]
    contact = client.post(f"{base}/customers", json={"display_name": "Revathi", "phone": "+919876500016"},
                          headers=owner).json()["data"]
    from zoneinfo import ZoneInfo

    ist = ZoneInfo("Asia/Kolkata")
    starts = datetime.combine(datetime.now(ist).date() + timedelta(days=2), datetime.min.time().replace(hour=11),
                              ist).astimezone(timezone.utc)
    booking = client.post(f"{base}/bookings", json={
        "location_id": primary_location(client, owner, bid), "offering_id": service["id"],
        "customer_contact_id": contact["id"], "reservation_mode": "appointment",
        "starts_at": starts.isoformat(), "ends_at": (starts + timedelta(hours=1)).isoformat()}, headers=owner)
    assert booking.status_code == 200, booking.text
    bk = booking.json()["data"]
    assert client.post(f"{base}/bookings/{bk['id']}/status", json={"status": "confirmed"},
                       headers=owner).status_code == 200
    drain_events(bid)
    moved_to = starts + timedelta(days=1)
    moved = client.post(f"{base}/bookings/{bk['id']}/reschedule", json={
        "starts_at": moved_to.isoformat(), "ends_at": (moved_to + timedelta(hours=1)).isoformat(),
        "reason": "Customer asked"}, headers=owner)
    assert moved.status_code == 200, moved.text
    drain_events(bid)
    steps = sql("select step_key, status, period_key from automation_steps where business_id = :b "
                "and ladder_key = 'booking.reminder' order by created_at, due_at", b=bid)
    old_key, new_key = starts.isoformat(), moved_to.isoformat()
    assert [(k, st) for k, st, key in steps if key == old_key] == [("day_before", "cancelled"),
                                                                   ("two_hours", "cancelled")], steps
    assert [(k, st) for k, st, key in steps if key == new_key] == [("day_before", "pending"),
                                                                   ("two_hours", "pending")], steps
    # At the old day-before moment nothing goes; at the new one, one reminder.
    run_automation(bid, now=starts - timedelta(hours=23, minutes=30))
    assert _messages(bid, template_key="booking_reminder") == []
    run_automation(bid, now=moved_to - timedelta(hours=23, minutes=30))
    run_automation(bid, now=moved_to - timedelta(hours=23, minutes=20))
    reminded = _messages(bid, template_key="booking_reminder")
    assert len(reminded) == 1 and reminded[0][3] == "sent"


@DB
def test_a_chat_waiting_ten_minutes_reaches_needs_you_now_and_the_owners_whatsapp(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("customer-relationships", "messaging"))
    base = f"/v1/platform/businesses/{bid}"
    _connect(owner, bid)
    client.put(f"{base}/messaging/alerts/me", json={"enabled": True, "phone": "+919840199999",
                                                    "kinds": ["chat.waiting"]}, headers=owner)
    _inbound(owner, bid, text="Is my order coming?")
    sql("update messaging_conversations set waiting_since = now() - interval '12 minutes' where business_id = :b", b=bid)
    run_automation(bid, now=datetime.now(timezone.utc) + timedelta(minutes=11))
    alert = _messages(bid, template_key="staff_alert")
    assert len(alert) == 1 and "Kavya has waited" in alert[0][4]
    home = client.get(f"{base}/home", headers=owner).json()["data"]
    now = next(b for b in home["bands"] if b["key"] == "now")
    assert any(i["label"] == "customers waiting over 10 minutes on WhatsApp" for i in now["items"]), now
    notes = sql("select notification_type from platform_notifications where business_id = :b", b=bid)
    assert ("messaging.waiting",) in notes


# ---------------------------------------------------------------- documents from the business number
@DB
def test_bills_and_statements_are_sent_from_the_business_number(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = billing_shop(client, owner, modules=("ledger", "customer-relationships", "messaging"))
    base, bid = shop["base"], shop["bid"]
    bill = client.post(f"{base}/invoices", json={
        "lines": [{"title": "Repair", "hsn_sac": "998719", "rate": 18, "unit_price": 500}],
        "buyer": {"name": "Ravi", "phone": "+919876500005"}}, headers=owner).json()["data"]
    not_yet = client.post(f"{base}/invoices/{bill['id']}/whatsapp", headers=owner)
    assert not_yet.status_code == 409 and "not connected" in not_yet.text
    _connect(owner, bid)
    sent = client.post(f"{base}/invoices/{bill['id']}/whatsapp", headers=owner)
    assert sent.status_code == 200, sent.text
    assert bill["number"] in sent.json()["data"]["body"] and "/bill/" in sent.json()["data"]["body"]
    acct = client.post(f"{base}/ledger/accounts", json={"party_type": "customer", "display_name": "Ravi",
                                                        "phone": "+919876500005", "opening_balance": 250},
                       headers=owner).json()["data"]
    st = client.post(f"{base}/ledger/accounts/{acct['id']}/whatsapp", headers=owner)
    assert st.status_code == 200 and "₹250.00 is due" in st.json()["data"]["body"]
    # One customer, one chat, both documents in it.
    convs = client.get(f"{base}/messaging/conversations", headers=owner).json()["data"]["conversations"]
    assert len(convs) == 1
    accountant = _join(owner, bid, monkeypatch, "accountant", [])
    assert client.post(f"{base}/ledger/accounts/{acct['id']}/whatsapp", headers=accountant).status_code == 403, \
        "the accountant never messages customers (§7.2)"


# ---------------------------------------------------------------- roles, webhooks, isolation
@DB
def test_roles_manager_replies_store_keeper_and_accountant_see_no_chats(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("customer-relationships", "inventory", "orders", "payments",
                                                  "invoicing", "messaging"))
    base = f"/v1/platform/businesses/{bid}/messaging"
    _connect(owner, bid)
    _inbound(owner, bid, text="hello")
    loc = primary_location(client, owner, bid)
    manager = _join(owner, bid, monkeypatch, "manager", [loc])
    keeper = _join(owner, bid, monkeypatch, "store_keeper", [loc])
    accountant = _join(owner, bid, monkeypatch, "accountant", [])
    listing = client.get(f"{base}/conversations", headers=manager)
    assert listing.status_code == 200
    cid = listing.json()["data"]["conversations"][0]["id"]
    assert client.post(f"{base}/conversations/{cid}/messages", json={"body": "Hi Kavya"},
                       headers=manager).status_code == 200
    assert client.post(f"{base}/channel/sandbox", json={"display_phone": "+919840000009"},
                       headers=manager).status_code == 403
    for who in (keeper, accountant):
        assert client.get(f"{base}/conversations", headers=who).status_code == 403
    # A chat goes only to someone who can reply on WhatsApp.
    assert client.post(f"{base}/conversations/{cid}/assign", json={"assigned_to": str(uuid.uuid4())},
                       headers=manager).status_code == 422


@DB
def test_the_webhook_needs_meta_signature_and_is_off_until_activated(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("customer-relationships", "messaging"))
    ch = _connect(owner, bid)
    [(pid,)] = sql("select phone_number_id from messaging_channels where id = :c", c=ch["id"])
    body = json.dumps(webhook_payload(pid, "+919840000001", {"from_phone": "919876500009", "name": "Ravi",
                                                              "text": "hello from Meta"})).encode()
    monkeypatch.delenv("META_APP_SECRET", raising=False)
    assert client.post("/v1/webhooks/whatsapp", content=body).status_code == 404
    assert client.get("/v1/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=x&hub.challenge=1").status_code == 404
    monkeypatch.setenv("META_APP_SECRET", "test-app-secret")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-me")
    assert client.get("/v1/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=verify-me&hub.challenge=42").text == "42"
    assert client.get("/v1/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=no&hub.challenge=42").status_code == 403
    assert client.post("/v1/webhooks/whatsapp", content=body,
                       headers={"X-Hub-Signature-256": "sha256=" + "0" * 64}).status_code == 403
    good = "sha256=" + hmac.new(b"test-app-secret", body, hashlib.sha256).hexdigest()
    ok = client.post("/v1/webhooks/whatsapp", content=body, headers={"X-Hub-Signature-256": good})
    assert ok.status_code == 200 and ok.json()["data"]["messages"] == 1
    assert _messages(bid, direction="in")[0][4] == "hello from Meta"


@DB
@pytest.mark.asyncio
@pytest.mark.parametrize("table", ["messaging_channels", "messaging_conversations", "messaging_messages"])
async def test_messaging_tables_are_tenant_isolated(table: str) -> None:
    async def insert(session: AsyncSession, business_id: uuid.UUID) -> None:
        ch = (await session.execute(text(
            "insert into messaging_channels (business_id, provider, status, phone_number_id) "
            "values (:b, 'sandbox', 'connected', :p) returning id"), {"b": business_id, "p": f"iso-{business_id}"})).scalar()
        if table == "messaging_channels":
            return
        conv = (await session.execute(text(
            "insert into messaging_conversations (business_id, channel_id, wa_id) values (:b, :c, '919800000000') "
            "returning id"), {"b": business_id, "c": ch})).scalar()
        if table == "messaging_messages":
            await session.execute(text(
                "insert into messaging_messages (business_id, conversation_id, direction, kind, status) "
                "values (:b, :c, 'in', 'text', 'received')"), {"b": business_id, "c": conv})

    await assert_tenant_isolated(table, insert)
