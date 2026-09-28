"""P1-09 owner-entered compliance dates, recurrence and reminders."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from platform_api.main import app
from platform_testing.phase_b import create_business, drain_events, new_identity, primary_location, run_automation, sql

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)
IST = ZoneInfo("Asia/Kolkata")


def _business(monkeypatch: Any) -> tuple[str, dict[str, str]]:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner)
    assert sql("SELECT activation_state FROM business_module_states WHERE business_id = :b AND module_id = 'compliance'",
               b=bid) == [("active",)]
    return bid, owner


@DB
def test_licence_date_is_owner_supplied_and_renewal_replaces_reminders(monkeypatch: Any) -> None:
    bid, owner = _business(monkeypatch)
    base = f"/v1/platform/businesses/{bid}"
    location_id = primary_location(client, owner, bid)
    due = datetime.now(IST).date() + timedelta(days=8)
    created = client.post(f"{base}/compliance/items", headers=owner, json={
        "location_id": location_id, "item_type": "licence", "kind": "fssai",
        "title": "Food licence", "licence_number": "FSSAI-TEST-123",
        "due_on": due.isoformat(), "show_on_site": True,
        "notes": "Owner-supplied expiry date",
    })
    assert created.status_code == 200, created.text
    item = created.json()["data"]
    assert item["due_on"] == due.isoformat() and item["attention"] == "upcoming"
    item_id = item["id"]
    drain_events(bid)
    steps = sql("""SELECT step_key, period_key, status FROM automation_steps
                   WHERE business_id = :b AND ladder_key = 'compliance.due' AND entity_id = :id
                   ORDER BY due_at""", b=bid, id=item_id)
    assert [row[0] for row in steps] == ["minus_7", "minus_1", "due"]
    assert all(row[1] == due.isoformat() and row[2] == "pending" for row in steps)
    tomorrow = datetime.combine(due - timedelta(days=7), datetime.min.time(), IST).replace(hour=10)
    run_automation(bid, now=tomorrow.astimezone(timezone.utc))
    assert sql("""SELECT count(*) FROM platform_notifications
                  WHERE business_id = :b AND notification_type = 'compliance.due'""", b=bid) == [(1,)]

    new_due = due + timedelta(days=365)
    renewed = client.post(f"{base}/compliance/items/{item_id}/renew", headers=owner,
                          json={"new_due_on": new_due.isoformat(), "note": "Renewal confirmed"})
    assert renewed.status_code == 200, renewed.text
    assert renewed.json()["data"]["due_on"] == new_due.isoformat()
    drain_events(bid)
    old_pending = sql("""SELECT count(*) FROM automation_steps WHERE business_id = :b
                         AND ladder_key = 'compliance.due' AND entity_id = :id
                         AND period_key = :period AND status = 'pending'""",
                      b=bid, id=item_id, period=due.isoformat())
    assert old_pending == [(0,)]
    history = client.get(f"{base}/compliance/items/{item_id}/history", headers=owner)
    assert history.status_code == 200, history.text
    assert [row["action"] for row in history.json()["data"]] == ["renewed", "created"]

    visible = client.post(f"/v1/b/{bid}/marketplace/visibility", headers=owner,
                          json={"visibility": "unlisted"})
    assert visible.status_code == 200, visible.text
    slug = sql("SELECT slug FROM businesses WHERE id = :b", b=bid)[0][0]
    public = client.get(f"/v1/public/websites/{slug}/licences")
    assert public.status_code == 200, public.text
    assert public.json()["data"] == [{"title": "Food licence", "licence_number": "FSSAI-TEST-123",
                                       "authority": ""}]
    assert "notes" not in public.text


@DB
def test_filing_advances_only_by_declared_recurrence_and_nonrecurring_archives(monkeypatch: Any) -> None:
    bid, owner = _business(monkeypatch)
    base = f"/v1/platform/businesses/{bid}"
    filed = client.post(f"{base}/compliance/items", headers=owner, json={
        "item_type": "filing", "kind": "gst_filing", "title": "Quarterly GST filing",
        "due_on": "2027-01-31", "recurrence": "quarterly",
    })
    assert filed.status_code == 200, filed.text
    item_id = filed.json()["data"]["id"]
    completed = client.post(f"{base}/compliance/items/{item_id}/filed", headers=owner,
                            json={"completed_on": "2027-01-30"})
    assert completed.status_code == 200, completed.text
    assert completed.json()["data"]["due_on"] == "2027-04-30"
    assert completed.json()["data"]["last_done_on"] == "2027-01-30"
    assert completed.json()["data"]["status"] == "active"

    once = client.post(f"{base}/compliance/items", headers=owner, json={
        "item_type": "filing", "kind": "other", "title": "One-off filing",
        "due_on": "2027-02-15", "recurrence": "none",
    })
    assert once.status_code == 200, once.text
    once_id = once.json()["data"]["id"]
    done = client.post(f"{base}/compliance/items/{once_id}/filed", headers=owner, json={})
    assert done.status_code == 200, done.text
    assert done.json()["data"]["status"] == "archived"
    rows = client.get(f"{base}/compliance/items", headers=owner).json()["data"]["items"]
    assert {row["id"] for row in rows} == {item_id}
    assert client.post(f"{base}/compliance/items/{once_id}/filed", headers=owner, json={}).status_code == 409


@DB
def test_due_date_never_invented_and_site_visibility_requires_a_number(monkeypatch: Any) -> None:
    bid, owner = _business(monkeypatch)
    base = f"/v1/platform/businesses/{bid}"
    assert client.post(f"{base}/compliance/items", headers=owner, json={
        "item_type": "licence", "kind": "fssai", "title": "Food licence",
    }).status_code == 422
    assert client.post(f"{base}/compliance/items", headers=owner, json={
        "item_type": "licence", "kind": "fssai", "title": "Food licence",
        "due_on": date.today().isoformat(), "show_on_site": True,
    }).status_code == 422
    assert client.get(f"{base}/compliance/items", headers=owner).json()["data"]["items"] == []


@DB
def test_due_item_stays_on_owner_home_until_renewed(monkeypatch: Any) -> None:
    bid, owner = _business(monkeypatch)
    base = f"/v1/platform/businesses/{bid}"
    due = datetime.now(IST).date() + timedelta(days=2)
    created = client.post(f"{base}/compliance/items", headers=owner, json={
        "item_type": "licence", "kind": "trade_licence", "title": "Trade licence",
        "due_on": due.isoformat(),
    })
    assert created.status_code == 200, created.text
    item_id = created.json()["data"]["id"]
    home = client.get(f"{base}/home", headers=owner)
    assert home.status_code == 200, home.text
    now = next(b for b in home.json()["data"]["bands"] if b["key"] == "now")
    attention = next(i for i in now["items"] if i["label"] == "licences or filings needing attention")
    assert "Trade licence" in attention["detail"]
    renewed = client.post(f"{base}/compliance/items/{item_id}/renew", headers=owner,
                          json={"new_due_on": (due + timedelta(days=365)).isoformat()})
    assert renewed.status_code == 200, renewed.text
    home_after = client.get(f"{base}/home", headers=owner).json()["data"]
    now_after = next(b for b in home_after["bands"] if b["key"] == "now")
    assert all(i["label"] != "licences or filings needing attention" for i in now_after["items"])
