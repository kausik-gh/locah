"""Per-customer export and erasure (CR-08, CO-01; MD §25.1 DPDP access / erasure).

A signed-in customer downloads what a shop keeps about them and asks it to
delete their details; the shop sees the request on Home, erases once nothing is
open (an order in progress and a khata balance wait), and what the law makes it
keep — the issued bill with the buyer as billed, khata entries — stays on an
anonymous record. Export and erasure are for people who see every location,
erasure needs customers.erase, and requests are tenant-isolated.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_testing.phase_b import assert_tenant_isolated, billing_shop, new_identity, sql
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)


def _shop(owner: dict[str, str]) -> tuple[dict[str, Any], str, dict[str, Any]]:
    shop: dict[str, Any] = dict(billing_shop(client, owner, modules=(
        "customer-relationships", "fulfilment", "ledger", "leads")))
    bid, base = shop["bid"], shop["base"]
    client.post(f"/v1/b/{bid}/marketplace/visibility", json={"visibility": "unlisted"}, headers=owner)
    client.patch(f"/v1/b/{bid}/fulfilment/settings", json={"pickup_enabled": True}, headers=owner)
    slug = client.get(f"/v1/b/{bid}", headers=owner).json()["data"]["slug"]
    item = client.post(f"{base}/products", json={"status": "active", "offering_type": "product", "title": "Ghee 500 ml",
                                                  "price_amount": 400, "hsn_sac": "0405", "tax_rate": 0},
                       headers=owner).json()["data"]
    return shop, slug, item


@DB
def test_a_customer_downloads_their_data_asks_to_be_erased_and_the_shop_erases(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop, slug, item = _shop(owner)
    bid, base = shop["bid"], shop["base"]
    me, customer = new_identity(monkeypatch)
    placed = client.post(f"/v1/public/websites/{slug}/checkout", json={
        "items": [{"offering_id": item["id"], "quantity": 1}], "fulfilment_mode": "pickup", "payment_method": "cod",
        "guest": {"name": "Meena Sundar", "phone": "+919840022001"}}, headers=customer)
    assert placed.status_code == 200, placed.text
    order_id = placed.json()["data"]["order"]["id"]
    contact = sql("select customer_contact_id from orders_orders where id = :o", o=order_id)[0][0]
    client.patch(f"{base}/customers/{contact}", json={"tags": ["regular"]}, headers=owner)
    client.post(f"{base}/customers/{contact}/notes", json={"body": "Prefers the cow ghee"}, headers=owner)
    client.post(f"{base}/customers/{contact}/consents", json={"purpose": "marketing", "channel": "whatsapp",
                                                             "granted": True, "source": "staff_recorded"}, headers=owner)
    bill = client.post(f"{base}/invoices", json={"issue": True, "customer_contact_id": str(contact),
                                                 "buyer": {"name": "Meena Sundar"},
                                                 "lines": [{"offering_id": item["id"], "quantity": 2}]}, headers=owner)
    assert bill.status_code == 200, bill.text
    acct = client.post(f"{base}/ledger/accounts", json={"party_type": "customer", "customer_contact_id": str(contact),
                                                         "opening_balance": 150}, headers=owner).json()["data"]
    lead = client.post(f"{base}/leads", json={"display_name": "Meena Sundar", "phone": "+919840022001",
                                              "message": "Do you deliver to Adyar?"}, headers=owner)
    assert lead.status_code == 200, lead.text
    sql("update leads_leads set customer_contact_id = :c where id = :l", c=contact, l=lead.json()["data"]["id"])
    channel = sql("insert into messaging_channels (business_id, provider) values (:b, 'meta_cloud') returning id",
                  b=bid)[0][0]
    conv = sql("insert into messaging_conversations (business_id, channel_id, contact_id, wa_id, kind, profile_name) "
               "values (:b, :ch, :c, '919840022001', 'customer', 'Meena') returning id", b=bid, ch=channel, c=contact)[0][0]
    sql("insert into messaging_messages (business_id, conversation_id, direction, kind, body, status) "
        "values (:b, :cv, 'in', 'text', 'Is the ghee fresh?', 'received')", b=bid, cv=conv)

    # the customer downloads what the shop keeps about them
    mine = client.get(f"/v1/me/businesses/{slug}/my-data", headers=customer)
    assert mine.status_code == 200, mine.text
    data = mine.json()["data"]
    assert data["records"][0]["display_name"] == "Meena Sundar" and data["records"][0]["tags"] == ["regular"]
    assert data["orders"][0]["items"][0]["item"] == "Ghee 500 ml" and len(data["bills"]) == 1
    assert data["notes"][0]["body"] == "Prefers the cow ghee" and data["consents"][0]["purpose"] == "marketing"
    assert data["khata"][0]["balance"] == 150.0 and data["enquiries"][0]["message"] == "Do you deliver to Adyar?"
    assert data["whatsapp_messages"][0]["body"] == "Is the ghee fresh?"
    _, stranger = new_identity(monkeypatch)
    assert client.get(f"/v1/me/businesses/{slug}/my-data", headers=stranger).status_code == 404

    # ... and asks for their details to be deleted: the owner sees it on Home
    asked = client.post(f"/v1/me/businesses/{slug}/erasure-request", json={"note": "Please delete my number"},
                        headers=customer)
    assert asked.status_code == 200 and asked.json()["data"] == {"requested": True, "already": False}
    again = client.post(f"/v1/me/businesses/{slug}/erasure-request", json={}, headers=customer)
    assert again.json()["data"]["already"] is True
    home = client.get(f"{base}/home", headers=owner).json()["data"]
    now = {i["label"]: i for b in home["bands"] if b["key"] == "now" for i in b["items"]}
    assert now["customers asked you to delete their details"]["count"] == 1
    assert "Meena Sundar" in now["customers asked you to delete their details"]["detail"]

    # erasure waits for the open order and the khata balance, and needs the name typed
    privacy = client.get(f"{base}/customers/{contact}/privacy", headers=owner).json()["data"]
    assert privacy["open"] == ["1 order still in progress", "a khata balance of ₹150 they owe"]
    assert privacy["requests"][0]["kind"] == "erasure" and privacy["requests"][0]["status"] == "open"
    blocked = client.post(f"{base}/customers/{contact}/erase", json={"confirm": "Meena Sundar"}, headers=owner)
    assert blocked.status_code == 409 and "still in progress" in blocked.text
    client.post(f"{base}/orders/{order_id}/cancel", json={"reason": "Customer asked"}, headers=owner)
    client.post(f"{base}/ledger/accounts/{acct['id']}/payments", json={"amount": 150, "method": "cash"}, headers=owner)
    wrong = client.post(f"{base}/customers/{contact}/erase", json={"confirm": "Meena"}, headers=owner)
    assert wrong.status_code == 422
    done = client.post(f"{base}/customers/{contact}/erase", json={"confirm": "meena  sundar", "reason": "Asked by customer"},
                       headers=owner)
    assert done.status_code == 200, done.text
    result = done.json()["data"]
    assert result["removed"]["notes"] == 1 and result["removed"]["whatsapp_chats"] == 1
    assert any("72 months" in k["for"] for k in result["kept"])

    row = sql("select display_name, phone, email, tags, identity_id, erased_at is not null from "
              "customer_relationships_contacts where id = :c", c=contact)[0]
    assert row == ("Erased customer", None, None, [], None, True)
    assert sql("select count(*) from customer_relationships_notes where contact_id = :c", c=contact) == [(0,)]
    assert sql("select count(*) from messaging_conversations where contact_id = :c", c=contact) == [(0,)]
    assert sql("select display_name, phone, message from leads_leads where customer_contact_id = :c", c=contact) == \
        [("Erased customer", None, None)]
    assert sql("select display_name, phone from ledger_accounts where id = :a", a=acct["id"]) == [("Erased customer", None)]
    kept = sql("select buyer->>'name', grand_total from invoicing_documents where id = :d", d=bill.json()["data"]["id"])
    assert kept == [("Meena Sundar", 800)], "the issued bill keeps the buyer as billed (GST law)"
    assert sql("select count(*) from customer_consents where contact_id = :c and withdrawn_at is null", c=contact) == [(0,)]
    assert sql("select status from customer_relationships_privacy_requests where contact_id = :c and kind = 'erasure'",
               c=contact) == [("done",)]
    audit = sql("select after_state::text from platform_audit_events where resource_id = :c and event_type = 'customer.erased'",
                c=contact)
    assert audit and "Meena" not in audit[0][0], "the audit says who erased and when — not the erased details"
    assert client.post(f"{base}/customers/{contact}/erase", json={"confirm": "Erased customer"},
                       headers=owner).status_code == 409
    assert client.get(f"/v1/me/businesses/{slug}/my-data", headers=customer).status_code == 404, \
        "the erased record is no longer linked to their account"
    assert sql("select count(*) from consumer_activity_projections where identity_id = :i and business_id = :b",
               i=me, b=bid) == [(0,)]


@DB
def test_who_may_export_erase_and_decline(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop, slug, item = _shop(owner)
    bid, base = shop["bid"], shop["base"]
    contact = client.post(f"{base}/customers", json={"display_name": "Kumar", "phone": "+919840022009"},
                          headers=owner).json()["data"]["id"]
    person, manager = new_identity(monkeypatch)
    inv = client.post(f"/v1/b/{bid}/team/invitations", json={"identity_id": str(person), "role": "member"},
                      headers=owner).json()["data"]["id"]
    client.post(f"/v1/b/{bid}/team/members/{inv}/activate", headers=owner)
    branch = client.post(f"{base}/locations", json={"name": "Branch"}, headers=owner).json()["data"]["id"]
    client.put(f"{base}/members/{inv}/role", json={"role": "manager", "location_ids": [branch]}, headers=owner)
    assert client.post(f"{base}/customers/{contact}/erase", json={"confirm": "Kumar"}, headers=manager).status_code == 403
    exported = client.get(f"{base}/customers/{contact}/export", headers=manager)
    assert exported.status_code == 403, "a branch manager cannot export every location's records"
    full = client.get(f"{base}/customers/{contact}/export", headers=owner)
    assert full.status_code == 200 and full.json()["data"]["records"][0]["display_name"] == "Kumar"
    assert sql("select kind, status, source from customer_relationships_privacy_requests where contact_id = :c",
               c=contact) == [("access", "done", "staff")]
    req = sql("insert into customer_relationships_privacy_requests (business_id, contact_id, kind, source) "
              "values (:b, :c, 'erasure', 'customer') returning id", b=bid, c=contact)[0][0]
    assert client.post(f"{base}/customers/privacy-requests/{req}/decline", json={"reason": " "},
                       headers=owner).status_code == 422
    declined = client.post(f"{base}/customers/privacy-requests/{req}/decline",
                           json={"reason": "Money is still owed on an open job"}, headers=owner)
    assert declined.status_code == 200
    assert client.get(f"{base}/customers/privacy-requests", headers=owner).json()["data"] == []
    _, other = new_identity(monkeypatch)
    from platform_testing.phase_b import create_business

    create_business(client, other)
    assert client.get(f"{base}/customers/{contact}/export", headers=other).status_code in (403, 404)


@pytest.mark.asyncio
@DB
async def test_privacy_requests_are_tenant_isolated() -> None:
    async def insert(session: AsyncSession, business_id: uuid.UUID) -> None:
        cid = (await session.execute(text(
            "INSERT INTO customer_relationships_contacts (business_id, display_name) VALUES (:b, 'X') RETURNING id"),
            {"b": business_id})).scalar()
        await session.execute(text(
            "INSERT INTO customer_relationships_privacy_requests (business_id, contact_id, kind, source) "
            "VALUES (:b, :c, 'access', 'staff')"), {"b": business_id, "c": cid})

    await assert_tenant_isolated("customer_relationships_privacy_requests", insert)
