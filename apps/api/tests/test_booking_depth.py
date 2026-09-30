"""Bookings depth: holds that release, a waitlist that offers and waits,
recurring series, and the no-show follow-up — through the API, the outbox
subscribers and the automation lane, as the worker runs them."""

from __future__ import annotations

import os
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_testing.phase_b import create_business, drain_events, new_identity, primary_location, run_automation, sql

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)
IST = ZoneInfo("Asia/Kolkata")
MODULES = ("workforce", "bookings", "offerings-catalog", "payments", "customer-relationships", "messaging")


def _shop(monkeypatch: Any, **policy: Any) -> tuple[dict[str, str], str, str, str]:
    monkeypatch.setenv("MESSAGING_SANDBOX", "1")
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, business_type="salon", modules=MODULES)
    loc = primary_location(client, owner, bid)
    base = f"/v1/platform/businesses/{bid}"
    if policy:
        r = client.patch(f"{base}/bookings-policy", json=policy, headers=owner)
        assert r.status_code == 200, r.text
    return owner, bid, loc, base


def _connect(owner: dict[str, str], base: str) -> None:
    assert client.post(f"{base}/messaging/channel/sandbox", json={
        "display_phone": "+919840000081", "display_name": "Glow"}, headers=owner).status_code == 200


def _customer(owner: dict[str, str], base: str, name: str, phone: str) -> str:
    r = client.post(f"{base}/customers", json={"display_name": name, "phone": phone}, headers=owner)
    assert r.status_code == 200, r.text
    return str(r.json()["data"]["id"])


def _class(owner: dict[str, str], base: str, places: int) -> str:
    r = client.post(f"{base}/products", json={"title": "Sunrise yoga", "offering_type": "class_session",
                                              "status": "active", "visibility": "public", "price_amount": 300,
                                              "attributes": {"capacity": places, "duration_minutes": 60}},
                    headers=owner)
    assert r.status_code == 200, r.text
    return str(r.json()["data"]["id"])


def _slot(days: int, hh: int = 7, minutes: int = 60) -> tuple[str, str]:
    day = datetime.now(IST).date() + timedelta(days=days)
    start = datetime.combine(day, time(hh, 0), IST)
    return start.isoformat(), (start + timedelta(minutes=minutes)).isoformat()


def _daytime() -> datetime:
    """Now, or the next 9 am in India when now falls in quiet hours (21:00–08:00),
    so a customer-facing step runs instead of waiting for the morning."""
    now = datetime.now(IST)
    if time(8, 0) <= now.time() < time(21, 0):
        return now
    day = now.date() if now.time() < time(8, 0) else now.date() + timedelta(days=1)
    return datetime.combine(day, time(9, 0), IST)


def _book(owner: dict[str, str], base: str, **body: Any) -> dict[str, Any]:
    r = client.post(f"{base}/bookings", json=body, headers=owner)
    assert r.status_code == 200, r.text
    return dict(r.json()["data"])


# ------------------------------------------------------------------ holds


def test_an_unpaid_online_deposit_holds_the_slot_and_then_releases_it(monkeypatch: Any) -> None:
    owner, bid, loc, base = _shop(monkeypatch, require_deposit=True, deposit_amount=200, hold_minutes=10)
    starts, ends = _slot(days=5, hh=11)
    held = _book(owner, base, location_id=loc, reservation_mode="appointment", title="Facial",
                 starts_at=starts, ends_at=ends, payment_method="online")
    assert held["hold_expires_at"], held
    expires = datetime.fromisoformat(held["hold_expires_at"])
    assert timedelta(minutes=9) < expires - datetime.now(timezone.utc) <= timedelta(minutes=10)

    paid = _book(owner, base, location_id=loc, reservation_mode="appointment", title="Paid facial",
                 starts_at=_slot(days=6, hh=11)[0], ends_at=_slot(days=6, hh=11)[1], payment_method="online")
    assert client.patch(f"{base}/bookings/{paid['id']}", json={"payment_status": "deposit_paid"},
                        headers=owner).status_code == 200
    offline = _book(owner, base, location_id=loc, reservation_mode="appointment", title="Counter",
                    starts_at=_slot(days=7, hh=11)[0], ends_at=_slot(days=7, hh=11)[1], payment_method="cod")
    assert offline["hold_expires_at"] is None, "paying at the counter is not an online hold"

    assert run_automation(bid) == 0, "nothing is due before the hold runs out"
    run_automation(bid, now=expires + timedelta(minutes=1))
    assert sql("select status, cancellation_reason from bookings_bookings where id = :i", i=held["id"]) == [
        ("cancelled", "The deposit was not paid in time; the slot was released")]
    assert sql("select status, hold_expires_at from bookings_bookings where id = :i", i=paid["id"]) == [
        ("pending", None)], "paid in time: kept"
    assert sql("select count(*) from platform_outbox_events where business_id = :b "
               "and event_type = 'booking.hold_released'", b=bid) == [(1,)]
    run_automation(bid, now=expires + timedelta(minutes=30))  # replay: nothing twice
    assert sql("select count(*) from platform_outbox_events where business_id = :b "
               "and event_type = 'booking.hold_released'", b=bid) == [(1,)]
    # The slot is free again.
    again = _book(owner, base, location_id=loc, reservation_mode="appointment", title="Facial again",
                  starts_at=starts, ends_at=ends, payment_method="cod")
    assert again["status"] == "pending"


# ------------------------------------------------------------------ waitlist


def test_a_freed_class_place_is_offered_to_the_first_person_waiting_who_takes_it(monkeypatch: Any) -> None:
    owner, bid, loc, base = _shop(monkeypatch)
    _connect(owner, base)
    yoga = _class(owner, base, places=1)
    slug = sql("select slug from businesses where id = :b", b=bid)[0][0]
    starts, ends = _slot(days=3)
    body = {"location_id": loc, "offering_id": yoga, "reservation_mode": "class_session",
            "starts_at": starts, "ends_at": ends}
    anu = _customer(owner, base, "Anu", "+919876500081")
    first = _book(owner, base, customer_contact_id=anu, **body)
    public = f"/v1/public/websites/{slug}/waitlist"
    assert client.post(f"/v1/b/{bid}/marketplace/visibility", json={"visibility": "unlisted"},
                       headers=owner).status_code == 200

    off = client.post(public, json={**body, "guest": {"name": "Ravi", "email": "ravi@example.com"}})
    assert off.status_code == 422 and off.json()["error"]["details"]["code"] == "waitlist_disabled"
    client.patch(f"{base}/bookings-policy", json={"waitlist_enabled": True, "waitlist_offer_minutes": 30},
                 headers=owner)
    free_slot = {**body, "starts_at": _slot(days=4)[0], "ends_at": _slot(days=4)[1]}
    free = client.post(public, json={**free_slot, "guest": {"name": "Ravi", "email": "ravi@example.com"}})
    assert free.status_code == 422 and free.json()["error"]["details"]["code"] == "slot_available"

    ravi = client.post(public, json={**body, "guest": {"name": "Ravi", "email": "ravi@example.com",
                                                        "phone": "+919876500082"}})
    assert ravi.status_code == 200 and ravi.json()["data"]["status"] == "waiting", ravi.text
    again = client.post(public, json={**body, "guest": {"name": "Ravi", "email": "ravi@example.com",
                                                         "phone": "+919876500082"}})
    assert again.json()["data"]["id"] == ravi.json()["data"]["id"], "one request per person per slot"
    meena = _customer(owner, base, "Meena", "+919876500083")
    staff_add = client.post(f"{base}/bookings-waitlist", json={**body, "customer_contact_id": meena}, headers=owner)
    assert staff_add.status_code == 200, staff_add.text

    # Anu cancels: the place goes to Ravi (first in line), never booked silently.
    assert client.post(f"{base}/bookings/{first['id']}/status", json={"status": "cancelled", "reason": "Unwell"},
                       headers=owner).status_code == 200
    drain_events(bid)
    run_automation(bid, now=_daytime())
    waiting = client.get(f"{base}/bookings-waitlist", headers=owner).json()["data"]
    by_id = {w["id"]: w for w in waiting}
    offer = by_id[ravi.json()["data"]["id"]]
    assert offer["status"] == "offered" and by_id[staff_add.json()["data"]["id"]]["status"] == "waiting"
    assert offer["offer_link"] and "/waitlist/" in offer["offer_link"]
    [(status, text)] = sql("select status, body from messaging_messages where business_id = :b "
                           "and template_key = 'booking_waitlist_opening'", b=bid)
    assert status == "sent" and "Sunrise yoga" in text and offer["offer_link"] in text
    assert sql("select count(*) from bookings_bookings where business_id = :b and status in "
               "('pending', 'confirmed')", b=bid) == [(0,)], "nothing is booked until Ravi takes it"
    drain_events(bid)
    assert sql("select count(*) from automation_steps where business_id = :b and ladder_key = 'booking.waitlist'",
               b=bid) == [(1,)], "one offer at a time, once"

    token = offer["offer_link"].split("t=")[1]
    shown = client.get(f"/v1/public/websites/{slug}/waitlist/{offer['id']}?t={token}").json()["data"]
    assert shown["can_take"] is True and shown["title"] == "Sunrise yoga"
    wrong = client.post(f"/v1/public/websites/{slug}/waitlist/{offer['id']}/claim", json={"token": "nope"})
    assert wrong.status_code == 404
    took = client.post(f"/v1/public/websites/{slug}/waitlist/{offer['id']}/claim", json={"token": token})
    assert took.status_code == 200, took.text
    booking = took.json()["data"]
    assert datetime.fromisoformat(booking["starts_at"]) == datetime.fromisoformat(starts) and booking["management_token"]
    replay = client.post(f"/v1/public/websites/{slug}/waitlist/{offer['id']}/claim", json={"token": token})
    assert replay.status_code == 404, "the link is spent once the place is taken"
    assert sql("select status, booking_id::text from bookings_waitlist_entries where id = :i", i=offer["id"]) == [
        ("booked", booking["id"])]
    full = client.post(f"{base}/bookings", json={**body, "customer_contact_id": anu}, headers=owner)
    assert full.status_code == 409, "the class is full again"

    # Ravi cancels in turn: Meena is offered, lets it run out, and it passes on to nobody.
    assert client.post(f"{base}/bookings/{booking['id']}/status", json={"status": "cancelled", "reason": "Travel"},
                       headers=owner).status_code == 200
    drain_events(bid)
    run_automation(bid, now=_daytime())
    [(m_status, m_expires)] = sql("select status, offer_expires_at from bookings_waitlist_entries where id = :i",
                                  i=staff_add.json()["data"]["id"])
    assert m_status == "offered"
    run_automation(bid, now=m_expires + timedelta(minutes=1))
    assert sql("select status from bookings_waitlist_entries where id = :i", i=staff_add.json()["data"]["id"]) == [
        ("expired",)]
    assert client.post(f"{base}/bookings", json={**body, "customer_contact_id": anu}, headers=owner).status_code == 200


# ------------------------------------------------------------------ series


def test_a_weekly_series_is_linked_bookings_changed_from_one_on_and_ended(monkeypatch: Any) -> None:
    owner, bid, loc, base = _shop(monkeypatch)
    anu = _customer(owner, base, "Anu", "+919876500091")
    starts, ends = _slot(days=2, hh=17)
    first = _book(owner, base, location_id=loc, customer_contact_id=anu, reservation_mode="appointment",
                  title="Physio", starts_at=starts, ends_at=ends, provider_id=None)
    series = client.post(f"{base}/bookings/{first['id']}/repeat", json={"interval_weeks": 1, "occurrences": 4},
                         headers=owner)
    assert series.status_code == 200, series.text
    data = series.json()["data"]
    assert [b["occurrence_index"] for b in data["occurrences"]] == [1, 2, 3, 4] and data["skipped"] == []
    assert len({b["starts_at"][11:16] for b in data["occurrences"]}) == 1, "same time each week"
    again = client.post(f"{base}/bookings/{first['id']}/repeat", json={"occurrences": 3}, headers=owner)
    assert again.status_code == 409

    # Edit one: occurrence 2 moves on its own.
    two, three = data["occurrences"][1], data["occurrences"][2]
    moved_two = datetime.fromisoformat(two["starts_at"]) + timedelta(hours=1)
    r = client.post(f"{base}/bookings/{two['id']}/reschedule",
                    json={"starts_at": moved_two.isoformat(), "ends_at": (moved_two + timedelta(hours=1)).isoformat()},
                    headers=owner)
    assert r.status_code == 200, r.text
    # Change 3 and later: two hours later each week.
    new_three = datetime.fromisoformat(three["starts_at"]) + timedelta(hours=2)
    changed = client.post(f"{base}/bookings-series/{data['id']}/change-future", json={
        "from_booking_id": three["id"], "starts_at": new_three.isoformat(),
        "ends_at": (new_three + timedelta(hours=1)).isoformat()}, headers=owner)
    assert changed.status_code == 200, changed.text
    after = {b["occurrence_index"]: datetime.fromisoformat(b["starts_at"]) for b in changed.json()["data"]["occurrences"]}
    assert after[1] == datetime.fromisoformat(first["starts_at"]), "earlier occurrences untouched"
    assert after[2] == moved_two, "the one edited on its own keeps its own time"
    assert after[3] == new_three and after[4] == new_three + timedelta(weeks=1)

    # End from 4: only 4 is cancelled; the series is ended.
    four = changed.json()["data"]["occurrences"][3]
    ended = client.post(f"{base}/bookings-series/{data['id']}/end", json={"from_booking_id": four["id"]},
                        headers=owner)
    assert ended.status_code == 200, ended.text
    statuses = {b["occurrence_index"]: b["status"] for b in ended.json()["data"]["occurrences"]}
    assert statuses == {1: "pending", 2: "pending", 3: "pending", 4: "cancelled"}
    assert ended.json()["data"]["status"] == "ended"


def test_changing_later_occurrences_is_all_or_nothing(monkeypatch: Any) -> None:
    owner, bid, loc, base = _shop(monkeypatch)
    cut = client.post(f"{base}/products", json={"title": "Cut", "offering_type": "service", "status": "active",
                                                "price_amount": 100, "attributes": {"duration_minutes": 60}},
                      headers=owner).json()["data"]["id"]
    priya = client.post(f"{base}/workforce/members", json={"display_name": "Priya", "location_ids": [loc],
                                                           "primary_location_id": loc, "offering_ids": [cut]},
                        headers=owner).json()["data"]["id"]
    starts, ends = _slot(days=2, hh=10)
    first = _book(owner, base, location_id=loc, offering_id=cut, provider_id=priya, reservation_mode="appointment",
                  starts_at=starts, ends_at=ends)
    data = client.post(f"{base}/bookings/{first['id']}/repeat", json={"occurrences": 3}, headers=owner).json()["data"]
    # Priya is taken at 12:00 in week 3, so moving 2 and later to 12:00 cannot happen for week 3.
    week3_noon = datetime.fromisoformat(data["occurrences"][2]["starts_at"]) + timedelta(hours=2)
    _book(owner, base, location_id=loc, offering_id=cut, provider_id=priya, reservation_mode="appointment",
          starts_at=week3_noon.isoformat(), ends_at=(week3_noon + timedelta(hours=1)).isoformat())
    two = data["occurrences"][1]
    new_two = datetime.fromisoformat(two["starts_at"]) + timedelta(hours=2)
    clash = client.post(f"{base}/bookings-series/{data['id']}/change-future", json={
        "from_booking_id": two["id"], "starts_at": new_two.isoformat(),
        "ends_at": (new_two + timedelta(hours=1)).isoformat()}, headers=owner)
    assert clash.status_code == 409, clash.text
    err = clash.json()["error"]
    assert err["details"]["code"] == "series_conflict" and [c["occurrence"] for c in err["details"]["clashes"]] == [3]
    unchanged = client.get(f"{base}/bookings-series/{data['id']}", headers=owner).json()["data"]["occurrences"]
    assert [b["starts_at"] for b in unchanged] == [b["starts_at"] for b in data["occurrences"]], "nothing moved"


# ------------------------------------------------------------------ no-show


def test_a_no_show_gets_one_we_missed_you_an_hour_later(monkeypatch: Any) -> None:
    owner, bid, loc, base = _shop(monkeypatch)
    _connect(owner, base)
    anu = _customer(owner, base, "Anu", "+919876500095")
    starts, ends = _slot(days=1, hh=10)
    b = _book(owner, base, location_id=loc, customer_contact_id=anu, reservation_mode="appointment",
              title="Consultation", starts_at=starts, ends_at=ends)
    for status in ("confirmed",):
        assert client.post(f"{base}/bookings/{b['id']}/status", json={"status": status},
                           headers=owner).status_code == 200
    assert client.post(f"{base}/bookings/{b['id']}/status", json={"status": "no_show", "reason": "Did not come"},
                       headers=owner).status_code == 200
    drain_events(bid)
    drain_events(bid)
    noon = datetime.combine(datetime.now(IST).date() + timedelta(days=1), time(12, 0), IST)
    run_automation(bid, now=noon)
    run_automation(bid, now=noon + timedelta(hours=3))
    rows = sql("select status, body from messaging_messages where business_id = :b and template_key = 'booking_missed'",
               b=bid)
    assert len(rows) == 1 and rows[0][0] == "sent" and "Consultation" in rows[0][1] and "/book" in rows[0][1], rows
