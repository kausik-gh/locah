"""Khata / credit book (Capability Universe §6.2 `ledger`, §14.5; §26.3 P1-06).

The packet's done-when is here by name: the balance equals the sum of the
entries under concurrent writes. Around it: bills on the customer's account
and the limit a manager may override, money received applied to the oldest
bills first, ageing, credit notes and cancellations flowing back, the counter's
khata tender and khata payments into the drawer, supplier accounts, the
customer's statement link, the roles, and tenant isolation.
"""

from __future__ import annotations

import asyncio
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

from platform_core.services.ledger import LedgerService, age
from platform_testing.phase_b import (
    assert_tenant_isolated,
    billing_shop,
    db_url,
    new_identity,
    sql,
)

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)
TODAY = date.today()


class _E:
    def __init__(self, seq: int, amount: str, entry_date: date, due: date | None = None) -> None:
        self.seq, self.amount, self.entry_date, self.due_date = seq, D(amount), entry_date, due


# ---------------------------------------------------------------- ageing (no DB)
def test_ageing_is_fifo_money_settles_the_oldest_first() -> None:
    entries: list[Any] = [
        _E(1, "1000", TODAY - timedelta(days=75)),  # due day 60 ago with 15 credit days
        _E(2, "500", TODAY - timedelta(days=20)),   # due 5 days ago
        _E(3, "-1200", TODAY - timedelta(days=2)),  # settles #1 and 200 of #2
        _E(4, "300", TODAY),                        # not due yet
    ]
    a = age(entries, TODAY, 15)
    view = {b["key"]: b["amount"] for b in a.view()["buckets"]}
    assert view == {"current": 300.0, "d1_30": 300.0, "d31_60": 0.0, "d61_90": 0.0, "d90": 0.0}
    assert a.overdue == D("300") and a.advance == 0
    ahead = age([_E(1, "-200", TODAY), _E(2, "150", TODAY)], TODAY, 0)
    assert ahead.advance == D("50") and ahead.overdue == 0, "money paid ahead is used by the next credit"


# ---------------------------------------------------------------- helpers
def _shop(owner: dict[str, str]) -> dict[str, Any]:
    shop: dict[str, Any] = dict(billing_shop(client, owner, modules=("pos", "ledger")))
    item = client.post(f"{shop['base']}/products", json={
        "status": "active", "offering_type": "product", "title": "Cement bag 50 kg", "price_amount": 400,
        "hsn_sac": "2523", "tax_rate": 28}, headers=owner)
    assert item.status_code == 200, item.text
    shop["item"] = item.json()["data"]
    return shop


def _account(owner: dict[str, str], shop: dict[str, Any], **body: Any) -> dict[str, Any]:
    r = client.post(f"{shop['base']}/ledger/accounts", json={"party_type": "customer", **body}, headers=owner)
    assert r.status_code == 200, r.text
    return dict(r.json()["data"])


def _khata_bill(headers: dict[str, str], shop: dict[str, Any], contact_id: str, qty: int = 1, **extra: Any) -> Any:
    return client.post(f"{shop['base']}/invoices", json={
        "lines": [{"offering_id": shop["item"]["id"], "quantity": qty}], "customer_contact_id": contact_id,
        "on_account": True, **extra}, headers=headers)


def _join(owner: dict[str, str], shop: dict[str, Any], monkeypatch: Any, role: str) -> tuple[uuid.UUID, dict[str, str]]:
    person_id, headers = new_identity(monkeypatch)
    inv = client.post(f"/v1/b/{shop['bid']}/team/invitations", json={"identity_id": str(person_id), "role": "member"},
                      headers=owner)
    mid = inv.json()["data"]["id"]
    assert client.post(f"/v1/b/{shop['bid']}/team/members/{mid}/activate", headers=owner).status_code == 200
    given = client.put(f"{shop['base']}/members/{mid}/role", json={"role": role, "location_ids": [shop["loc"]]},
                       headers=owner)
    assert given.status_code == 200, given.text
    return person_id, dict(headers)


def _sums_agree(account_id: str) -> None:
    [(balance, total, n, max_seq)] = sql(
        "select a.balance, coalesce(sum(e.amount), 0), count(e.id), coalesce(max(e.seq), 0) from ledger_accounts a "
        "left join ledger_entries e on e.account_id = a.id where a.id = :a group by a.balance", a=account_id)
    assert balance == total, f"balance {balance} but entries sum to {total}"
    assert n == max_seq, "entries are numbered 1..n with no gap"


# ---------------------------------------------------------------- bills on khata
@DB
def test_a_bill_on_khata_raises_the_balance_within_the_limit(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _shop(owner)
    acct = _account(owner, shop, display_name="Murugan Traders", phone="+919811100001", credit_limit=2000,
                    credit_days=15, opening_balance=250)
    assert acct["balance"] == 250.0 and acct["entries"][0]["kind"] == "opening_balance"
    contact = acct["customer_contact_id"]
    bill = _khata_bill(owner, shop, contact, qty=3)  # 1200 + 28% = 1536
    assert bill.status_code == 200, bill.text
    b = bill.json()["data"]
    assert b["on_account"] is True and b["amount_due"] == 1536.0 and b["payment_status"] == "unpaid"
    after = client.get(f"{shop['base']}/ledger/accounts/{acct['id']}", headers=owner).json()["data"]
    top = after["entries"][0]
    assert after["balance"] == 1786.0 and top["kind"] == "credit_sale" and top["document_number"] == b["number"]
    assert top["due_date"] == (TODAY + timedelta(days=15)).isoformat()

    # The limit (§14.5): 1786 + 512 > 2000 — refused, with what is left to give.
    over = _khata_bill(owner, shop, contact, qty=1)
    assert over.status_code == 409 and over.json()["error"]["details"]["needs"] == "credit_approval", over.text
    assert over.json()["error"]["details"]["room"] == 214.0
    assert sql("select count(*) from invoicing_documents where business_id = :b", b=shop["bid"]) == [(1,)], \
        "the refused bill left nothing behind"
    # A manager without ledger.manage cannot allow it; the owner can.
    _, manager = _join(owner, shop, monkeypatch, "manager")
    still = _khata_bill(manager, shop, contact, qty=1, allow_over_limit=True)
    assert still.status_code == 409
    allowed = _khata_bill(owner, shop, contact, qty=1, allow_over_limit=True)
    assert allowed.status_code == 200, allowed.text
    [(approved,)] = sql("select over_limit_approved_by from ledger_entries where document_id = :d",
                        d=allowed.json()["data"]["id"])
    assert approved is not None
    listing = client.get(f"{shop['base']}/ledger/accounts", headers=owner).json()["data"]
    row = listing["accounts"][0]
    assert row["over_limit"] is True and listing["totals"]["receivable"] == 2298.0
    # No customer, no khata.
    nobody = client.post(f"{shop['base']}/invoices", json={
        "lines": [{"offering_id": shop["item"]["id"], "quantity": 1}], "on_account": True}, headers=owner)
    assert nobody.status_code == 422
    _sums_agree(acct["id"])


@DB
def test_money_received_settles_the_oldest_bills_first(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _shop(owner)
    acct = _account(owner, shop, display_name="Lakshmi Hardware", phone="+919811100002")
    b1 = _khata_bill(owner, shop, acct["customer_contact_id"]).json()["data"]  # 512
    b2 = _khata_bill(owner, shop, acct["customer_contact_id"]).json()["data"]  # 512
    paid = client.post(f"{shop['base']}/ledger/accounts/{acct['id']}/payments", json={
        "amount": 700, "method": "upi", "reference": "UTR 4411", "idempotency_key": "pay-1"}, headers=owner)
    assert paid.status_code == 200, paid.text
    applied = paid.json()["meta"]["applied"]
    assert [(a["number"], a["applied"]) for a in applied] == [(b1["number"], 512.0), (b2["number"], 188.0)]
    assert paid.json()["data"]["balance"] == 324.0
    again = client.post(f"{shop['base']}/ledger/accounts/{acct['id']}/payments", json={
        "amount": 700, "method": "upi", "idempotency_key": "pay-1"}, headers=owner)
    assert again.json()["data"]["balance"] == 324.0 and again.json()["meta"]["applied"] == [], "a retry posts nothing"
    first = client.get(f"{shop['base']}/invoices/{b1['id']}", headers=owner).json()["data"]
    second = client.get(f"{shop['base']}/invoices/{b2['id']}", headers=owner).json()["data"]
    assert first["payment_status"] == "paid" and second["payment_status"] == "part_paid"
    assert second["outstanding"] == 324.0, "the bills and the khata agree"

    # Money recorded on the bill itself also comes off the khata.
    client.post(f"{shop['base']}/invoices/{b2['id']}/payments", json={"amount": 124, "method": "cash"}, headers=owner)
    # A return on a khata bill lowers what is owed.
    lines = client.get(f"{shop['base']}/invoices/{b2['id']}", headers=owner).json()["data"]["lines"]
    note = client.post(f"{shop['base']}/invoices/{b2['id']}/notes", json={
        "kind": "credit_note", "reason": "price_reduction",
        "lines": [{"original_line_id": lines[0]["id"], "amount": 100}]}, headers=owner)
    assert note.status_code == 200, note.text
    detail = client.get(f"{shop['base']}/ledger/accounts/{acct['id']}", headers=owner).json()["data"]
    kinds = [e["kind"] for e in detail["entries"]]
    assert kinds[:2] == ["return_credit", "payment_received"] and detail["balance"] == 72.0
    # A cancelled khata bill takes back what it put on the khata.
    b3 = _khata_bill(owner, shop, acct["customer_contact_id"]).json()["data"]
    client.post(f"{shop['base']}/invoices/{b3['id']}/cancel", json={"reason": "Billed twice"}, headers=owner)
    detail = client.get(f"{shop['base']}/ledger/accounts/{acct['id']}", headers=owner).json()["data"]
    assert detail["entries"][0]["kind"] == "adjustment" and detail["balance"] == 72.0
    _sums_agree(acct["id"])


async def _thirty_writers(bid: uuid.UUID, aid: uuid.UUID, actor: uuid.UUID) -> None:
    engine = create_async_engine(db_url(), pool_size=12, max_overflow=4)

    async def write(i: int) -> None:
        async with AsyncSession(engine) as s, s.begin():
            if i % 3 == 2:
                await LedgerService.receive(s, bid, aid, actor, amount=D("7.25"), method="cash")
            else:
                await LedgerService.post(s, bid, aid, kind="opening_balance" if i % 3 else "adjustment",
                                         amount=D("10.10") if i % 2 else D("-3.05"), actor_id=actor, note=f"w{i}")

    try:
        await asyncio.gather(*(write(i) for i in range(30)))
    finally:
        await engine.dispose()


@DB
def test_balance_equals_sum_of_entries_under_concurrent_writes(monkeypatch: Any) -> None:
    """§26.3 P1-06 done-when: many writers at once (two counters, a payment
    taken in the office) never lose an update or reuse a line number."""
    owner_id, owner = new_identity(monkeypatch)
    shop = _shop(owner)
    acct = _account(owner, shop, display_name="Concurrent Co", phone="+919811100003")
    asyncio.run(_thirty_writers(uuid.UUID(shop["bid"]), uuid.UUID(acct["id"]), owner_id))
    [(n,)] = sql("select count(*) from ledger_entries where account_id = :a", a=acct["id"])
    assert n == 30
    _sums_agree(acct["id"])
    rows = sql("select seq, amount, balance_after from ledger_entries where account_id = :a order by seq",
               a=acct["id"])
    running = D(0)
    for seq, amount, after in rows:
        running += amount
        assert after == running, f"line {seq}: running balance {after} should be {running}"


@DB
@pytest.mark.asyncio
async def test_entries_are_append_only() -> None:
    engine = create_async_engine(db_url(), poolclass=NullPool)
    try:
        async with AsyncSession(engine) as s:
            b = (await s.execute(text("select id from businesses limit 1"))).scalar()
            a = (await s.execute(text(
                "insert into ledger_accounts (business_id, party_type, display_name) values (:b, 'supplier', 'X') "
                "returning id"), {"b": b})).scalar()
            e = (await s.execute(text(
                "insert into ledger_entries (business_id, account_id, seq, kind, amount, balance_after, entry_date) "
                "values (:b, :a, 1, 'purchase', 100, 100, current_date) returning id"), {"b": b, "a": a})).scalar()
            for stmt in ("update ledger_entries set amount = 1 where id = :e", "delete from ledger_entries where id = :e"):
                await s.execute(text("savepoint s"))
                with pytest.raises(Exception, match="append-only"):
                    await s.execute(text(stmt), {"e": e})
                await s.execute(text("rollback to savepoint s"))
            await s.rollback()
    finally:
        await engine.dispose()


# ---------------------------------------------------------------- the counter's khata
def _open(headers: dict[str, str], shop: dict[str, Any], cash: float = 500) -> dict[str, Any]:
    r = client.post(f"{shop['base']}/pos/shifts", json={"register_id": shop["register"]["id"], "device_id": "till",
                                                         "opening_cash": cash}, headers=headers)
    assert r.status_code == 200, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


def _sync(headers: dict[str, str], shop: dict[str, Any], kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    r = client.post(f"{shop['base']}/sync", json={"device_id": "till", "mutations": [
        {"client_mutation_id": str(uuid.uuid4()), "kind": kind, "payload": payload}]}, headers=headers)
    assert r.status_code == 200, r.text
    res: dict[str, Any] = r.json()["data"]["results"][0]
    return res


def _counter_sale(shop: dict[str, Any], shift: dict[str, Any], tenders: list[dict[str, Any]], **extra: Any
                  ) -> dict[str, Any]:
    return {"shift_id": shift["shift"]["id"], "client_bill_id": str(uuid.uuid4()),
            "lines": [{"offering_id": shop["item"]["id"], "quantity": 1, "unit_price": 400}], "tenders": tenders,
            "catalogue_version": datetime.now(timezone.utc).isoformat(), **extra}


@DB
def test_counter_khata_tender_limit_manager_pin_payment_return_and_void(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _shop(owner)
    cashier_id, cashier = _join(owner, shop, monkeypatch, "cashier")
    manager_id, manager = _join(owner, shop, monkeypatch, "manager")
    assert client.put(f"{shop['base']}/pos/pin", json={"pin": "4826"}, headers=manager).status_code == 200
    setup = client.get(f"{shop['base']}/pos/setup", headers=cashier).json()["data"]
    assert setup["khata"] is True
    shift = _open(cashier, shop)
    customer = {"phone": "+919811100004", "name": "Selvi"}

    need_customer = _sync(cashier, shop, "pos.sale", _counter_sale(shop, shift, [{"method": "khata", "amount": 512}]))
    assert need_customer["status"] == "rejected" and "phone" in need_customer["reason"]
    split = _sync(cashier, shop, "pos.sale", _counter_sale(
        shop, shift, [{"method": "cash", "amount": 200}, {"method": "khata", "amount": 312}], customer=customer))
    assert split["status"] == "applied", split
    look = client.get(f"{shop['base']}/ledger/lookup", params={"phone": "+919811100004"}, headers=cashier).json()["data"]
    acct = look["account"]
    assert acct["balance"] == 312.0
    bill = client.get(f"{shop['base']}/invoices/{split['document_id']}", headers=owner).json()["data"]
    assert bill["on_account"] and bill["amount_paid"] == 200.0 and bill["outstanding"] == 312.0

    # The owner sets a limit; the next khata sale is over it.
    assert client.patch(f"{shop['base']}/ledger/accounts/{acct['id']}", json={"credit_limit": 500},
                        headers=cashier).status_code == 403
    client.patch(f"{shop['base']}/ledger/accounts/{acct['id']}", json={"credit_limit": 500}, headers=owner)
    over = _counter_sale(shop, shift, [{"method": "khata", "amount": 512}], customer=customer)
    refused = _sync(cashier, shop, "pos.sale", over)
    assert refused["status"] == "rejected" and "limit" in refused["reason"]
    pin = client.post(f"{shop['base']}/pos/approve", json={"approver_id": str(manager_id), "pin": "4826",
                                                           "action": "credit"}, headers=cashier)
    assert pin.status_code == 200, pin.text
    ok = _sync(cashier, shop, "pos.sale", {**over, "client_bill_id": str(uuid.uuid4()), "credit_approval": pin.json()["data"]["token"]})
    assert ok["status"] == "applied", ok
    [(by,)] = sql("select over_limit_approved_by from ledger_entries where document_id = :d", d=ok["document_id"])
    assert str(by) == str(manager_id)

    # Khata paid off at the counter: the cash is in the drawer.
    pay = _sync(cashier, shop, "pos.khata_payment", {"shift_id": shift["shift"]["id"], "account_id": acct["id"],
                                                     "amount": 300, "method": "cash"})
    assert pay["status"] == "applied" and pay["balance"] == 524.0 and pay["applied"][0]["applied"] == 300.0
    # Goods back from a khata bill go back to the khata; a void takes the credit back.
    line = client.get(f"{shop['base']}/invoices/{split['document_id']}", headers=owner).json()["data"]["lines"][0]
    ret = _sync(cashier, shop, "pos.return", {"shift_id": shift["shift"]["id"], "document_id": split["document_id"],
                                              "lines": [{"original_line_id": line["id"], "quantity": 1}]})
    assert ret["status"] == "applied" and ret["refund_method"] == "khata", ret
    void = _sync(cashier, shop, "pos.void", {"document_id": ok["document_id"], "reason": "Customer changed mind"})
    assert void["status"] == "applied", void
    summary = client.get(f"{shop['base']}/pos/shifts/{shift['shift']['id']}", headers=cashier).json()["data"]["summary"]
    assert summary["khata_given"] == 312.0 and summary["khata_received"] == 300.0
    assert summary["expected_cash"] == 500 + 200 + 300 and summary["refunds"] == 0
    final = client.get(f"{shop['base']}/ledger/accounts/{acct['id']}", headers=owner).json()["data"]
    # 312 on khata + 512 allowed over the limit − 300 paid − 512 returned − 512 voided: ₹500 held for them.
    assert final["balance"] == -500.0 and final["ageing"]["advance"] == 500.0
    _sums_agree(acct["id"])


# ---------------------------------------------------------------- suppliers, statements, roles
@DB
def test_supplier_account_purchases_and_payments(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _shop(owner)
    r = client.post(f"{shop['base']}/ledger/accounts", json={"party_type": "supplier", "display_name": "Ramco Depot",
                                                             "credit_days": 30}, headers=owner)
    sup = r.json()["data"]
    bought = client.post(f"{shop['base']}/ledger/accounts/{sup['id']}/entries", json={
        "kind": "purchase", "amount": 18000, "reference": "RD/2291"}, headers=owner)
    assert bought.status_code == 200 and bought.json()["data"]["balance"] == 18000.0
    assert bought.json()["data"]["entries"][0]["due_date"] == (TODAY + timedelta(days=30)).isoformat()
    paid = client.post(f"{shop['base']}/ledger/accounts/{sup['id']}/payments", json={
        "amount": 8000, "method": "bank_transfer"}, headers=owner).json()["data"]
    assert paid["balance"] == 10000.0 and paid["entries"][0]["kind"] == "payment_made"
    wrong = client.post(f"{shop['base']}/ledger/accounts/{sup['id']}/entries", json={
        "kind": "adjustment", "amount": -100}, headers=owner)
    assert wrong.status_code == 422, "a correction says what it is for"
    future = client.post(f"{shop['base']}/ledger/accounts/{sup['id']}/payments", json={
        "amount": 1, "method": "cash", "entry_date": (TODAY + timedelta(days=2)).isoformat()}, headers=owner)
    assert future.status_code == 422
    assert client.post(f"{shop['base']}/ledger/accounts/{sup['id']}/share", headers=owner).status_code == 409
    totals = client.get(f"{shop['base']}/ledger/accounts?party=supplier", headers=owner).json()["data"]["totals"]
    assert totals["payable"] == 10000.0 and totals["receivable"] == 0
    assert client.patch(f"{shop['base']}/ledger/accounts/{sup['id']}", json={"status": "closed"},
                        headers=owner).status_code == 409, "an account with a balance stays open"


@DB
def test_the_statement_link_shows_only_that_customers_khata(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _shop(owner)
    client.put(f"{shop['base']}/pos/settings", json={"upi_vpa": "sristores@okaxis", "return_window_days": 7},
               headers=owner)
    acct = _account(owner, shop, display_name="Anbu", phone="+919811100005", opening_balance=640)
    other = _account(owner, shop, display_name="Bala", phone="+919811100006", opening_balance=90)
    share = client.post(f"{shop['base']}/ledger/accounts/{acct['id']}/share", headers=owner).json()["data"]
    assert share["phone"] == "+919811100005" and "₹640.00 is due" in share["message"]
    slug = share["path"].split("/")[1]
    public = client.get(f"/v1/public/websites/{slug}/khata/{share['token']}")
    assert public.status_code == 200, public.text
    data = public.json()["data"]
    assert data["name"] == "Anbu" and data["balance"] == 640.0 and "Bala" not in public.text
    assert data["upi_uri"].startswith("upi://pay?pa=sristores@okaxis") and "am=640.00" in data["upi_uri"]
    assert "customer_contact_id" not in data and "phone" not in data
    qr = client.get(f"/v1/public/websites/{slug}/khata/{share['token']}/upi-qr.svg")
    assert qr.status_code == 200 and qr.headers["content-type"].startswith("image/svg+xml")
    assert client.get(f"/v1/public/websites/{slug}/khata/{'x' * 32}").status_code == 404
    assert client.get(f"/v1/public/websites/wrong-slug/khata/{share['token']}").status_code == 404
    st = client.get(f"{shop['base']}/ledger/accounts/{other['id']}/statement", headers=owner).json()["data"]
    assert st["closing"] == 90.0 and st["entries"][0]["kind"] == "opening_balance"
    pdf = client.get(f"{shop['base']}/ledger/accounts/{other['id']}/statement.pdf", headers=owner)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


@DB
def test_roles_cashier_records_accountant_manages_store_keeper_sees_none(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _shop(owner)
    acct = _account(owner, shop, display_name="Chitra", phone="+919811100007", opening_balance=100)
    _, cashier = _join(owner, shop, monkeypatch, "cashier")
    _, accountant = _join(owner, shop, monkeypatch, "accountant")
    _, keeper = _join(owner, shop, monkeypatch, "store_keeper")
    base = f"{shop['base']}/ledger/accounts"
    assert client.get(base, headers=keeper).status_code == 403
    assert client.get(base, headers=cashier).status_code == 200
    assert client.post(f"{base}/{acct['id']}/payments", json={"amount": 50, "method": "cash"},
                       headers=cashier).status_code == 200
    assert client.post(f"{base}/{acct['id']}/entries", json={"kind": "adjustment", "amount": -10, "note": "x"},
                       headers=cashier).status_code == 403
    assert client.post(base, json={"party_type": "supplier", "display_name": "Y"}, headers=cashier).status_code == 403
    assert client.patch(f"{base}/{acct['id']}", json={"credit_limit": 1000}, headers=accountant).status_code == 200
    fixed = client.post(f"{base}/{acct['id']}/entries", json={"kind": "adjustment", "amount": -10,
                                                              "note": "Rounded off at settlement"}, headers=accountant)
    assert fixed.status_code == 200 and fixed.json()["data"]["balance"] == 40.0


@DB
def test_late_khata_reaches_the_owner_and_the_accountant_home(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = _shop(owner)
    acct = _account(owner, shop, display_name="Devi", phone="+919811100008", credit_days=30)
    late = client.post(f"{shop['base']}/ledger/accounts/{acct['id']}/entries", json={
        "kind": "opening_balance", "amount": 900, "note": "From the notebook",
        "entry_date": (TODAY - timedelta(days=45)).isoformat()}, headers=owner)
    assert late.status_code == 200 and late.json()["data"]["ageing"]["overdue"] == 900.0
    home = client.get(f"{shop['base']}/home", headers=owner).json()["data"]
    now = next(b for b in home["bands"] if b["key"] == "now")
    assert any(i["label"] == "khata accounts past due" and i["count"] == 1 for i in now["items"]), now
    _, accountant = _join(owner, shop, monkeypatch, "accountant")
    bands = {b["key"]: b for b in client.get(f"{shop['base']}/home", headers=accountant).json()["data"]["bands"]}
    assert any(i["label"] == "customers owe on khata" for i in bands["unpaid"]["items"])
    assert any(i["label"] == "khata accounts past due" for i in bands["due"]["items"])
    due = client.get(f"{shop['base']}/ledger/accounts?due=true", headers=owner).json()["data"]
    assert [a["id"] for a in due["accounts"]] == [acct["id"]] and due["totals"]["overdue"] == 900.0


# ---------------------------------------------------------------- isolation
async def _ledger_rows(session: AsyncSession, business_id: uuid.UUID) -> None:
    a = (await session.execute(text(
        "insert into ledger_accounts (business_id, party_type, display_name) values (:b, 'supplier', 'S') "
        "returning id"), {"b": business_id})).scalar()
    await session.execute(text(
        "insert into ledger_entries (business_id, account_id, seq, kind, amount, balance_after, entry_date) "
        "values (:b, :a, 1, 'purchase', 10, 10, current_date)"), {"b": business_id, "a": a})


@DB
@pytest.mark.asyncio
@pytest.mark.parametrize("table", ["ledger_accounts", "ledger_entries"])
async def test_ledger_tables_are_tenant_isolated(table: str) -> None:
    async def insert(session: AsyncSession, business_id: uuid.UUID) -> None:
        if table == "ledger_accounts":
            await session.execute(text(
                "insert into ledger_accounts (business_id, party_type, display_name) values (:b, 'supplier', 'S')"),
                {"b": business_id})
        else:
            await _ledger_rows(session, business_id)

    await assert_tenant_isolated(table, insert)
