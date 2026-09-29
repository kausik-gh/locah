"""Assignment scope (Capability Universe §7.2–§7.3, §24 #11; P2-01).

"Assignment is the new security primitive." A provider sees and changes only
their own appointments and the customers on them; a sales executive only the
enquiries assigned to them and the quotes for those customers. These tests give
people those roles through the API and check what the server lets them see and
do — and that the database's restrictive policies repeat the rule.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from platform_testing.phase_b import create_business, db_url, new_identity, primary_location

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)


def _join(owner: dict[str, str], bid: str, monkeypatch: Any, role: str) -> tuple[uuid.UUID, str, dict[str, str]]:
    person, headers = new_identity(monkeypatch)
    inv = client.post(f"/v1/b/{bid}/team/invitations", json={"identity_id": str(person), "role": "member"},
                      headers=owner)
    assert inv.status_code == 200, inv.text
    mid = inv.json()["data"]["id"]
    assert client.post(f"/v1/b/{bid}/team/members/{mid}/activate", headers=owner).status_code == 200
    given = client.put(f"/v1/platform/businesses/{bid}/members/{mid}/role", json={"role": role}, headers=owner)
    assert given.status_code == 200, given.text
    return person, mid, headers


def _customer(owner: dict[str, str], bid: str, name: str) -> str:
    r = client.post(f"/v1/platform/businesses/{bid}/customers", json={
        "display_name": name, "phone": f"98{uuid.uuid4().int % 10**8:08d}"}, headers=owner)
    assert r.status_code == 200, r.text
    return str(r.json()["data"]["id"])


def _provider(owner: dict[str, str], bid: str, loc: str, name: str, identity: uuid.UUID | None = None) -> str:
    body: dict[str, Any] = {"display_name": name, "location_ids": [loc], "primary_location_id": loc}
    if identity:
        body["identity_id"] = str(identity)
    r = client.post(f"/v1/platform/businesses/{bid}/workforce/members", json=body, headers=owner)
    assert r.status_code == 200, r.text
    return str(r.json()["data"]["id"])


def _book(owner: dict[str, str], bid: str, loc: str, provider: str, customer: str, title: str,
          hours: float) -> str:
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) + timedelta(hours=hours)
    r = client.post(f"/v1/platform/businesses/{bid}/bookings", json={
        "location_id": loc, "provider_id": provider, "customer_contact_id": customer, "title": title,
        "reservation_mode": "appointment", "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(minutes=45)).isoformat()}, headers=owner)
    assert r.status_code == 200, r.text
    return str(r.json()["data"]["id"])


def _salon(owner: dict[str, str]) -> tuple[str, str]:
    bid = create_business(client, owner, business_type="salon",
                          modules=("workforce", "bookings", "offerings-catalog", "payments", "customer-relationships"))
    return bid, primary_location(client, owner, bid)


def test_catalogue_offers_provider_and_sales_executive_once_their_modules_run(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    salon, _ = _salon(owner)
    keys = [t["key"] for t in client.get(f"/v1/platform/businesses/{salon}/roles", headers=owner).json()["data"]["templates"]]
    assert "provider" in keys and "sales_executive" not in keys
    firm = create_business(client, owner, modules=("leads", "customer-relationships"))
    keys = [t["key"] for t in client.get(f"/v1/platform/businesses/{firm}/roles", headers=owner).json()["data"]["templates"]]
    assert "sales_executive" in keys and "provider" not in keys
    # A custom role limited to its assignments may hold booking/enquiry permissions only.
    ok = client.post(f"/v1/platform/businesses/{firm}/roles/custom", json={
        "name": "Field sales", "permissions": ["leads.read", "leads.update_status"], "scope": "assignment"},
        headers=owner)
    assert ok.status_code == 200 and ok.json()["data"]["scope"] == "assignment", ok.text
    wide = client.post(f"/v1/platform/businesses/{firm}/roles/custom", json={
        "name": "Field sales plus", "permissions": ["leads.read", "customers.update"], "scope": "assignment"},
        headers=owner)
    assert wide.status_code == 422 and wide.json()["error"]["details"]["not_assignable"] == ["customers.update"]


def test_provider_sees_and_changes_only_their_own_appointments(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, loc = _salon(owner)
    base = f"/v1/platform/businesses/{bid}"
    anbu, _, anbu_h = _join(owner, bid, monkeypatch, "provider")
    mine = _provider(owner, bid, loc, "Anbu", anbu)
    other = _provider(owner, bid, loc, "Bala")
    meena, ravi = _customer(owner, bid, "Meena"), _customer(owner, bid, "Ravi")
    my_booking = _book(owner, bid, loc, mine, meena, "Haircut", 1)
    their_booking = _book(owner, bid, loc, other, ravi, "Facial", 2)

    seen = client.get(f"{base}/bookings", headers=anbu_h)
    assert seen.status_code == 200, seen.text
    assert [b["id"] for b in seen.json()["data"]] == [my_booking]
    assert len(client.get(f"{base}/bookings", headers=owner).json()["data"]) == 2
    assert client.get(f"{base}/bookings/{my_booking}", headers=anbu_h).status_code == 200
    assert client.get(f"{base}/bookings/{their_booking}", headers=anbu_h).status_code == 404

    customers = client.get(f"{base}/customers", headers=anbu_h)
    assert customers.status_code == 200, customers.text
    assert [c["id"] for c in customers.json()["data"]] == [meena]
    assert client.get(f"{base}/customers/{ravi}", headers=anbu_h).status_code == 404

    # They can move their own appointment along, not someone else's.
    ok = client.post(f"{base}/bookings/{my_booking}/status", json={"status": "confirmed"}, headers=anbu_h)
    assert ok.status_code == 200, ok.text
    no = client.post(f"{base}/bookings/{their_booking}/status", json={"status": "confirmed"}, headers=anbu_h)
    assert no.status_code == 404, no.text
    # Their own booking notes, not anyone else's.
    assert client.post(f"{base}/bookings/{my_booking}/notes", json={"body": "Prefers a trim"},
                       headers=anbu_h).status_code == 200
    assert client.post(f"{base}/bookings/{their_booking}/notes", json={"body": "x"}, headers=anbu_h).status_code == 404
    assert client.get(f"{base}/bookings/{their_booking}/notes", headers=anbu_h).status_code == 404
    assert client.get(f"{base}/bookings/{their_booking}/history", headers=anbu_h).status_code == 404
    # A provider cannot create bookings at all (the template does not hold it).
    assert client.post(f"{base}/bookings", json={"location_id": loc, "starts_at": "2030-01-01T10:00:00Z",
                                                 "ends_at": "2030-01-01T11:00:00Z"}, headers=anbu_h).status_code == 403

    # Their numbers count their own appointments only.
    def booked(h: dict[str, str]) -> Any:
        cards = client.get(f"{base}/insights?period=today", headers=h).json()["data"]["cards"]
        return next(c for c in cards if c["key"] == "bookings")["value"]

    if booked(owner) == "2":  # both appointments fall on today's date in India
        assert booked(anbu_h) == "1"

    home = client.get(f"{base}/home", headers=anbu_h)
    assert home.status_code == 200, home.text
    body = home.json()["data"]
    assert body["role"]["key"] == "provider" and body["role"]["question"] == "My next appointment and my day"
    band = body["bands"][0]
    assert band["key"] == "myday" and [i["label"] for i in band["items"]] in (["Haircut"], [])


def test_sales_executive_works_only_their_enquiries_and_quotes(monkeypatch: Any) -> None:
    owner_id, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("offerings-catalog", "leads", "quotes", "customer-relationships"))
    base = f"/v1/platform/businesses/{bid}"
    priya, _, priya_h = _join(owner, bid, monkeypatch, "sales_executive")
    mine = client.post(f"{base}/leads", json={"display_name": "Kavin Interiors", "phone": "9876500011",
                                              "assignee_identity_id": str(priya)}, headers=owner).json()["data"]
    theirs = client.post(f"{base}/leads", json={"display_name": "Lakshmi Homes", "phone": "9876500022",
                                                "assignee_identity_id": str(owner_id)}, headers=owner).json()["data"]
    nobody = client.post(f"{base}/leads", json={"display_name": "Walk-in", "phone": "9876500033"},
                         headers=owner).json()["data"]

    listed = client.get(f"{base}/leads", headers=priya_h)
    assert listed.status_code == 200, listed.text
    assert [x["id"] for x in listed.json()["data"]] == [mine["id"]]
    for other in (theirs, nobody):
        assert client.get(f"{base}/leads/{other['id']}", headers=priya_h).status_code == 404

    # An enquiry they add is theirs; they cannot hand it to someone else.
    made = client.post(f"{base}/leads", json={"display_name": "Site visit Adyar", "phone": "9876500044"},
                       headers=priya_h)
    assert made.status_code == 200, made.text
    assert made.json()["data"]["assignee_identity_id"] == str(priya)
    handed = client.post(f"{base}/leads", json={"display_name": "For the owner", "phone": "9876500055",
                                                "assignee_identity_id": str(owner_id)}, headers=priya_h)
    assert handed.status_code == 403 and handed.json()["error"]["details"]["permission"] == "assignment_scope"

    # Winning their enquiry makes a customer they can then see and quote.
    for status in ("contacted", "won"):
        moved = client.post(f"{base}/leads/{mine['id']}/move-stage", json={"status": status}, headers=priya_h)
        assert moved.status_code == 200, moved.text
    contact = moved.json()["data"]["customer_contact_id"]
    assert contact and [c["id"] for c in client.get(f"{base}/customers", headers=priya_h).json()["data"]] == [contact]
    quote = client.post(f"{base}/quotes", json={"customer_contact_id": contact, "title": "Modular kitchen",
                                                "items": [{"title": "Cabinets", "unit_price": 85000}]},
                        headers=priya_h)
    assert quote.status_code == 200, quote.text
    owners_quote = client.post(f"{base}/quotes", json={"title": "Owner's own", "items": [
        {"title": "Survey", "unit_price": 1500}]}, headers=owner)
    assert owners_quote.status_code == 200, owners_quote.text
    quotes = client.get(f"{base}/quotes", headers=priya_h)
    assert quotes.status_code == 200, quotes.text
    assert [q["id"] for q in quotes.json()["data"]["quotes"]] == [quote.json()["data"]["id"]]
    assert client.get(f"{base}/quotes/{owners_quote.json()['data']['id']}", headers=priya_h).status_code == 404
    assert len(client.get(f"{base}/quotes", headers=owner).json()["data"]["quotes"]) == 2

    home = client.get(f"{base}/home", headers=priya_h).json()["data"]
    assert home["role"]["key"] == "sales_executive"
    assert home["bands"][0]["key"] == "followups"
    assert [i["label"] for i in home["bands"][0]["items"]] == ["Site visit Adyar"]


def test_database_repeats_the_assignment_limit(monkeypatch: Any) -> None:
    """Defence in depth: with the API role and app.current_assignee bound, the database itself returns only
    that person's bookings and enquiries, and refuses to hand one to someone else."""
    owner_id, owner = new_identity(monkeypatch)
    bid, loc = _salon(owner)
    for mid in ("leads",):
        assert client.post(f"/v1/b/{bid}/modules/{mid}/enable", headers=owner).status_code == 200
    anbu, _ = new_identity(monkeypatch)
    mine = _provider(owner, bid, loc, "Anbu", anbu)
    other = _provider(owner, bid, loc, "Bala")
    cust = _customer(owner, bid, "Meena")
    _book(owner, bid, loc, mine, cust, "Haircut", 3)
    _book(owner, bid, loc, other, cust, "Facial", 4)
    for who in (anbu, owner_id):
        r = client.post(f"/v1/platform/businesses/{bid}/leads", json={
            "display_name": f"Lead {who}", "phone": "9876500099", "assignee_identity_id": str(who)}, headers=owner)
        assert r.status_code == 200, r.text

    async def run() -> tuple[int, int, int, int, int]:
        engine = create_async_engine(db_url(), poolclass=NullPool)
        try:
            async with AsyncSession(engine) as s:
                await s.execute(text("set local role platform_api"))
                await s.execute(text("select set_config('app.current_business_id', :b, true)"), {"b": bid})
                all_bookings = (await s.execute(text("select count(*) from bookings_bookings"))).scalar_one()
                await s.execute(text("select set_config('app.current_assignee', :a, true)"), {"a": str(anbu)})
                my_bookings = (await s.execute(text("select count(*) from bookings_bookings"))).scalar_one()
                my_leads = (await s.execute(text("select count(*) from leads_leads"))).scalar_one()
                touched = len((await s.execute(text(
                    "update bookings_bookings set updated_at = now() where provider_id = :p returning id"),
                    {"p": other})).all())
                await s.execute(text("savepoint handover"))
                try:
                    await s.execute(text("update leads_leads set assignee_identity_id = :o returning id"),
                                    {"o": str(owner_id)})
                    refused = 0
                except Exception:
                    refused = 1
                await s.rollback()
                return int(all_bookings), int(my_bookings), int(my_leads), touched, refused
        finally:
            await engine.dispose()

    assert asyncio.run(run()) == (2, 1, 1, 0, 1)


def test_a_provider_cannot_change_the_business_booking_rules(monkeypatch: Any) -> None:
    """bookings.update lets a provider move their own appointments along — not set the deposit policy."""
    _, owner = new_identity(monkeypatch)
    bid, _ = _salon(owner)
    _, _, anbu_h = _join(owner, bid, monkeypatch, "provider")
    url = f"/v1/platform/businesses/{bid}/bookings-policy"
    assert client.get(url, headers=anbu_h).status_code == 200
    assert client.patch(url, json={"require_deposit": True, "deposit_amount": 500}, headers=anbu_h).status_code == 403
    assert client.patch(url, json={"require_deposit": True, "deposit_amount": 500}, headers=owner).status_code == 200
