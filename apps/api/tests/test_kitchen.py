"""Kitchen tickets follow an accepted order. They are not a second order.

Local Postgres only. The database guard refuses a remote URL.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import jwt
import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_core.db import get_database_url
from platform_core.events.registry import EventContext
from platform_testing.db_helpers import ensure_auth_user
from platform_testing.phase_b import drain_events, sql
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")

TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"
PHONE = "9876543210"


def _token(sub: uuid.UUID, email: str) -> str:
    return jwt.encode(
        {"sub": str(sub), "email": email, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


def _headers(user_id: uuid.UUID, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(user_id, email)}"}


def _seed(user_id: uuid.UUID, email: str) -> None:
    async def _run() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await ensure_auth_user(session, user_id, email)
            await session.commit()
        await engine.dispose()

    asyncio.run(_run())


@pytest.fixture
def owner(monkeypatch: Any) -> tuple[dict[str, str], uuid.UUID]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed(user_id, email)
    return _headers(user_id, email), user_id


def _business(client: TestClient, headers: dict[str, str], *modules: str) -> str:
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"Kitchen Co {uuid.uuid4().hex[:8]}", "business_type": "restaurant"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    business_id = cast(str, resp.json()["data"]["business"]["id"])
    for module_id in modules:
        enabled = client.post(f"/v1/b/{business_id}/modules/{module_id}/enable", headers=headers)
        assert enabled.status_code == 200, enabled.text
    return business_id


def _location(client: TestClient, headers: dict[str, str], business_id: str) -> str:
    resp = client.get(f"/v1/platform/businesses/{business_id}/locations", headers=headers)
    assert resp.status_code == 200, resp.text
    for loc in resp.json()["data"]:
        if loc["is_primary"]:
            return cast(str, loc["id"])
    raise AssertionError("primary location missing")


def _offering(
    client: TestClient,
    headers: dict[str, str],
    business_id: str,
    *,
    title: str,
    kind: str,
    track: bool = False,
    groups: list[dict[str, Any]] | None = None,
) -> str:
    resp = client.post(
        f"/v1/platform/businesses/{business_id}/products",
        json={
            "title": title,
            "offering_type": kind,
            "status": "active",
            "price_amount": 120.0,
            "track_inventory": track,
            "option_groups": groups or [],
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return cast(str, resp.json()["data"]["id"])


def _accept(
    client: TestClient,
    headers: dict[str, str],
    business_id: str,
    location_id: str,
    items: list[dict[str, Any]],
    *,
    reference: str = "Table 4",
) -> dict[str, Any]:
    created = client.post(
        f"/v1/platform/businesses/{business_id}/orders",
        json={
            "location_id": location_id,
            "channel": "workspace",
            "internal_reference": reference,
            "items": items,
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    order = created.json()["data"]
    noted = client.post(
        f"/v1/platform/businesses/{business_id}/orders/{order['id']}/notes",
        json={"body": f"No onion. Guest phone {PHONE}"},
        headers=headers,
    )
    assert noted.status_code == 200, noted.text
    accepted = client.post(
        f"/v1/platform/businesses/{business_id}/orders/{order['id']}/status",
        json={"status": "accepted"},
        headers=headers,
    )
    assert accepted.status_code == 200, accepted.text
    drain_events(business_id)
    return cast(dict[str, Any], accepted.json()["data"])


def _board(client: TestClient, headers: dict[str, str], business_id: str, station_id: str | None = None) -> dict[str, Any]:
    query = f"?station_id={station_id}" if station_id else ""
    resp = client.get(f"/v1/platform/businesses/{business_id}/kitchen/board{query}", headers=headers)
    assert resp.status_code == 200, resp.text
    return cast(dict[str, Any], resp.json()["data"])


def _tickets(board: dict[str, Any]) -> list[dict[str, Any]]:
    columns = board["columns"]
    return [*columns["new"], *columns["preparing"], *columns["ready"]]


def _step(client: TestClient, headers: dict[str, str], business_id: str, ticket_id: str, step: str, version: int) -> dict[str, Any]:
    resp = client.post(
        f"/v1/platform/businesses/{business_id}/kitchen/tickets/{ticket_id}/{step}",
        json={"version": version},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return cast(dict[str, Any], resp.json()["data"])


def _replay_same_event(business_id: str, order_id: str) -> None:
    """Deliver the original accept event again. The intake row makes it a no-op."""
    rows = sql(
        """
        select id::text from platform_outbox_events
        where business_id = :b and event_type = 'order.accepted'
        order by created_at desc limit 1
        """,
        b=business_id,
    )
    assert rows, "accept did not publish order.accepted"
    event_id = uuid.UUID(rows[0][0])

    async def _run() -> None:
        url = get_database_url() or ""
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        from platform_core.kitchen.intake import OrderIntake

        ctx = EventContext(
            event_id=event_id,
            event_type="order.accepted",
            payload={"order_id": order_id, "business_id": business_id},
            business_id=uuid.UUID(business_id),
            correlation_id="replay",
            attempt=2,
        )
        async with factory() as session:
            await OrderIntake.handle(session, ctx)
            await OrderIntake.handle(session, ctx)
            await session.commit()
        # Drop the claim and deliver again. The ticket is still unique per order.
        async with factory() as session:
            await session.execute(text("delete from kitchen_intakes where event_id = :id"), {"id": event_id})
            await OrderIntake.handle(session, ctx)
            await session.commit()
        await engine.dispose()

    asyncio.run(_run())


def test_accept_creates_one_ticket_and_replay_does_not(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _business(client, headers, "offerings-catalog", "orders", "kitchen")
    location_id = _location(client, headers, business_id)
    shawarma = _offering(
        client, headers, business_id, title="Shawarma", kind="menu_item",
        groups=[{"name": "Spice", "required": False, "max": 1, "choices": [{"label": "Mild", "price_delta": 0}]}],
    )
    soap = _offering(client, headers, business_id, title="Soap", kind="product")
    order = _accept(
        client, headers, business_id, location_id,
        [
            {"offering_id": shawarma, "quantity": 2, "options": {"choices": {"Spice": ["Mild"]}}},
            {"offering_id": soap, "quantity": 1},
        ],
    )
    board = _board(client, headers, business_id)
    tickets = _tickets(board)
    assert len(tickets) == 1
    ticket = tickets[0]
    assert ticket["ticket_number"].startswith("KOT-")
    assert ticket["service_mode"] == "dine_in"
    assert ticket["service_label"] == "Table 4"
    assert len(ticket["lines"]) == 1
    assert ticket["lines"][0]["title"].startswith("Shawarma")
    assert ticket["lines"][0]["quantity"] == 2
    assert "Mild" in " ".join(ticket["lines"][0]["modifiers"])
    dumped = json.dumps(board)
    assert "unit_price" not in dumped
    assert PHONE not in dumped
    assert "Soap" not in dumped
    assert sql("select count(*) from kitchen_tickets where business_id = :b", b=business_id)[0][0] == 1

    _replay_same_event(business_id, order["id"])
    drain_events(business_id)
    assert sql("select count(*) from kitchen_tickets where business_id = :b", b=business_id)[0][0] == 1
    assert len(_tickets(_board(client, headers, business_id))) == 1


def test_station_routing_is_one_ticket(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _business(client, headers, "offerings-catalog", "orders", "kitchen")
    location_id = _location(client, headers, business_id)
    plate = _offering(client, headers, business_id, title="Mixed plate", kind="menu_item")
    fries = _offering(client, headers, business_id, title="Fries", kind="menu_item")
    stations = {}
    for key, name in (("grill", "Grill"), ("fryer", "Fryer")):
        created = client.post(
            f"/v1/platform/businesses/{business_id}/kitchen/stations",
            json={"key": key, "name": name},
            headers=headers,
        )
        assert created.status_code == 200, created.text
        stations[key] = created.json()["data"]["id"]
    routed = client.put(
        f"/v1/platform/businesses/{business_id}/kitchen/routes",
        json={"offering_id": plate, "station_ids": [stations["grill"], stations["fryer"]]},
        headers=headers,
    )
    assert routed.status_code == 200, routed.text
    _accept(
        client, headers, business_id, location_id,
        [{"offering_id": plate, "quantity": 1}, {"offering_id": fries, "quantity": 1}],
    )
    board = _board(client, headers, business_id)
    tickets = _tickets(board)
    assert len(tickets) == 1
    titles = sorted(line["title"] for line in tickets[0]["lines"])
    assert titles == ["Fries", "Mixed plate", "Mixed plate"]
    stations_for_plate = {line["station_name"] for line in tickets[0]["lines"] if line["title"] == "Mixed plate"}
    assert stations_for_plate == {"Grill", "Fryer"}
    fries_line = next(line for line in tickets[0]["lines"] if line["title"] == "Fries")
    assert fries_line["station_name"] == "General"
    grill_id = stations["grill"]
    grill_board = _board(client, headers, business_id, grill_id)
    grill_tickets = _tickets(grill_board)
    assert len(grill_tickets) == 1
    assert [line["title"] for line in grill_tickets[0]["lines"]] == ["Mixed plate"]


def test_start_ready_serve_publishes_completion_and_leaves_stock(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _business(client, headers, "offerings-catalog", "orders", "inventory", "kitchen")
    location_id = _location(client, headers, business_id)
    dish = _offering(client, headers, business_id, title="Grill wrap", kind="menu_item", track=True)
    stocked = client.post(
        f"/v1/platform/businesses/{business_id}/inventory/opening-stock",
        json={"offering_id": dish, "location_id": location_id, "quantity": 8, "reason": "Opening"},
        headers=headers,
    )
    assert stocked.status_code == 200, stocked.text
    order = _accept(client, headers, business_id, location_id, [{"offering_id": dish, "quantity": 2}])
    ticket = _tickets(_board(client, headers, business_id))[0]
    started = _step(client, headers, business_id, ticket["id"], "start", ticket["version"])
    assert started["status"] == "preparing"
    ready = _step(client, headers, business_id, ticket["id"], "ready", started["version"])
    assert ready["status"] == "ready"
    assert _tickets(_board(client, headers, business_id))[0]["ticket_number"] == ticket["ticket_number"]
    before = sql(
        "select count(*) from platform_outbox_events where business_id = :b and event_type = 'inventory.stock.updated'",
        b=business_id,
    )[0][0]
    served = _step(client, headers, business_id, ticket["id"], "serve", ready["version"])
    assert served["status"] == "completed"
    assert _tickets(_board(client, headers, business_id)) == []
    after = sql(
        "select count(*) from platform_outbox_events where business_id = :b and event_type = 'inventory.stock.updated'",
        b=business_id,
    )[0][0]
    assert after == before
    completed = sql(
        "select count(*) from platform_outbox_events where business_id = :b and event_type = 'kitchen.preparation.completed'",
        b=business_id,
    )[0][0]
    assert completed == 1
    on_hand = client.get(
        f"/v1/platform/businesses/{business_id}/inventory?offering_id={dish}",
        headers=headers,
    )
    assert on_hand.status_code == 200, on_hand.text
    assert on_hand.json()["data"][0]["quantity_on_hand"] == 8
    still = client.get(f"/v1/platform/businesses/{business_id}/orders/{order['id']}", headers=headers)
    assert still.status_code == 200, still.text
    assert still.json()["data"]["status"] == "accepted"


def test_cancel_before_start_and_change_after_start(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _business(client, headers, "offerings-catalog", "orders", "kitchen")
    location_id = _location(client, headers, business_id)
    dish = _offering(
        client, headers, business_id, title="Burger", kind="menu_item",
        groups=[{"name": "Cheese", "required": False, "max": 1, "choices": [
            {"label": "Plain", "price_delta": 0},
            {"label": "Extra", "price_delta": 20},
        ]}],
    )

    early = _accept(
        client, headers, business_id, location_id,
        [{"offering_id": dish, "quantity": 1, "options": {"choices": {"Cheese": ["Plain"]}}}],
        reference="Table 1",
    )
    early_ticket = _tickets(_board(client, headers, business_id))[0]
    cancelled = client.post(
        f"/v1/platform/businesses/{business_id}/orders/{early['id']}/cancel",
        json={"reason": "Guest left"},
        headers=headers,
    )
    assert cancelled.status_code == 200, cancelled.text
    drain_events(business_id)
    assert _tickets(_board(client, headers, business_id)) == []
    assert sql(
        "select status from kitchen_tickets where id = :id", id=early_ticket["id"]
    )[0][0] == "cancelled"

    live = _accept(
        client, headers, business_id, location_id,
        [{"offering_id": dish, "quantity": 1, "options": {"choices": {"Cheese": ["Plain"]}}}],
        reference="Table 2",
    )
    ticket = next(item for item in _tickets(_board(client, headers, business_id)) if item["service_label"] == "Table 2")
    started = _step(client, headers, business_id, ticket["id"], "start", ticket["version"])
    line_id = live["items"][0]["id"]
    changed = client.post(
        f"/v1/platform/businesses/{business_id}/orders/{live['id']}/change",
        json={"lines": [{"line_id": line_id, "quantity": 3}], "reason": "Two more", "customer_agreed": True},
        headers=headers,
    )
    assert changed.status_code == 200, changed.text
    drain_events(business_id)
    card = next(item for item in _tickets(_board(client, headers, business_id)) if item["id"] == ticket["id"])
    original = next(line for line in card["lines"] if line["origin"] == "original")
    added = next(line for line in card["lines"] if line["origin"] == "added")
    assert original["quantity"] == 1
    assert added["quantity"] == 2
    assert any("Add 2" in event["summary"] for event in card["events"])

    shrunk = client.post(
        f"/v1/platform/businesses/{business_id}/orders/{live['id']}/change",
        json={"lines": [{"line_id": line_id, "quantity": 1}], "reason": "Back to one", "customer_agreed": True},
        headers=headers,
    )
    assert shrunk.status_code == 200, shrunk.text
    drain_events(business_id)
    card = next(item for item in _tickets(_board(client, headers, business_id)) if item["id"] == ticket["id"])
    original = next(line for line in card["lines"] if line["origin"] == "original")
    assert original["quantity"] == 1
    assert any(event["kind"] == "quantity_changed" for event in card["events"])

    _rewrite_modifiers(line_id, {"choices": {"Cheese": ["Extra"]}})
    drain_events(business_id)
    # The order row changed without a new event. Deliver the same update shape once.
    _deliver_updated(business_id, live["id"])
    card = next(item for item in _tickets(_board(client, headers, business_id)) if item["id"] == ticket["id"])
    original = next(line for line in card["lines"] if line["origin"] == "original")
    assert "Plain" in " ".join(original["modifiers"])
    assert "Extra" not in " ".join(original["modifiers"])
    assert any(event["kind"] == "modifier_changed" for event in card["events"])

    stopped = client.post(
        f"/v1/platform/businesses/{business_id}/orders/{live['id']}/cancel",
        json={"reason": "Guest cancelled"},
        headers=headers,
    )
    assert stopped.status_code == 200, stopped.text
    drain_events(business_id)
    card = next(item for item in _tickets(_board(client, headers, business_id)) if item["id"] == ticket["id"])
    assert card["attention"] == "cancel"
    original = next(line for line in card["lines"] if line["origin"] == "original")
    assert original["quantity"] == 1
    assert original["prep_status"] == "preparing"
    kept = sql(
        "select quantity, prep_status, started_at is not null from kitchen_ticket_lines where id = :id",
        id=original["id"],
    )[0]
    assert kept == (1, "preparing", True)
    assert started["status"] == "preparing"


def _rewrite_modifiers(line_id: str, options: dict[str, Any]) -> None:
    sql(
        "update orders_order_line_items set options = cast(:options as jsonb) where id = :id",
        options=json.dumps(options),
        id=line_id,
    )


def _deliver_updated(business_id: str, order_id: str) -> None:
    async def _run() -> None:
        url = get_database_url() or ""
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        from platform_core.kitchen.intake import OrderIntake

        ctx = EventContext(
            event_id=uuid.uuid4(),
            event_type="order.updated",
            payload={"order_id": order_id, "business_id": business_id},
            business_id=uuid.UUID(business_id),
            correlation_id="modifier",
            attempt=1,
        )
        async with factory() as session:
            await OrderIntake.handle(session, ctx)
            await session.commit()
        await engine.dispose()

    asyncio.run(_run())


def test_tenant_and_location_isolation(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    first = _business(client, headers, "offerings-catalog", "orders", "kitchen")
    second = _business(client, headers, "offerings-catalog", "orders", "kitchen")
    location_id = _location(client, headers, first)
    dish = _offering(client, headers, first, title="Secret plate", kind="menu_item")
    _accept(client, headers, first, location_id, [{"offering_id": dish, "quantity": 1}], reference="Table 9")
    own = _tickets(_board(client, headers, first))
    assert len(own) == 1
    assert _tickets(_board(client, headers, second)) == []
    stolen = client.post(
        f"/v1/platform/businesses/{second}/kitchen/tickets/{own[0]['id']}/start",
        json={},
        headers=headers,
    )
    assert stolen.status_code == 404, stolen.text

    async def _rls() -> tuple[int, int]:
        url = get_database_url() or ""
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        try:
            async with AsyncSession(engine) as session:
                await session.execute(text("set local role platform_api"))
                await session.execute(
                    text("select set_config('app.current_business_id', :b, true)"),
                    {"b": second},
                )
                other = int((await session.execute(text("select count(*) from kitchen_tickets"))).scalar_one())
                await session.rollback()
            async with AsyncSession(engine) as session:
                await session.execute(text("set local role platform_api"))
                await session.execute(
                    text("select set_config('app.current_business_id', :b, true)"),
                    {"b": first},
                )
                await session.execute(
                    text("select set_config('app.current_location_scope', :s, true)"),
                    {"s": str(uuid.uuid4())},
                )
                hidden = int((await session.execute(text("select count(*) from kitchen_tickets"))).scalar_one())
                await session.rollback()
            return other, hidden
        finally:
            await engine.dispose()

    other_count, hidden_count = asyncio.run(_rls())
    assert other_count == 0
    assert hidden_count == 0
