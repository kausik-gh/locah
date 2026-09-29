"""Solo businesses and one calendar (OM-21; MD §22 "Solo professionals: org shape
solo — simplified navigation (no team menus), one calendar").

The Workspace context says a business is run solo when its organisation shape
is solo and it has one active member; a second person joining ends that. The
calendar lists bookings, orders wanted for a day, follow-ups, memberships
ending and licences due for the days ahead, only for tools that are on and
that the viewer may see.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_testing.phase_b import create_business, new_identity, primary_location, sql

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)
IST = ZoneInfo("Asia/Kolkata")


def _context(bid: str, headers: dict[str, str]) -> dict[str, Any]:
    r = client.get("/v1/me/context", headers={**headers, "X-Operating-Context": "business", "X-Business-Id": bid})
    assert r.status_code == 200, r.text
    return cast(dict[str, Any], r.json()["data"])


@DB
def test_solo_until_a_second_person_joins(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("offerings-catalog", "bookings"))
    assert _context(bid, owner)["solo"] is False, "a business is a team unless its shape says solo"
    r = client.put(f"/v1/platform/businesses/{bid}/classification", json={"org_shape": "solo"}, headers=owner)
    assert r.status_code == 200, r.text
    assert _context(bid, owner)["solo"] is True
    person, _ = new_identity(monkeypatch)
    inv = client.post(f"/v1/b/{bid}/team/invitations", json={"identity_id": str(person), "role": "member"},
                      headers=owner).json()["data"]["id"]
    client.post(f"/v1/b/{bid}/team/members/{inv}/activate", headers=owner)
    assert _context(bid, owner)["solo"] is False, "a second person brings the team menus back"


@DB
def test_one_calendar_lists_the_days_ahead(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("offerings-catalog", "workforce", "bookings", "payments", "orders",
                                                  "leads", "memberships", "customer-relationships", "compliance"))
    base = f"/v1/platform/businesses/{bid}"
    loc = primary_location(client, owner, bid)
    service = client.post(f"{base}/products", json={"title": "Maths class", "offering_type": "service",
                                                    "status": "active", "price_amount": 500}, headers=owner).json()["data"]
    pupil = client.post(f"{base}/customers", json={"display_name": "Arjun", "phone": "+919840044001"},
                        headers=owner).json()["data"]["id"]
    today = datetime.now(timezone.utc).astimezone(IST).replace(minute=0, second=0, microsecond=0)
    tomorrow_5pm = (today + timedelta(days=1)).replace(hour=17)
    r = client.post(f"{base}/bookings", json={
        "location_id": loc, "offering_id": service["id"], "reservation_mode": "appointment", "customer_contact_id": pupil,
        "starts_at": tomorrow_5pm.isoformat(), "ends_at": (tomorrow_5pm + timedelta(hours=1)).isoformat()}, headers=owner)
    assert r.status_code == 200, r.text
    lead = client.post(f"{base}/leads", json={"display_name": "Kavya's mother", "phone": "+919840044002"},
                       headers=owner).json()["data"]
    sql("update leads_leads set next_follow_up_at = now() - interval '2 days' where id = :l", l=lead["id"])
    plan = sql("insert into memberships_plans (business_id, name) values (:b, 'Term fees') returning id", b=bid)[0][0]
    sql("insert into memberships_enrolments (business_id, plan_id, customer_contact_id, starts_at, ends_at, status) "
        "values (:b, :p, :c, now() - interval '80 days', now() + interval '3 days', 'active')", b=bid, p=plan, c=pupil)
    sql("insert into compliance_items (business_id, item_type, kind, title, due_on) "
        "values (:b, 'filing', 'professional_tax', 'Professional tax', current_date + 20)", b=bid)

    week = client.get(f"{base}/calendar", headers=owner).json()["data"]
    flat = [(d["label"], i["kind"], i["title"], i["who"], i["time"]) for d in week["days_list"] for i in d["items"]]
    assert ("Today", "follow_up", "Follow up", "Kavya's mother", "Overdue") in flat
    assert ("Tomorrow", "booking", "Maths class", "Arjun", "5 pm") in flat
    assert any(k == "membership" and w == "Arjun" for _, k, _, w, _ in flat)
    assert not any(k == "due" for _, k, _, _, _ in flat), "the filing is 20 days away"
    month = client.get(f"{base}/calendar", params={"days": 30}, headers=owner).json()["data"]
    assert any(i["kind"] == "due" and i["href"] == "/compliance" for d in month["days_list"] for i in d["items"])

    # someone who may not see bookings does not see them on the calendar
    person, keeper = new_identity(monkeypatch)
    inv = client.post(f"/v1/b/{bid}/team/invitations", json={"identity_id": str(person), "role": "member"},
                      headers=owner).json()["data"]["id"]
    client.post(f"/v1/b/{bid}/team/members/{inv}/activate", headers=owner)
    client.put(f"{base}/members/{inv}/role", json={"role": "store_keeper", "location_ids": [loc]}, headers=owner)
    theirs = client.get(f"{base}/calendar", headers=keeper).json()["data"]
    assert theirs["count"] == 0
    _, other = new_identity(monkeypatch)
    create_business(client, other)
    assert client.get(f"{base}/calendar", headers=other).status_code in (403, 404)
