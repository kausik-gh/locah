"""Counter billing (Capability Universe §14.1–§14.3, §14.5, §14.6; §26.3 P1-05).

The packet's done-when is here by name: offline bills from two registers sync
with no duplicate or missing numbers. Around it: shifts and cash closing,
tenders and change, the discount cap and a manager's PIN, returns and voids,
UPI taken without confirmation, prices that changed after the counter cached
them, stock that was wrong on the books, scanning, in-store codes and labels.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D
from typing import Any

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from platform_core.catalog.offering_kinds import gtin_ok
from platform_core.exceptions import ValidationError
from platform_core.pos.barcodes import clean_weighed_format, decode_weighed, in_store_code
from platform_core.services.number_series import financial_year
from platform_testing.phase_b import (
    assert_tenant_isolated,
    billing_shop,
    db_url,
    new_identity,
    sql,
)

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)
FY = financial_year(date.today())


# ---------------------------------------------------------------- scanning (no DB)
def test_in_store_codes_are_valid_restricted_ean13() -> None:
    codes = [in_store_code(n) for n in (1, 42, 9_999_999_999)]
    assert all(c.startswith("20") and len(c) == 13 and gtin_ok(c) for c in codes)
    assert len(set(codes)) == 3


def test_weighed_label_format_is_the_owners_and_decodes_weight_or_price() -> None:
    with pytest.raises(ValidationError):
        clean_weighed_format({"prefix": "2", "item_digits": 5, "value": "weight", "value_digits": 5})  # clashes with 20…
    with pytest.raises(ValidationError):
        clean_weighed_format({"prefix": "21", "item_digits": 5, "value": "weight", "value_digits": 6})  # 14 digits
    fmt = clean_weighed_format({"prefix": "21", "item_digits": 5, "value": "weight", "value_digits": 5,
                                "value_decimals": 3})
    body = "21" + "00123" + "01250"
    code = body + str((10 - sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body))) % 10) % 10)
    scan = decode_weighed(code, fmt)
    assert scan is not None and scan.item_code == "00123" and scan.value == D("1.250") and scan.kind == "weight"
    assert decode_weighed("8901234567890", fmt) is None
    with pytest.raises(ValidationError):
        decode_weighed(code[:-1] + str((int(code[-1]) + 1) % 10), fmt)
    price = clean_weighed_format({"prefix": "22", "item_digits": 4, "value": "price", "value_digits": 6,
                                  "value_decimals": 2})
    body2 = "22" + "0042" + "018550"
    code2 = body2 + str((10 - sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body2))) % 10) % 10)
    scan2 = decode_weighed(code2, price)
    assert scan2 is not None and scan2.value == D("185.50")


# ---------------------------------------------------------------- helpers
def _counter(owner: dict[str, str], **kw: Any) -> dict[str, Any]:
    shop: dict[str, Any] = dict(billing_shop(client, owner, modules=("pos",), **kw))
    base = shop["base"]
    item = client.post(f"{base}/products", json={
        "status": "active", "offering_type": "product", "title": "Toor dal 1 kg", "price_amount": 150,
        "hsn_sac": "0713", "tax_rate": 5, "track_inventory": True, "barcode": "8901234567890"}, headers=owner)
    assert item.status_code == 200, item.text
    shop["item"] = item.json()["data"]
    client.post(f"{base}/inventory/opening-stock", json={"offering_id": shop["item"]["id"], "location_id": shop["loc"],
                                                         "quantity": 100}, headers=owner)
    return shop


def _open(owner: dict[str, str], shop: dict[str, Any], register_id: str | None = None, device: str = "tab-1",
          cash: float = 1000) -> dict[str, Any]:
    r = client.post(f"{shop['base']}/pos/shifts", json={"register_id": register_id or shop["register"]["id"],
                                                         "device_id": device, "opening_cash": cash}, headers=owner)
    assert r.status_code == 200, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


def _sale(shop: dict[str, Any], shift: dict[str, Any], *, qty: float = 1, price: float | None = None,
          tenders: list[dict[str, Any]] | None = None, number: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    return {"client_mutation_id": str(uuid.uuid4()), "kind": "pos.sale", "payload": {
        "shift_id": shift["shift"]["id"], "client_bill_id": str(uuid.uuid4()),
        "lines": [{"offering_id": shop["item"]["id"], "quantity": qty,
                   "unit_price": price if price is not None else shop["item"]["price_amount"]}],
        "tenders": tenders or [{"method": "cash", "amount": 1000}], "number": number,
        "catalogue_version": datetime.now(timezone.utc).isoformat(), **extra}}


def _sync(owner: dict[str, str], shop: dict[str, Any], mutations: list[dict[str, Any]], device: str = "tab-1") -> list[dict[str, Any]]:
    r = client.post(f"{shop['base']}/sync", json={"device_id": device, "mutations": mutations}, headers=owner)
    assert r.status_code == 200, r.text
    return list(r.json()["data"]["results"])


# ---------------------------------------------------------------- the counter
@DB
def test_shift_sale_change_stock_and_cash_closing(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _counter(owner)
    opened = _open(owner, shop, cash=500)
    block = opened["block"]
    assert (block["start"], block["end"], block["next"]) == (1, 50, 1)
    [res] = _sync(owner, shop, [_sale(shop, opened, qty=2, tenders=[{"method": "cash", "amount": 500}],
                                     number={"block_id": block["id"], "value": 1})])
    assert res["status"] == "applied", res
    assert res["number"] == f"CHN1/{FY}/00001" and res["amount_due"] == 315.0 and res["change"] == 185.0
    stock = sql("select quantity_on_hand from inventory_records where offering_id = :o", o=shop["item"]["id"])
    assert stock == [(98,)]
    bill = client.get(f"{shop['base']}/invoices/{res['document_id']}", headers=owner).json()["data"]
    assert bill["source"] == "pos" and bill["payment_status"] == "paid" and bill["cgst_total"] == 7.5

    shift_id = opened["shift"]["id"]
    petty = _sync(owner, shop, [{"client_mutation_id": str(uuid.uuid4()), "kind": "pos.cash",
                                 "payload": {"shift_id": shift_id, "kind": "petty_expense", "amount": 40,
                                             "reason": "Tea for staff"}}])
    assert petty[0]["status"] == "applied"
    summary = client.get(f"{shop['base']}/pos/shifts/{shift_id}", headers=owner).json()["data"]["summary"]
    # opening + cash sales − cash refunds − petty expenses = expected (§14.5)
    assert summary["cash_sales"] == 315.0 and summary["expected_cash"] == 500 + 315 - 40
    closed = client.post(f"{shop['base']}/pos/shifts/{shift_id}/close", json={"counted_cash": 770}, headers=owner)
    assert closed.status_code == 200, closed.text
    assert closed.json()["data"]["variance"] == -5.0
    # The unused end of the block went back: the series stays gapless.
    nxt = sql("select next_value from number_series where business_id = :b and series_key = :k and period = :p",
              b=shop["bid"], k=f"inv:{shop['register']['id']}", p=FY)
    assert nxt == [(2,)]
    reopened = _open(owner, shop)
    assert reopened["block"]["start"] == 2 and reopened["block"]["next"] == 2


@DB
def test_two_registers_offline_sync_with_no_duplicate_or_missing_numbers(monkeypatch: Any) -> None:
    """§14.6 / PKT-05: bills rung up offline on two registers, synced late and
    out of order, with a replayed batch, number each register 1..n exactly."""
    _, owner = new_identity(monkeypatch)
    shop = _counter(owner)
    second = client.post(f"{shop['base']}/invoicing/registers", json={
        "location_id": shop["loc"], "registration_id": shop["registration"]["id"], "code": "CHN2"}, headers=owner)
    assert second.status_code == 200
    a = _open(owner, shop, device="tab-a")
    b = _open(owner, shop, register_id=second.json()["data"]["id"], device="tab-b")
    queues: dict[str, list[dict[str, Any]]] = {"tab-a": [], "tab-b": []}
    for device, opened in (("tab-a", a), ("tab-b", b)):
        blk = opened["block"]
        for i in range(4):  # offline: numbered from the block on the device
            queues[device].append(_sale(shop, opened, number={"block_id": blk["id"], "value": blk["next"] + i},
                                        sold_offline=True))
    # Network returns: tab-b syncs first, then tab-a in two batches, then tab-b replays everything.
    assert all(r["status"] == "applied" for r in _sync(owner, shop, queues["tab-b"], "tab-b"))
    assert all(r["status"] == "applied" for r in _sync(owner, shop, queues["tab-a"][2:], "tab-a"))
    assert all(r["status"] == "applied" for r in _sync(owner, shop, queues["tab-a"][:2], "tab-a"))
    replay = _sync(owner, shop, queues["tab-b"], "tab-b")
    assert all(r["replayed"] for r in replay)
    rows = sql("select number from invoicing_documents where business_id = :b and source = 'pos' order by number",
               b=shop["bid"])
    numbers = [r[0] for r in rows]
    assert numbers == [f"CHN1/{FY}/0000{i}" for i in range(1, 5)] + [f"CHN2/{FY}/0000{i}" for i in range(1, 5)]
    assert len(numbers) == len(set(numbers))
    stock = sql("select quantity_on_hand from inventory_records where offering_id = :o", o=shop["item"]["id"])
    assert stock == [(92,)], "each sale moved stock once, replay moved none"
    report = client.get(f"{shop['base']}/invoicing/reports/documents", headers=owner).json()["data"]
    for row in report["rows"]:
        assert row["total"] == 4


@DB
def test_a_used_number_is_refused_and_prices_are_rechecked(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _counter(owner)
    opened = _open(owner, shop)
    blk = opened["block"]
    first = _sync(owner, shop, [_sale(shop, opened, number={"block_id": blk["id"], "value": 1})])
    assert first[0]["status"] == "applied"
    dup = _sync(owner, shop, [_sale(shop, opened, number={"block_id": blk["id"], "value": 1})])
    assert dup[0]["status"] == "rejected" and "already used" in dup[0]["reason"]
    dearer = _sync(owner, shop, [_sale(shop, opened, price=175)])
    assert dearer[0]["status"] == "rejected" and "above the catalogue price" in dearer[0]["reason"]
    # The owner changed the price after the counter cached it: sold at the old price, noted.
    stale = _sale(shop, opened, price=150)
    stale["payload"]["catalogue_version"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    client.patch(f"{shop['base']}/products/{shop['item']['id']}", json={"price_amount": 160}, headers=owner)
    ok = _sync(owner, shop, [stale])
    assert ok[0]["status"] == "applied" and "price changed" in ok[0]["notes"][0]


@DB
def test_discount_cap_and_a_managers_pin(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _counter(owner)
    client.put(f"{shop['base']}/pos/settings", json={"discount_caps": {"cashier": 5, "manager": 20},
                                                     "return_window_days": 7}, headers=owner)
    cashier_id, cashier = new_identity(monkeypatch)
    manager_id, manager = new_identity(monkeypatch)
    for pid, role in ((cashier_id, "cashier"), (manager_id, "manager")):
        inv = client.post(f"/v1/b/{shop['bid']}/team/invitations", json={"identity_id": str(pid), "role": "member"},
                          headers=owner)
        mid = inv.json()["data"]["id"]
        client.post(f"/v1/b/{shop['bid']}/team/members/{mid}/activate", headers=owner)
        given = client.put(f"{shop['base']}/members/{mid}/role", json={"role": role, "location_ids": [shop["loc"]]},
                           headers=owner)
        assert given.status_code == 200, given.text
    assert client.put(f"{shop['base']}/pos/settings", json={}, headers=cashier).status_code == 403
    opened = _open(cashier, shop, device="till")
    within = _sale(shop, opened, qty=2)
    within["payload"]["bill_discount"] = 15  # 5% of 300
    assert _sync(cashier, shop, [within], "till")[0]["status"] == "applied"
    above = _sale(shop, opened, qty=2)
    above["payload"]["bill_discount"] = 30  # 10%
    refused = _sync(cashier, shop, [above], "till")
    assert refused[0]["status"] == "rejected" and "manager's PIN" in refused[0]["reason"]

    assert client.put(f"{shop['base']}/pos/pin", json={"pin": "1111"}, headers=manager).status_code == 422
    assert client.put(f"{shop['base']}/pos/pin", json={"pin": "4826"}, headers=manager).status_code == 200
    assert client.put(f"{shop['base']}/pos/pin", json={"pin": "4826"}, headers=cashier).status_code == 403
    setup = client.get(f"{shop['base']}/pos/setup", headers=cashier).json()["data"]
    assert setup["discount_cap"] == 5 and [a["identity_id"] for a in setup["approvers"]] == [str(manager_id)]
    wrong = client.post(f"{shop['base']}/pos/approve", json={"approver_id": str(manager_id), "pin": "0000",
                                                             "action": "discount", "max_discount_pct": 10}, headers=cashier)
    assert wrong.status_code == 422
    good = client.post(f"{shop['base']}/pos/approve", json={"approver_id": str(manager_id), "pin": "4826",
                                                            "action": "discount", "max_discount_pct": 10}, headers=cashier)
    assert good.status_code == 200, good.text
    above["client_mutation_id"] = str(uuid.uuid4())
    above["payload"]["approval"] = good.json()["data"]["token"]
    approved = _sync(cashier, shop, [above], "till")
    assert approved[0]["status"] == "applied" and "approved" in approved[0]["notes"][-1]
    forged = _sale(shop, opened, qty=2)
    forged["payload"]["bill_discount"] = 30
    forged["payload"]["approval"] = good.json()["data"]["token"][:-3] + "abc"
    assert _sync(cashier, shop, [forged], "till")[0]["status"] == "rejected"
    for _ in range(5):
        client.post(f"{shop['base']}/pos/approve", json={"approver_id": str(manager_id), "pin": "9999",
                                                         "action": "void"}, headers=cashier)
    locked = client.post(f"{shop['base']}/pos/approve", json={"approver_id": str(manager_id), "pin": "4826",
                                                              "action": "void"}, headers=cashier)
    assert locked.status_code == 409, "five wrong PINs lock the approver for a while"


@DB
def test_returns_voids_and_upi_to_verify(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _counter(owner)
    opened = _open(owner, shop, cash=200)
    shift_id = opened["shift"]["id"]
    sale = _sync(owner, shop, [_sale(shop, opened, qty=3, tenders=[{"method": "cash", "amount": 472.5}])])[0]
    bill = client.get(f"{shop['base']}/invoices/{sale['document_id']}", headers=owner).json()["data"]
    back = _sync(owner, shop, [{"client_mutation_id": str(uuid.uuid4()), "kind": "pos.return", "payload": {
        "shift_id": shift_id, "number": sale["number"], "refund_method": "cash", "restock": True,
        "lines": [{"original_line_id": bill["lines"][0]["id"], "quantity": 1}]}}])[0]
    assert back["status"] == "applied" and back["number"] == f"CN/{FY}/00001" and back["refund"] == 157.5
    assert sql("select quantity_on_hand from inventory_records where offering_id = :o", o=shop["item"]["id"]) == [(98,)]

    upi = _sync(owner, shop, [_sale(shop, opened, tenders=[{"method": "upi", "amount": 157.5, "to_verify": True}])])[0]
    card = _sync(owner, shop, [_sale(shop, opened, tenders=[{"method": "card", "amount": 157.5, "reference": "4411"}])])[0]
    void = _sync(owner, shop, [{"client_mutation_id": str(uuid.uuid4()), "kind": "pos.void",
                                "payload": {"document_id": card["document_id"], "reason": "Customer changed mind"}}])[0]
    assert void["status"] == "applied"
    summary = client.get(f"{shop['base']}/pos/shifts/{shift_id}", headers=owner).json()["data"]["summary"]
    assert summary["expected_cash"] == 200 + 472.5 - 157.5 and summary["upi_to_verify"] == 157.5
    assert summary["card"] == 0 and summary["voided"] == 1 and summary["returns"] == 1

    pending = client.get(f"{shop['base']}/pos/upi-to-verify", headers=owner).json()["data"]
    assert [p["document_id"] for p in pending] == [upi["document_id"]]
    client.post(f"{shop['base']}/pos/payments/{pending[0]['id']}/verify", json={"received": False}, headers=owner)
    after = client.get(f"{shop['base']}/invoices/{upi['document_id']}", headers=owner).json()["data"]
    assert after["payment_status"] == "unpaid" and after["outstanding"] == 157.5

    client.post(f"{shop['base']}/pos/shifts/{shift_id}/close", json={"counted_cash": 515}, headers=owner)
    later = _open(owner, shop)
    old_void = _sync(owner, shop, [{"client_mutation_id": str(uuid.uuid4()), "kind": "pos.void",
                                    "payload": {"document_id": sale["document_id"], "reason": "x"}}])[0]
    assert old_void["status"] == "rejected" and "manager's PIN" in old_void["reason"]
    assert later["shift"]["status"] == "open"


@DB
def test_a_wrong_stock_count_never_blocks_the_counter(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _counter(owner)
    sql("update inventory_records set quantity_on_hand = 1 where offering_id = :o", o=shop["item"]["id"])
    opened = _open(owner, shop)
    res = _sync(owner, shop, [_sale(shop, opened, qty=3)])[0]
    assert res["status"] == "applied" and res["stock_short"][0]["sold"] == 3 and res["stock_short"][0]["on_record"] == 1
    assert sql("select quantity_on_hand from inventory_records where offering_id = :o", o=shop["item"]["id"]) == [(0,)]


@DB
def test_closing_waits_for_the_devices_bills(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _counter(owner)
    opened = _open(owner, shop)
    _sync(owner, shop, [_sale(shop, opened, number={"block_id": opened["block"]["id"], "value": 1})])
    early = client.post(f"{shop['base']}/pos/shifts/{opened['shift']['id']}/close",
                        json={"counted_cash": 1157.5, "last_used": 3}, headers=owner)
    assert early.status_code == 409 and "Sync them" in early.text


@DB
def test_catalogue_scan_codes_labels_and_upi_qr(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _counter(owner)
    base = shop["base"]
    made = client.post(f"{base}/products", json={"status": "active", "offering_type": "weighed_product",
                                                 "title": "Cashews", "price_amount": 900, "sku": "00123",
                                                 "attributes": {"price_per": "kg"},
                                                 "sell_units": [{"label": "250 g", "qty": 250}]}, headers=owner)
    assert made.status_code == 200, made.text
    loose = made.json()["data"]
    cat = client.get(f"{base}/pos/catalogue?location_id={shop['loc']}", headers=owner).json()["data"]
    titles = {i["title"]: i for i in cat["items"]}
    assert cat["version"] and titles["Toor dal 1 kg"]["rate"] == 5.0 and titles["Toor dal 1 kg"]["available"] == 100
    assert titles["Cashews"]["rate"] is None, "no rate is invented"
    code = client.post(f"{base}/pos/in-store-code/{loose['id']}", headers=owner).json()["data"]["barcode"]
    assert code.startswith("20") and gtin_ok(code)
    assert client.post(f"{base}/pos/in-store-code/{loose['id']}", headers=owner).status_code == 409
    assert client.get(f"{base}/pos/scan?code={code}", headers=owner).json()["data"]["title"] == "Cashews"
    assert client.get(f"{base}/pos/scan?code=8901234567890", headers=owner).json()["data"]["title"] == "Toor dal 1 kg"
    client.put(f"{base}/pos/settings", json={"weighed_label": {"prefix": "21", "item_digits": 5, "value": "weight",
                                                               "value_digits": 5, "value_decimals": 3},
                                             "upi_vpa": "srisweets@okbank"}, headers=owner)
    body = "21" + "00123" + "00500"
    label = body + str((10 - sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body))) % 10) % 10)
    weighed = client.get(f"{base}/pos/scan?code={label}", headers=owner).json()["data"]
    assert weighed["title"] == "Cashews" and weighed["value"] == 0.5
    pdf = client.get(f"{base}/pos/labels?ids={loose['id']}&copies=3", headers=owner)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.get(f"{base}/pos/labels?ids={loose['id']}&layout=label_50x25", headers=owner).status_code == 200
    qr = client.get(f"{base}/pos/upi-qr?amount=450.5&note=Bill", headers=owner)
    assert qr.status_code == 200 and qr.headers["content-type"].startswith("image/svg+xml") and b"<svg" in qr.content


@DB
def test_a_cashier_limited_to_one_location_sees_only_its_shifts(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _counter(owner)
    loc_b = client.post(f"{shop['base']}/locations", json={"name": "Branch B"}, headers=owner).json()["data"]["id"]
    reg_b = client.post(f"{shop['base']}/invoicing/registers", json={
        "location_id": loc_b, "registration_id": shop["registration"]["id"], "code": "BRB1"}, headers=owner).json()["data"]
    other = _open(owner, shop, register_id=reg_b["id"], device="b-till")
    cashier_id, cashier = new_identity(monkeypatch)
    inv = client.post(f"/v1/b/{shop['bid']}/team/invitations", json={"identity_id": str(cashier_id), "role": "member"},
                      headers=owner)
    mid = inv.json()["data"]["id"]
    client.post(f"/v1/b/{shop['bid']}/team/members/{mid}/activate", headers=owner)
    client.put(f"{shop['base']}/members/{mid}/role", json={"role": "cashier", "location_ids": [shop["loc"]]}, headers=owner)
    setup = client.get(f"{shop['base']}/pos/setup", headers=cashier).json()["data"]
    assert [r["code"] for r in setup["registers"]] == ["CHN1"]
    home = client.get(f"{shop['base']}/home", headers=cashier).json()["data"]
    assert home["role"]["question"] == "Open shift, bills, drawer balance"
    counter = next(b for b in home["bands"] if b["key"] == "counter")
    assert counter["stats"][0]["label"] == "No shift open", "Branch B's shift is not the cashier's to see"
    assert client.get(f"{shop['base']}/pos/shifts/{other['shift']['id']}", headers=cashier).status_code == 404
    refused = client.post(f"{shop['base']}/pos/shifts", json={"register_id": reg_b["id"], "device_id": "x-till",
                                                              "opening_cash": 0}, headers=cashier)
    assert refused.status_code == 404


TABLES = {
    "pos_settings": "insert into pos_settings (business_id) values (:b)",
}


@DB
@pytest.mark.asyncio
async def test_pos_tables_are_tenant_isolated() -> None:
    async def settings(session: AsyncSession, business_id: uuid.UUID) -> None:
        await session.execute(text(TABLES["pos_settings"]), {"b": business_id})

    await assert_tenant_isolated("pos_settings", settings)

    async def shift(session: AsyncSession, business_id: uuid.UUID) -> None:
        loc = (await session.execute(text(
            "insert into business_locations (business_id, name) values (:b, 'L') returning id"), {"b": business_id})).scalar()
        reg = (await session.execute(text(
            "insert into invoicing_registrations (business_id, scheme, legal_name, state_code) "
            "values (:b, 'unregistered', 'x', '33') returning id"), {"b": business_id})).scalar()
        rgs = (await session.execute(text(
            "insert into invoicing_registers (business_id, location_id, registration_id, code, name) "
            "values (:b, :l, :r, 'A1', 'A') returning id"), {"b": business_id, "l": loc, "r": reg})).scalar()
        owner = (await session.execute(text("select id from platform_identities limit 1"))).scalar()
        sid = (await session.execute(text(
            "insert into pos_shifts (business_id, location_id, register_id, device_id, opened_by, opening_cash) "
            "values (:b, :l, :g, 'dev', :o, 0) returning id"), {"b": business_id, "l": loc, "g": rgs, "o": owner})).scalar()
        await session.execute(text(
            "insert into pos_cash_movements (business_id, shift_id, location_id, kind, amount, reason, created_by) "
            "values (:b, :s, :l, 'petty_expense', 1, 'x', :o)"), {"b": business_id, "s": sid, "l": loc, "o": owner})

    for table in ("pos_shifts", "pos_cash_movements"):
        await assert_tenant_isolated(table, shift)


@DB
@pytest.mark.asyncio
async def test_approval_pins_are_never_readable_outside_the_api() -> None:
    engine = create_async_engine(db_url(), poolclass=NullPool)
    try:
        async with AsyncSession(engine) as s:
            policies = (await s.execute(text(
                "select policyname from pg_policies where tablename = 'pos_approval_pins'"))).scalars().all()
            assert policies == ["pos_approval_pins_api_write"]
    finally:
        await engine.dispose()


def test_the_counter_engine_matches_the_server_engine_to_the_paisa(tmp_path: Any) -> None:
    """The counter prints totals offline with a TypeScript port of the billing
    engine; on sync the server issues the bill with the Python engine. Random
    bills must agree to the paisa in every context."""
    import json
    import random
    import shutil
    import subprocess
    from pathlib import Path

    from platform_core.invoicing import LineIn, TaxContext, compute

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    rng = random.Random(1406)
    cases: list[dict[str, Any]] = []
    for _ in range(300):
        lines = [{"quantity": rng.choice([1, 2, 3, 0.5, 1.25, 0.333, 12]),
                  "unitPrice": rng.choice([9.99, 105, 199.5, 420, 1234.56, 0.5, 2360]),
                  "rate": rng.choice([0, 3, 5, 12, 18, 28, 0.25, None]),
                  "discount": rng.choice([0, 0, 0, 1, 10.5])} for _ in range(rng.randint(1, 5))]
        ctx = {"scheme": rng.choice(["regular", "regular", "composition", "unregistered"]),
               "inclusive": rng.random() < 0.5, "intraState": rng.random() < 0.7, "roundOff": rng.random() < 0.5}
        cases.append({"lines": lines, "ctx": ctx, "billDiscount": rng.choice([0, 0, 5, 37.5])})
    engine = Path(__file__).resolve().parents[2] / "workspace" / "src" / "lib" / "pos" / "engine.ts"
    script = tmp_path / "run.mts"
    script.write_text(
        f"import {{ compute }} from {json.dumps(engine.as_uri())};\n"
        "import { readFileSync } from 'node:fs';\n"
        "const cases = JSON.parse(readFileSync(process.argv[2], 'utf8'));\n"
        "console.log(JSON.stringify(cases.map((c) => { const b = compute(c.lines, c.ctx, c.billDiscount);"
        " return [b.taxable, b.cgst, b.sgst, b.igst, b.roundOff, b.total]; })));\n")
    data = tmp_path / "cases.json"
    data.write_text(json.dumps(cases))
    out = subprocess.run([node, "--experimental-strip-types", "--no-warnings", str(script), str(data)],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    ts = json.loads(out.stdout)
    for case, got in zip(cases, ts):
        c = case["ctx"]
        bill = compute([LineIn(D(str(x["quantity"])), D(str(x["unitPrice"])),
                               D(str(x["rate"])) if x["rate"] is not None else None, D(str(x["discount"])))
                        for x in case["lines"]],
                       TaxContext(c["scheme"], c["inclusive"], c["intraState"], c["roundOff"]),
                       bill_discount=D(str(case["billDiscount"])))
        want = [int(v * 100) for v in (bill.taxable, bill.cgst, bill.sgst, bill.igst, bill.round_off, bill.amount_due)]
        assert got == want, (case, got, want)
