"""Shared tasks: create, assign, checklist, compliance hook, assignment visibility."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.main import app
from platform_testing.phase_b import (
    assert_tenant_isolated, create_business, drain_events, new_identity, primary_location, run_automation, sql,
)

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)


def _shop(monkeypatch: Any, *modules: str) -> tuple[str, dict[str, str]]:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("workforce", "tasks", *modules))
    return bid, owner


def _member(owner: dict[str, str], bid: str, loc: str, name: str, identity: uuid.UUID | None = None) -> str:
    body: dict[str, Any] = {"display_name": name, "location_ids": [loc], "primary_location_id": loc}
    if identity:
        body["identity_id"] = str(identity)
    made = client.post(f"/v1/platform/businesses/{bid}/workforce/members", headers=owner, json=body)
    assert made.status_code == 200, made.text
    return str(made.json()["data"]["id"])


@DB
def test_create_assign_checklist_and_complete(monkeypatch: Any) -> None:
    bid, owner = _shop(monkeypatch)
    loc = primary_location(client, owner, bid)
    person = _member(owner, bid, loc, "Housekeeping")
    due = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    made = client.post(f"/v1/platform/businesses/{bid}/tasks", headers=owner, json={
        "title": "Turn room 4", "priority": "high", "due_at": due, "location_id": loc,
        "related_type": "business", "related_id": bid,
    })
    assert made.status_code == 200, made.text
    task_id = made.json()["data"]["id"]
    assert made.json()["data"]["status"] == "open"
    assigned = client.post(f"/v1/platform/businesses/{bid}/tasks/{task_id}/assign", headers=owner, json={
        "assignee_member_id": person,
    })
    assert assigned.status_code == 200 and assigned.json()["data"]["assignee_member_id"] == person
    item = client.post(f"/v1/platform/businesses/{bid}/tasks/{task_id}/items", headers=owner, json={
        "label": "Change linen", "required": True,
    })
    assert item.status_code == 200, item.text
    blocked = client.post(f"/v1/platform/businesses/{bid}/tasks/{task_id}/complete", headers=owner)
    assert blocked.status_code == 409
    item_id = item.json()["data"]["checklist"][0]["id"]
    checked = client.post(
        f"/v1/platform/businesses/{bid}/tasks/{task_id}/items/{item_id}/check",
        headers=owner, json={"done": True},
    )
    assert checked.status_code == 200 and checked.json()["data"]["checklist"][0]["done"] is True
    done = client.post(f"/v1/platform/businesses/{bid}/tasks/{task_id}/complete", headers=owner)
    assert done.status_code == 200 and done.json()["data"]["status"] == "completed"
    listed = client.get(f"/v1/platform/businesses/{bid}/tasks?view=completed", headers=owner)
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()["data"]["tasks"]] == [task_id]
    history = client.get(f"/v1/platform/businesses/{bid}/tasks/{task_id}", headers=owner)
    assert "completed" in [row["action"] for row in history.json()["data"]["history"]]
    drain_events(bid)
    assert sql(
        "SELECT count(*) FROM platform_outbox_events WHERE business_id = :b AND event_type = 'task.completed'",
        b=bid,
    ) == [(1,)]


@DB
def test_repeatable_checklist_spawns_once(monkeypatch: Any) -> None:
    bid, owner = _shop(monkeypatch)
    template = client.post(f"/v1/platform/businesses/{bid}/tasks/templates", headers=owner, json={
        "name": "Opening", "kind": "opening",
        "items": [{"label": "Unlock"}, {"label": "Count the till", "required": True}],
    })
    assert template.status_code == 200, template.text
    template_id = template.json()["data"]["id"]
    body = {"occurrence_key": "2026-09-29-opening"}
    first = client.post(
        f"/v1/platform/businesses/{bid}/tasks/templates/{template_id}/spawn", headers=owner, json=body,
    )
    assert first.status_code == 200, first.text
    assert [item["label"] for item in first.json()["data"]["checklist"]] == ["Unlock", "Count the till"]
    second = client.post(
        f"/v1/platform/businesses/{bid}/tasks/templates/{template_id}/spawn", headers=owner, json=body,
    )
    assert second.status_code == 200 and second.json()["data"]["id"] == first.json()["data"]["id"]
    assert sql("SELECT count(*) FROM tasks_tasks WHERE business_id = :b", b=bid) == [(1,)]


@DB
def test_compliance_due_creates_one_task(monkeypatch: Any) -> None:
    bid, owner = _shop(monkeypatch)
    item = client.post(f"/v1/platform/businesses/{bid}/compliance/items", headers=owner, json={
        "item_type": "licence", "kind": "fssai", "title": "Food licence",
        "due_on": "2026-12-01",
    })
    assert item.status_code == 200, item.text
    item_id = item.json()["data"]["id"]
    made = client.post(f"/v1/platform/businesses/{bid}/tasks/from-compliance", headers=owner, json={
        "item_id": item_id,
    })
    assert made.status_code == 200, made.text
    assert made.json()["data"]["related_type"] == "compliance_item"
    assert made.json()["data"]["related_id"] == item_id
    again = client.post(f"/v1/platform/businesses/{bid}/tasks/from-compliance", headers=owner, json={
        "item_id": item_id,
    })
    assert again.json()["data"]["id"] == made.json()["data"]["id"]
    assert sql("SELECT count(*) FROM tasks_tasks WHERE business_id = :b", b=bid) == [(1,)]


@DB
def test_due_event_fires_once(monkeypatch: Any) -> None:
    bid, owner = _shop(monkeypatch)
    due = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=3)
    made = client.post(f"/v1/platform/businesses/{bid}/tasks", headers=owner, json={
        "title": "File the return", "due_at": due.isoformat(),
        "related_type": "business", "related_id": bid,
    })
    assert made.status_code == 200, made.text
    drain_events(bid)
    run_automation(bid, now=due + timedelta(minutes=5))
    drain_events(bid)
    assert sql(
        "SELECT count(*) FROM platform_outbox_events WHERE business_id = :b AND event_type = 'task.due'",
        b=bid,
    ) == [(1,)]
    run_automation(bid, now=due + timedelta(minutes=10))
    drain_events(bid)
    assert sql(
        "SELECT count(*) FROM platform_outbox_events WHERE business_id = :b AND event_type = 'task.due'",
        b=bid,
    ) == [(1,)]


@DB
def test_assignment_sees_only_their_tasks(monkeypatch: Any) -> None:
    bid, owner = _shop(monkeypatch)
    loc = primary_location(client, owner, bid)
    person, headers = new_identity(monkeypatch)
    invited = client.post(f"/v1/b/{bid}/team/invitations", headers=owner, json={
        "identity_id": str(person), "role": "member",
    })
    assert invited.status_code == 200, invited.text
    mid = invited.json()["data"]["id"]
    assert client.post(f"/v1/b/{bid}/team/members/{mid}/activate", headers=owner).status_code == 200
    role = client.post(f"/v1/platform/businesses/{bid}/roles/custom", headers=owner, json={
        "name": "Room attendant",
        "permissions": ["business.read", "locations.read", "notifications.read", "tasks.read", "tasks.complete"],
        "scope": "assignment",
    })
    assert role.status_code == 200, role.text
    applied = client.put(
        f"/v1/platform/businesses/{bid}/members/{mid}/role", headers=owner,
        json={"role": role.json()["data"]["key"]},
    )
    assert applied.status_code == 200, applied.text
    mine = _member(owner, bid, loc, "Anbu", person)
    other = _member(owner, bid, loc, "Someone else")
    own = client.post(f"/v1/platform/businesses/{bid}/tasks", headers=owner, json={
        "title": "Room 2", "assignee_member_id": mine, "related_type": "staff_assignment", "related_id": mine,
    })
    assert own.status_code == 200, own.text
    theirs = client.post(f"/v1/platform/businesses/{bid}/tasks", headers=owner, json={
        "title": "Room 9", "assignee_member_id": other, "related_type": "staff_assignment", "related_id": other,
    })
    assert theirs.status_code == 200, theirs.text
    seen = client.get(f"/v1/platform/businesses/{bid}/tasks?view=open", headers=headers)
    assert seen.status_code == 200, seen.text
    assert [row["title"] for row in seen.json()["data"]["tasks"]] == ["Room 2"]
    hidden = client.get(
        f"/v1/platform/businesses/{bid}/tasks/{theirs.json()['data']['id']}", headers=headers,
    )
    assert hidden.status_code == 404


async def _task_rows(session: AsyncSession, business_id: uuid.UUID, table: str) -> None:
    task = (await session.execute(text(
        """insert into tasks_tasks (business_id, title, related_type, related_id)
           values (:b, 'Prep', 'business', :b) returning id"""
    ), {"b": business_id})).scalar_one()
    if table == "tasks_tasks":
        return
    if table == "tasks_checklist_items":
        await session.execute(text(
            """insert into tasks_checklist_items (business_id, task_id, position, label)
               values (:b, :t, 0, 'Step')"""
        ), {"b": business_id, "t": task})
        return
    if table == "tasks_history":
        await session.execute(text(
            """insert into tasks_history (business_id, task_id, action, to_status)
               values (:b, :t, 'created', 'open')"""
        ), {"b": business_id, "t": task})
        return
    template = (await session.execute(text(
        "insert into tasks_checklist_templates (business_id, name) values (:b, 'Open') returning id"
    ), {"b": business_id})).scalar_one()
    if table == "tasks_checklist_templates":
        return
    await session.execute(text(
        """insert into tasks_checklist_template_items (business_id, template_id, position, label)
           values (:b, :t, 0, 'Unlock')"""
    ), {"b": business_id, "t": template})


@DB
@pytest.mark.asyncio
@pytest.mark.parametrize("table", [
    "tasks_tasks", "tasks_checklist_items", "tasks_history",
    "tasks_checklist_templates", "tasks_checklist_template_items",
])
async def test_task_tables_are_tenant_isolated(table: str) -> None:
    async def insert(session: AsyncSession, business_id: uuid.UUID) -> None:
        await _task_rows(session, business_id, table)

    await assert_tenant_isolated(table, insert)
