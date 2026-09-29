"""Dispatch execution (Capability Universe §13).

Create a delivery, assign a crew member, pick it up, send it out, deliver it.
The same idempotency key does not move the job twice. A delivery partner sees
only their own jobs. Another business sees none.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_testing.phase_b import assert_tenant_isolated, create_business, new_identity, primary_location

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)

MODULES = (
    "offerings-catalog", "orders", "inventory", "payments", "fulfilment",
    "dispatch", "workforce", "customer-relationships",
)


def _shop(owner: dict[str, str]) -> tuple[str, str]:
    bid = create_business(client, owner, modules=MODULES)
    return bid, primary_location(client, owner, bid)


def _order(owner: dict[str, str], bid: str, loc: str, name: str) -> str:
    product = client.post(f"/v1/platform/businesses/{bid}/products", json={
        "title": f"Parcel {uuid.uuid4().hex[:6]}", "sku": f"P-{uuid.uuid4().hex[:6]}",
        "track_inventory": True, "status": "active", "price_amount": 50, "tax_rate": 0,
    }, headers=owner)
    assert product.status_code == 200, product.text
    offering = product.json()["data"]["id"]
    stock = client.post(f"/v1/platform/businesses/{bid}/inventory/opening-stock", json={
        "offering_id": offering, "location_id": loc, "quantity": 10, "reason": "Test stock",
    }, headers=owner)
    assert stock.status_code == 200, stock.text
    customer = client.post(f"/v1/platform/businesses/{bid}/customers", json={
        "display_name": name, "phone": f"98{uuid.uuid4().int % 10**8:08d}",
    }, headers=owner)
    assert customer.status_code == 200, customer.text
    order = client.post(f"/v1/platform/businesses/{bid}/orders", json={
        "location_id": loc, "customer_contact_id": customer.json()["data"]["id"],
        "payment_method": "cod", "idempotency_key": str(uuid.uuid4()),
        "items": [{"offering_id": offering, "quantity": 1}],
    }, headers=owner)
    assert order.status_code == 200, order.text
    return str(order.json()["data"]["id"])


def _join(owner: dict[str, str], bid: str, monkeypatch: Any, role: str) -> tuple[uuid.UUID, dict[str, str]]:
    person, headers = new_identity(monkeypatch)
    inv = client.post(f"/v1/b/{bid}/team/invitations", json={"identity_id": str(person), "role": "member"},
                      headers=owner)
    assert inv.status_code == 200, inv.text
    mid = inv.json()["data"]["id"]
    assert client.post(f"/v1/b/{bid}/team/members/{mid}/activate", headers=owner).status_code == 200
    given = client.put(f"/v1/platform/businesses/{bid}/members/{mid}/role", json={"role": role}, headers=owner)
    assert given.status_code == 200, given.text
    return person, headers


def _crew(owner: dict[str, str], bid: str, loc: str, name: str, identity: uuid.UUID) -> str:
    created = client.post(f"/v1/platform/businesses/{bid}/workforce/members", json={
        "display_name": name, "identity_id": str(identity), "location_ids": [loc], "primary_location_id": loc,
    }, headers=owner)
    assert created.status_code == 200, created.text
    return str(created.json()["data"]["id"])


def test_delivery_runs_from_create_to_delivered_and_replays(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, loc = _shop(owner)
    order_id = _order(owner, bid, loc, "Lakshmi")
    anbu, anbu_h = _join(owner, bid, monkeypatch, "delivery_partner")
    bala, bala_h = _join(owner, bid, monkeypatch, "delivery_partner")
    anbu_member = _crew(owner, bid, loc, "Anbu", anbu)
    _crew(owner, bid, loc, "Bala", bala)

    created = client.post(f"/v1/b/{bid}/dispatch/jobs", json={
        "order_id": order_id, "kind": "delivery", "dropoff": {"line": "12 Temple Street", "city": "Coimbatore"},
        "idempotency_key": f"create-{order_id}",
    }, headers=owner)
    assert created.status_code == 200, created.text
    job = created.json()["data"]
    assert job["status"] == "unassigned" and job["kind"] == "delivery"
    assert job["live_location"] is None and job["location_mode"] == "status_only"
    again = client.post(f"/v1/b/{bid}/dispatch/jobs", json={
        "order_id": order_id, "kind": "delivery", "idempotency_key": f"create-{order_id}",
    }, headers=owner)
    assert again.status_code == 200 and again.json()["data"]["id"] == job["id"]

    assigned = client.post(f"/v1/b/{bid}/dispatch/jobs/{job['id']}/assign", json={
        "member_id": anbu_member, "idempotency_key": "assign-1",
    }, headers=owner)
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["data"]["status"] == "assigned"
    assert assigned.json()["data"]["assignee_name"] == "Anbu"
    replay_assign = client.post(f"/v1/b/{bid}/dispatch/jobs/{job['id']}/assign", json={
        "member_id": anbu_member, "idempotency_key": "assign-1",
    }, headers=owner)
    assert replay_assign.status_code == 200
    assert replay_assign.json()["data"]["version"] == assigned.json()["data"]["version"]

    picked = client.post(f"/v1/b/{bid}/dispatch/jobs/{job['id']}/status", json={
        "status": "picked_up", "idempotency_key": "pick-1",
    }, headers=anbu_h)
    assert picked.status_code == 200, picked.text
    assert picked.json()["data"]["status"] == "picked_up"
    assert picked.json()["data"]["customer"]["phone"]

    out = client.post(f"/v1/b/{bid}/dispatch/jobs/{job['id']}/status", json={
        "status": "out_for_delivery", "idempotency_key": "out-1",
    }, headers=anbu_h)
    assert out.status_code == 200, out.text
    assert out.json()["data"]["status"] == "out_for_delivery"

    delivered = client.post(f"/v1/b/{bid}/dispatch/jobs/{job['id']}/status", json={
        "status": "delivered", "proof_note": "Handed to Lakshmi", "idempotency_key": "done-1",
    }, headers=anbu_h)
    assert delivered.status_code == 200, delivered.text
    body = delivered.json()["data"]
    assert body["status"] == "delivered" and body["proof_note"] == "Handed to Lakshmi"
    assert body["customer"]["phone"] is None  # the job is no longer active
    replay = client.post(f"/v1/b/{bid}/dispatch/jobs/{job['id']}/status", json={
        "status": "delivered", "proof_note": "Handed to Lakshmi", "idempotency_key": "done-1",
    }, headers=anbu_h)
    assert replay.status_code == 200
    assert replay.json()["data"]["version"] == body["version"]

    # Bala is crew too, and this job is not his.
    hidden = client.get(f"/v1/b/{bid}/dispatch/jobs/{job['id']}", headers=bala_h)
    assert hidden.status_code == 404
    mine = client.get(f"/v1/b/{bid}/dispatch/mine", headers=bala_h)
    assert mine.status_code == 200
    assert all(row["id"] != job["id"] for row in mine.json()["data"]["jobs"])
    stranger = client.get(f"/v1/b/{bid}/dispatch/board", headers=new_identity(monkeypatch)[1])
    assert stranger.status_code == 403

    # The events messaging already listens for, plus the dispatch-owned ones.
    async def _outbox() -> list[tuple[str, str | None]]:
        from platform_testing.phase_b import db_url
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        engine = create_async_engine(db_url(), poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            rows = (await session.execute(text(
                "select event_type, payload->>'to' from platform_outbox_events "
                "where business_id = :b and (event_type like 'dispatch.%' or event_type like 'fulfilment.%') "
                "order by created_at"
            ), {"b": bid})).all()
        await engine.dispose()
        return [(str(row[0]), row[1]) for row in rows]

    published = asyncio.run(_outbox())
    assert published.count(("dispatch.assigned", "assigned")) == 1
    assert published.count(("fulfilment.status_changed", "out_for_delivery")) == 1
    assert published.count(("fulfilment.delivered", "delivered")) == 1
    assert published.count(("dispatch.delivered", "delivered")) == 1

    # The customer page reads the same dispatch state. No coordinate is stored.
    async def _tracking_token() -> str:
        from platform_testing.phase_b import db_url
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        engine = create_async_engine(db_url(), poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        token = uuid.uuid4().hex
        async with factory() as session:
            existing = (await session.execute(text(
                "select tracking_token from fulfilment_jobs where order_id = :o"
            ), {"o": order_id})).scalar()
            if existing:
                token = str(existing)
            else:
                await session.execute(text(
                    "insert into fulfilment_jobs (business_id, order_id, location_id, mode, tracking_token, "
                    "tracking_expires_at) values (:b, :o, :l, 'delivery', :t, now() + interval '1 day')"
                ), {"b": bid, "o": order_id, "l": loc, "t": token})
                await session.commit()
        await engine.dispose()
        return token

    tracked = client.get(f"/v1/public/orders/{order_id}/tracking?token={asyncio.run(_tracking_token())}")
    assert tracked.status_code == 200, tracked.text
    dispatch_view = tracked.json()["data"]["dispatch"]
    assert dispatch_view["status"] == "delivered"
    assert dispatch_view["reached_step"] == "delivered"
    assert dispatch_view["live_location"] is None
    assert dispatch_view["location_mode"] == "status_only"


def test_pickup_does_not_go_out_for_delivery(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, loc = _shop(owner)
    order_id = _order(owner, bid, loc, "Ravi")
    person, _headers = _join(owner, bid, monkeypatch, "delivery_partner")
    member = _crew(owner, bid, loc, "Anbu", person)
    created = client.post(f"/v1/b/{bid}/dispatch/jobs", json={
        "order_id": order_id, "kind": "pickup",
    }, headers=owner)
    assert created.status_code == 200, created.text
    job_id = created.json()["data"]["id"]
    assert client.post(f"/v1/b/{bid}/dispatch/jobs/{job_id}/assign", json={"member_id": member}, headers=owner).status_code == 200
    assert client.post(f"/v1/b/{bid}/dispatch/jobs/{job_id}/status", json={"status": "picked_up"}, headers=owner).status_code == 200
    refused = client.post(f"/v1/b/{bid}/dispatch/jobs/{job_id}/status", json={"status": "out_for_delivery"}, headers=owner)
    assert refused.status_code == 422


def test_another_business_cannot_see_the_job(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, loc = _shop(owner)
    order_id = _order(owner, bid, loc, "Meena")
    job_id = client.post(f"/v1/b/{bid}/dispatch/jobs", json={
        "order_id": order_id, "kind": "delivery", "dropoff": {"line": "1 Road", "city": "Erode"},
    }, headers=owner).json()["data"]["id"]
    _, other = new_identity(monkeypatch)
    other_bid = create_business(client, other, modules=("dispatch",))
    missing = client.get(f"/v1/b/{other_bid}/dispatch/jobs/{job_id}", headers=other)
    assert missing.status_code == 404
    board = client.get(f"/v1/b/{other_bid}/dispatch/board", headers=other)
    assert board.status_code == 200
    assert all(column["jobs"] == [] for column in board.json()["data"]["columns"])


@pytest.mark.asyncio
async def test_dispatch_tables_are_tenant_isolated() -> None:
    async def insert_job(session: AsyncSession, business_id: uuid.UUID) -> None:
        loc = (await session.execute(text(
            "insert into business_locations (business_id, name) values (:b, 'Shop') returning id"
        ), {"b": business_id})).scalar()
        order = (await session.execute(text(
            "insert into orders_orders (business_id, location_id, order_number) "
            "values (:b, :l, :n) returning id"
        ), {"b": business_id, "l": loc, "n": f"N-{uuid.uuid4().hex[:8]}"})).scalar()
        await session.execute(text(
            "insert into dispatch_jobs (business_id, order_id, location_id, kind, order_number) "
            "values (:b, :o, :l, 'delivery', 'N')"
        ), {"b": business_id, "o": order, "l": loc})

    await assert_tenant_isolated("dispatch_jobs", insert_job)

    async def insert_event(session: AsyncSession, business_id: uuid.UUID) -> None:
        loc = (await session.execute(text(
            "insert into business_locations (business_id, name) values (:b, 'Shop') returning id"
        ), {"b": business_id})).scalar()
        order = (await session.execute(text(
            "insert into orders_orders (business_id, location_id, order_number) "
            "values (:b, :l, :n) returning id"
        ), {"b": business_id, "l": loc, "n": f"E-{uuid.uuid4().hex[:8]}"})).scalar()
        job = (await session.execute(text(
            "insert into dispatch_jobs (business_id, order_id, location_id, kind, order_number) "
            "values (:b, :o, :l, 'pickup', 'E') returning id"
        ), {"b": business_id, "o": order, "l": loc})).scalar()
        await session.execute(text(
            "insert into dispatch_events (business_id, job_id, location_id, idempotency_key, to_status) "
            "values (:b, :j, :l, :k, 'unassigned')"
        ), {"b": business_id, "j": job, "l": loc, "k": f"k-{uuid.uuid4().hex}"})

    await assert_tenant_isolated("dispatch_events", insert_event)
