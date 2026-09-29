"""Integration: Memberships decides who may come in; Attendance records the visit.

Through the real API, engine and worker on local PostgreSQL: an unpaid member is
refused at the door with Memberships' own words, a paid member checks in by the
code on their card and a replay returns the same visit, and a pack that counts
at the door uses one session per visit — once, however often the event is
delivered — until the pack is used up and the desk refuses the next visit.
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


def _count(query: str, **params: Any) -> int:
    return int(sql(query, **params)[0][0])


def _gym(monkeypatch: Any) -> tuple[dict[str, str], str, str]:
    monkeypatch.setenv("MESSAGING_SANDBOX", "1")
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, business_type="other", modules=(
        "offerings-catalog", "memberships", "payments", "customer-relationships", "attendance"))
    return owner, bid, f"/v1/platform/businesses/{bid}"


def _plan(owner: dict[str, str], base: str, **kw: Any) -> dict[str, Any]:
    body = {"name": f"Plan {uuid.uuid4().hex[:5]}", "price_amount": 1500, "duration_days": 30, "status": "active",
            "visibility": "public", **kw}
    r = client.post(f"{base}/membership-plans", json=body, headers=owner)
    assert r.status_code == 200, r.text
    return dict(r.json()["data"])


def _member(owner: dict[str, str], base: str, plan_id: str) -> dict[str, Any]:
    c = client.post(f"{base}/customers", json={"display_name": "Meera",
                                                "phone": f"+9197{uuid.uuid4().int % 10**8:08d}"}, headers=owner)
    assert c.status_code == 200, c.text
    r = client.post(f"{base}/membership-enrolments", json={
        "plan_id": plan_id, "customer_contact_id": c.json()["data"]["id"], "payment_method": "pay_at_business",
        "idempotency_key": str(uuid.uuid4())}, headers=owner)
    assert r.status_code == 200, r.text
    return dict(r.json()["data"])


def _pay(owner: dict[str, str], base: str, eid: str, amount: float) -> None:
    r = client.post(f"{base}/collect/record", json={"source_type": "membership", "source_id": eid,
                                                     "amount": amount, "method": "cash"}, headers=owner)
    assert r.status_code == 200, r.text


def _checkin(owner: dict[str, str], bid: str, code: str, key: str) -> Any:
    return client.post(f"/v1/b/{bid}/attendance/member-checkins",
                       json={"code": code, "channel": "qr", "idempotency_key": key}, headers=owner)


@DB
def test_the_door_asks_memberships_and_attendance_records_the_visit_once(monkeypatch: Any) -> None:
    owner, bid, base = _gym(monkeypatch)
    plan = _plan(owner, base, grace_days=3, grace_allows_entry=True)
    e = _member(owner, base, plan["id"])

    unpaid = _checkin(owner, bid, e["checkin_code"], "door-0001")
    assert unpaid.status_code == 409 and "Not paid yet" in unpaid.text, unpaid.text
    assert _count("select count(*) from attendance_events where business_id = :b", b=bid) == 0

    _pay(owner, base, e["id"], 1500)
    ok = _checkin(owner, bid, e["checkin_code"].lower(), "door-0002")
    assert ok.status_code == 200, ok.text
    visit = ok.json()["data"]
    assert visit["context"] == "membership_checkin" and visit["source_id"] == e["id"]
    assert visit["verification_metadata"]["eligibility_state"] == "allowed"

    again = _checkin(owner, bid, e["checkin_code"], "door-0002")
    assert again.status_code == 200 and again.json()["data"]["id"] == visit["id"], "the same scan is one visit"

    # The front desk's day view: today's visits by name, and today's classes (none here).
    today = client.get(f"/v1/b/{bid}/attendance/events", params={"today": "true"}, headers=owner)
    assert today.status_code == 200, today.text
    assert [(v["id"], v["subject_name"]) for v in today.json()["data"]] == [(visit["id"], "Meera")]
    classes = client.get(f"/v1/b/{bid}/attendance/sessions/today", headers=owner)
    assert classes.status_code == 200 and classes.json()["data"] == [], classes.text
    assert _count("select count(*) from attendance_events where business_id = :b", b=bid) == 1


@DB
def test_a_pack_that_counts_at_the_door_uses_one_session_per_visit(monkeypatch: Any) -> None:
    owner, bid, base = _gym(monkeypatch)
    plan = _plan(owner, base, plan_kind="session_pack", sessions_included=2, duration_days=60, price_amount=900,
                 consume_on="checkin")
    e = _member(owner, base, plan["id"])
    _pay(owner, base, e["id"], 900)

    def remaining() -> int:
        r = client.get(f"{base}/membership-enrolments/{e['id']}", headers=owner)
        assert r.status_code == 200, r.text
        return int(r.json()["data"]["detail"]["sessions_remaining"])

    assert remaining() == 2
    assert _checkin(owner, bid, e["checkin_code"], "pack-0001").status_code == 200
    drain_events(bid)
    drain_events(bid)
    assert remaining() == 1, "one visit, one session"
    uses = "select count(*) from memberships_session_uses where business_id = :b and source_type = 'checkin'"
    assert _count(uses, b=bid) == 1

    # The same scan again is the same visit, and so the same session.
    assert _checkin(owner, bid, e["checkin_code"], "pack-0001").status_code == 200
    drain_events(bid)
    assert remaining() == 1 and _count(uses, b=bid) == 1

    assert _checkin(owner, bid, e["checkin_code"], "pack-0002").status_code == 200
    drain_events(bid)
    assert remaining() == 0

    # A used-up pack has ended in Memberships' lifecycle; the door repeats its reason.
    refused = _checkin(owner, bid, e["checkin_code"], "pack-0003")
    assert refused.status_code == 409 and "renew" in refused.json()["error"]["message"], refused.text
    assert _count("select count(*) from attendance_events where business_id = :b", b=bid) == 2
