"""Customer tags and rule-built segments (CR-03, CR-04; MD §6.1; §18.2 Audiences).

Pure tests pin rule validation, words and which rules a business is offered.
Database tests build a bakery's customers from real orders, a counter bill, a
khata balance, a lapsed customer and an ended membership, then check each rule
and their combination, the WhatsApp-offer count from the consent store, tag
filtering, the location scope of a branch manager, and tenant isolation.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_core.customers.segments import available, clean_rules, words
from platform_core.exceptions import ValidationError
from platform_testing.phase_b import (
    assert_tenant_isolated,
    billing_shop,
    create_business,
    new_identity,
    primary_location,
    sql,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)
OFFERING = str(uuid.uuid4())


# ---------------------------------------------------------------- pure
def test_rules_are_validated_and_offered_only_with_their_tool() -> None:
    kinds = {k["kind"] for k in available({"orders"})}
    assert {"bought", "spent", "lapsed", "new", "tag"} <= kinds and not {"booked", "owes", "membership_ended"} & kinds
    rules = clean_rules([{"kind": "bought", "offering_id": OFFERING, "times": "2", "days": 60},
                         {"kind": "tag", "tag": "  Regular   Customer "}], {"orders"})
    assert rules[0] == {"kind": "bought", "offering_id": OFFERING, "times": 2, "days": 60}
    assert rules[1] == {"kind": "tag", "tag": "regular customer"}
    assert words(rules[0], {OFFERING: "Custom cake"}) == "Bought Custom cake 2+ times in the last 60 days"
    assert words({"kind": "membership_ended", "from_days": 15, "to_days": 60}) == \
        "Membership ended 15–60 days ago and not renewed"
    assert words({"kind": "spent", "amount": "5000", "days": 90}) == "Spent ₹5,000+ in the last 90 days"
    for bad in ([], [{"kind": "nearby"}], [{"kind": "booked", "times": 2, "days": 30}],
                [{"kind": "spent", "amount": "-1", "days": 30}], [{"kind": "lapsed", "days": 0}],
                [{"kind": "membership_ended", "from_days": 60, "to_days": 15}], [{"kind": "tag", "tag": ""}],
                [{"kind": "new", "days": 5}] * 7):
        with pytest.raises(ValidationError):
            clean_rules(bad, {"orders", "memberships"})


# ---------------------------------------------------------------- database
def _customer(base: str, owner: dict[str, str], name: str, phone: str, tags: list[str] | None = None) -> str:
    r = client.post(f"{base}/customers", json={"display_name": name, "phone": phone, "tags": tags or []}, headers=owner)
    assert r.status_code == 200, r.text
    return str(r.json()["data"]["id"])


def _order(base: str, owner: dict[str, str], loc: str, contact: str, item: str, qty: int = 1) -> str:
    r = client.post(f"{base}/orders", json={"location_id": loc, "payment_method": "pay_at_business",
                                            "channel": "phone", "customer_contact_id": contact,
                                            "items": [{"offering_id": item, "quantity": qty}]}, headers=owner)
    assert r.status_code == 200, r.text
    return str(r.json()["data"]["id"])


def _preview(base: str, owner: dict[str, str], rules: list[dict[str, Any]]) -> dict[str, Any]:
    r = client.post(f"{base}/customers/segments/preview", json={"rules": rules}, headers=owner)
    assert r.status_code == 200, r.text
    return cast(dict[str, Any], r.json()["data"])


def _names(found: dict[str, Any]) -> list[str]:
    return sorted(m["display_name"] for m in found["members"])


@DB
def test_segments_are_worked_out_from_real_records(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = billing_shop(client, owner, modules=("customer-relationships", "ledger", "pos"))
    base, loc = shop["base"], shop["loc"]
    cake = client.post(f"{base}/products", json={"status": "active", "offering_type": "product", "title": "Plum cake",
                                                  "price_amount": 800, "hsn_sac": "1905", "tax_rate": 0},
                       headers=owner).json()["data"]["id"]
    buns = client.post(f"{base}/products", json={"status": "active", "offering_type": "product", "title": "Buns",
                                                  "price_amount": 60, "hsn_sac": "1905", "tax_rate": 0},
                       headers=owner).json()["data"]["id"]
    asha = _customer(base, owner, "Asha", "+919840000001", ["Regular", "vip"])
    ravi = _customer(base, owner, "Ravi", "+919840000002")
    meena = _customer(base, owner, "Meena", "+919840000003", ["regular"])
    kumar = _customer(base, owner, "Kumar", "+919840000004")
    for _ in range(3):
        _order(base, owner, loc, asha, cake)
    _order(base, owner, loc, ravi, buns, qty=2)
    cancelled = _order(base, owner, loc, ravi, cake)
    client.post(f"{base}/orders/{cancelled}/cancel", json={"reason": "Changed mind"}, headers=owner)
    # Meena buys at the counter: a bill with no order, ₹6,400
    bill = client.post(f"{base}/invoices", json={"issue": True, "customer_contact_id": meena,
                                                 "lines": [{"offering_id": cake, "quantity": 8}]}, headers=owner)
    assert bill.status_code == 200, bill.text
    # Kumar bought once, 120 days ago
    old = _order(base, owner, loc, kumar, cake)
    sql("update orders_orders set created_at = now() - interval '120 days' where id = :o", o=old)
    # Ravi owes ₹500 on khata
    acct = client.post(f"{base}/ledger/accounts", json={"party_type": "customer", "customer_contact_id": ravi,
                                                         "opening_balance": 500}, headers=owner)
    assert acct.status_code == 200, acct.text
    # Asha and Meena said yes to offers on WhatsApp; Meena later withdrew
    for who, granted in ((asha, True), (meena, True), (meena, False)):
        r = client.post(f"{base}/customers/{who}/consents", json={
            "purpose": "marketing", "channel": "whatsapp", "granted": granted, "source": "staff_recorded"}, headers=owner)
        assert r.status_code == 200, r.text

    bought = _preview(base, owner, [{"kind": "bought", "offering_id": cake, "times": 2, "days": 60}])
    assert _names(bought) == ["Asha"] and bought["rule_words"] == ["Bought Plum cake 2+ times in the last 60 days"]
    assert _names(_preview(base, owner, [{"kind": "bought", "offering_id": cake, "times": 1, "days": 60}])) == \
        ["Asha", "Meena"], "a counter bill counts; a cancelled order and one 120 days ago do not"
    assert _names(_preview(base, owner, [{"kind": "spent", "amount": 2000, "days": 30}])) == ["Asha", "Meena"]
    assert _names(_preview(base, owner, [{"kind": "lapsed", "days": 90}])) == ["Kumar"]
    assert _names(_preview(base, owner, [{"kind": "owes"}])) == ["Ravi"]
    assert _names(_preview(base, owner, [{"kind": "tag", "tag": "regular"}])) == ["Asha", "Meena"]
    both = _preview(base, owner, [{"kind": "tag", "tag": "Regular"}, {"kind": "spent", "amount": 2000, "days": 30}])
    assert both["count"] == 2 and both["whatsapp_offers"] == 1, "only Asha still said yes to WhatsApp offers"
    assert _names(_preview(base, owner, [{"kind": "new", "days": 7}])) == ["Asha", "Kumar", "Meena", "Ravi"]
    off = client.post(f"{base}/customers/segments/preview", json={"rules": [{"kind": "booked", "times": 1, "days": 30}]},
                      headers=owner)
    assert off.status_code == 422 and "switched off" in off.text

    # save, open, rename, archive
    made = client.post(f"{base}/customers/segments", json={"name": "Cake regulars", "rules": [
        {"kind": "bought", "offering_id": cake, "times": 2, "days": 60}]}, headers=owner)
    assert made.status_code == 200, made.text
    seg = made.json()["data"]
    assert seg["count"] == 1 and seg["rule_words"] == ["Bought Plum cake 2+ times in the last 60 days"]
    dup = client.post(f"{base}/customers/segments", json={"name": "cake regulars", "rules": [{"kind": "owes"}]},
                      headers=owner)
    assert dup.status_code == 409
    _order(base, owner, loc, ravi, cake)
    _order(base, owner, loc, ravi, cake)
    opened = client.get(f"{base}/customers/segments/{seg['id']}", headers=owner).json()["data"]
    assert [m["display_name"] for m in opened["members"]] == ["Asha", "Ravi"], "members are worked out each time"
    listed = client.get(f"{base}/customers/segments", headers=owner).json()
    assert [s["name"] for s in listed["data"]] == ["Cake regulars"] and listed["data"][0]["count"] == 2
    assert {"bought", "owes", "tag"} <= {k["kind"] for k in listed["meta"]["rules"]}
    renamed = client.patch(f"{base}/customers/segments/{seg['id']}", json={"name": "Cake lovers", "version": seg["version"]},
                           headers=owner)
    assert renamed.status_code == 200 and renamed.json()["data"]["name"] == "Cake lovers"
    stale = client.patch(f"{base}/customers/segments/{seg['id']}", json={"name": "X", "version": seg["version"]},
                         headers=owner)
    assert stale.status_code == 409
    assert client.post(f"{base}/customers/segments/{seg['id']}/archive", headers=owner).status_code == 200
    assert client.get(f"{base}/customers/segments/{seg['id']}", headers=owner).status_code == 404

    # tags: the list with counts, and the customer list filtered by one
    tags = client.get(f"{base}/customers/tags", headers=owner).json()["data"]
    assert tags[0] == {"tag": "regular", "count": 2} and {"tag": "vip", "count": 1} in tags
    tagged = client.get(f"{base}/customers", params={"tag": "VIP"}, headers=owner).json()["data"]
    assert [c["display_name"] for c in tagged] == ["Asha"]


@DB
def test_a_branch_manager_counts_their_branch_and_others_see_nothing(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("offerings-catalog", "orders", "customer-relationships"))
    base = f"/v1/platform/businesses/{bid}"
    a = primary_location(client, owner, bid)
    b = client.post(f"{base}/locations", json={"name": "Branch"}, headers=owner).json()["data"]["id"]
    item = client.post(f"{base}/products", json={"title": "Cake", "status": "active", "price_amount": 1000,
                                                  "sku": f"C-{uuid.uuid4().hex[:6]}"}, headers=owner).json()["data"]["id"]
    asha = _customer(base, owner, "Asha", "+919840000011")
    _order(base, owner, a, asha, item, qty=3)
    _order(base, owner, b, asha, item, qty=3)
    rule = [{"kind": "spent", "amount": 5000, "days": 30}]
    assert _preview(base, owner, rule)["count"] == 1, "₹6,000 across both locations"
    person, manager = new_identity(monkeypatch)
    inv = client.post(f"/v1/b/{bid}/team/invitations", json={"identity_id": str(person), "role": "member"},
                      headers=owner).json()["data"]["id"]
    client.post(f"/v1/b/{bid}/team/members/{inv}/activate", headers=owner)
    client.put(f"{base}/members/{inv}/role", json={"role": "manager", "location_ids": [b]}, headers=owner)
    r = client.post(f"{base}/customers/segments/preview", json={"rules": rule}, headers=manager)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["count"] == 0, "the branch manager's segment counts only the branch's ₹3,000"
    lower = client.post(f"{base}/customers/segments/preview", json={"rules": [
        {"kind": "spent", "amount": 3000, "days": 30}]}, headers=manager).json()["data"]
    assert lower["count"] == 1
    _, other = new_identity(monkeypatch)
    create_business(client, other)
    assert client.post(f"{base}/customers/segments/preview", json={"rules": rule}, headers=other).status_code in (403, 404)
    assert client.get(f"{base}/customers/tags", headers=other).status_code in (403, 404)


@pytest.mark.asyncio
@DB
async def test_segments_are_tenant_isolated() -> None:
    async def insert(session: AsyncSession, business_id: uuid.UUID) -> None:
        await session.execute(text(
            "INSERT INTO customer_relationships_segments (business_id, name, rules) "
            "VALUES (:b, :n, '[{\"kind\": \"owes\"}]'::jsonb)"), {"b": business_id, "n": f"S {uuid.uuid4().hex[:6]}"})

    await assert_tenant_isolated("customer_relationships_segments", insert)



@DB
def test_booked_and_membership_ended_rules(monkeypatch: Any) -> None:
    from datetime import datetime, timedelta, timezone

    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("offerings-catalog", "workforce", "bookings", "payments",
                                                  "memberships", "customer-relationships"))
    base = f"/v1/platform/businesses/{bid}"
    loc = primary_location(client, owner, bid)
    service = client.post(f"{base}/products", json={"title": "Haircut", "offering_type": "service",
                                                    "status": "active", "price_amount": 300}, headers=owner).json()["data"]
    priya = _customer(base, owner, "Priya", "+919840000021")
    arun = _customer(base, owner, "Arun", "+919840000022")
    lakshmi = _customer(base, owner, "Lakshmi", "+919840000023")
    now = datetime.now(timezone.utc)
    for days_ago in (3, 10, 20):
        start = now - timedelta(days=days_ago)
        r = client.post(f"{base}/bookings", json={
            "location_id": loc, "offering_id": service["id"], "reservation_mode": "appointment",
            "customer_contact_id": priya, "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(minutes=30)).isoformat()}, headers=owner)
        assert r.status_code == 200, r.text
    assert _names(_preview(base, owner, [{"kind": "booked", "times": 3, "days": 30}])) == ["Priya"]
    assert _preview(base, owner, [{"kind": "booked", "times": 3, "days": 15}])["count"] == 0
    plan = sql("insert into memberships_plans (business_id, name) values (:b, 'Monthly') returning id", b=bid)[0][0]
    for who, ended, status in ((arun, 30, "expired"), (lakshmi, 30, "expired"), (lakshmi, -20, "active")):
        sql("insert into memberships_enrolments (business_id, plan_id, customer_contact_id, starts_at, ends_at, status) "
            "values (:b, :p, :c, now() - interval '60 days', now() - make_interval(days => :e), :s)",
            b=bid, p=plan, c=who, e=ended, s=status)
    lapsed = _preview(base, owner, [{"kind": "membership_ended", "from_days": 15, "to_days": 60}])
    assert _names(lapsed) == ["Arun"], "Lakshmi renewed, so she is not in it"
