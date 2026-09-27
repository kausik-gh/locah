"""Offering kinds (Capability Universe §6.1, §6.3; §26.3 P1-03): kind fields,
packs for goods sold by weight, cuts and modifiers priced by the server,
variant matrix, HSN/SAC and GTIN checks, and website enquiries as leads."""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app

from platform_testing.phase_b import create_business, new_identity, primary_location, sql

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)


def _public_shop(owner: dict[str, str], *modules: str) -> tuple[str, str]:
    bid = create_business(client, owner, modules=("offerings-catalog", "orders", "inventory", "payments",
                                                   "fulfilment", *modules))
    assert client.post(f"/v1/b/{bid}/marketplace/visibility", json={"visibility": "unlisted"},
                       headers=owner).status_code == 200
    client.patch(f"/v1/b/{bid}/fulfilment/settings", json={"pickup_enabled": True}, headers=owner)
    slug = client.get(f"/v1/b/{bid}", headers=owner).json()["data"]["slug"]
    return bid, slug


def _offering(owner: dict[str, str], bid: str, body: dict[str, Any]) -> dict[str, Any]:
    r = client.post(f"/v1/platform/businesses/{bid}/products", json={"status": "active", **body}, headers=owner)
    assert r.status_code == 200, r.text
    return dict(r.json()["data"])


def _checkout(slug: str, items: list[dict[str, Any]]) -> Any:
    return client.post(f"/v1/public/websites/{slug}/checkout", json={
        "items": items, "fulfilment_mode": "pickup", "payment_method": "cod",
        "guest": {"name": "Guest", "email": f"{uuid.uuid4()}@example.com"}})


CHICKEN = {
    "title": "Chicken", "offering_type": "weighed_product", "price_amount": 280, "track_inventory": True,
    "attributes": {"price_per": "kg"},
    "sell_units": [{"label": "500 g", "qty": 500}, {"label": "1 kg", "qty": 1000}],
    "option_groups": [{"name": "Cut", "required": True, "max": 1,
                       "choices": [{"label": "Curry cut", "price_delta": 0}, {"label": "Boneless", "price_delta": 60}]}],
}


def test_kinds_catalogue_covers_the_source_table() -> None:
    kinds = {k["key"]: k for k in client.get("/v1/public/offering-kinds").json()["data"]}
    sources = {k["source"] for k in kinds.values()}
    assert sources == {"product", "weighed_product", "menu_item", "service", "class", "course", "room_type",
                       "rental_resource", "plan", "package", "property_project", "unit", "vehicle",
                       "portfolio_item", "digital_product", "cause"}
    assert kinds["weighed_product"]["packs"] and kinds["menu_item"]["options"] and kinds["product"]["variants"]
    assert kinds["service"]["tax_code"] == "SAC" and kinds["product"]["tax_code"] == "HSN"
    assert kinds["vehicle"]["extra_ctas"] == ["Book a test drive"]


def test_weighed_goods_are_sold_in_packs_with_cuts_priced_by_the_server(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, slug = _public_shop(owner)
    chicken = _offering(owner, bid, CHICKEN)
    assert chicken["stock_unit"] == "g"
    loc = primary_location(client, owner, bid)
    client.post(f"/v1/platform/businesses/{bid}/inventory/opening-stock",
                json={"offering_id": chicken["id"], "location_id": loc, "quantity": 5000}, headers=owner)
    listed = next(o for o in client.get(f"/v1/public/websites/{slug}/offerings").json()["data"]["offerings"]
                  if o["id"] == chicken["id"])
    assert listed["packs"] == [{"label": "500 g", "price_amount": 140.0}, {"label": "1 kg", "price_amount": 280.0}]
    assert listed["kind"]["flow"] == "cart" and listed["option_groups"][0]["name"] == "Cut"

    no_cut = _checkout(slug, [{"offering_id": chicken["id"], "quantity": 1, "options": {"pack": "500 g"}}])
    assert no_cut.status_code == 422 and "Choose cut" in no_cut.json()["error"]["message"]
    bad_pack = _checkout(slug, [{"offering_id": chicken["id"], "quantity": 1, "options": {"pack": "2 kg"}}])
    assert bad_pack.status_code == 422

    placed = _checkout(slug, [{"offering_id": chicken["id"], "quantity": 2, "unit_price": 1,
                               "options": {"pack": "500 g", "choices": {"Cut": ["Boneless"]}}}])
    assert placed.status_code == 200, placed.text
    order_id = placed.json()["data"]["order"]["id"]
    order = client.get(f"/v1/platform/businesses/{bid}/orders/{order_id}", headers=owner).json()["data"]
    line = next(li for li in order["items"] if li["offering_id"] == chicken["id"])
    assert line["title"] == "Chicken — 500 g · Boneless"
    assert float(line["unit_price"]) == 200.0 and line["stock_quantity"] == 1000
    assert line["options"] == {"pack": "500 g", "price_per": "kg", "choices": {"Cut": ["Boneless"]}}
    stock = sql("select quantity_on_hand, quantity_reserved from inventory_records where offering_id = :o",
                o=chicken["id"])
    assert stock == [(5000, 1000)]


def test_menu_modifiers_and_add_ons(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, slug = _public_shop(owner)
    pizza = _offering(owner, bid, {
        "title": "Margherita", "offering_type": "menu_item", "price_amount": 250,
        "attributes": {"diet": "Veg"},
        "option_groups": [
            {"name": "Size", "required": True, "max": 1,
             "choices": [{"label": "Regular", "price_delta": 0}, {"label": "Large", "price_delta": 150}]},
            {"name": "Add-ons", "required": False, "max": 2,
             "choices": [{"label": "Extra cheese", "price_delta": 40}, {"label": "Olives", "price_delta": 30},
                         {"label": "Jalapeño", "price_delta": 30}]}]})
    too_many = _checkout(slug, [{"offering_id": pizza["id"], "quantity": 1, "options": {"choices": {
        "Size": ["Large"], "Add-ons": ["Extra cheese", "Olives", "Jalapeño"]}}}])
    assert too_many.status_code == 422
    ok = _checkout(slug, [{"offering_id": pizza["id"], "quantity": 1, "options": {"choices": {
        "Size": ["Large"], "Add-ons": ["Extra cheese", "Olives"]}}}])
    assert ok.status_code == 200, ok.text
    assert float(ok.json()["data"]["order"]["total_amount"]) == 470.0


def test_variant_matrix_and_tax_codes(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("offerings-catalog",))
    shirt = _offering(owner, bid, {"title": "Kurta", "price_amount": 899, "hsn_sac": "6211",
                                   "variant_options": [{"name": "Size", "values": ["S", "M"]},
                                                       {"name": "Colour", "values": ["Indigo", "Rust"]}]})
    made = client.post(f"/v1/platform/businesses/{bid}/products/{shirt['id']}/variants/matrix", headers=owner)
    assert made.status_code == 200 and made.json()["meta"]["created"] == 4
    assert sorted(v["name"] for v in made.json()["data"]) == ["M / Indigo", "M / Rust", "S / Indigo", "S / Rust"]
    again = client.post(f"/v1/platform/businesses/{bid}/products/{shirt['id']}/variants/matrix", headers=owner)
    assert again.json()["meta"]["created"] == 0
    stray = client.post(f"/v1/platform/businesses/{bid}/products/{shirt['id']}/variants",
                        json={"name": "XL", "attributes": {"Size": "XL"}}, headers=owner)
    assert stray.status_code == 422

    base = f"/v1/platform/businesses/{bid}/products"
    assert client.post(base, json={"title": "Bad HSN", "hsn_sac": "12345"}, headers=owner).status_code == 422
    assert client.post(base, json={"title": "Haircut", "offering_type": "service", "hsn_sac": "999722"},
                       headers=owner).status_code == 200
    assert client.post(base, json={"title": "Bad SAC", "offering_type": "service", "hsn_sac": "123456"},
                       headers=owner).status_code == 422
    assert client.post(base, json={"title": "Pen", "barcode": "4006381333931"}, headers=owner).status_code == 200
    typo = client.post(base, json={"title": "Pen 2", "barcode": "4006381333932"}, headers=owner)
    assert typo.status_code == 422 and "last digit" in typo.json()["error"]["message"]


def test_new_kinds_need_their_fields_first_launch_kinds_report_them(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("offerings-catalog",))
    base = f"/v1/platform/businesses/{bid}/products"
    car = client.post(base, json={"title": "Swift VXi", "offering_type": "vehicle", "attributes": {"model": "Swift"}},
                      headers=owner)
    assert car.status_code == 422 and "Make" in car.json()["error"]["message"]
    project = _offering(owner, bid, {"title": "Palm Grove", "offering_type": "property_project",
                                     "price_type": "starting_from", "price_amount": 8200000,
                                     "attributes": {"project_status": "Live", "location": "OMR, Chennai",
                                                    "unit_types": "2 BHK · 1,050 sq ft\n3 BHK · 1,420 sq ft"}})
    assert project["attributes"]["unit_types"] == ["2 BHK · 1,050 sq ft", "3 BHK · 1,420 sq ft"]
    haircut = _offering(owner, bid, {"title": "Haircut", "offering_type": "service", "price_amount": 300})
    assert haircut["missing_fields"] == ["How long it takes"]


def test_checkout_refuses_enquiry_kinds_and_prices_gifts_within_the_cause(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, slug = _public_shop(owner)
    flat = _offering(owner, bid, {"title": "A-402", "offering_type": "property_unit", "price_type": "enquiry",
                                  "attributes": {"project": "Palm Grove", "unit_status": "Available"}})
    refused = _checkout(slug, [{"offering_id": flat["id"], "quantity": 1}])
    assert refused.status_code == 422 and "enquired about" in refused.json()["error"]["message"]
    meals = _offering(owner, bid, {"title": "Feed a child for a month", "offering_type": "cause",
                                   "attributes": {"min_amount": 250, "goal_amount": 100000,
                                                  "suggested_amounts": "500\n1,000"}})
    assert meals["price_type"] == "variable" and meals["attributes"]["suggested_amounts"] == ["500", "1000"]
    small = _checkout(slug, [{"offering_id": meals["id"], "quantity": 1, "options": {"amount": 100}}])
    assert small.status_code == 422 and "Gifts start at ₹250" in small.json()["error"]["message"]
    gift = _checkout(slug, [{"offering_id": meals["id"], "quantity": 1, "options": {"amount": 1000}}])
    assert gift.status_code == 200, gift.text
    assert float(gift.json()["data"]["order"]["total_amount"]) == 1000.0
    listed = next(o for o in client.get(f"/v1/public/websites/{slug}/offerings").json()["data"]["offerings"]
                  if o["id"] == meals["id"])
    assert listed["raised_amount"] == 0.0  # pending gifts are not counted as raised


def test_website_enquiries_become_leads(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid, slug = _public_shop(owner)
    car = _offering(owner, bid, {"title": "Swift VXi 2022", "offering_type": "vehicle", "price_amount": 610000,
                                 "attributes": {"make": "Maruti Suzuki", "model": "Swift", "fuel": "Petrol"}})
    url = f"/v1/public/websites/{slug}/enquiries"
    off = client.post(url, json={"name": "Ravi", "phone": "+919000011111", "offering_id": car["id"]})
    assert off.status_code == 422 and off.json()["error"]["details"]["code"] == "enquiries_off"
    assert client.post(f"/v1/b/{bid}/modules/leads/enable", headers=owner).status_code == 200
    from datetime import date, timedelta

    when = (date.today() + timedelta(days=3)).isoformat()
    sent = client.post(url, json={"name": "Ravi", "phone": "+919000011111", "offering_id": car["id"],
                                  "purpose": "test_drive", "preferred_date": when, "message": "Weekend please"})
    assert sent.status_code == 200, sent.text
    assert client.post(url, json={"name": "Bot", "phone": "+919000000000", "website": "spam"}).status_code == 200
    assert client.post(url, json={"name": "No contact"}).status_code == 422
    leads = client.get(f"/v1/platform/businesses/{bid}/leads", headers=owner).json()["data"]
    assert [lead["display_name"] for lead in leads] == ["Ravi"]
    lead = leads[0]
    assert lead["source"] == "website_enquiry" and lead["offering_id"] == car["id"]
    assert lead["origin_context"]["purpose_label"] == "Test drive request"
    assert lead["origin_context"]["preferred_date"] == when
