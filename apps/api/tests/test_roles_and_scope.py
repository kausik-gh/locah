"""Roles and location scope (Capability Universe §7.2–§7.3; Business OS Guide §5).

"A role is not just a sidebar label. It is permissions + scope + default
surface ... UI hiding is not the security boundary." These tests give people
roles through the API and then check what the server lets them see and do —
including the database's own restrictive policies.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from platform_testing.phase_b import (
    assert_tenant_isolated,
    create_business,
    db_url,
    new_identity,
    primary_location,
)

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)


def _join(owner: dict[str, str], bid: str, monkeypatch: Any, role: str = "member") -> tuple[str, dict[str, str]]:
    """An active member with no role template yet."""
    person_id, headers = new_identity(monkeypatch)
    inv = client.post(f"/v1/b/{bid}/team/invitations", json={"identity_id": str(person_id), "role": role},
                      headers=owner)
    assert inv.status_code == 200, inv.text
    mid = inv.json()["data"]["id"]
    assert client.post(f"/v1/b/{bid}/team/members/{mid}/activate", headers=owner).status_code == 200
    return mid, headers


def _stocked_shop(owner: dict[str, str]) -> tuple[str, str, str, str]:
    bid = create_business(client, owner, modules=("offerings-catalog", "inventory", "orders", "payments"))
    loc_a = primary_location(client, owner, bid)
    loc_b = client.post(f"/v1/platform/businesses/{bid}/locations", json={"name": "Branch B"}, headers=owner)
    assert loc_b.status_code == 200, loc_b.text
    loc_b_id = loc_b.json()["data"]["id"]
    product = client.post(f"/v1/platform/businesses/{bid}/products", json={
        "title": "Basmati 5 kg", "sku": f"B-{uuid.uuid4().hex[:6]}", "track_inventory": True, "status": "active",
        "price_amount": 650}, headers=owner).json()["data"]["id"]
    for loc, qty in ((loc_a, 10), (loc_b_id, 20)):
        r = client.post(f"/v1/platform/businesses/{bid}/inventory/opening-stock",
                        json={"offering_id": product, "location_id": loc, "quantity": qty}, headers=owner)
        assert r.status_code == 200, r.text
    return bid, loc_a, loc_b_id, product


def test_role_catalogue_offers_only_what_this_business_can_use(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    shop = create_business(client, owner, modules=("offerings-catalog", "inventory", "orders", "payments"))
    keys = [t["key"] for t in client.get(f"/v1/platform/businesses/{shop}/roles", headers=owner).json()["data"]["templates"]]
    assert keys == ["manager", "store_keeper", "accountant"]  # cashier waits for POS; P2 roles are not offered
    consultant = create_business(client, owner)
    data = client.get(f"/v1/platform/businesses/{consultant}/roles", headers=owner).json()["data"]
    assert [t["key"] for t in data["templates"]] == ["manager"]  # no stock or money tools → no store keeper/accountant
    assert data["owner"]["home"] == "Needs you now · Today · Your business"
    assert set(data["scopes"]) == {"business", "location"}  # assignment scope is not enforceable yet


def test_store_keeper_at_one_location_sees_and_changes_only_that_location(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, loc_a, loc_b, product = _stocked_shop(owner)
    mid, keeper = _join(owner, bid, monkeypatch)
    given = client.put(f"/v1/platform/businesses/{bid}/members/{mid}/role",
                       json={"role": "store_keeper", "location_ids": [loc_a]}, headers=owner)
    assert given.status_code == 200, given.text
    me = next(m for m in given.json()["data"] if m["id"] == mid)
    assert me["role"]["label"] == "Store keeper" and [x["id"] for x in me["locations"]] == [loc_a]

    seen = client.get(f"/v1/platform/businesses/{bid}/inventory", headers=keeper).json()["data"]
    assert {r["location_id"] for r in seen} == {loc_a}
    assert len(client.get(f"/v1/platform/businesses/{bid}/inventory", headers=owner).json()["data"]) == 2

    ok = client.post(f"/v1/platform/businesses/{bid}/inventory/adjust", json={
        "offering_id": product, "location_id": loc_a, "quantity_delta": -1, "reason": "Damaged"}, headers=keeper)
    assert ok.status_code == 200, ok.text
    other = client.post(f"/v1/platform/businesses/{bid}/inventory/adjust", json={
        "offering_id": product, "location_id": loc_b, "quantity_delta": -1, "reason": "Damaged"}, headers=keeper)
    assert other.status_code in (403, 404), other.text
    # Store keepers do not see orders or payments at all.
    assert client.get(f"/v1/platform/businesses/{bid}/orders", headers=keeper).status_code == 403


def test_database_repeats_the_location_limit(monkeypatch: Any) -> None:
    """Defence in depth: with the API role and a location scope bound, the
    database itself returns only that location's stock."""
    _, owner = new_identity(monkeypatch)
    bid, loc_a, loc_b, _ = _stocked_shop(owner)

    async def run() -> tuple[int, int, int]:
        engine = create_async_engine(db_url(), poolclass=NullPool)
        try:
            async with AsyncSession(engine) as s:
                await s.execute(text("set local role platform_api"))
                await s.execute(text("select set_config('app.current_business_id', :b, true)"), {"b": bid})
                everything = (await s.execute(text("select count(*) from inventory_records"))).scalar_one()
                await s.execute(text("select set_config('app.current_location_scope', :l, true)"), {"l": loc_a})
                scoped = (await s.execute(text("select count(*) from inventory_records"))).scalar_one()
                moved = (await s.execute(text("update inventory_records set updated_at = now() "
                                              "where location_id = :l returning id"), {"l": loc_b})).all()
                await s.rollback()
                return int(everything), int(scoped), len(moved)
        finally:
            await engine.dispose()

    assert asyncio.run(run()) == (2, 1, 0)


def test_custom_role_is_cloned_and_never_exceeds_the_giver(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, loc_a, _, _ = _stocked_shop(owner)
    base = f"/v1/platform/businesses/{bid}"
    made = client.post(f"{base}/roles/custom", json={
        "name": "Stock checker", "based_on": "store_keeper", "permissions": ["inventory.read", "offerings.read"],
        "scope": "business"}, headers=owner)
    assert made.status_code == 200, made.text
    role = made.json()["data"]
    assert role["based_on_label"] == "Store keeper" and role["permissions"] == ["inventory.read", "offerings.read"]
    dup = client.post(f"{base}/roles/custom", json={"name": "stock checker", "permissions": ["inventory.read"]},
                      headers=owner)
    assert dup.status_code == 409
    later = client.post(f"{base}/roles/custom", json={"name": "Runner", "permissions": ["inventory.read"],
                                                      "scope": "assignment"}, headers=owner)
    assert later.status_code == 422  # assignment scope is not enforced yet, so it cannot be chosen

    mid, checker = _join(owner, bid, monkeypatch)
    assert client.put(f"{base}/members/{mid}/role", json={"role": role["key"]}, headers=owner).status_code == 200
    assert client.get(f"{base}/inventory", headers=checker).status_code == 200
    adjust = client.post(f"{base}/inventory/adjust", json={
        "offering_id": str(uuid.uuid4()), "location_id": loc_a, "quantity_delta": -1, "reason": "x"}, headers=checker)
    assert adjust.status_code == 403

    # A person who may change roles can still only hand out what they hold.
    helper = client.post(f"{base}/roles/custom", json={
        "name": "Team helper", "permissions": ["team.read", "team.update_role", "inventory.read"]}, headers=owner)
    hid, helper_headers = _join(owner, bid, monkeypatch)
    assert client.put(f"{base}/members/{hid}/role", json={"role": helper.json()["data"]["key"]},
                      headers=owner).status_code == 200
    too_much = client.put(f"{base}/members/{mid}/role", json={"role": "accountant"}, headers=helper_headers)
    assert too_much.status_code == 403, too_much.text
    held = client.delete(f"{base}/roles/custom/{role['id']}", headers=owner)
    assert held.status_code == 409 and "Give them another role first" in held.json()["error"]["message"]


def test_assigning_a_role_replaces_earlier_grants(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, _, _, _ = _stocked_shop(owner)
    mid, person = _join(owner, bid, monkeypatch)
    granted = client.post(f"/v1/b/{bid}/team/members/{mid}/permissions", json={"permissions": ["orders.read"]},
                          headers=owner)
    assert granted.status_code == 200
    assert client.get(f"/v1/platform/businesses/{bid}/orders", headers=person).status_code == 200
    client.put(f"/v1/platform/businesses/{bid}/members/{mid}/role", json={"role": "store_keeper",
               "location_ids": [primary_location(client, owner, bid)]}, headers=owner)
    assert client.get(f"/v1/platform/businesses/{bid}/orders", headers=person).status_code == 403


def test_owner_role_cannot_be_reassigned_and_unknown_locations_are_refused(monkeypatch: Any) -> None:
    owner_id, owner = new_identity(monkeypatch)
    bid, _, _, _ = _stocked_shop(owner)
    team = client.get(f"/v1/platform/businesses/{bid}/team", headers=owner).json()["data"]["members"]
    me = team[0]
    assert me["role"]["label"] == "Owner" and me["identity_id"] == str(owner_id)
    refused = client.put(f"/v1/platform/businesses/{bid}/members/{me['id']}/role", json={"role": "manager"},
                         headers=owner)
    assert refused.status_code in (403, 422)
    mid, _ = _join(owner, bid, monkeypatch)
    bad = client.put(f"/v1/platform/businesses/{bid}/members/{mid}/role",
                     json={"role": "manager", "location_ids": [str(uuid.uuid4())]}, headers=owner)
    assert bad.status_code == 422
    none = client.put(f"/v1/platform/businesses/{bid}/members/{mid}/role", json={"role": "manager"}, headers=owner)
    assert none.status_code == 422 and "location" in none.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_custom_roles_are_tenant_isolated() -> None:
    async def insert(session: AsyncSession, business_id: uuid.UUID) -> None:
        await session.execute(text(
            "insert into business_custom_roles (business_id, name, permissions) values (:b, :n, '{inventory.read}')"),
            {"b": business_id, "n": f"Role {uuid.uuid4().hex[:6]}"})

    await assert_tenant_isolated("business_custom_roles", insert)


# ======================================================================== staff logins
def test_owner_adds_a_person_who_joins_with_the_role_already_set(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, loc_a, _, _ = _stocked_shop(owner)
    person_id, person = new_identity(monkeypatch)
    email = f"{person_id}@example.com"
    added = client.post(f"/v1/platform/businesses/{bid}/team/people", json={
        "name": "Murugan", "email": email, "role": "store_keeper", "location_ids": [loc_a]}, headers=owner)
    assert added.status_code == 200, added.text
    join_path = added.json()["data"]["join_path"]
    token = join_path.split("/join/")[1]

    view = client.get(f"/v1/public/join/{token}")
    assert view.status_code == 200, view.text
    v = view.json()["data"]
    assert v["role"]["label"] == "Store keeper" and v["role"]["home"] == "What is low, what arrived"
    assert v["name"] == "Murugan" and v["status"] == "pending" and email not in v["email_hint"]
    assert v["locations"] and v["business"]["id"] == bid

    team = client.get(f"/v1/platform/businesses/{bid}/team", headers=owner).json()["data"]
    assert [i["name"] for i in team["invited"]] == ["Murugan"] and team["invited"][0]["role_label"] == "Store keeper"

    stranger_id, stranger = new_identity(monkeypatch)
    wrong = client.post(f"/v1/platform/businesses/{bid}/invitations/{v['invitation_id']}/accept", headers=stranger)
    assert wrong.status_code in (403, 422), wrong.text

    joined = client.post(f"/v1/platform/businesses/{bid}/invitations/{v['invitation_id']}/accept", headers=person)
    assert joined.status_code == 200, joined.text
    assert client.get(f"/v1/public/join/{token}").status_code == 404  # the link works once
    seen = client.get(f"/v1/platform/businesses/{bid}/inventory", headers=person).json()["data"]
    assert {r["location_id"] for r in seen} == {loc_a}
    me = next(m for m in client.get(f"/v1/platform/businesses/{bid}/team", headers=owner).json()["data"]["members"]
              if m["identity_id"] == str(person_id))
    assert me["role"]["label"] == "Store keeper" and me["name"] == "Murugan"


def test_a_new_link_replaces_the_old_one_and_roles_are_bounded_by_the_adder(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, loc_a, _, _ = _stocked_shop(owner)
    added = client.post(f"/v1/platform/businesses/{bid}/team/people", json={
        "name": "Asha", "email": "asha@example.com", "role": "accountant"}, headers=owner).json()["data"]
    old = added["join_path"].split("/join/")[1]
    fresh = client.post(f"/v1/platform/businesses/{bid}/team/invitations/{added['invitation_id']}/link", headers=owner)
    assert fresh.status_code == 200
    assert client.get(f"/v1/public/join/{old}").status_code == 404
    assert client.get(f"/v1/public/join/{fresh.json()['data']['join_path'].split('/join/')[1]}").status_code == 200

    # Someone who may add people but only holds stock permissions cannot add an accountant.
    helper = client.post(f"/v1/platform/businesses/{bid}/roles/custom", json={
        "name": "Hiring helper", "permissions": ["team.read", "team.invite", "inventory.read"]}, headers=owner)
    hid, helper_headers = _join(owner, bid, monkeypatch)
    client.put(f"/v1/platform/businesses/{bid}/members/{hid}/role", json={"role": helper.json()["data"]["key"]},
               headers=owner)
    refused = client.post(f"/v1/platform/businesses/{bid}/team/people", json={
        "name": "Ravi", "email": "ravi@example.com", "role": "accountant"}, headers=helper_headers)
    assert refused.status_code == 403, refused.text
    assert client.get("/v1/public/join/not-a-real-token-at-all-000").status_code == 404
