"""Business classification, operating traits and module recommendations
(Capability Universe §4.4, §24 #1–2; Founder §50) through the API.

Proves: the picked kind becomes columns and seeds default traits; an owner's
trait choices survive a re-seed; traits are tenant-isolated in the database;
a member without settings.update cannot change them; recommendations carry
real readiness; and a module that is not built cannot be switched on.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_testing.phase_b import assert_tenant_isolated, create_business, new_identity

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")

client = TestClient(app)


@pytest.fixture
def owner(monkeypatch: Any) -> dict[str, str]:
    return cast(dict[str, str], new_identity(monkeypatch)[1])


def test_picked_kind_becomes_columns_and_seeds_default_traits(owner: dict[str, str]) -> None:
    bid = create_business(client, owner, category_key="fresh_grocery", subcategory_key="meat_shop",
                          business_type="retail")
    resp = client.get(f"/v1/platform/businesses/{bid}/classification", headers=owner)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert (data["category_key"], data["subcategory_key"]) == ("fresh_grocery", "meat_shop")
    assert {"weight_based", "local_delivery", "walk_in", "perishable"} <= set(data["traits"])
    assert data["traits"] == data["default_traits"]
    assert data["org_shape"] == "team" and data["org_shape_is_default"] is True
    labels = {t["key"]: t["label"] for g in data["trait_groups"] for t in g["traits"]}
    assert labels["weight_based"] == "I sell by weight"  # owner words, never keys


def test_owner_trait_choices_survive_reclassification(owner: dict[str, str]) -> None:
    bid = create_business(client, owner, category_key="food_service", subcategory_key="bakery",
                          business_type="cafe")
    patched = client.patch(f"/v1/platform/businesses/{bid}/traits",
                           json={"traits": {"walk_in": False, "b2b": True}}, headers=owner)
    assert patched.status_code == 200, patched.text
    after = patched.json()["data"]
    assert "walk_in" not in after["traits"] and "b2b" in after["traits"]

    moved = client.put(f"/v1/platform/businesses/{bid}/classification",
                       json={"category_key": "home_food", "subcategory_key": "home_bakery"}, headers=owner)
    assert moved.status_code == 200, moved.text
    data = moved.json()["data"]
    assert data["subcategory_key"] == "home_bakery"
    # Defaults followed the new kind; the owner's two choices did not change.
    assert "b2b" in data["traits"] and "walk_in" not in data["traits"]
    by_key = {t["key"]: t for g in data["trait_groups"] for t in g["traits"]}
    assert by_key["b2b"]["source"] == "owner" and by_key["walk_in"]["source"] == "owner"


def test_unknown_traits_and_kinds_are_rejected(owner: dict[str, str]) -> None:
    bid = create_business(client, owner)
    bad = client.patch(f"/v1/platform/businesses/{bid}/traits", json={"traits": {"flying": True}}, headers=owner)
    assert bad.status_code == 422
    bad_kind = client.put(f"/v1/platform/businesses/{bid}/classification",
                          json={"category_key": "retail", "subcategory_key": "meat_shop"}, headers=owner)
    assert bad_kind.status_code == 422
    bad_shape = client.put(f"/v1/platform/businesses/{bid}/classification",
                           json={"org_shape": "galaxy"}, headers=owner)
    assert bad_shape.status_code == 422
    ok = client.put(f"/v1/platform/businesses/{bid}/classification", json={"org_shape": "solo"}, headers=owner)
    assert ok.json()["data"]["org_shape"] == "solo"


def test_a_stranger_cannot_read_or_change_traits(owner: dict[str, str], monkeypatch: Any) -> None:
    bid = create_business(client, owner, category_key="beauty", subcategory_key="salon")
    _, stranger = new_identity(monkeypatch)
    assert client.get(f"/v1/platform/businesses/{bid}/classification", headers=stranger).status_code in (403, 404)
    denied = client.patch(f"/v1/platform/businesses/{bid}/traits", json={"traits": {"b2b": True}}, headers=stranger)
    assert denied.status_code in (403, 404)


def test_recommendations_carry_real_readiness(owner: dict[str, str]) -> None:
    bid = create_business(client, owner, category_key="fitness", subcategory_key="gym", business_type="gym")
    resp = client.get(f"/v1/platform/businesses/{bid}/module-recommendations", headers=owner)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["family"] == "gyms_crossfit_powerlifting"
    assert {"memberships", "attendance", "payments", "bookings"} <= set(data["core"])
    by = {m["module"]: m for m in data["modules"]}
    plans = by["memberships"]
    assert plans["does"] and plans["customer_can"] and plans["staff_can"]
    assert plans["readiness"]["enabled"] is False
    assert plans["readiness"]["steps"] == [
        {"key": "plan_live", "label": "Publish at least one plan", "done": False}
    ]
    assert by["attendance"]["built"] is False  # recommended by the source, not built yet


def test_unbuilt_module_cannot_be_switched_on(owner: dict[str, str]) -> None:
    bid = create_business(client, owner)
    resp = client.post(f"/v1/b/{bid}/modules/dispatch/enable", headers=owner)
    assert resp.status_code == 422, resp.text
    assert "not available yet" in resp.text


@pytest.mark.asyncio
async def test_business_traits_are_tenant_isolated() -> None:
    async def insert(session: AsyncSession, business_id: uuid.UUID) -> None:
        await session.execute(text(
            "insert into business_traits (business_id, trait_key, source) values (:b, 'b2c', 'default')"),
            {"b": business_id})

    await assert_tenant_isolated("business_traits", insert)


def test_storefront_is_always_on(owner: dict[str, str]) -> None:
    """Capability Universe §6.1: "Storefront is always on" — every built
    Storefront module is active from the start and cannot be switched off."""
    from platform_core.catalog.modules import storefront_modules

    bid = create_business(client, owner)
    assert "customer-relationships" in storefront_modules()
    states = {m["module_id"]: m["activation_state"]
              for m in client.get(f"/v1/b/{bid}/modules", headers=owner).json()["data"]}
    for module_id in storefront_modules():
        assert states.get(module_id) == "active", module_id
    off = client.post(f"/v1/b/{bid}/modules/customer-relationships/deactivate", headers=owner)
    assert off.status_code == 422, off.text
    assert "stays on" in off.json()["error"]["message"]
    added = client.post(f"/v1/platform/businesses/{bid}/customers", json={"display_name": "Walk-in", "phone": "+919800000002"},
                          headers=owner)
    assert added.status_code == 200, added.text
