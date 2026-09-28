"""P1-10A stock depth (Capability Universe §15.1; Business OS Guide §11).

One inventory domain, different work: a meat shop cuts whole birds into cuts
and sees trim; a pharmacy sells the earliest expiry first and is warned before
a batch expires; a mobile store sells a unit by its serial and can look up its
warranty; everyone counts shelves, and a count changes stock only when someone
allowed to approves it. Every figure is checked against the one stock record.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from platform_api.main import app
from platform_core.stock import profile
from platform_testing.phase_b import (
    assert_tenant_isolated,
    billing_shop,
    create_business,
    drain_events,
    new_identity,
    primary_location,
    sql,
)

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)
IST = ZoneInfo("Asia/Kolkata")
TODAY = datetime.now(IST).date()


def _item(owner: dict[str, str], bid: str, **body: Any) -> dict[str, Any]:
    r = client.post(f"/v1/platform/businesses/{bid}/products",
                    json={"status": "active", "offering_type": "product", "track_inventory": True, **body},
                    headers=owner)
    assert r.status_code == 200, r.text
    return dict(r.json()["data"])


def _weighed(owner: dict[str, str], bid: str, title: str, price: int) -> dict[str, Any]:
    return _item(owner, bid, title=title, offering_type="weighed_product", price_amount=price,
                 attributes={"price_per": "kg"}, sell_units=[{"label": "1 kg", "qty": 1000}])


def _record(offering_id: str) -> tuple[int, int]:
    rows = sql("SELECT quantity_on_hand, stock_value_paise FROM inventory_records WHERE offering_id = :o",
               o=offering_id)
    assert len(rows) == 1, rows
    return int(rows[0][0]), int(rows[0][1])


# ---------------------------------------------------------------- the lenses (deterministic, no DB)
@pytest.mark.parametrize(("sub", "first", "also"), [
    ("meat_shop", "weighed", set()),  # the source says inventory (yield) for meat, not batches
    ("pharmacy", "batches", set()),
    ("mobile_store", "serials", {"variants"}),
    ("clothing", "variants", set()),
    ("restaurant", "ingredients", set()),
    ("hardware", "variants", {"counter"}),
])
def test_each_business_sees_stock_its_own_way(sub: str, first: str, also: set[str]) -> None:
    from platform_core.catalog.recommendation import family_key_for
    from platform_core.catalog.taxonomy import SUBCATEGORIES

    _, s = SUBCATEGORIES[sub]
    hints = profile.family_hints(family_key_for(sub, s.playbook))
    lenses = profile.lenses(s.traits, hints, {})
    assert lenses[0] == first, (sub, lenses)
    assert also <= set(lenses) and "counter" in lenses
    # A name alone decides nothing: a business with no stock traits sees the counter view only.
    assert profile.lenses((), (), {}) == ["counter"]


def test_meat_shop_offers_cutting_and_trim_first() -> None:
    from platform_core.catalog.taxonomy import SUBCATEGORIES

    _, meat = SUBCATEGORIES["meat_shop"]
    assert "yield" in profile.family_hints("meat_chicken_fish_shops")
    assert profile.yield_offered(meat.traits, {"yield"}, {})
    assert profile.wastage_reasons(["weighed", "counter"])[0] == "trim_loss"
    assert profile.wastage_reasons(["batches", "counter"])[0] == "expired"
    # What an owner configures also counts: one batch-tracked item turns the lens on.
    assert "batches" in profile.lenses((), (), {"batch_tracked": 1})


# ---------------------------------------------------------------- meat: yield, value, trim
@DB
def test_cutting_run_carries_cost_into_the_cuts_and_reports_trim(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, category_key="fresh_grocery", subcategory_key="meat_shop",
                          modules=("offerings-catalog", "inventory", "orders", "payments"))
    base = f"/v1/platform/businesses/{bid}"
    loc = primary_location(client, owner, bid)
    whole = _weighed(owner, bid, "Whole chicken", 180)
    curry = _weighed(owner, bid, "Chicken curry cut", 260)
    boneless = _weighed(owner, bid, "Chicken boneless", 340)

    prof = client.get(f"{base}/stock/profile", headers=owner).json()["data"]
    assert prof["primary"] == "weighed" and prof["yield_offered"] is True
    assert prof["wastage_reasons"][0]["key"] == "trim_loss"
    assert "weight_based" in prof["because"]["traits"] and "yield" in prof["because"]["playbook_hints"]

    got = client.post(f"{base}/stock/receipts", json={
        "location_id": loc, "offering_id": whole["id"], "quantity": 10_000, "total_cost_paise": 180_000,
        "note": "Morning supply"}, headers=owner)
    assert got.status_code == 200, got.text
    assert got.json()["data"]["on_hand_text"] == "10 kg"
    assert _record(whole["id"]) == (10_000, 180_000)

    y = client.put(f"{base}/stock/yields", json={"source_offering_id": whole["id"],
                                                 "output_offering_id": curry["id"], "yield_percent": 80},
                   headers=owner)
    assert y.status_code == 200, y.text

    too_much = client.post(f"{base}/stock/conversions", json={
        "location_id": loc, "source_offering_id": whole["id"], "source_quantity": 5_000,
        "outputs": [{"offering_id": curry["id"], "quantity": 4_000}, {"offering_id": boneless["id"],
                                                                        "quantity": 1_500}]}, headers=owner)
    assert too_much.status_code == 422  # outputs cannot weigh more than what was cut

    run = client.post(f"{base}/stock/conversions", json={
        "location_id": loc, "source_offering_id": whole["id"], "source_quantity": 5_000,
        "outputs": [{"offering_id": curry["id"], "quantity": 3_600}, {"offering_id": boneless["id"],
                                                                        "quantity": 400}],
        "idempotency_key": "cut-1"}, headers=owner)
    assert run.status_code == 200, run.text
    data = run.json()["data"]
    assert data["trim_text"] == "1 kg" and data["trim_percent"] == 20.0
    curry_out = next(o for o in data["outputs"] if o["offering_id"] == curry["id"])
    assert curry_out["expected"] == 4_000 and curry_out["actual"] == 3_600
    # Half the birds (₹900) now sit in 4 kg of cuts: the trim's cost is in the cuts.
    assert _record(whole["id"]) == (5_000, 90_000)
    curry_qty, curry_value = _record(curry["id"])
    bone_qty, bone_value = _record(boneless["id"])
    assert (curry_qty, bone_qty) == (3_600, 400) and curry_value + bone_value == 90_000
    assert curry_value == 81_000
    replay = client.post(f"{base}/stock/conversions", json={
        "location_id": loc, "source_offering_id": whole["id"], "source_quantity": 5_000,
        "outputs": [{"offering_id": curry["id"], "quantity": 3_600}], "idempotency_key": "cut-1"}, headers=owner)
    assert replay.status_code == 200 and replay.json()["data"]["id"] == data["id"]
    assert _record(whole["id"]) == (5_000, 90_000)  # a replayed run moves nothing

    yields = client.get(f"{base}/stock/yields", headers=owner).json()["data"]
    assert yields[0]["actual_percent_of_expected"] == 90.0 and yields[0]["runs"] == 1

    rec_id = sql("SELECT id FROM inventory_records WHERE offering_id = :o", o=curry["id"])[0][0]
    wasted = client.post(f"{base}/stock/wastage", json={
        "inventory_record_id": str(rec_id), "quantity": 600, "reason_code": "spoiled"}, headers=owner)
    assert wasted.status_code == 200, wasted.text
    assert _record(curry["id"]) == (3_000, 67_500)
    summary = client.get(f"{base}/stock/wastage", headers=owner).json()["data"]
    assert summary["reasons"][0]["reason"] == "spoiled" and summary["reasons"][0]["quantities"] == ["0.6 kg"]
    assert summary["cutting"]["trim_percent"] == 20.0

    view = client.get(f"{base}/stock", headers=owner).json()["data"]
    row = next(i for i in view["items"] if i["offering_id"] == curry["id"])
    assert row["on_hand_text"] == "3 kg" and row["value_paise"] == 67_500
    moves = sql("SELECT movement_type, quantity_delta, value_delta_paise FROM inventory_movements "
                "WHERE offering_id = :o ORDER BY created_at", o=curry["id"])
    assert [m[0] for m in moves] == ["conversion_in", "wastage"]
    assert sum(m[2] for m in moves) == 67_500


# ---------------------------------------------------------------- pharmacy: FEFO, expiry
@DB
def test_pharmacy_sells_earliest_expiry_first_and_is_warned_before_expiry(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = billing_shop(client, owner)
    bid, loc = shop["bid"], shop["loc"]
    base = f"/v1/platform/businesses/{bid}"
    para = _item(owner, bid, title="Paracetamol 500 strip", price_amount=30, hsn_sac="3004", tax_rate=12)
    assert client.patch(f"{base}/stock/items/{para['id']}", json={"batch_tracked": True},
                        headers=owner).status_code == 200
    # Opening stock cannot skip the batch record.
    assert client.post(f"{base}/inventory/opening-stock", json={
        "offering_id": para["id"], "location_id": loc, "quantity": 5}, headers=owner).status_code == 422

    no_batch = client.post(f"{base}/stock/receipts", json={"location_id": loc, "offering_id": para["id"],
                                                           "quantity": 10}, headers=owner)
    assert no_batch.status_code == 422
    expired = client.post(f"{base}/stock/receipts", json={
        "location_id": loc, "offering_id": para["id"], "quantity": 10, "batch_code": "OLD",
        "expires_on": (TODAY - timedelta(days=1)).isoformat()}, headers=owner)
    assert expired.status_code == 422
    late = client.post(f"{base}/stock/receipts", json={
        "location_id": loc, "offering_id": para["id"], "quantity": 100, "batch_code": "B-LATE",
        "expires_on": (TODAY + timedelta(days=200)).isoformat(), "total_cost_paise": 200_000}, headers=owner)
    soon = client.post(f"{base}/stock/receipts", json={
        "location_id": loc, "offering_id": para["id"], "quantity": 50, "batch_code": "B-SOON",
        "expires_on": (TODAY + timedelta(days=40)).isoformat(), "total_cost_paise": 100_000}, headers=owner)
    assert late.status_code == 200 and soon.status_code == 200, (late.text, soon.text)

    drain_events(bid)
    steps = sql("SELECT step_key FROM automation_steps WHERE business_id = :b AND ladder_key = 'inventory.expiry' "
                "AND entity_id = :e ORDER BY due_at", b=bid, e=soon.json()["data"]["batch_id"])
    assert [s[0] for s in steps] == ["minus_30", "minus_7", "expiry"]

    bill = client.post(f"{base}/invoices", json={"lines": [{"offering_id": para["id"], "quantity": 60}]},
                       headers=owner)
    assert bill.status_code == 200, bill.text
    batches = dict(sql("SELECT batch_code, quantity_on_hand FROM inventory_batches WHERE offering_id = :o",
                       o=para["id"]))
    assert batches == {"B-SOON": 0, "B-LATE": 90}  # the 40-day batch went first
    line = bill.json()["data"]["lines"][0]
    alloc = sql("SELECT batch_allocations FROM invoicing_document_lines WHERE id = :l", l=line["id"])[0][0]
    assert [a["quantity"] for a in alloc] == [50, 10]
    assert _record(para["id"]) == (90, 180_000)  # 60 of 150 left at the average: 300000 * 90/150

    cancelled = client.post(f"{base}/invoices/{bill.json()['data']['id']}/cancel", json={"reason": "Wrong bill"},
                            headers=owner)
    assert cancelled.status_code == 200, cancelled.text
    batches = dict(sql("SELECT batch_code, quantity_on_hand FROM inventory_batches WHERE offering_id = :o",
                       o=para["id"]))
    assert batches == {"B-SOON": 50, "B-LATE": 100}  # back to the same batches, at the value it left with
    assert _record(para["id"]) == (150, 300_000)

    exp = client.get(f"{base}/stock/expiring?days=45", headers=owner).json()["data"]
    assert [b["batch_code"] for b in exp] == ["B-SOON"] and exp[0]["days_left"] == 40
    off = client.post(f"{base}/stock/batches/{soon.json()['data']['batch_id']}/write-off",
                      json={"note": "Returned to distributor"}, headers=owner)
    assert off.status_code == 200 and off.json()["data"]["status"] == "written_off"
    assert _record(para["id"])[0] == 100


# ---------------------------------------------------------------- electronics: serials, warranty
@DB
def test_phone_is_sold_by_serial_and_its_warranty_can_be_looked_up(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = billing_shop(client, owner)
    bid, loc = shop["bid"], shop["loc"]
    base = f"/v1/platform/businesses/{bid}"
    phone = _item(owner, bid, title="Moto G phone", price_amount=15_000, hsn_sac="8517", tax_rate=18)
    assert client.patch(f"{base}/stock/items/{phone['id']}", json={"serial_tracked": True, "warranty_months": 12},
                        headers=owner).status_code == 200
    short = client.post(f"{base}/stock/receipts", json={"location_id": loc, "offering_id": phone["id"],
                                                        "quantity": 2, "serials": ["IMEI0001"]}, headers=owner)
    assert short.status_code == 422  # one serial per unit
    ok = client.post(f"{base}/stock/receipts", json={"location_id": loc, "offering_id": phone["id"],
                                                     "quantity": 2, "serials": "imei0001\nIMEI0002"}, headers=owner)
    assert ok.status_code == 200, ok.text
    again = client.post(f"{base}/stock/receipts", json={"location_id": loc, "offering_id": phone["id"],
                                                        "quantity": 1, "serials": ["IMEI0002"]}, headers=owner)
    assert again.status_code == 409  # a serial is on record once

    missing = client.post(f"{base}/invoices", json={"lines": [{"offering_id": phone["id"], "quantity": 1}]},
                          headers=owner)
    assert missing.status_code == 422 and "serial" in missing.text
    unknown = client.post(f"{base}/invoices", json={"lines": [
        {"offering_id": phone["id"], "quantity": 1, "serials": ["NOPE999"]}]}, headers=owner)
    assert unknown.status_code == 422
    sold = client.post(f"{base}/invoices", json={"lines": [
        {"offering_id": phone["id"], "quantity": 1, "serials": ["IMEI0001"]}]}, headers=owner)
    assert sold.status_code == 200, sold.text
    looked = client.get(f"{base}/stock/serials/imei0001", headers=owner).json()["data"]
    assert looked["status"] == "sold" and looked["in_warranty"] is True
    from platform_core.stock.ledger import add_months

    assert looked["warranty_until"] == add_months(datetime.now(IST).date(), 12).isoformat()
    assert looked["bill_number"] == sold.json()["data"]["number"]

    line = sold.json()["data"]["lines"][0]["id"]
    back = client.post(f"{base}/invoices/{sold.json()['data']['id']}/notes", json={
        "kind": "credit_note", "reason": "return", "restock": True,
        "lines": [{"original_line_id": line, "quantity": 1}]}, headers=owner)
    assert back.status_code == 200, back.text
    assert client.get(f"{base}/stock/serials/IMEI0001", headers=owner).json()["data"]["status"] == "in_stock"
    assert _record(phone["id"])[0] == 2


# ---------------------------------------------------------------- counts need approval
@DB
def test_count_changes_stock_only_when_approved_and_the_counter_counts_blind(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("offerings-catalog", "inventory", "orders", "payments"))
    base = f"/v1/platform/businesses/{bid}"
    loc = primary_location(client, owner, bid)
    rice = _item(owner, bid, title="Sona masoori 1 kg", price_amount=70)
    assert client.post(f"{base}/inventory/opening-stock", json={
        "offering_id": rice["id"], "location_id": loc, "quantity": 20, "total_cost_paise": 120_000},
        headers=owner).status_code == 200

    person, keeper = new_identity(monkeypatch)
    inv = client.post(f"/v1/b/{bid}/team/invitations", json={"identity_id": str(person), "role": "member"},
                      headers=owner)
    mid = inv.json()["data"]["id"]
    assert client.post(f"/v1/b/{bid}/team/members/{mid}/activate", headers=owner).status_code == 200
    assert client.put(f"{base}/members/{mid}/role", json={"role": "store_keeper", "location_ids": [loc]},
                      headers=owner).status_code == 200

    started = client.post(f"{base}/stock/counts", json={"location_id": loc, "label": "Rice shelf"}, headers=keeper)
    assert started.status_code == 200, started.text
    count_id = started.json()["data"]["id"]
    assert client.post(f"{base}/stock/counts", json={"location_id": loc}, headers=owner).status_code == 409
    record_id = sql("SELECT id FROM inventory_records WHERE offering_id = :o", o=rice["id"])[0][0]
    blind = client.get(f"{base}/stock/counts/{count_id}", headers=keeper).json()["data"]
    assert "expected_quantity" not in blind["lines"][0]  # the counter does not see the answer
    assert client.put(f"{base}/stock/counts/{count_id}/lines", json={"lines": [
        {"inventory_record_id": str(record_id), "counted_quantity": 18}]}, headers=keeper).status_code == 200
    assert client.post(f"{base}/stock/counts/{count_id}/submit", headers=keeper).status_code == 200
    # Nothing moved yet: a count is a claim until someone approves it.
    assert _record(rice["id"]) == (20, 120_000)
    denied = client.post(f"{base}/stock/counts/{count_id}/decision", json={"approve": True}, headers=keeper)
    assert denied.status_code == 403
    # Store keepers never see what stock is worth.
    keeper_view = client.get(f"{base}/stock", headers=keeper).json()["data"]
    assert "value_paise" not in keeper_view["items"][0] and "value_paise" not in keeper_view["totals"]

    # A sale during the count is not undone by approving it.
    assert client.post(f"{base}/inventory/adjust", json={"offering_id": rice["id"], "location_id": loc,
                                                        "quantity_delta": -1, "reason": "Sold at counter"},
                       headers=owner).status_code == 200
    seen = client.get(f"{base}/stock/counts/{count_id}", headers=owner).json()["data"]
    assert seen["lines"][0]["variance"] == -2 and seen["variances"] == 1
    approved = client.post(f"{base}/stock/counts/{count_id}/decision", json={"approve": True}, headers=owner)
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["variances_applied"] == 1
    qty, value = _record(rice["id"])
    assert qty == 17 and value == 102_000  # 20 → 19 (sale) → 17 (variance), at ₹60 each
    assert sql("SELECT count(*) FROM inventory_movements WHERE offering_id = :o AND movement_type = 'count_variance'",
               o=rice["id"]) == [(1,)]


# ---------------------------------------------------------------- isolation
@DB
@pytest.mark.parametrize("table", ["inventory_batches", "inventory_serials", "inventory_yields",
                                   "inventory_conversions", "inventory_counts", "inventory_count_lines"])
def test_stock_depth_tables_are_tenant_isolated(table: str) -> None:
    # Dependencies are made once per business as the owner; the call made as
    # the API role for the other business inserts only the row under test, so
    # the refusal comes from this table's own policy.
    deps: dict[uuid.UUID, dict[str, Any]] = {}

    async def insert(session: Any, business_id: uuid.UUID) -> None:
        if business_id not in deps:
            owner = (await session.execute(text("SELECT primary_owner_identity_id FROM businesses WHERE id = :b"),
                                           {"b": business_id})).scalar()
            d: dict[str, Any] = {"loc": uuid.uuid4(), "off": uuid.uuid4(), "rec": uuid.uuid4(), "owner": owner,
                                 "outs": [uuid.uuid4() for _ in range(3)], "counts": [uuid.uuid4() for _ in range(3)],
                                 "calls": 0}
            await session.execute(text("INSERT INTO business_locations (id, business_id, name) VALUES (:l, :b, 'L')"),
                                  {"b": business_id, "l": d["loc"]})
            for oid, title in ((d["off"], "Item"), *((o, "Cut") for o in d["outs"])):
                await session.execute(text(
                    "INSERT INTO offerings_catalog_offerings (id, business_id, title, track_inventory) "
                    "VALUES (:o, :b, :t, true)"), {"b": business_id, "o": oid, "t": title})
            await session.execute(text(
                "INSERT INTO inventory_records (id, business_id, offering_id, location_id) VALUES (:r, :b, :o, :l)"),
                {"b": business_id, "r": d["rec"], "o": d["off"], "l": d["loc"]})
            for cid in d["counts"]:
                await session.execute(text(
                    "INSERT INTO inventory_counts (id, business_id, location_id, label, started_by) "
                    "VALUES (:c, :b, :l, 'Count', :u)"), {"b": business_id, "c": cid, "l": d["loc"], "u": owner})
            deps[business_id] = d
        d = deps[business_id]
        n = d["calls"]
        d["calls"] = n + 1
        p = {"b": business_id, "l": d["loc"], "o": d["off"], "t": d["outs"][n], "r": d["rec"],
             "c": d["counts"][n], "u": d["owner"], "s": f"SER{uuid.uuid4().hex[:8]}"}
        statements = {
            "inventory_batches": "INSERT INTO inventory_batches (business_id, location_id, inventory_record_id, "
                                 "offering_id, batch_code, quantity_received, quantity_on_hand) "
                                 "VALUES (:b, :l, :r, :o, 'B1', 5, 5)",
            "inventory_serials": "INSERT INTO inventory_serials (business_id, location_id, inventory_record_id, "
                                 "offering_id, serial) VALUES (:b, :l, :r, :o, :s)",
            "inventory_yields": "INSERT INTO inventory_yields (business_id, source_offering_id, output_offering_id, "
                                "yield_bp) VALUES (:b, :o, :t, 8000)",
            "inventory_conversions": "INSERT INTO inventory_conversions (business_id, location_id, "
                                     "source_offering_id, source_quantity, outputs, trim_quantity) "
                                     "VALUES (:b, :l, :o, 10, '[]'::jsonb, 0)",
            "inventory_counts": "INSERT INTO inventory_counts (business_id, location_id, label, started_by) "
                                "VALUES (:b, :l, 'Another count', :u)",
            "inventory_count_lines": "INSERT INTO inventory_count_lines (business_id, count_id, inventory_record_id, "
                                     "expected_quantity) VALUES (:b, :c, :r, 3)",
        }
        await session.execute(text(statements[table]), p)

    asyncio.run(assert_tenant_isolated(table, insert))


@DB
def test_stock_history_cannot_be_deleted_by_the_api_role() -> None:
    rows = sql("SELECT table_name FROM information_schema.role_table_grants WHERE grantee = 'platform_api' "
               "AND privilege_type = 'DELETE' AND table_name IN ('inventory_batches', 'inventory_serials', "
               "'inventory_conversions', 'inventory_counts', 'inventory_count_lines')")
    assert rows == []


def test_expiry_anchor_is_nine_in_the_morning_india_time() -> None:
    from platform_core.stock.service import StockService

    anchor = StockService.expiry_anchor(date(2026, 12, 1))
    assert anchor == datetime(2026, 12, 1, 3, 30, tzinfo=timezone.utc)
