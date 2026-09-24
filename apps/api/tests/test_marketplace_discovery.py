"""Marketplace discovery depth: taxonomy, place, actions, pipeline, ranking, personalisation.

The pure tests run anywhere. The database tests build real Businesses through
the owner API (publish, opt in) and read them back through the public API,
the same path a visitor's request takes.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, cast

import jwt
import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_core.business_categories import (
    CATEGORY_FAMILIES,
    classify,
    match_query,
    serialize_taxonomy,
)
from platform_core.db import get_database_url
from platform_core.geo.india_places import place_from_address, place_from_pin
from platform_core.models import (
    Business,
    BusinessProfile,
    MarketplaceBusinessProjection,
    Website,
    WebsitePage,
    WebsiteSection,
)
from platform_core.services.marketplace_indexing import MarketplaceIndexingService
from platform_core.services.marketplace_search import (
    MarketplaceSearchService,
    VisitorPlace,
    listing_actions,
    serialize_listing,
)
from platform_testing.db_helpers import ensure_auth_user
from platform_worker.job_runner import poll_and_execute_jobs
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"
needs_db = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")

# Fields that would be invented if a listing ever carried them: nothing in
# LOCAH records any of these, so no listing may claim them.
_INVENTED = {"rating", "ratings", "reviews", "review_count", "popularity", "popular", "open_now",
             "delivery_time", "price_level", "discount", "bestseller", "orders_count"}


# ---------------------------------------------------------------------------
# Pure: taxonomy, place, actions
# ---------------------------------------------------------------------------


def test_classify_reads_published_words_before_the_coarse_type() -> None:
    meat = classify("retail", ["Chicken curry cut, mutton, prawns", "Fresh meat and seafood daily"])
    assert (meat.family_id, meat.category_id) == ("fresh-grocery", "meat-seafood")
    assert "chicken" in meat.evidence

    homes = classify("other", ["2 BHK apartments, villas and plots in a gated community"])
    assert (homes.family_id, homes.category_id) == ("real-estate", "developers")

    gym = classify("gym", [])
    assert (gym.family_id, gym.category_id) == ("fitness", "gyms")

    tutors = classify("professional_service", ["We run small-group tutoring and exam preparation"])
    assert (tutors.family_id, tutors.category_id) == ("learning", "tuition")


def test_classify_leaves_a_silent_business_unplaced() -> None:
    placement = classify("other", ["", None])
    assert placement.family_id is None and placement.category_id is None


def test_taxonomy_is_one_list_with_real_counts_only() -> None:
    families = serialize_taxonomy({("food-drink", None): 2, ("food-drink", "home-kitchens"): 2})
    ids = [f["id"] for f in families]
    assert len(ids) == len(set(ids)) == len(CATEGORY_FAMILIES)
    food = next(f for f in families if f["id"] == "food-drink")
    assert food["count"] == 2 and food["icon"]
    assert next(c for c in food["categories"] if c["id"] == "home-kitchens")["count"] == 2
    # A family nobody is in says zero; it is not padded.
    assert next(f for f in families if f["id"] == "pets")["count"] == 0


def test_match_query_prefers_the_longest_phrase() -> None:
    assert match_query("pet grooming near me")[0]["category"] == "pet-grooming"
    assert match_query("cakes")[0]["category"] == "cafes-bakeries"
    assert match_query("zz") == []


def test_place_from_address_and_pin() -> None:
    place = place_from_address("12, Nookampalayam Road, Chennai 600130")
    assert place is not None
    assert (place.city, place.state) == ("Chennai", "Tamil Nadu")
    assert place.locality == "Nookampalayam Road"
    assert place_from_address("Somewhere with no known town") is None
    # Addresses written as sentences, or ending on a landmark.
    sentence = place_from_address("Our home in Saibaba Colony, Coimbatore")
    assert sentence is not None and sentence.locality == "Saibaba Colony"
    landmark = place_from_address("Anna Nagar, near Madurai Road, Chennai")
    assert landmark is not None and landmark.locality == "Anna Nagar"
    pin = place_from_pin("641 004")
    assert pin is not None and pin.city == "Coimbatore"
    assert place_from_pin("12345") is None


def test_visitor_coordinates_are_rounded_and_bounded() -> None:
    place = MarketplaceSearchService.resolve_place(lat=13.08271, lng=80.27071)
    assert place is not None
    assert (place.lat, place.lng, place.precision) == (13.08, 80.27, "device")
    assert place.label == "Chennai"
    # Outside India is not a place the Marketplace can order by.
    assert MarketplaceSearchService.resolve_place(lat=51.5, lng=-0.12) is None
    typed = MarketplaceSearchService.resolve_place(q="Kovai")
    assert typed is not None and typed.label == "Coimbatore" and typed.precision == "city"


def _row(**overrides: Any) -> MarketplaceBusinessProjection:
    base: dict[str, Any] = {
        "business_id": uuid.uuid4(),
        "slug": "sample",
        "display_name": "Sample",
        "capability_flags": {},
        "site_paths": {},
        "public_contact": {},
        "offering_count": 0,
        "tags": [],
        "highlights": [],
        "geo_precision": None,
    }
    base.update(overrides)
    return MarketplaceBusinessProjection(**base)


def test_actions_are_only_the_ones_that_work() -> None:
    bare = listing_actions(_row(capability_flags={"order": True, "enquire": True, "join": True}))
    # Orders on but nothing to order, enquiries on but no contact section,
    # memberships on but no plans page: none of them is offered.
    assert [a["action"] for a in bare] == ["visit_website"]

    full = listing_actions(_row(
        capability_flags={"order": True, "book": True, "enquire": True},
        offering_count=3,
        site_paths={"browse": "/menu", "contact": "#contact"},
        public_contact={"phone": "98400 12345", "whatsapp": "+91 98400 12345"},
    ))
    by_action = {a["action"]: a["href"] for a in full}
    assert by_action["order"] == "/sample/menu"
    assert by_action["book"] == "/sample/book"
    assert by_action["enquire"] == "/sample#contact"
    assert by_action["whatsapp"] == "https://wa.me/919840012345"
    assert by_action["call"] == "tel:9840012345"


def test_distance_is_shown_only_between_two_exact_points() -> None:
    exact = _row(geo_precision="exact")
    town = _row(geo_precision="city")
    device = VisitorPlace(13.08, 80.27, "Chennai", "device")
    picked = VisitorPlace(13.08, 80.27, "Chennai", "city")
    assert serialize_listing(exact, km=2.345, place=device)["distance_km"] == 2.3
    assert serialize_listing(town, km=2.345, place=device)["distance_km"] is None
    assert serialize_listing(exact, km=2.345, place=picked)["distance_km"] is None


def test_a_listing_claims_nothing_it_does_not_know() -> None:
    listing = serialize_listing(_row(capability_flags={"order": True}))
    assert not (_INVENTED & set(listing))


# ---------------------------------------------------------------------------
# Database: through the owner API and back out of the public one
# ---------------------------------------------------------------------------


def _run_db(fn: Callable[[AsyncSession], Awaitable[Any]]) -> Any:
    async def _go() -> Any:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as session:
                result = await fn(session)
                await session.commit()
                return result
        finally:
            await engine.dispose()

    return asyncio.run(_go())


@pytest.fixture
def owner(monkeypatch: Any) -> dict[str, str]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"

    async def _seed(session: AsyncSession) -> None:
        await ensure_auth_user(session, user_id, email)

    _run_db(_seed)
    token = jwt.encode(
        {"sub": str(user_id), "email": email, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _drain() -> None:
    async def _go(session: AsyncSession) -> None:
        for _ in range(5):
            await poll_and_execute_jobs(session, "mkt-discovery-worker")

    _run_db(_go)


def _create_business(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str,
    business_type: str = "retail",
    description: str | None = None,
    publish: bool = True,
    opt_in: bool = True,
) -> dict[str, Any]:
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": name, "business_type": business_type},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    business = cast(dict[str, Any], resp.json()["data"]["business"])
    bid = business["id"]
    _drain()
    client.patch(
        f"/v1/platform/businesses/{bid}/profile",
        json={"description": description or f"{name} description for discovery", "tagline": name},
        headers=headers,
    )
    if publish:
        assert client.post(f"/v1/b/{bid}/website/publish", headers=headers).status_code == 200
    if opt_in:
        opt = client.post(f"/v1/b/{bid}/marketplace/opt-in", json={"confirmed": True}, headers=headers)
        assert opt.status_code == 200, opt.text
    return business


def _publish_sections(business_id: str, sections: list[dict[str, Any]], contact: dict[str, str] | None = None) -> None:
    """Add sections to the published home page, as a generated site has them."""
    bid = uuid.UUID(business_id)

    async def _go(session: AsyncSession) -> None:
        website = (await session.execute(select(Website).where(Website.business_id == bid))).scalars().one()
        home = (
            await session.execute(
                select(WebsitePage).where(
                    WebsitePage.website_version_id == website.published_version_id,
                    WebsitePage.slug == "home",
                )
            )
        ).scalars().one()
        for index, section in enumerate(sections):
            session.add(WebsiteSection(
                page_id=home.id,
                business_id=bid,
                section_type_id=section["type"],
                content=section["content"],
                sort_order=100 + index,
                is_visible=True,
            ))
        if contact is not None:
            await session.execute(
                update(BusinessProfile).where(BusinessProfile.business_id == bid).values(contact=contact)
            )
        await session.flush()
        await MarketplaceIndexingService.reindex_business(
            session, business_id=bid, correlation_id=str(uuid.uuid4()), trigger="test"
        )

    _run_db(_go)


def _search(client: TestClient, **params: Any) -> dict[str, Any]:
    resp = client.get("/v1/public/search", params=params)
    assert resp.status_code == 200, resp.text
    return cast(dict[str, Any], resp.json()["data"])


@needs_db
def test_published_business_is_listed_with_place_category_and_actions(owner: dict[str, str]) -> None:
    client = TestClient(app)
    tag = uuid.uuid4().hex[:6]
    business = _create_business(
        client, owner, name=f"Amma Kitchen {tag}", business_type="other",
        description="Home food, podi and pickles made in our kitchen",
    )
    _publish_sections(
        business["id"],
        [
            {"type": "product_showcase", "content": {"anchor": "menu", "items": [{"title": f"Kaju Katli {tag}"}, {"title": "Gunpowder podi"}]}},
            {"type": "contact", "content": {"address": "4, Anna Nagar West, Chennai 600040"}},
        ],
        contact={"phone": "+91 98400 12345"},
    )

    found = _search(client, q=f"katli {tag}")
    listing = next(b for b in found["businesses"] if b["business_id"] == business["id"])
    assert (listing["family"], listing["category"]) == ("food-drink", "home-kitchens")
    assert listing["city"] == "Chennai"
    assert listing["locality"] == "Anna Nagar West"
    assert listing["postal_code"] == "600040"
    actions = {a["action"] for a in listing["actions"]}
    assert {"call", "visit_website"} <= actions
    assert "order" not in actions  # Orders is not switched on for this Business.
    assert not (_INVENTED & set(listing))

    # The category filter finds it; another family does not.
    assert any(b["business_id"] == business["id"] for b in _search(client, q=tag, family="food-drink")["businesses"])
    assert not any(b["business_id"] == business["id"] for b in _search(client, q=tag, family="fitness")["businesses"])
    # Its city is a hard filter; its PIN too.
    assert _search(client, q=tag, location="Chennai")["counts"]["businesses"] >= 1
    assert _search(client, q=tag, location="600040")["counts"]["businesses"] >= 1
    assert _search(client, q=tag, location="Madurai")["counts"]["businesses"] == 0
    # The profile says the same things, with nothing invented.
    profile = client.get(f"/v1/public/businesses/{business['slug']}").json()["data"]
    assert profile["business"]["category_label"] == "Home Kitchens"
    assert profile["business"]["area_label"] == "Anna Nagar West, Chennai"
    assert not (_INVENTED & set(profile["business"]))


@needs_db
def test_unpublished_private_and_opted_out_are_never_listed(owner: dict[str, str]) -> None:
    client = TestClient(app)
    tag = uuid.uuid4().hex[:6]
    draft = _create_business(client, owner, name=f"Draft Only {tag}", publish=False, opt_in=False)
    published_private = _create_business(client, owner, name=f"Published Private {tag}", opt_in=False)
    listed = _create_business(client, owner, name=f"Listed Then Gone {tag}")

    ids = {b["business_id"] for b in _search(client, q=tag)["businesses"]}
    assert listed["id"] in ids
    assert draft["id"] not in ids and published_private["id"] not in ids

    off = client.post(
        f"/v1/b/{listed['id']}/marketplace/visibility", json={"visibility": "private"}, headers=owner
    )
    assert off.status_code == 200, off.text
    assert listed["id"] not in {b["business_id"] for b in _search(client, q=tag)["businesses"]}
    assert client.get(f"/v1/public/businesses/{listed['slug']}").status_code == 404


@needs_db
def test_reconcile_sweeps_deleted_businesses_and_books_the_next_run(owner: dict[str, str]) -> None:
    client = TestClient(app)
    tag = uuid.uuid4().hex[:6]
    gone = _create_business(client, owner, name=f"Deleted Later {tag}")
    kept = _create_business(client, owner, name=f"Still Here {tag}")
    gone_id, kept_id = uuid.UUID(gone["id"]), uuid.UUID(kept["id"])

    async def _delete_and_reconcile(session: AsyncSession) -> dict[str, Any]:
        await session.execute(
            update(Business).where(Business.id == gone_id).values(deleted_at=datetime.now(timezone.utc))
        )
        return dict(
            await MarketplaceIndexingService.reconcile_all(
                session, correlation_id=str(uuid.uuid4()), business_ids=[gone_id, kept_id]
            )
        )

    result = _run_db(_delete_and_reconcile)
    assert result["swept"] == 1
    assert result["indexed"] == 1

    async def _projections(session: AsyncSession) -> set[uuid.UUID]:
        rows = await session.execute(
            select(MarketplaceBusinessProjection.business_id).where(
                MarketplaceBusinessProjection.business_id.in_([gone_id, kept_id])
            )
        )
        return {row[0] for row in rows}

    assert _run_db(_projections) == {kept_id}

    async def _schedule_twice(session: AsyncSession) -> tuple[bool, bool, int]:
        await session.execute(text(
            "UPDATE platform_scheduled_jobs SET status = 'cancelled' "
            "WHERE recurrence_key = 'marketplace.reconcile' AND status = 'pending'"
        ))
        first = await MarketplaceIndexingService.schedule_next_reconcile(session, minutes=30)
        second = await MarketplaceIndexingService.schedule_next_reconcile(session, minutes=30)
        pending = (await session.execute(text(
            "SELECT count(*) FROM platform_scheduled_jobs "
            "WHERE recurrence_key = 'marketplace.reconcile' AND status = 'pending'"
        ))).scalar_one()
        return first, second, int(pending)

    assert _run_db(_schedule_twice) == (True, False, 1)


@needs_db
def test_location_orders_results_without_hiding_the_rest(owner: dict[str, str]) -> None:
    client = TestClient(app)
    tag = uuid.uuid4().hex[:6]
    chennai = _create_business(client, owner, name=f"Madras Florist {tag}")
    kovai = _create_business(client, owner, name=f"Kovai Florist {tag}")
    _publish_sections(chennai["id"], [{"type": "contact", "content": {"address": "T Nagar, Chennai"}}])
    _publish_sections(kovai["id"], [{"type": "contact", "content": {"address": "RS Puram, Coimbatore"}}])

    near_chennai = _search(client, q=tag, place="Chennai", sort="nearest")["businesses"]
    near_kovai = _search(client, q=tag, place="641002", sort="nearest")["businesses"]
    assert [b["business_id"] for b in near_chennai][:2] == [chennai["id"], kovai["id"]]
    assert [b["business_id"] for b in near_kovai][:2] == [kovai["id"], chennai["id"]]
    # Town-centre coordinates never become a distance on screen.
    assert all(b["distance_km"] is None for b in near_chennai)
    # No duplicates, however the page is ordered.
    ids = [b["business_id"] for b in near_chennai]
    assert len(ids) == len(set(ids))


@needs_db
def test_partial_word_and_prefix_queries_still_find_a_business(owner: dict[str, str]) -> None:
    client = TestClient(app)
    tag = uuid.uuid4().hex[:6]
    business = _create_business(client, owner, name=f"Sundaram Sweets {tag}")
    # A prefix, as typed.
    assert any(b["business_id"] == business["id"] for b in _search(client, q=f"sundar {tag}")["businesses"])
    # Every word must match first; when none does, any word may.
    loose = _search(client, q=f"sundaram nonexistentword{tag}")
    assert loose["match"] == "any"
    assert any(b["business_id"] == business["id"] for b in loose["businesses"])


@needs_db
def test_discover_explains_every_personal_rail_and_invents_none(owner: dict[str, str]) -> None:
    client = TestClient(app)
    tag = uuid.uuid4().hex[:6]
    bakery = _create_business(
        client, owner, name=f"Crumb Bakery {tag}", business_type="cafe",
        description="Cakes, bread and pastries baked every morning",
    )

    plain = client.get("/v1/public/discover").json()["data"]
    assert plain["personalised"] is False
    assert plain["location_state"] == "none"
    assert not any(r["id"] == "for_you" for r in plain["rails"])
    assert any(f["id"] == "food-drink" and f["count"] >= 1 for f in plain["categories"])

    picked = client.get("/v1/public/discover", params={"searched": "cakes"}).json()["data"]
    for_you = next(r for r in picked["rails"] if r["id"] == "for_you")
    assert for_you["explain"]
    assert all(item["reason"] for item in for_you["items"])
    assert any(item["business_id"] == bakery["id"] for item in for_you["items"])
    assert "“cakes”" in next(i for i in for_you["items"] if i["business_id"] == bakery["id"])["reason"]
    ids = [i["business_id"] for i in for_you["items"]]
    assert len(ids) == len(set(ids))
    for rail in picked["rails"]:
        for item in rail["items"]:
            assert not (_INVENTED & set(item))

    # A booking id for a Business that is not listed never surfaces it.
    private = _create_business(client, owner, name=f"Private Salon {tag}", opt_in=False)
    again = client.get("/v1/public/discover", params={"used": private["id"]}).json()["data"]
    assert not any(r["id"] == "again" for r in again["rails"])

    # A place with nothing near says so rather than pretending.
    far = client.get("/v1/public/discover", params={"place": "Shillong"}).json()["data"]
    assert far["place"]["label"] == "Shillong"
    assert far["location_state"] in {"nearby", "none_nearby"}


@needs_db
def test_capability_filter_needs_the_module_and_something_to_order(owner: dict[str, str]) -> None:
    client = TestClient(app)
    tag = uuid.uuid4().hex[:6]
    business = _create_business(client, owner, name=f"No Orders Here {tag}")
    assert _search(client, q=tag)["counts"]["businesses"] >= 1
    assert not any(b["business_id"] == business["id"] for b in _search(client, q=tag, can="order")["businesses"])
    facets = _search(client, q=tag)["facets"]
    assert set(facets["capabilities"]) == {"order", "book", "enquire", "join"}


@needs_db
def test_places_endpoint_resolves_and_suggests() -> None:
    client = TestClient(app)
    data = client.get("/v1/public/places", params={"q": "Coim"}).json()["data"]
    assert any(s["city"] == "Coimbatore" for s in data["suggestions"])
    pin = client.get("/v1/public/places", params={"q": "600040"}).json()["data"]
    assert pin["resolved"]["label"] == "Chennai" and pin["resolved"]["precision"] == "pin"
    device = client.get("/v1/public/places", params={"near": "13.0827,80.2707"}).json()["data"]
    assert device["resolved"]["lat"] == 13.08
