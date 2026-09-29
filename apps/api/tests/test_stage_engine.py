"""The stage engine (P2-01; Capability Universe §24 #10).

"Configurable stage sets with guarded transitions shared by orders, jobs, leads,
projects." A business adds its own steps inside a module's open statuses and
renames stages; moving a record to a step of another status still runs the
module's own rules (a cancelled order releases its stock, a won enquiry becomes a
customer). These tests drive it through the API.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app

from platform_testing.phase_b import create_business, new_identity, primary_location

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)


def _shop(owner: dict[str, str]) -> tuple[str, str, str]:
    bid = create_business(client, owner, modules=("offerings-catalog", "inventory", "orders", "payments"))
    loc = primary_location(client, owner, bid)
    base = f"/v1/platform/businesses/{bid}"
    product = client.post(f"{base}/products", json={
        "title": "Ghee 1 L", "sku": f"G-{uuid.uuid4().hex[:6]}", "track_inventory": True, "status": "active",
        "price_amount": 620}, headers=owner).json()["data"]["id"]
    r = client.post(f"{base}/inventory/opening-stock", json={"offering_id": product, "location_id": loc,
                                                            "quantity": 10}, headers=owner)
    assert r.status_code == 200, r.text
    return bid, loc, product


def _order(owner: dict[str, str], bid: str, loc: str, product: str, qty: int = 2) -> dict[str, Any]:
    r = client.post(f"/v1/platform/businesses/{bid}/orders", json={
        "location_id": loc, "payment_method": "cod", "idempotency_key": str(uuid.uuid4()),
        "items": [{"offering_id": product, "quantity": qty}]}, headers=owner)
    assert r.status_code == 200, r.text
    return dict(r.json()["data"])


def _with_steps(stages: list[dict[str, Any]], status: str, *labels: str, note: bool = False) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in stages:
        out.append(s)
        if s["key"] == status:
            out.extend({"label": x, "status": status, "needs_note": note and i == len(labels) - 1}
                       for i, x in enumerate(labels))
    return out


def _join(owner: dict[str, str], bid: str, monkeypatch: Any, role: str) -> tuple[uuid.UUID, dict[str, str]]:
    person, headers = new_identity(monkeypatch)
    inv = client.post(f"/v1/b/{bid}/team/invitations", json={"identity_id": str(person), "role": "member"},
                      headers=owner)
    mid = inv.json()["data"]["id"]
    assert client.post(f"/v1/b/{bid}/team/members/{mid}/activate", headers=owner).status_code == 200
    assert client.put(f"/v1/platform/businesses/{bid}/members/{mid}/role", json={"role": role},
                      headers=owner).status_code == 200
    return person, headers


def test_default_stages_are_the_modules_own_statuses(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, _, _ = _shop(owner)
    r = client.get(f"/v1/b/{bid}/stages/orders", headers=owner)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["version"] == 0
    assert [s["key"] for s in data["stages"]] == ["pending", "accepted", "preparing", "ready", "completed",
                                                   "cancelled", "rejected"]
    assert sorted(data["moves"]["pending"]) == ["accepted", "cancelled", "rejected"]
    assert data["moves"]["completed"] == []
    # A module the business has not turned on has no stages to read.
    assert client.get(f"/v1/b/{bid}/stages/leads", headers=owner).status_code in (403, 409)
    assert client.get(f"/v1/b/{bid}/stages/invoices", headers=owner).status_code == 404


def test_business_adds_steps_inside_open_statuses_only(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, _, _ = _shop(owner)
    url = f"/v1/b/{bid}/stages/orders"
    stages = client.get(url, headers=owner).json()["data"]["stages"]
    stages = [dict(s, label="Ready for pickup") if s["key"] == "ready" else s for s in stages]
    saved = client.put(url, json={"stages": _with_steps(stages, "preparing", "Picking", "Packed", note=True)},
                       headers=owner)
    assert saved.status_code == 200, saved.text
    data = saved.json()["data"]
    assert data["version"] == 1
    assert [(s["key"], s["label"]) for s in data["stages"]][2:6] == [
        ("preparing", "Preparing"), ("s_picking", "Picking"), ("s_packed", "Packed"), ("ready", "Ready for pickup")]
    assert next(s for s in data["stages"] if s["key"] == "s_packed")["needs_note"] is True
    assert "s_picking" in data["moves"]["accepted"] and "s_picking" not in data["moves"]["pending"]

    ending = client.put(url, json={"stages": _with_steps(stages, "completed", "Invoiced")}, headers=owner)
    assert ending.status_code == 422 and "only inside open stages" in ending.json()["error"]["message"]
    dropped = client.put(url, json={"stages": [s for s in stages if s["key"] != "rejected"]}, headers=owner)
    assert dropped.status_code == 422 and "Declined" in dropped.json()["error"]["message"]
    stranger = client.put(url, json={"stages": [*stages, {"label": "Lost", "status": "misplaced"}]}, headers=owner)
    assert stranger.status_code == 422
    many = client.put(url, json={"stages": _with_steps(stages, "preparing", *[f"Step {i}" for i in range(21)])},
                      headers=owner)
    assert many.status_code == 422 and "Up to 20" in many.json()["error"]["message"]


def test_moving_an_order_runs_the_order_rules(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, loc, product = _shop(owner)
    base = f"/v1/platform/businesses/{bid}"
    stages = client.get(f"/v1/b/{bid}/stages/orders", headers=owner).json()["data"]["stages"]
    assert client.put(f"/v1/b/{bid}/stages/orders", json={
        "stages": _with_steps(stages, "preparing", "Picking", "Packed", note=True)}, headers=owner).status_code == 200
    order = _order(owner, bid, loc, product)
    move = f"/v1/b/{bid}/stages/orders/{order['id']}/move"

    skip = client.post(move, json={"to": "s_picking"}, headers=owner)
    assert skip.status_code == 422 and "From “New” it can move to" in skip.json()["error"]["message"]
    assert client.post(move, json={"to": "accepted"}, headers=owner).status_code == 200
    picked = client.post(move, json={"to": "s_picking"}, headers=owner)
    assert picked.status_code == 200, picked.text
    assert picked.json()["data"]["status"] == "preparing" and picked.json()["data"]["stage"]["key"] == "s_picking"
    no_note = client.post(move, json={"to": "s_packed"}, headers=owner)
    assert no_note.status_code == 422 and "Add a note" in no_note.json()["error"]["message"]
    stale = client.post(move, json={"to": "s_packed", "note": "2 bags", "version": 1}, headers=owner)
    assert stale.status_code == 409
    packed = client.post(move, json={"to": "s_packed", "note": "2 bags, sealed"}, headers=owner)
    assert packed.status_code == 200, packed.text

    detail = client.get(f"{base}/orders/{order['id']}", headers=owner).json()["data"]
    assert detail["status"] == "preparing" and detail["stage"] == "s_packed"
    where = client.get(f"/v1/b/{bid}/stages/orders/{order['id']}", headers=owner).json()["data"]
    assert where["stage"]["label"] == "Packed"
    assert [(h["from"], h["to"]) for h in where["history"]] == [("New", "Accepted"), ("Accepted", "Picking"),
                                                                ("Picking", "Packed")]
    assert where["history"][-1]["note"] == "2 bags, sealed"

    # A status changed another way (the order's own buttons) shows that status's own stage.
    assert client.post(f"{base}/orders/{order['id']}/status", json={"status": "ready"},
                       headers=owner).status_code == 200
    where = client.get(f"/v1/b/{bid}/stages/orders/{order['id']}", headers=owner).json()["data"]
    assert where["stage"]["key"] == "ready" and [m["key"] for m in where["moves"]] == ["completed", "cancelled"]

    # Cancelling through the stages releases the stock, as the Cancel button does.
    other = _order(owner, bid, loc, product, qty=3)
    held = client.get(f"{base}/inventory?offering_id={product}", headers=owner).json()["data"][0]
    assert held["quantity_reserved"] == 5
    gone = client.post(f"/v1/b/{bid}/stages/orders/{other['id']}/move", json={"to": "cancelled",
                                                                             "note": "Customer called"},
                       headers=owner)
    assert gone.status_code == 200, gone.text
    after = client.get(f"{base}/inventory?offering_id={product}", headers=owner).json()["data"][0]
    assert after["quantity_reserved"] == 2
    assert client.get(f"{base}/orders/{other['id']}", headers=owner).json()["data"]["cancellation_reason"] == \
        "Customer called"


def test_moves_need_the_modules_own_permission(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, loc, product = _shop(owner)
    order = _order(owner, bid, loc, product)
    _, accountant = _join(owner, bid, monkeypatch, "accountant")
    assert client.get(f"/v1/b/{bid}/stages/orders/{order['id']}", headers=accountant).status_code == 200
    denied = client.post(f"/v1/b/{bid}/stages/orders/{order['id']}/move", json={"to": "accepted"},
                         headers=accountant)
    assert denied.status_code == 403, denied.text
    stages = client.get(f"/v1/b/{bid}/stages/orders", headers=accountant).json()["data"]["stages"]
    assert client.put(f"/v1/b/{bid}/stages/orders", json={"stages": stages}, headers=accountant).status_code == 403

    # Another business cannot read or move it.
    _, stranger = new_identity(monkeypatch)
    create_business(client, stranger, modules=("orders",))
    for call in (client.get(f"/v1/b/{bid}/stages/orders/{order['id']}", headers=stranger),
                 client.post(f"/v1/b/{bid}/stages/orders/{order['id']}/move", json={"to": "accepted"},
                             headers=stranger)):
        assert call.status_code in (403, 404), call.text


def test_enquiry_steps_and_winning_makes_a_customer(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("leads", "customer-relationships"))
    base = f"/v1/platform/businesses/{bid}"
    stages = client.get(f"/v1/b/{bid}/stages/leads", headers=owner).json()["data"]["stages"]
    saved = client.put(f"/v1/b/{bid}/stages/leads", json={
        "stages": _with_steps(stages, "contacted", "Site visit booked")}, headers=owner)
    assert saved.status_code == 200, saved.text
    lead = client.post(f"{base}/leads", json={"display_name": "Kavin Interiors", "phone": "9876500123"},
                       headers=owner).json()["data"]
    move = f"/v1/b/{bid}/stages/leads/{lead['id']}/move"

    visit = client.post(move, json={"to": "s_site_visit_booked"}, headers=owner)
    assert visit.status_code == 200 and visit.json()["data"]["status"] == "contacted", visit.text
    # The enquiry module asks for a reason when an enquiry is lost.
    lost = client.post(move, json={"to": "lost"}, headers=owner)
    assert lost.status_code == 422, lost.text
    won = client.post(move, json={"to": "won"}, headers=owner)
    assert won.status_code == 200, won.text
    detail = client.get(f"{base}/leads/{lead['id']}", headers=owner).json()["data"]
    assert detail["status"] == "won" and detail["customer_contact_id"]
    assert client.post(move, json={"to": "contacted"}, headers=owner).status_code == 422  # a won enquiry stays won


def test_assignment_scope_limits_stage_moves(monkeypatch: Any) -> None:
    owner_id, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("leads", "customer-relationships"))
    base = f"/v1/platform/businesses/{bid}"
    priya, priya_h = _join(owner, bid, monkeypatch, "sales_executive")
    mine = client.post(f"{base}/leads", json={"display_name": "Mine", "phone": "9876500201",
                                              "assignee_identity_id": str(priya)}, headers=owner).json()["data"]
    theirs = client.post(f"{base}/leads", json={"display_name": "Theirs", "phone": "9876500202",
                                                "assignee_identity_id": str(owner_id)}, headers=owner).json()["data"]
    ok = client.post(f"/v1/b/{bid}/stages/leads/{mine['id']}/move", json={"to": "contacted"}, headers=priya_h)
    assert ok.status_code == 200, ok.text
    for call in (client.get(f"/v1/b/{bid}/stages/leads/{theirs['id']}", headers=priya_h),
                 client.post(f"/v1/b/{bid}/stages/leads/{theirs['id']}/move", json={"to": "contacted"},
                             headers=priya_h)):
        assert call.status_code == 404, call.text


def test_project_steps_go_through_the_project_rules(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("projects", "quotes", "customer-relationships", "workforce"))
    stages = client.get(f"/v1/b/{bid}/stages/projects", headers=owner).json()["data"]["stages"]
    assert client.put(f"/v1/b/{bid}/stages/projects", json={
        "stages": _with_steps(stages, "active", "Site survey", "Fabrication")}, headers=owner).status_code == 200
    project = client.post(f"/v1/platform/businesses/{bid}/projects", json={"title": "Kitchen refit"},
                          headers=owner)
    assert project.status_code == 200, project.text
    pid = project.json()["data"]["id"]
    survey = client.post(f"/v1/b/{bid}/stages/projects/{pid}/move", json={"to": "s_site_survey"}, headers=owner)
    assert survey.status_code == 200 and survey.json()["data"]["status"] == "active", survey.text
    fab = client.post(f"/v1/b/{bid}/stages/projects/{pid}/move", json={"to": "s_fabrication"}, headers=owner)
    assert fab.status_code == 200, fab.text
    detail = client.get(f"/v1/platform/businesses/{bid}/projects/{pid}", headers=owner).json()["data"]
    assert detail["status"] == "active" and detail["stage"] == "s_fabrication"
