"""Inventory field: transfers, van stock, job consumption, client-owned stock, assets.

Local Postgres only. Proves the in-transit gap, receipt, replay, the van
contract, and that another business cannot see the rows.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_testing.phase_b import assert_tenant_isolated, create_business, new_identity, primary_location, sql

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)

MODULES = ("offerings-catalog", "inventory", "customer-relationships")


def _shop(owner: dict[str, str]) -> tuple[str, str]:
    bid = create_business(client, owner, modules=MODULES)
    return bid, primary_location(client, owner, bid)


def _place(owner: dict[str, str], bid: str, name: str, role: str) -> str:
    created = client.post(f"/v1/platform/businesses/{bid}/locations", json={
        "name": name, "stock_role": role,
    }, headers=owner)
    assert created.status_code == 200, created.text
    return str(created.json()["data"]["id"])


def _item(owner: dict[str, str], bid: str) -> str:
    product = client.post(f"/v1/platform/businesses/{bid}/products", json={
        "title": f"Capacitor {uuid.uuid4().hex[:6]}", "sku": f"C-{uuid.uuid4().hex[:6]}",
        "track_inventory": True, "status": "active", "price_amount": 40, "tax_rate": 0,
    }, headers=owner)
    assert product.status_code == 200, product.text
    return str(product.json()["data"]["id"])


def _open(owner: dict[str, str], bid: str, offering: str, location: str, quantity: int) -> None:
    opened = client.post(f"/v1/platform/businesses/{bid}/inventory/opening-stock", json={
        "offering_id": offering, "location_id": location, "quantity": quantity, "reason": "Opening",
    }, headers=owner)
    assert opened.status_code == 200, opened.text


def _customer(owner: dict[str, str], bid: str, name: str) -> str:
    created = client.post(f"/v1/platform/businesses/{bid}/customers", json={
        "display_name": name, "phone": f"98{uuid.uuid4().int % 10**8:08d}",
    }, headers=owner)
    assert created.status_code == 200, created.text
    return str(created.json()["data"]["id"])


def _balance(bid: str, location: str, offering: str, *, client_id: str | None = None) -> tuple[int, int]:
    if client_id:
        rows = sql(
            "select quantity_on_hand, quantity_reserved from inventory_records "
            "where business_id = :b and location_id = :l and offering_id = :o and owner_customer_id = :c",
            b=bid, l=location, o=offering, c=client_id,
        )
    else:
        rows = sql(
            "select quantity_on_hand, quantity_reserved from inventory_records "
            "where business_id = :b and location_id = :l and offering_id = :o and owner_customer_id is null",
            b=bid, l=location, o=offering,
        )
    if not rows:
        return 0, 0
    return int(rows[0][0]), int(rows[0][1])


def _available(bid: str, location: str, offering: str, *, client_id: str | None = None) -> int:
    on_hand, reserved = _balance(bid, location, offering, client_id=client_id)
    return on_hand - reserved


def test_transfer_holds_stock_in_transit_until_receipt_and_replay(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, source = _shop(owner)
    dest = _place(owner, bid, "Shop B", "store")
    offering = _item(owner, bid)
    _open(owner, bid, offering, source, 20)

    asked = client.post(f"/v1/platform/businesses/{bid}/inventory/transfers", json={
        "source_location_id": source, "destination_location_id": dest,
        "lines": [{"offering_id": offering, "quantity": 5}],
        "idempotency_key": "xfer-create-0001",
    }, headers=owner)
    assert asked.status_code == 200, asked.text
    transfer = asked.json()["data"]
    assert transfer["status"] == "requested"
    again = client.post(f"/v1/platform/businesses/{bid}/inventory/transfers", json={
        "source_location_id": source, "destination_location_id": dest,
        "lines": [{"offering_id": offering, "quantity": 5}],
        "idempotency_key": "xfer-create-0001",
    }, headers=owner)
    assert again.status_code == 200 and again.json()["data"]["id"] == transfer["id"]
    # Still at the source: a request has not moved anything.
    assert _available(bid, source, offering) == 20
    assert _available(bid, dest, offering) == 0

    sent = client.post(f"/v1/platform/businesses/{bid}/inventory/transfers/{transfer['id']}/send", json={
        "idempotency_key": "xfer-send-0001",
    }, headers=owner)
    assert sent.status_code == 200, sent.text
    assert sent.json()["data"]["status"] == "in_transit"
    assert _available(bid, source, offering) == 15
    assert _available(bid, dest, offering) == 0

    received = client.post(f"/v1/platform/businesses/{bid}/inventory/transfers/{transfer['id']}/receive", json={
        "idempotency_key": "xfer-recv-0001",
    }, headers=owner)
    assert received.status_code == 200, received.text
    assert received.json()["data"]["status"] == "received"
    assert _available(bid, source, offering) == 15
    assert _available(bid, dest, offering) == 5

    replay = client.post(f"/v1/platform/businesses/{bid}/inventory/transfers/{transfer['id']}/receive", json={
        "idempotency_key": "xfer-recv-0001",
    }, headers=owner)
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["status"] == "received"
    assert _available(bid, dest, offering) == 5
    ins = sql(
        "select count(*) from inventory_movements where source_type = 'transfer' and source_id = :t "
        "and movement_type = 'transfer_in'",
        t=transfer["id"],
    )
    assert ins == [(1,)]

    # Another business sees none of it.
    _, other = new_identity(monkeypatch)
    other_bid = create_business(client, other, modules=MODULES)
    hidden = client.get(f"/v1/platform/businesses/{other_bid}/inventory/transfers", headers=other)
    assert hidden.status_code == 200
    assert hidden.json()["data"] == []
    stolen = client.post(
        f"/v1/platform/businesses/{other_bid}/inventory/transfers/{transfer['id']}/receive",
        json={"idempotency_key": "xfer-recv-other"}, headers=other,
    )
    assert stolen.status_code == 404


def test_approval_is_required_before_stock_leaves(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, source = _shop(owner)
    dest = _place(owner, bid, "Warehouse", "warehouse")
    offering = _item(owner, bid)
    _open(owner, bid, offering, source, 20)
    asked = client.post(f"/v1/platform/businesses/{bid}/inventory/transfers", json={
        "source_location_id": source, "destination_location_id": dest, "requires_approval": True,
        "lines": [{"offering_id": offering, "quantity": 5}],
        "idempotency_key": "xfer-need-approval",
    }, headers=owner)
    assert asked.status_code == 200, asked.text
    transfer_id = asked.json()["data"]["id"]
    early = client.post(f"/v1/platform/businesses/{bid}/inventory/transfers/{transfer_id}/send", json={
        "idempotency_key": "xfer-send-too-soon",
    }, headers=owner)
    assert early.status_code == 422
    assert _available(bid, source, offering) == 20
    approved = client.post(f"/v1/platform/businesses/{bid}/inventory/transfers/{transfer_id}/approve", json={
        "idempotency_key": "xfer-approve-0001",
    }, headers=owner)
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] == "approved"
    assert _available(bid, source, offering) == 20
    sent = client.post(f"/v1/platform/businesses/{bid}/inventory/transfers/{transfer_id}/send", json={
        "idempotency_key": "xfer-send-after-ok",
    }, headers=owner)
    assert sent.status_code == 200, sent.text
    assert sent.json()["data"]["status"] == "in_transit"
    assert _available(bid, source, offering) == 15
    assert _available(bid, dest, offering) == 0


def test_van_stock_job_consumption_and_unused_return(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, central = _shop(owner)
    van = _place(owner, bid, "Service van", "van")
    offering = _item(owner, bid)
    _open(owner, bid, offering, central, 20)
    job_ref = str(uuid.uuid4())

    loaded = client.post(f"/v1/platform/businesses/{bid}/inventory/transfers", json={
        "source_location_id": central, "destination_location_id": van,
        "lines": [{"offering_id": offering, "quantity": 4}],
        "idempotency_key": "van-load-0001",
    }, headers=owner)
    assert loaded.status_code == 200, loaded.text
    transfer_id = loaded.json()["data"]["id"]
    assert client.post(f"/v1/platform/businesses/{bid}/inventory/transfers/{transfer_id}/send", json={
        "idempotency_key": "van-load-send",
    }, headers=owner).status_code == 200
    assert _available(bid, van, offering) == 0
    assert client.post(f"/v1/platform/businesses/{bid}/inventory/transfers/{transfer_id}/receive", json={
        "idempotency_key": "van-load-recv",
    }, headers=owner).status_code == 200
    assert _available(bid, central, offering) == 16
    assert _available(bid, van, offering) == 4

    board = client.get(f"/v1/platform/businesses/{bid}/inventory/vans", headers=owner)
    assert board.status_code == 200, board.text
    vans = board.json()["data"]["vans"]
    assert len(vans) == 1 and vans[0]["name"] == "Service van"
    assert vans[0]["lines"][0]["available"] == 4

    used = client.post(f"/v1/platform/businesses/{bid}/inventory/jobs/consume", json={
        "location_id": van, "job_ref": job_ref,
        "lines": [{"offering_id": offering, "quantity": 3}],
        "idempotency_key": "job-use-0001",
    }, headers=owner)
    assert used.status_code == 200, used.text
    assert used.json()["data"]["lines"][0]["on_hand"] == 1
    assert _available(bid, van, offering) == 1
    replay = client.post(f"/v1/platform/businesses/{bid}/inventory/jobs/consume", json={
        "location_id": van, "job_ref": job_ref,
        "lines": [{"offering_id": offering, "quantity": 3}],
        "idempotency_key": "job-use-0001",
    }, headers=owner)
    assert replay.status_code == 200
    assert _available(bid, van, offering) == 1

    back = client.post(f"/v1/platform/businesses/{bid}/inventory/jobs/return-unused", json={
        "location_id": van, "job_ref": job_ref,
        "lines": [{"offering_id": offering, "quantity": 1}],
        "idempotency_key": "job-back-0001",
    }, headers=owner)
    assert back.status_code == 200, back.text
    assert _available(bid, van, offering) == 2
    too_much = client.post(f"/v1/platform/businesses/{bid}/inventory/jobs/return-unused", json={
        "location_id": van, "job_ref": job_ref,
        "lines": [{"offering_id": offering, "quantity": 5}],
        "idempotency_key": "job-back-too-much",
    }, headers=owner)
    assert too_much.status_code == 422
    assert _available(bid, van, offering) == 2

    returning = client.post(f"/v1/platform/businesses/{bid}/inventory/transfers", json={
        "source_location_id": van, "destination_location_id": central,
        "lines": [{"offering_id": offering, "quantity": 2}],
        "idempotency_key": "van-return-0001",
    }, headers=owner)
    assert returning.status_code == 200, returning.text
    back_id = returning.json()["data"]["id"]
    assert client.post(f"/v1/platform/businesses/{bid}/inventory/transfers/{back_id}/send", json={
        "idempotency_key": "van-return-send",
    }, headers=owner).status_code == 200
    assert _available(bid, van, offering) == 0
    assert _available(bid, central, offering) == 16
    assert client.post(f"/v1/platform/businesses/{bid}/inventory/transfers/{back_id}/receive", json={
        "idempotency_key": "van-return-recv",
    }, headers=owner).status_code == 200
    assert _available(bid, central, offering) == 18
    assert _available(bid, van, offering) == 0


def test_client_owned_stock_stays_off_the_business_balance(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, loc = _shop(owner)
    offering = _item(owner, bid)
    _open(owner, bid, offering, loc, 20)
    customer = _customer(owner, bid, "Meena Stores")
    inward = client.post(f"/v1/platform/businesses/{bid}/inventory/client-stock", json={
        "location_id": loc, "customer_id": customer, "offering_id": offering,
        "quantity": 8, "direction": "inward", "idempotency_key": "client-in-0001",
    }, headers=owner)
    assert inward.status_code == 200, inward.text
    assert inward.json()["data"]["owner"] == "client"
    assert _available(bid, loc, offering) == 20
    assert _available(bid, loc, offering, client_id=customer) == 8
    outward = client.post(f"/v1/platform/businesses/{bid}/inventory/client-stock", json={
        "location_id": loc, "customer_id": customer, "offering_id": offering,
        "quantity": 3, "direction": "outward", "idempotency_key": "client-out-0001",
    }, headers=owner)
    assert outward.status_code == 200, outward.text
    assert _available(bid, loc, offering) == 20
    assert _available(bid, loc, offering, client_id=customer) == 5
    listed = client.get(f"/v1/platform/businesses/{bid}/stock", headers=owner)
    assert listed.status_code == 200, listed.text
    shop_rows = [row for row in listed.json()["data"]["items"] if row["offering_id"] == offering]
    assert sum(row["quantity_available"] for row in shop_rows) == 20
    client_rows = client.get(
        f"/v1/platform/businesses/{bid}/inventory/client-stock?customer_id={customer}", headers=owner)
    assert client_rows.status_code == 200
    assert client_rows.json()["data"][0]["available"] == 5
    assert client_rows.json()["data"][0]["owner"] == "client"


def test_customer_assets_are_one_primitive(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, _loc = _shop(owner)
    customer = _customer(owner, bid, "Arun")
    kinds = [
        ("vehicle", "KA 01 AB 1001", {"registration": "KA01AB1001"}),
        ("device", "IMEI 4901", {"imei": "490154203237518"}),
        ("ac_unit", "Hall AC", {"tonnage": 1.5}),
        ("machine", "Compressor 4", {"serial": "CMP-4"}),
        ("pet", "Bruno", {"species": "dog"}),
        ("policy", "Policy 7781", {"policy_number": "7781"}),
    ]
    ids = []
    for kind, label, traits in kinds:
        created = client.post(f"/v1/platform/businesses/{bid}/customer-assets", json={
            "customer_id": customer, "asset_kind": kind, "label": label, "traits": traits,
            "idempotency_key": f"asset-{kind}-0001",
        }, headers=owner)
        assert created.status_code == 200, created.text
        assert created.json()["data"]["asset_kind"] == kind
        ids.append(created.json()["data"]["id"])
    replay = client.post(f"/v1/platform/businesses/{bid}/customer-assets", json={
        "customer_id": customer, "asset_kind": "pet", "label": "Bruno",
        "idempotency_key": "asset-pet-0001",
    }, headers=owner)
    assert replay.status_code == 200 and replay.json()["data"]["id"] == ids[4]
    listed = client.get(f"/v1/platform/businesses/{bid}/customer-assets?customer_id={customer}", headers=owner)
    assert listed.status_code == 200
    assert {row["asset_kind"] for row in listed.json()["data"]} == {k for k, _, _ in kinds}
    _, other = new_identity(monkeypatch)
    other_bid = create_business(client, other, modules=MODULES)
    foreign = client.get(f"/v1/platform/businesses/{other_bid}/customer-assets", headers=other)
    assert foreign.status_code == 200 and foreign.json()["data"] == []


async def test_inventory_field_tables_are_tenant_isolated() -> None:
    async def transfers(session: AsyncSession, business_id: uuid.UUID) -> None:
        source, dest = uuid.uuid4(), uuid.uuid4()
        offering = uuid.uuid4()
        await session.execute(text(
            "insert into business_locations (id, business_id, name) values (:s, :b, 'A'), (:d, :b, 'B')"
        ), {"s": source, "d": dest, "b": business_id})
        await session.execute(text(
            "insert into offerings_catalog_offerings (id, business_id, title) values (:o, :b, 'Part')"
        ), {"o": offering, "b": business_id})
        transfer = uuid.uuid4()
        await session.execute(text(
            "insert into inventory_transfers (id, business_id, source_location_id, destination_location_id) "
            "values (:t, :b, :s, :d)"
        ), {"t": transfer, "b": business_id, "s": source, "d": dest})
        await session.execute(text(
            "insert into inventory_transfer_lines (business_id, transfer_id, offering_id, quantity) "
            "values (:b, :t, :o, 1)"
        ), {"b": business_id, "t": transfer, "o": offering})

    async def keys(session: AsyncSession, business_id: uuid.UUID) -> None:
        await session.execute(text(
            "insert into inventory_field_keys (business_id, idempotency_key, action, snapshot) "
            "values (:b, :k, 'send', '{}'::jsonb)"
        ), {"b": business_id, "k": f"key-{business_id.hex[:12]}"})

    async def uses(session: AsyncSession, business_id: uuid.UUID) -> None:
        location, offering = uuid.uuid4(), uuid.uuid4()
        await session.execute(text(
            "insert into business_locations (id, business_id, name) values (:l, :b, 'Van')"
        ), {"l": location, "b": business_id})
        await session.execute(text(
            "insert into offerings_catalog_offerings (id, business_id, title) values (:o, :b, 'Cable')"
        ), {"o": offering, "b": business_id})
        await session.execute(text(
            "insert into inventory_job_uses (business_id, location_id, job_ref, offering_id, quantity_out) "
            "values (:b, :l, :j, :o, 1)"
        ), {"b": business_id, "l": location, "j": uuid.uuid4(), "o": offering})

    async def assets(session: AsyncSession, business_id: uuid.UUID) -> None:
        customer = uuid.uuid4()
        await session.execute(text(
            "insert into customer_relationships_contacts (id, business_id, display_name) "
            "values (:c, :b, 'Client')"
        ), {"c": customer, "b": business_id})
        await session.execute(text(
            "insert into customer_assets (business_id, customer_id, asset_kind, label) "
            "values (:b, :c, 'vehicle', 'Van 1')"
        ), {"b": business_id, "c": customer})

    for table, insert in (
        ("inventory_transfers", transfers),
        ("inventory_transfer_lines", transfers),
        ("inventory_field_keys", keys),
        ("inventory_job_uses", uses),
        ("customer_assets", assets),
    ):
        await assert_tenant_isolated(table, insert)
