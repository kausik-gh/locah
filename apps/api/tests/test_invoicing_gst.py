"""GST invoicing (Capability Universe §14, §14.4, §14.6; §26.3 P1-04).

The §14.6 acceptance tests are here by name:
* same-state sale splits CGST / SGST; other-state sale uses IGST, from place
  of supply;
* a composition-scheme business never prints a tax line;
* round-off is shown as its own line and never changes the tax;
* bills from two registers never share or skip a number (the offline replay
  of those blocks is P1-05's POS test).
Plus the §14.4 rules: rates are dated data, never assumed; numbers are gapless
per GSTIN × FY × register; cancelled bills keep their number; notes reference
the original; the one billing engine prices the order and its bill alike.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import timedelta
from decimal import Decimal as D
from typing import Any

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from platform_core.invoicing import LineIn, TaxContext, compute, gstin_problem
from platform_core.invoicing.states import _check_char
from platform_core.services.invoicing import build_spec
from platform_core.services.number_series import financial_year
from platform_core.services.invoicing_setup import local_today
from platform_testing.phase_b import (
    assert_tenant_isolated,
    create_business,
    db_url,
    drain_events,
    new_identity,
    primary_location,
    sql,
)

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)
FY = financial_year(local_today())


def gstin(state: str, pan: str = "AAACL1234K") -> str:
    body = f"{state}{pan}1Z"
    return str(body + _check_char(body))


# ---------------------------------------------------------------- the engine (§14.6)
def test_same_state_splits_cgst_and_sgst_other_state_uses_igst() -> None:
    lines = [LineIn(D(2), D("100"), D(18)), LineIn(D(1), D("50"), D(5))]
    same = compute(lines, TaxContext("regular", inclusive=False, intra_state=True))
    assert (same.cgst, same.sgst, same.igst) == (D("19.25"), D("19.25"), D(0))
    other = compute(lines, TaxContext("regular", inclusive=False, intra_state=False))
    assert (other.cgst, other.sgst, other.igst) == (D(0), D(0), D("38.50"))
    assert same.taxable == other.taxable == D("250.00")


def test_composition_and_unregistered_charge_no_tax_whatever_the_rate() -> None:
    lines = [LineIn(D(3), D("99.50"), D(12))]
    for scheme in ("composition", "unregistered"):
        bill = compute(lines, TaxContext(scheme, inclusive=False, intra_state=True, round_off=True))
        assert bill.tax == 0 and bill.lines[0].rate is None
        assert bill.grand_total == D("299") and bill.round_off == D("0.50")


def test_round_off_is_its_own_figure_and_never_changes_the_tax() -> None:
    lines = [LineIn(D(1), D("99.99"), D(18)), LineIn(D(2), D("10.10"), D(5))]
    exact = compute(lines, TaxContext("regular", inclusive=False, intra_state=True, round_off=False))
    rounded = compute(lines, TaxContext("regular", inclusive=False, intra_state=True, round_off=True))
    assert rounded.tax == exact.tax and rounded.taxable == exact.taxable
    assert rounded.grand_total == rounded.grand_total.to_integral()
    assert rounded.grand_total - rounded.round_off == exact.grand_total
    assert exact.round_off == 0


def test_prices_including_gst_charge_exactly_the_shelf_price() -> None:
    bill = compute([LineIn(D(3), D("105"), D(5)), LineIn(D(1), D("99"), D(18))],
                   TaxContext("regular", inclusive=True, intra_state=True))
    assert bill.grand_total == D("414.00")
    assert bill.taxable + bill.tax == D("414.00")
    assert bill.lines[0].taxable == D("300.00") and bill.lines[0].cgst == D("7.50")


def test_discount_comes_off_before_tax_and_reverse_charge_is_shown_not_collected() -> None:
    bill = compute([LineIn(D(1), D("300"), D(18)), LineIn(D(1), D("100"), D(18))],
                   TaxContext("regular", False, False), bill_discount=40)
    assert bill.taxable == D("360.00") and bill.igst == D("64.80")
    assert [x.discount for x in bill.lines] == [D("30.00"), D("10.00")]
    rcm = compute([LineIn(D(1), D("1000"), D(18))], TaxContext("regular", False, True, reverse_charge=True))
    assert rcm.tax == D("180.00") and rcm.amount_due == D("1000.00") and rcm.grand_total == D("1180.00")


def test_a_missing_rate_is_reported_never_assumed() -> None:
    bill = compute([LineIn(D(1), D("100"), None)], TaxContext("regular", False, True))
    assert bill.missing_rates == [0] and bill.tax == 0


def test_gstin_check_character_and_state() -> None:
    good = gstin("33")
    assert gstin_problem(good) is None
    assert gstin_problem(good[:-1] + ("0" if good[-1] != "0" else "1")) == \
        "The last character does not match — check for a typing mistake"
    assert "state code" in (gstin_problem("99" + good[2:]) or "")
    assert gstin_problem("33ABC") == "A GSTIN has 15 characters"


def _spec_detail(kind: str, *, scheme: str, round_off: float = 0.0) -> dict[str, Any]:
    line: dict[str, Any] = {"title": "Rice 5 kg", "hsn_sac": "1006", "unit_label": "pcs", "quantity": 1.0, "unit_price": 450.0,
            "discount": 0.0, "taxable_value": 450.0, "tax_rate": None if scheme != "regular" else 5.0,
            "cgst": 0.0 if scheme != "regular" else 11.25, "sgst": 0.0 if scheme != "regular" else 11.25,
            "igst": 0.0, "line_total": 450.0 if scheme != "regular" else 472.5}
    return {"doc_kind": kind, "status": "issued", "number": f"CHN1/{FY}/00001", "issue_date": local_today().isoformat(),
            "seller": {"legal_name": "Sri Stores", "scheme": scheme, "gstin": gstin("33") if scheme != "unregistered"
                       else None, "state_code": "33", "declaration": "Composition taxable person, not eligible to "
                       "collect tax on supplies" if scheme == "composition" else None},
            "buyer": {"name": "Priya"}, "place_of_supply": "33", "place_of_supply_label": "Tamil Nadu (33)",
            "intra_state": True, "reverse_charge": False, "prices_include_tax": False, "lines": [line],
            "taxable_total": 450.0, "cgst_total": line["cgst"], "sgst_total": line["sgst"], "igst_total": 0.0,
            "round_off": round_off, "amount_due": line["line_total"] + round_off, "related": [], "tax_by_rate": [],
            "note_reason": None, "order_number": None, "due_date": None, "notes": None, "terms": None}


def test_a_composition_bill_of_supply_never_prints_a_tax_line() -> None:
    for thermal in (False, True):
        spec = build_spec(_spec_detail("bill_of_supply", scheme="composition"), thermal=thermal)
        printed = " ".join([spec.title, *spec.columns, *(k for k, _ in spec.totals), *(k for k, _ in spec.meta),
                            *(" ".join(r) for r in spec.rows)])
        for word in ("CGST", "SGST", "IGST", "GST %", "Taxable", "%"):
            assert word not in printed, (word, printed)
        assert spec.title == "Bill of supply" and spec.notes[0].startswith("Composition taxable person")
    bill = build_spec(_spec_detail("bill", scheme="unregistered"))
    assert not any("GSTIN" in x for x in bill.issuer + bill.party) and bill.meta == []


def test_the_printed_round_off_line_leaves_the_tax_lines_alone() -> None:
    spec = build_spec(_spec_detail("tax_invoice", scheme="regular", round_off=0.5))
    totals = dict(spec.totals)
    assert totals["CGST"] == "₹11.25" and totals["SGST"] == "₹11.25"
    assert totals["Round-off"] == "₹0.50" and totals["Total"] == "₹473.00"
    assert [k for k, _ in spec.totals] == ["Taxable value", "CGST", "SGST", "Round-off", "Total"]
    assert ("Reverse charge", "No") in spec.meta and ("Place of supply", "Tamil Nadu (33)") in spec.meta


# ---------------------------------------------------------------- API helpers
def _shop(owner: dict[str, str], *, scheme: str = "regular", inclusive: bool = False, round_off: bool = False,
          issue_on: str = "manual", state: str = "33") -> dict[str, Any]:
    bid = create_business(client, owner, modules=("offerings-catalog", "inventory", "orders", "payments",
                                                   "fulfilment", "invoicing"))
    base = f"/v1/platform/businesses/{bid}/invoicing"
    r = client.put(f"{base}/profile", json={"prices_include_tax": inclusive, "round_off": round_off,
                                            "issue_on": issue_on, "default_due_days": 15}, headers=owner)
    assert r.status_code == 200, r.text
    body: dict[str, Any] = {"scheme": scheme, "legal_name": "Sri Stores Pvt Ltd", "trade_name": "Sri Stores"}
    if scheme == "unregistered":
        body["state_code"] = state
    else:
        body["gstin"] = gstin(state, f"AA{uuid.uuid4().hex[:3].upper()}L1234K"[:10])
    if scheme == "composition":
        body["composition_declaration"] = "Composition taxable person, not eligible to collect tax on supplies"
    reg = client.post(f"{base}/registrations", json=body, headers=owner)
    assert reg.status_code == 200, reg.text
    loc = primary_location(client, owner, bid)
    register = client.post(f"{base}/registers", json={"location_id": loc, "registration_id": reg.json()["data"]["id"],
                                                      "code": "CHN1", "name": "Front counter"}, headers=owner)
    assert register.status_code == 200, register.text
    return {"bid": bid, "loc": loc, "registration": reg.json()["data"], "register": register.json()["data"],
            "base": f"/v1/platform/businesses/{bid}"}


def _item(owner: dict[str, str], shop: dict[str, Any], **body: Any) -> dict[str, Any]:
    r = client.post(f"{shop['base']}/products", json={"status": "active", "offering_type": "product", **body},
                    headers=owner)
    assert r.status_code == 200, r.text
    return dict(r.json()["data"])


def _order(owner: dict[str, str], shop: dict[str, Any], items: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    r = client.post(f"{shop['base']}/orders", json={"location_id": shop["loc"], "items": items,
                                                     "payment_method": "cod", **extra}, headers=owner)
    assert r.status_code == 200, r.text
    return dict(r.json()["data"])


def _bill(owner: dict[str, str], shop: dict[str, Any], lines: list[dict[str, Any]], **extra: Any) -> Any:
    return client.post(f"{shop['base']}/invoices", json={"lines": lines, **extra}, headers=owner)


# ---------------------------------------------------------------- orders and their bills
@DB
def test_order_and_its_bill_agree_same_state_cgst_sgst(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _shop(owner, inclusive=True, round_off=True)
    rice = _item(owner, shop, title="Ponni rice 5 kg", price_amount=105, hsn_sac="1006", tax_rate=5)
    oil = _item(owner, shop, title="Groundnut oil 1 l", price_amount=199, hsn_sac="1508", tax_rate=18)
    order = _order(owner, shop, [{"offering_id": rice["id"], "quantity": 3}, {"offering_id": oil["id"], "quantity": 1}])
    # Prices include GST: the customer pays the shelf price, tax is extracted.
    assert order["total_amount"] == 514.0 and order["tax_basis"]["inclusive"] is True
    assert order["tax_basis"]["scheme"] == "regular" and order["tax_basis"]["intra_state"] is True

    r = client.post(f"{shop['base']}/invoices/from-order/{order['id']}", json={}, headers=owner)
    assert r.status_code == 200, r.text
    bill = r.json()["data"]
    assert bill["doc_kind"] == "tax_invoice" and bill["number"] == f"CHN1/{FY}/00001"
    assert bill["amount_due"] == order["total_amount"]
    assert bill["igst_total"] == 0 and bill["cgst_total"] == bill["sgst_total"] > 0
    assert round(bill["taxable_total"] + bill["tax_total"] + bill["round_off"], 2) == bill["grand_total"]
    assert [ln["hsn_sac"] for ln in bill["lines"]] == ["1006", "1508"]
    again = client.post(f"{shop['base']}/invoices/from-order/{order['id']}", json={}, headers=owner)
    assert again.json()["data"]["id"] == bill["id"], "one live bill per order"


@DB
def test_other_state_delivery_uses_igst_from_the_place_of_supply(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _shop(owner, state="33")
    rice = _item(owner, shop, title="Rice", price_amount=100, hsn_sac="1006", tax_rate=5)
    order = _order(owner, shop, [{"offering_id": rice["id"], "quantity": 2}], place_of_supply="29")
    assert order["tax_amount"] == 10.0 and order["total_amount"] == 210.0
    bill = client.post(f"{shop['base']}/invoices/from-order/{order['id']}", json={}, headers=owner).json()["data"]
    assert bill["place_of_supply"] == "29" and bill["intra_state"] is False
    assert (bill["cgst_total"], bill["sgst_total"], bill["igst_total"]) == (0, 0, 10.0)
    pdf = client.get(f"{shop['base']}/invoices/{bill['id']}/pdf", headers=owner)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert pdf.headers["x-document-sha256"]
    for layout in ("thermal_80", "thermal_58"):
        assert client.get(f"{shop['base']}/invoices/{bill['id']}/pdf?layout={layout}",
                          headers=owner).content.startswith(b"%PDF")


@DB
def test_composition_business_orders_and_bills_carry_no_tax(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _shop(owner, scheme="composition", round_off=True)
    sweets = _item(owner, shop, title="Mysore pak 250 g", price_amount=180.5, tax_rate=5)
    order = _order(owner, shop, [{"offering_id": sweets["id"], "quantity": 1}])
    assert order["tax_amount"] == 0 and order["total_amount"] == 181.0 and order["round_off"] == 0.5
    bill = client.post(f"{shop['base']}/invoices/from-order/{order['id']}", json={}, headers=owner).json()["data"]
    assert bill["doc_kind"] == "bill_of_supply" and bill["tax_total"] == 0 and bill["lines"][0]["tax_rate"] is None


@DB
def test_rates_are_dated_data_and_a_missing_rate_blocks_the_bill(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _shop(owner)
    ghee = _item(owner, shop, title="Ghee 500 ml", price_amount=400, hsn_sac="04059020")
    blocked = _bill(owner, shop, [{"offering_id": ghee["id"], "quantity": 1}])
    assert blocked.status_code == 422 and "Set a GST rate before billing: Ghee 500 ml" in blocked.text
    assert sql("select count(*) from invoicing_documents where business_id = :b", b=shop["bid"]) == [(0,)]

    rates = f"{shop['base']}/invoicing/tax-rates"
    today = local_today()
    assert client.post(rates, json={"hsn_sac": "0405", "rate": 12, "effective_from": (today - timedelta(days=30))
                                    .isoformat()}, headers=owner).status_code == 200
    later = client.post(rates, json={"hsn_sac": "0405", "rate": 5, "effective_from": (today + timedelta(days=5))
                                     .isoformat(), "note": "Council revision"}, headers=owner)
    assert later.status_code == 200, later.text
    listing = client.get(rates, headers=owner).json()["data"]
    old = next(r for r in listing["rates"] if r["rate"] == 12)
    assert old["effective_to"] == (today + timedelta(days=4)).isoformat()
    assert next(i for i in listing["items"] if i["id"] == ghee["id"])["rate_today"] == 12.0

    ok = _bill(owner, shop, [{"offering_id": ghee["id"], "quantity": 1}])
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["lines"][0]["tax_rate"] == 12.0 and ok.json()["data"]["tax_total"] == 48.0


@DB
def test_b2b_bill_igst_stock_cancel_keeps_number_and_series_stays_gapless(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _shop(owner)
    pipe = _item(owner, shop, title="PVC pipe 3 m", price_amount=250, hsn_sac="3917", tax_rate=18,
                 track_inventory=True)
    client.post(f"{shop['base']}/inventory/opening-stock", json={"offering_id": pipe["id"], "location_id": shop["loc"],
                                                                 "quantity": 50}, headers=owner)
    buyer = {"name": "Kaveri Builders", "gstin": gstin("29", "AABCK1234Q"), "address": "Bengaluru"}
    first = _bill(owner, shop, [{"offering_id": pipe["id"], "quantity": 10}], buyer=buyer)
    assert first.status_code == 200, first.text
    b1 = first.json()["data"]
    assert b1["place_of_supply"] == "29" and b1["igst_total"] == 450.0 and b1["cgst_total"] == 0
    assert b1["due_date"] == (local_today() + timedelta(days=15)).isoformat()
    stock = sql("select quantity_on_hand from inventory_records where offering_id = :o", o=pipe["id"])
    assert stock == [(40,)]

    bad = _bill(owner, shop, [{"offering_id": pipe["id"], "quantity": 1}], buyer={"name": "X", "gstin": "29AABCK1234Q1ZZ"})
    assert bad.status_code == 422 and "Buyer GSTIN" in bad.text
    cancelled = client.post(f"{shop['base']}/invoices/{b1['id']}/cancel", json={"reason": "Wrong buyer"}, headers=owner)
    assert cancelled.status_code == 200 and cancelled.json()["data"]["status"] == "cancelled"
    assert cancelled.json()["data"]["number"] == f"CHN1/{FY}/00001"
    assert sql("select quantity_on_hand from inventory_records where offering_id = :o", o=pipe["id"]) == [(50,)]
    assert client.delete(f"{shop['base']}/invoices/{b1['id']}", headers=owner).status_code == 409

    b2 = _bill(owner, shop, [{"offering_id": pipe["id"], "quantity": 1}], buyer=buyer).json()["data"]
    draft = _bill(owner, shop, [{"title": "Site visit", "hsn_sac": "998719", "rate": 18, "unit_price": 500}],
                  issue=False).json()["data"]
    assert draft["status"] == "draft" and draft["number"] is None
    b3 = client.post(f"{shop['base']}/invoices/{draft['id']}/issue", headers=owner).json()["data"]
    assert [b2["number"], b3["number"]] == [f"CHN1/{FY}/00002", f"CHN1/{FY}/00003"]
    docs = client.get(f"{shop['base']}/invoicing/reports/documents", headers=owner).json()["data"]
    assert docs["rows"][0]["total"] == 3
    assert docs["rows"][0]["cancelled"] == 1 and docs["rows"][0]["gaps"] == "None"


@DB
def test_credit_note_returns_restock_and_reduce_what_is_owed(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _shop(owner)
    fan = _item(owner, shop, title="Ceiling fan", price_amount=2000, hsn_sac="8414", tax_rate=18, track_inventory=True)
    client.post(f"{shop['base']}/inventory/opening-stock", json={"offering_id": fan["id"], "location_id": shop["loc"],
                                                                 "quantity": 5}, headers=owner)
    bill = _bill(owner, shop, [{"offering_id": fan["id"], "quantity": 2}]).json()["data"]
    assert bill["amount_due"] == 4720.0 and bill["payment_status"] == "unpaid"
    line = bill["lines"][0]["id"]
    too_many = client.post(f"{shop['base']}/invoices/{bill['id']}/notes", json={
        "kind": "credit_note", "reason": "return", "restock": True,
        "lines": [{"original_line_id": line, "quantity": 3}]}, headers=owner)
    assert too_many.status_code == 422
    cn = client.post(f"{shop['base']}/invoices/{bill['id']}/notes", json={
        "kind": "credit_note", "reason": "return", "restock": True,
        "lines": [{"original_line_id": line, "quantity": 1}]}, headers=owner)
    assert cn.status_code == 200, cn.text
    note = cn.json()["data"]
    assert note["number"] == f"CN/{FY}/00001" and note["amount_due"] == 2360.0 and note["cgst_total"] == 180.0
    assert note["related"][0]["id"] == bill["id"]
    assert sql("select quantity_on_hand from inventory_records where offering_id = :o", o=fan["id"]) == [(4,)]
    after = client.get(f"{shop['base']}/invoices/{bill['id']}", headers=owner).json()["data"]
    assert after["outstanding"] == 2360.0 and after["lines"][0]["returnable_quantity"] == 1.0
    assert client.post(f"{shop['base']}/invoices/{bill['id']}/cancel", json={"reason": "x"},
                       headers=owner).status_code == 409

    over = client.post(f"{shop['base']}/invoices/{bill['id']}/payments", json={"amount": 5000, "method": "upi"},
                       headers=owner)
    assert over.status_code == 422
    part = client.post(f"{shop['base']}/invoices/{bill['id']}/payments",
                       json={"amount": 1000, "method": "upi", "reference": "UTR123"}, headers=owner).json()["data"]
    assert part["payment_status"] == "part_paid" and part["outstanding"] == 1360.0
    paid = client.post(f"{shop['base']}/invoices/{bill['id']}/payments", json={"amount": 1360, "method": "cash"},
                       headers=owner).json()["data"]
    assert paid["payment_status"] == "paid"
    dn = client.post(f"{shop['base']}/invoices/{bill['id']}/notes", json={
        "kind": "debit_note", "reason": "price_increase", "lines": [{"original_line_id": line, "amount": 100}]},
        headers=owner)
    assert dn.status_code == 200 and dn.json()["data"]["number"] == f"DN/{FY}/00001"
    assert dn.json()["data"]["amount_due"] == 118.0

    reg = client.get(f"{shop['base']}/invoicing/reports/sales_register", headers=owner).json()["data"]
    assert reg["totals"]["taxable"] == 4000.0 - 2000.0 + 100.0
    by_rate = client.get(f"{shop['base']}/invoicing/reports/tax_by_rate", headers=owner).json()["data"]
    assert by_rate["rows"] == [{"rate": "18", "taxable": 2100.0, "cgst": 189.0, "sgst": 189.0, "igst": 0.0,
                                "tax": 378.0}]
    hsn = client.get(f"{shop['base']}/invoicing/reports/hsn_summary", headers=owner).json()["data"]
    assert hsn["rows"][0]["hsn_sac"] == "8414" and hsn["rows"][0]["quantity"] == 1.0
    csv = client.get(f"{shop['base']}/invoicing/reports/gstr1.csv", headers=owner)
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv") and "# b2c" in csv.text


@DB
def test_orders_are_billed_automatically_when_the_owner_chose(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _shop(owner, issue_on="order_completed")
    item = _item(owner, shop, title="Notebook", price_amount=60, hsn_sac="4820", tax_rate=12)
    order = _order(owner, shop, [{"offering_id": item["id"], "quantity": 2}])
    for status in ("accepted", "preparing", "ready"):
        client.post(f"{shop['base']}/orders/{order['id']}/status", json={"status": status}, headers=owner)
    drain_events(shop["bid"])
    assert client.get(f"{shop['base']}/invoices?order_id={order['id']}", headers=owner).json()["data"] == []
    assert client.post(f"{shop['base']}/orders/{order['id']}/complete", json={}, headers=owner).status_code == 200
    drain_events(shop["bid"])
    bills = client.get(f"{shop['base']}/invoices?order_id={order['id']}", headers=owner).json()["data"]
    assert len(bills) == 1 and bills[0]["number"] == f"CHN1/{FY}/00001" and bills[0]["amount_due"] == 134.4

    # An order that cannot be billed is not guessed around: the team is told.
    blank = _item(owner, shop, title="Loose item", price_amount=10)
    order2 = _order(owner, shop, [{"offering_id": blank["id"], "quantity": 1}])
    for status in ("accepted", "preparing", "ready"):
        client.post(f"{shop['base']}/orders/{order2['id']}/status", json={"status": status}, headers=owner)
    client.post(f"{shop['base']}/orders/{order2['id']}/complete", json={}, headers=owner)
    drain_events(shop["bid"])
    notes = sql("select title, body from platform_notifications where business_id = :b and "
                "notification_type = 'invoicing.bill_blocked'", b=shop["bid"])
    assert notes and "could not be billed" in notes[0][0] and "Loose item" in notes[0][1]


@DB
def test_the_customer_bill_link_shows_only_that_bill(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _shop(owner)
    item = _item(owner, shop, title="Haircut", offering_type="service", price_amount=300, hsn_sac="999721", tax_rate=18)
    bill = _bill(owner, shop, [{"offering_id": item["id"], "quantity": 1}],
                 buyer={"name": "Ravi", "phone": "+919800000000"}).json()["data"]
    share = client.get(f"{shop['base']}/invoices/{bill['id']}/share", headers=owner).json()["data"]
    assert share["message"].startswith("Your bill from Sri Stores: Tax invoice") and share["phone"] == "+919800000000"
    slug = share["path"].split("/")[1]
    public = client.get(f"/v1/public/websites/{slug}/bills/{share['token']}")
    assert public.status_code == 200, public.text
    data = public.json()["data"]
    assert data["number"] == bill["number"] and "customer_contact_id" not in data and "register_id" not in data
    assert client.get(f"/v1/public/websites/{slug}/bills/{share['token']}/pdf").content.startswith(b"%PDF")
    assert client.get(f"/v1/public/websites/{slug}/bills/{'x' * 32}").status_code == 404
    other = create_business(client, owner)
    other_slug = client.get(f"/v1/b/{other}", headers=owner).json()["data"]["slug"]
    assert client.get(f"/v1/public/websites/{other_slug}/bills/{share['token']}").status_code == 404
    draft = _bill(owner, shop, [{"offering_id": item["id"], "quantity": 1}], issue=False).json()["data"]
    assert client.get(f"{shop['base']}/invoices/{draft['id']}/share", headers=owner).status_code == 409


def _join(owner: dict[str, str], bid: str, monkeypatch: Any, role: str, locations: list[str] | None = None
          ) -> dict[str, str]:
    person_id, headers = new_identity(monkeypatch)
    inv = client.post(f"/v1/b/{bid}/team/invitations", json={"identity_id": str(person_id), "role": "member"},
                      headers=owner)
    mid = inv.json()["data"]["id"]
    assert client.post(f"/v1/b/{bid}/team/members/{mid}/activate", headers=owner).status_code == 200
    given = client.put(f"/v1/platform/businesses/{bid}/members/{mid}/role",
                       json={"role": role, "location_ids": locations or []}, headers=owner)
    assert given.status_code == 200, given.text
    return dict(headers)


@DB
def test_roles_accountant_sets_up_tax_manager_bills_store_keeper_sees_none(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _shop(owner)
    item = _item(owner, shop, title="Soap", price_amount=40, hsn_sac="3401", tax_rate=18)
    accountant = _join(owner, shop["bid"], monkeypatch, "accountant")
    manager = _join(owner, shop["bid"], monkeypatch, "manager", [shop["loc"]])
    keeper = _join(owner, shop["bid"], monkeypatch, "store_keeper", [shop["loc"]])
    rates = f"{shop['base']}/invoicing/tax-rates"
    assert client.post(rates, json={"hsn_sac": "3401", "rate": 18, "effective_from": "2026-04-01"},
                       headers=accountant).status_code == 200
    assert client.post(rates, json={"hsn_sac": "3402", "rate": 18, "effective_from": "2026-04-01"},
                       headers=manager).status_code == 403
    made = _bill(manager, shop, [{"offering_id": item["id"], "quantity": 3}])
    assert made.status_code == 200, made.text
    assert client.get(f"{shop['base']}/invoicing/reports/sales_register", headers=manager).status_code == 403
    assert client.get(f"{shop['base']}/invoicing/reports/sales_register", headers=accountant).status_code == 200
    assert client.get(f"{shop['base']}/invoices", headers=keeper).status_code == 403


@DB
def test_a_location_limited_manager_sees_only_their_locations_bills(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _shop(owner)
    item = _item(owner, shop, title="Tea", price_amount=10, hsn_sac="0902", tax_rate=5)
    loc_b = client.post(f"{shop['base']}/locations", json={"name": "Branch B"}, headers=owner).json()["data"]["id"]
    reg_b = client.post(f"{shop['base']}/invoicing/registers", json={
        "location_id": loc_b, "registration_id": shop["registration"]["id"], "code": "BRB1"}, headers=owner)
    assert reg_b.status_code == 200, reg_b.text
    a = _bill(owner, shop, [{"offering_id": item["id"], "quantity": 1}],
              register_id=shop["register"]["id"]).json()["data"]
    b = _bill(owner, shop, [{"offering_id": item["id"], "quantity": 1}],
              register_id=reg_b.json()["data"]["id"]).json()["data"]
    assert b["number"] == f"BRB1/{FY}/00001" and a["number"] == f"CHN1/{FY}/00001"
    manager = _join(owner, shop["bid"], monkeypatch, "manager", [shop["loc"]])
    seen = {x["id"] for x in client.get(f"{shop['base']}/invoices", headers=manager).json()["data"]}
    assert seen == {a["id"]}
    assert client.get(f"{shop['base']}/invoices/{b['id']}", headers=manager).status_code == 404
    blocked = _bill(manager, shop, [{"offering_id": item["id"], "quantity": 1}], register_id=reg_b.json()["data"]["id"])
    assert blocked.status_code in (403, 404, 422), blocked.text


@DB
def test_two_registers_reserve_blocks_that_never_share_or_skip_a_number(monkeypatch: Any) -> None:
    from platform_core.services.number_series import NumberSeriesService

    _, owner = new_identity(monkeypatch)
    shop = _shop(owner)
    reg2 = client.post(f"{shop['base']}/invoicing/registers", json={
        "location_id": shop["loc"], "registration_id": shop["registration"]["id"], "code": "CHN2"}, headers=owner)
    assert reg2.status_code == 200
    ids = [shop["register"]["id"], reg2.json()["data"]["id"]]

    async def run() -> list[list[str]]:
        engine = create_async_engine(db_url(), poolclass=NullPool)
        out = []
        try:
            async with AsyncSession(engine) as s:
                for rid, code in zip(ids, ("CHN1", "CHN2")):
                    first = await NumberSeriesService.reserve_block(
                        s, uuid.UUID(shop["bid"]), series_key=f"inv:{rid}", holder=code, period=FY, prefix=code,
                        pad=5, size=3)
                    second = await NumberSeriesService.reserve_block(
                        s, uuid.UUID(shop["bid"]), series_key=f"inv:{rid}", holder=code, period=FY, prefix=code,
                        pad=5, size=2)
                    out.append([first.number(v) for v in range(first.start, first.end + 1)]
                               + [second.number(v) for v in range(second.start, second.end + 1)])
                await s.commit()
        finally:
            await engine.dispose()
        return out

    one, two = asyncio.run(run())
    assert one == [f"CHN1/{FY}/0000{i}" for i in range(1, 6)] and two == [f"CHN2/{FY}/0000{i}" for i in range(1, 6)]
    online = client.post(f"{shop['base']}/invoices", json={"lines": [{"title": "Service", "rate": 18,
                                                                      "unit_price": 10}]}, headers=owner)
    assert online.status_code == 422  # two registers at the location: the bill must say which
    chosen = client.post(f"{shop['base']}/invoices", json={"register_id": ids[0], "lines": [
        {"title": "Service", "rate": 18, "unit_price": 10}]}, headers=owner).json()["data"]
    assert chosen["number"] == f"CHN1/{FY}/00006"


@DB
def test_setup_validates_gstin_scheme_and_locks_used_registrations(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("offerings-catalog", "invoicing"))
    base = f"/v1/platform/businesses/{bid}/invoicing"
    setup = client.get(f"{base}/setup", headers=owner).json()["data"]
    assert setup["ready"] is False and setup["profile"] is None and len(setup["needs"]) == 3
    bad = client.post(f"{base}/registrations", json={"scheme": "regular", "legal_name": "X", "gstin": "33ABCDE1234F1Z0"},
                      headers=owner)
    assert bad.status_code == 422
    comp = client.post(f"{base}/registrations", json={"scheme": "composition", "legal_name": "X", "gstin": gstin("33")},
                       headers=owner)
    assert comp.status_code == 422 and "declaration" in comp.text
    unreg = client.post(f"{base}/registrations", json={"scheme": "unregistered", "legal_name": "X", "state_code": "33"},
                        headers=owner)
    assert unreg.status_code == 200 and unreg.json()["data"]["document"] == "bill"
    also = client.post(f"{base}/registrations", json={"scheme": "regular", "legal_name": "X", "gstin": gstin("33")},
                       headers=owner)
    assert also.status_code == 409
    long_code = client.post(f"{base}/registers", json={"location_id": primary_location(client, owner, bid),
                            "registration_id": unreg.json()["data"]["id"], "code": "CHENNAI1", "pad": 6}, headers=owner)
    assert long_code.status_code == 200 and long_code.json()["data"]["too_long"] is True


TABLES = {
    "invoicing_tax_profiles": "insert into invoicing_tax_profiles (business_id, prices_include_tax, round_off, issue_on) "
                              "values (:b, true, true, 'manual')",
    "invoicing_registrations": "insert into invoicing_registrations (business_id, scheme, legal_name, state_code) "
                               "values (:b, 'unregistered', 'x', '33')",
    "invoicing_tax_rates": "insert into invoicing_tax_rates (business_id, hsn_sac, rate, effective_from) "
                           "values (:b, '1006', 5, '2026-04-01')",
}


@DB
@pytest.mark.parametrize("table", sorted(TABLES))
@pytest.mark.asyncio
async def test_setup_tables_are_tenant_isolated(table: str) -> None:
    async def insert(session: AsyncSession, business_id: uuid.UUID) -> None:
        await session.execute(text(TABLES[table]), {"b": business_id})

    await assert_tenant_isolated(table, insert)


async def _doc(session: AsyncSession, business_id: uuid.UUID) -> uuid.UUID:
    loc = (await session.execute(text("insert into business_locations (business_id, name) values (:b, 'L') returning id"),
                                 {"b": business_id})).scalar()
    reg = (await session.execute(text(
        "insert into invoicing_registrations (business_id, scheme, legal_name, state_code) "
        "values (:b, 'unregistered', 'x', '33') returning id"), {"b": business_id})).scalar()
    rgs = (await session.execute(text(
        "insert into invoicing_registers (business_id, location_id, registration_id, code, name) "
        "values (:b, :l, :r, 'A1', 'A') returning id"), {"b": business_id, "l": loc, "r": reg})).scalar()
    doc = (await session.execute(text(
        "insert into invoicing_documents (business_id, location_id, register_id, registration_id, doc_kind) "
        "values (:b, :l, :g, :r, 'bill') returning id"), {"b": business_id, "l": loc, "g": rgs, "r": reg})).scalar()
    await session.execute(text(
        "insert into invoicing_document_lines (business_id, document_id, title, quantity, unit_price, taxable_value, "
        "line_total) values (:b, :d, 't', 1, 1, 1, 1)"), {"b": business_id, "d": doc})
    await session.execute(text(
        "insert into invoicing_payments (business_id, document_id, amount, method, received_on) "
        "values (:b, :d, 1, 'cash', current_date)"), {"b": business_id, "d": doc})
    return uuid.UUID(str(doc))


@DB
@pytest.mark.parametrize("table", ["invoicing_documents", "invoicing_document_lines", "invoicing_payments",
                                   "invoicing_registers"])
@pytest.mark.asyncio
async def test_bill_tables_are_tenant_isolated(table: str) -> None:
    async def insert(session: AsyncSession, business_id: uuid.UUID) -> None:
        await _doc(session, business_id)

    await assert_tenant_isolated(table, insert)


@DB
@pytest.mark.asyncio
async def test_the_bill_token_policy_opens_exactly_one_issued_bill() -> None:
    engine = create_async_engine(db_url(), poolclass=NullPool)
    try:
        async with AsyncSession(engine) as s:
            bid = (await s.execute(text("select id from businesses limit 1"))).scalar()
            doc = await _doc(s, uuid.UUID(str(bid)))
            await _doc(s, uuid.UUID(str(bid)))
            await s.execute(text("update invoicing_documents set public_token_hash = 'h1' where id = :d"), {"d": doc})
            await s.execute(text("set local role platform_api"))
            draft = (await s.execute(text("select set_config('app.current_bill_token', 'h1', true)"))).scalar()
            assert draft == "h1"
            seen = (await s.execute(text("select count(*) from invoicing_documents"))).scalar()
            assert seen == 0, "a draft is never opened by its link"
            await s.execute(text("reset role"))
            await s.execute(text("update invoicing_documents set status = 'issued', number = 'A1/1', seq = 1, "
                                 "issue_date = current_date where id = :d"), {"d": doc})
            await s.execute(text("set local role platform_api"))
            rows = (await s.execute(text("select id from invoicing_documents"))).scalars().all()
            lines = (await s.execute(text("select count(*) from invoicing_document_lines"))).scalar()
            payments = (await s.execute(text("select count(*) from invoicing_payments"))).scalar()
            assert [str(r) for r in rows] == [str(doc)] and lines == 1 and payments == 0
            await s.rollback()
    finally:
        await engine.dispose()


@DB
def test_overdue_bills_reach_the_owner_and_the_accountant_home(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _shop(owner)
    late = _bill(owner, shop, [{"title": "Annual maintenance", "hsn_sac": "998719", "rate": 18, "unit_price": 1000}],
                 buyer={"name": "Kaveri Builders", "gstin": gstin("33", "AABCK1234Q")},
                 due_date=(local_today() - timedelta(days=3)).isoformat())
    assert late.status_code == 200, late.text
    assert late.json()["data"]["overdue"] is True
    overdue = client.get(f"{shop['base']}/invoices?payment=overdue", headers=owner).json()["data"]
    assert [b["id"] for b in overdue] == [late.json()["data"]["id"]]
    home = client.get(f"{shop['base']}/home", headers=owner).json()["data"]
    now = next(b for b in home["bands"] if b["key"] == "now")
    assert any(i["label"] == "bills past their due date" and i["count"] == 1 for i in now["items"]), now
    accountant = _join(owner, shop["bid"], monkeypatch, "accountant")
    bands = {b["key"]: b for b in client.get(f"{shop['base']}/home", headers=accountant).json()["data"]["bands"]}
    assert any(i["label"] == "bills not fully paid" for i in bands["unpaid"]["items"])
    assert any(i["label"] == "bills past their due date" for i in bands["due"]["items"])
