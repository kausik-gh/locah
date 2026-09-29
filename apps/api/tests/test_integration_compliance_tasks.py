"""Integration: a licence coming due opens one shared Task, not one per reminder.

Through the real compliance ladder (automation lane) and the shared Tasks
engine on local PostgreSQL: the 30-day reminder opens the task, the 7-day
reminder returns the same task, and renewing to a new date makes the next
reminder open a new task for that date. Without Tasks switched on, reminders
still go out and no task appears.
"""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_testing.phase_b import create_business, drain_events, new_identity, run_automation, sql

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)
IST = ZoneInfo("Asia/Kolkata")


def _at(day: date) -> datetime:
    return datetime.combine(day, time(10, 0), IST)


def _tasks(bid: str) -> list[Any]:
    return list(sql("select id::text, title from tasks_tasks where business_id = :b and "
                    "related_type = 'compliance_item' order by created_at", b=bid))


def _licence(monkeypatch: Any, *modules: str) -> tuple[str, dict[str, str], str, date]:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("compliance", *modules))
    due = date.today() + timedelta(days=40)
    item = client.post(f"/v1/platform/businesses/{bid}/compliance/items", headers=owner, json={
        "item_type": "licence", "kind": "fssai", "title": "Food licence", "due_on": due.isoformat()})
    assert item.status_code == 200, item.text
    drain_events(bid)
    return bid, owner, str(item.json()["data"]["id"]), due


def test_reminders_for_one_due_date_share_one_task(monkeypatch: Any) -> None:
    bid, owner, item_id, due = _licence(monkeypatch, "workforce", "tasks")

    run_automation(bid, now=_at(due - timedelta(days=29)))
    first = _tasks(bid)
    assert [t[1] for t in first] == ["Renew: Food licence"], "the first reminder opens the task"

    run_automation(bid, now=_at(due - timedelta(days=6)))
    assert _tasks(bid) == first, "the 7-day reminder is the same task"

    new_due = due + timedelta(days=365)
    renewed = client.post(f"/v1/platform/businesses/{bid}/compliance/items/{item_id}/renew", headers=owner,
                          json={"new_due_on": new_due.isoformat()})
    assert renewed.status_code == 200, renewed.text
    drain_events(bid)
    run_automation(bid, now=_at(new_due - timedelta(days=29)))
    assert len(_tasks(bid)) == 2, "a new due date is a new occurrence, so a new task"


def test_no_tasks_module_reminds_without_a_task(monkeypatch: Any) -> None:
    bid, _owner, _item, due = _licence(monkeypatch)
    run_automation(bid, now=_at(due - timedelta(days=29)))
    done = sql("select count(*) from automation_steps where business_id = :b and status = 'done'", b=bid)
    assert int(done[0][0]) >= 1, "the reminder itself still ran"
    assert _tasks(bid) == []
