"""Walk-in queue: issue, call, serve, miss, requeue, and one queue per provider."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.main import app
from platform_testing.phase_b import assert_tenant_isolated, create_business, drain_events, new_identity, primary_location, sql

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)


def _clinic(monkeypatch: Any) -> tuple[str, dict[str, str], str]:
    _, owner = new_identity(monkeypatch)
    bid = create_business(
        client, owner, business_type="clinic",
        modules=("workforce", "bookings", "customer-relationships", "queue-operations"),
    )
    return bid, owner, primary_location(client, owner, bid)


def _lane(owner: dict[str, str], bid: str, loc: str, name: str, **extra: Any) -> str:
    body = {"location_id": loc, "name": name, "turn_soon_ahead": 0, "allow_requeue": True, **extra}
    made = client.post(f"/v1/platform/businesses/{bid}/queue/lanes", headers=owner, json=body)
    assert made.status_code == 200, made.text
    return str(made.json()["data"]["id"])


def _token(owner: dict[str, str], bid: str, lane: str, name: str, **extra: Any) -> dict[str, Any]:
    body = {"lane_id": lane, "party_label": name, **extra}
    made = client.post(f"/v1/platform/businesses/{bid}/queue/entries", headers=owner, json=body)
    assert made.status_code == 200, made.text
    return cast(dict[str, Any], made.json()["data"])


def _provider(owner: dict[str, str], bid: str, loc: str, name: str, identity: uuid.UUID | None = None) -> str:
    body: dict[str, Any] = {"display_name": name, "location_ids": [loc], "primary_location_id": loc}
    if identity:
        body["identity_id"] = str(identity)
    made = client.post(f"/v1/platform/businesses/{bid}/workforce/members", headers=owner, json=body)
    assert made.status_code == 200, made.text
    return str(made.json()["data"]["id"])


@DB
def test_issue_call_serve_and_turn_soon_once(monkeypatch: Any) -> None:
    bid, owner, loc = _clinic(monkeypatch)
    lane = _lane(owner, bid, loc, "OPD", avg_service_minutes=10)
    first = _token(owner, bid, lane, "Meena")
    second = _token(owner, bid, lane, "Ravi")
    assert first["token_number"] == 1 and first["status"] == "waiting"
    assert second["token_number"] == 2
    drain_events(bid)
    notices = sql(
        "SELECT token_number FROM queue_turn_notices WHERE business_id = :b ORDER BY token_number", b=bid,
    )
    assert notices == [(1,)]
    drain_events(bid)
    assert sql("SELECT count(*) FROM queue_turn_notices WHERE business_id = :b", b=bid) == [(1,)]

    called = client.post(f"/v1/platform/businesses/{bid}/queue/lanes/{lane}/call-next", headers=owner)
    assert called.status_code == 200, called.text
    assert called.json()["data"]["token_number"] == 1 and called.json()["data"]["status"] == "called"
    serving = client.post(
        f"/v1/platform/businesses/{bid}/queue/entries/{first['id']}/serve", headers=owner,
    )
    assert serving.status_code == 200 and serving.json()["data"]["status"] == "serving"
    done = client.post(
        f"/v1/platform/businesses/{bid}/queue/entries/{first['id']}/complete", headers=owner,
    )
    assert done.status_code == 200 and done.json()["data"]["status"] == "served"
    board = client.get(f"/v1/platform/businesses/{bid}/queue/lanes/{lane}", headers=owner)
    assert board.status_code == 200, board.text
    columns = board.json()["data"]["columns"]
    assert [row["token_number"] for row in columns["waiting"]] == [2]
    assert columns["waiting"][0]["estimated_wait_minutes"] == 0
    assert [row["status"] for row in columns["done"]] == ["served"]
    drain_events(bid)
    assert sql("SELECT count(*) FROM queue_turn_notices WHERE business_id = :b", b=bid) == [(2,)]


@DB
def test_miss_requeue_and_requeue_refused(monkeypatch: Any) -> None:
    bid, owner, loc = _clinic(monkeypatch)
    lane = _lane(owner, bid, loc, "Lab")
    closed = _lane(owner, bid, loc, "Scan", allow_requeue=False)
    token = _token(owner, bid, lane, "Anita")
    missed = client.post(f"/v1/platform/businesses/{bid}/queue/entries/{token['id']}/miss", headers=owner)
    assert missed.status_code == 200 and missed.json()["data"]["status"] == "missed"
    back = client.post(f"/v1/platform/businesses/{bid}/queue/entries/{token['id']}/requeue", headers=owner)
    assert back.status_code == 200, back.text
    assert back.json()["data"]["status"] == "waiting"
    other = _token(owner, bid, closed, "Vikram")
    assert client.post(
        f"/v1/platform/businesses/{bid}/queue/entries/{other['id']}/miss", headers=owner,
    ).status_code == 200
    refused = client.post(
        f"/v1/platform/businesses/{bid}/queue/entries/{other['id']}/requeue", headers=owner,
    )
    assert refused.status_code == 422


@DB
def test_booking_joins_the_queue_without_a_second_booking(monkeypatch: Any) -> None:
    bid, owner, loc = _clinic(monkeypatch)
    lane = _lane(owner, bid, loc, "Consults")
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)
    booked = client.post(f"/v1/platform/businesses/{bid}/bookings", headers=owner, json={
        "location_id": loc, "title": "Review visit", "reservation_mode": "appointment",
        "starts_at": start.isoformat(), "ends_at": (start + timedelta(minutes=20)).isoformat(),
    })
    assert booked.status_code == 200, booked.text
    booking_id = booked.json()["data"]["id"]
    first = client.post(f"/v1/platform/businesses/{bid}/queue/entries", headers=owner, json={
        "lane_id": lane, "booking_id": booking_id,
    })
    assert first.status_code == 200, first.text
    assert first.json()["data"]["source"] == "booking"
    assert first.json()["data"]["booking_id"] == booking_id
    assert first.json()["data"]["display_name"] == "Review visit"
    again = client.post(f"/v1/platform/businesses/{bid}/queue/entries", headers=owner, json={
        "lane_id": lane, "booking_id": booking_id,
    })
    assert again.status_code == 200 and again.json()["data"]["id"] == first.json()["data"]["id"]
    assert sql("SELECT count(*) FROM bookings_bookings WHERE business_id = :b", b=bid) == [(1,)]
    assert sql(
        "SELECT party_label IS NULL FROM queue_entries WHERE id = :id", id=first.json()["data"]["id"],
    ) == [(True,)]


@DB
def test_provider_and_department_queues_stay_separate(monkeypatch: Any) -> None:
    bid, owner, loc = _clinic(monkeypatch)
    person, headers = new_identity(monkeypatch)
    other, other_headers = new_identity(monkeypatch)
    invited = client.post(f"/v1/b/{bid}/team/invitations", headers=owner, json={
        "identity_id": str(person), "role": "member",
    })
    assert invited.status_code == 200, invited.text
    mid = invited.json()["data"]["id"]
    assert client.post(f"/v1/b/{bid}/team/members/{mid}/activate", headers=owner).status_code == 200
    given = client.put(
        f"/v1/platform/businesses/{bid}/members/{mid}/role", headers=owner, json={"role": "provider"},
    )
    assert given.status_code == 200, given.text
    invited_b = client.post(f"/v1/b/{bid}/team/invitations", headers=owner, json={
        "identity_id": str(other), "role": "member",
    })
    mid_b = invited_b.json()["data"]["id"]
    assert client.post(f"/v1/b/{bid}/team/members/{mid_b}/activate", headers=owner).status_code == 200
    assert client.put(
        f"/v1/platform/businesses/{bid}/members/{mid_b}/role", headers=owner, json={"role": "provider"},
    ).status_code == 200
    mine = _provider(owner, bid, loc, "Dr Meena", person)
    theirs = _provider(owner, bid, loc, "Dr Ravi", other)
    opd = _lane(owner, bid, loc, "Meena OPD", provider_id=mine, department="OPD")
    ent = _lane(owner, bid, loc, "Ravi ENT", provider_id=theirs, department="ENT")
    _token(owner, bid, opd, "Walk-in")
    _token(owner, bid, ent, "Other walk-in")
    mine_board = client.get(f"/v1/platform/businesses/{bid}/queue/lanes/{opd}", headers=headers)
    assert mine_board.status_code == 200, mine_board.text
    assert mine_board.json()["data"]["columns"]["waiting"][0]["display_name"] == "Walk-in"
    hidden = client.get(f"/v1/platform/businesses/{bid}/queue/lanes/{ent}", headers=headers)
    assert hidden.status_code == 404
    called = client.post(f"/v1/platform/businesses/{bid}/queue/lanes/{opd}/call-next", headers=headers)
    assert called.status_code == 200 and called.json()["data"]["status"] == "called"
    stolen = client.post(f"/v1/platform/businesses/{bid}/queue/lanes/{ent}/call-next", headers=headers)
    assert stolen.status_code == 404
    still = client.get(f"/v1/platform/businesses/{bid}/queue/lanes/{ent}", headers=other_headers)
    assert still.status_code == 200
    assert still.json()["data"]["columns"]["waiting"][0]["display_name"] == "Other walk-in"


async def _queue_rows(session: AsyncSession, business_id: uuid.UUID, table: str) -> None:
    loc = (await session.execute(text(
        "insert into business_locations (business_id, name) values (:b, 'Desk') returning id"
    ), {"b": business_id})).scalar_one()
    lane = (await session.execute(text(
        "insert into queue_lanes (business_id, location_id, name) values (:b, :l, 'Front') returning id"
    ), {"b": business_id, "l": loc})).scalar_one()
    if table == "queue_lanes":
        return
    entry = (await session.execute(text(
        """insert into queue_entries
             (business_id, location_id, lane_id, token_number, token_day, source, party_label)
           values (:b, :l, :lane, 1, current_date, 'walk_in', 'A') returning id"""
    ), {"b": business_id, "l": loc, "lane": lane})).scalar_one()
    if table == "queue_entries":
        return
    if table == "queue_entry_events":
        await session.execute(text(
            """insert into queue_entry_events (business_id, entry_id, action, to_status)
               values (:b, :e, 'issued', 'waiting')"""
        ), {"b": business_id, "e": entry})
        return
    await session.execute(text(
        """insert into queue_turn_notices (business_id, entry_id, visit_cycle, ahead, token_number)
           values (:b, :e, 1, 0, 1)"""
    ), {"b": business_id, "e": entry})


@DB
@pytest.mark.asyncio
@pytest.mark.parametrize("table", ["queue_lanes", "queue_entries", "queue_entry_events", "queue_turn_notices"])
async def test_queue_tables_are_tenant_isolated(table: str) -> None:
    async def insert(session: AsyncSession, business_id: uuid.UUID) -> None:
        await _queue_rows(session, business_id, table)

    await assert_tenant_isolated(table, insert)
