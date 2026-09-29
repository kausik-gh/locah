"""Integration: an order is cooked from its recipe, and stock moves once.

Order accepted → exactly one KOT → start, ready, serve → the kitchen publishes
kitchen.preparation.completed (it never touches stock) → Recipe/BOM turns the
cooked lines into ingredient movements through Inventory. Real API, worker and
local PostgreSQL: 1000 g of paneer, 2 wraps at 150 g → 700 g. Draining again,
re-delivering the same completion event, and re-accepting the order leave one
KOT and 700 g.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_core.events.registry import EventContext
from platform_testing.phase_b import create_business, db_url, drain_events, new_identity, primary_location, sql
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)


def _offering(owner: dict[str, str], bid: str, title: str, kind: str, *, track: bool, unit: str = "piece") -> str:
    r = client.post(f"/v1/platform/businesses/{bid}/products", json={
        "title": title, "offering_type": kind, "status": "active", "price_amount": 180.0,
        "track_inventory": track, "stock_unit": unit}, headers=owner)
    assert r.status_code == 200, r.text
    return str(r.json()["data"]["id"])


def _on_hand(owner: dict[str, str], bid: str, offering: str) -> int:
    r = client.get(f"/v1/platform/businesses/{bid}/inventory?offering_id={offering}", headers=owner)
    assert r.status_code == 200, r.text
    return int(r.json()["data"][0]["quantity_on_hand"])


def _redeliver(bid: str, event_type: str) -> None:
    """Hand the stored event to its subscriber again, as a retried delivery would."""
    from platform_core.events.subscribers.recipe_consumption import consume_cooked

    row = sql("select id::text, payload::text from platform_outbox_events "
              "where business_id = :b and event_type = :t", b=bid, t=event_type)
    assert len(row) == 1, row

    async def run() -> None:
        engine = create_async_engine(db_url(), echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        ctx = EventContext(event_id=uuid.UUID(row[0][0]), event_type=event_type, payload=json.loads(row[0][1]),
                           business_id=uuid.UUID(bid), correlation_id="replay", attempt=2)
        try:
            async with factory() as session:
                await consume_cooked(session, ctx)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_a_cooked_order_uses_its_recipe_from_stock_exactly_once(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, business_type="restaurant", modules=(
        "offerings-catalog", "orders", "inventory", "kitchen", "procurement", "recipes"))
    loc = primary_location(client, owner, bid)
    wrap = _offering(owner, bid, "Paneer wrap", "menu_item", track=False)
    paneer = _offering(owner, bid, "Paneer", "product", track=True, unit="g")
    stocked = client.post(f"/v1/platform/businesses/{bid}/inventory/opening-stock", json={
        "offering_id": paneer, "location_id": loc, "quantity": 1000, "reason": "Opening"}, headers=owner)
    assert stocked.status_code == 200, stocked.text
    recipe = client.put(f"/v1/platform/businesses/{bid}/recipes", json={
        "offering_id": wrap, "lines": [{"component_offering_id": paneer, "quantity_per": 150}]}, headers=owner)
    assert recipe.status_code == 200, recipe.text
    listed = client.get(f"/v1/platform/businesses/{bid}/recipes", headers=owner).json()["data"]
    assert [(r["dish"], [(ln["component"], ln["quantity_per"]) for ln in r["lines"]]) for r in listed] == [
        ("Paneer wrap", [("Paneer", 150.0)])]

    order = client.post(f"/v1/platform/businesses/{bid}/orders", json={
        "location_id": loc, "channel": "workspace", "internal_reference": "Table 2",
        "items": [{"offering_id": wrap, "quantity": 2}]}, headers=owner).json()["data"]
    accepted = client.post(f"/v1/platform/businesses/{bid}/orders/{order['id']}/status",
                           json={"status": "accepted"}, headers=owner)
    assert accepted.status_code == 200, accepted.text
    drain_events(bid)
    drain_events(bid)
    tickets = sql("select id::text, version from kitchen_tickets where business_id = :b", b=bid)
    assert len(tickets) == 1, "an accepted food order is exactly one KOT"
    assert _on_hand(owner, bid, paneer) == 1000, "accepting and cooking do not touch stock"

    ticket_id, version = tickets[0]
    for step in ("start", "ready", "serve"):
        r = client.post(f"/v1/platform/businesses/{bid}/kitchen/tickets/{ticket_id}/{step}",
                        json={"version": version}, headers=owner)
        assert r.status_code == 200, r.text
        version = r.json()["data"]["version"]
    assert _on_hand(owner, bid, paneer) == 1000, "the kitchen never edits stock itself"

    drain_events(bid)
    assert _on_hand(owner, bid, paneer) == 700, "2 wraps × 150 g"
    drain_events(bid)
    _redeliver(bid, "kitchen.preparation.completed")
    assert _on_hand(owner, bid, paneer) == 700, "one preparation consumes once"
    assert int(sql("select count(*) from recipe_consumptions where business_id = :b", b=bid)[0][0]) == 1

    again = client.post(f"/v1/platform/businesses/{bid}/orders/{order['id']}/status",
                        json={"status": "accepted"}, headers=owner)
    assert again.status_code in (200, 409, 422), again.text
    drain_events(bid)
    assert int(sql("select count(*) from kitchen_tickets where business_id = :b", b=bid)[0][0]) == 1
    assert _on_hand(owner, bid, paneer) == 700
