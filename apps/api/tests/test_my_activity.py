"""Stage 7 Section 5 — My Activity consumer feed (Doc 09 ACC-011, Doc 11 §17.7).

Scope is deliberately narrow and these tests pin that narrowness in place:

  * `consumer_activity_projections` is written by BookingService and
    BookingLifecycleService ONLY. Orders and Payments do not feed it.
  * a row is written only when the booking's CustomerContact carries an
    `identity_id`. A guest booking writes nothing, pending FL-DEC-024
    (guest-to-authenticated linking).

`test_orders_do_not_appear_in_my_activity` and
`test_guest_booking_is_not_attributed_to_an_identity` exist to fail loudly if
someone later widens the projection without also widening the My Activity UI's
stated coverage — the surface claims Bookings only, and that claim must stay
true.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import jwt
import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_core.db import get_database_url
from platform_testing.db_helpers import ensure_auth_user
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"


def _token(sub: uuid.UUID, email: str) -> str:
    return jwt.encode(
        {"sub": str(sub), "email": email, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


def _headers(user_id: uuid.UUID, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(user_id, email)}"}


def _seed(user_id: uuid.UUID, email: str) -> None:
    async def _run() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await ensure_auth_user(session, user_id, email)
            await session.commit()
        await engine.dispose()

    asyncio.run(_run())


def _new_identity() -> tuple[dict[str, str], uuid.UUID, str]:
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed(user_id, email)
    return _headers(user_id, email), user_id, email


@pytest.fixture
def owner(monkeypatch: Any) -> tuple[dict[str, str], uuid.UUID]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    headers, user_id, _ = _new_identity()
    return headers, user_id


def _create_business(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"Activity Co {uuid.uuid4().hex[:8]}", "business_type": "salon"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    business_id = cast(str, resp.json()["data"]["business"]["id"])
    for module_id in (
        "workforce",
        "bookings",
        "offerings-catalog",
        "payments",
        "customer-relationships",
        "orders",
        "inventory",
    ):
        enabled = client.post(f"/v1/b/{business_id}/modules/{module_id}/enable", headers=headers)
        assert enabled.status_code == 200, enabled.text
    return business_id


def _primary_location_id(client: TestClient, headers: dict[str, str], business_id: str) -> str:
    resp = client.get(f"/v1/platform/businesses/{business_id}/locations", headers=headers)
    assert resp.status_code == 200, resp.text
    for loc in resp.json()["data"]:
        if loc["is_primary"]:
            return cast(str, loc["id"])
    raise AssertionError("primary location missing")


def _create_service(client: TestClient, headers: dict[str, str], business_id: str) -> str:
    resp = client.post(
        f"/v1/platform/businesses/{business_id}/products",
        json={
            "title": f"Consultation {uuid.uuid4().hex[:6]}",
            "offering_type": "service",
            "status": "active",
            "price_amount": 75.0,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return cast(str, resp.json()["data"]["id"])


def _create_linked_contact(
    client: TestClient,
    headers: dict[str, str],
    business_id: str,
    identity_id: uuid.UUID,
    email: str,
) -> str:
    """A CustomerContact carrying an identity_id — the only kind that projects."""
    resp = client.post(
        f"/v1/platform/businesses/{business_id}/customers",
        json={
            "display_name": "Booking Consumer",
            "email": email,
            "identity_id": str(identity_id),
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return cast(str, resp.json()["data"]["id"])


def _slot(hours_ahead: int = 24) -> tuple[str, str]:
    start = datetime.now(timezone.utc) + timedelta(hours=hours_ahead)
    return start.isoformat(), (start + timedelta(hours=1)).isoformat()


def _book(
    client: TestClient,
    headers: dict[str, str],
    business_id: str,
    location_id: str,
    offering_id: str,
    customer_contact_id: str | None,
) -> str:
    starts_at, ends_at = _slot(hours_ahead=24 + uuid.uuid4().int % 500)
    body: dict[str, Any] = {
        "location_id": location_id,
        "offering_id": offering_id,
        "reservation_mode": "appointment",
        "starts_at": starts_at,
        "ends_at": ends_at,
    }
    if customer_contact_id is not None:
        body["customer_contact_id"] = customer_contact_id
    resp = client.post(
        f"/v1/platform/businesses/{business_id}/bookings", json=body, headers=headers
    )
    assert resp.status_code == 200, resp.text
    return cast(str, resp.json()["data"]["id"])


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_booking_appears_in_my_activity(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    consumer_headers, consumer_id, consumer_email = _new_identity()

    with TestClient(app) as client:
        bid = _create_business(client, headers)
        location_id = _primary_location_id(client, headers, bid)
        offering_id = _create_service(client, headers, bid)
        contact_id = _create_linked_contact(client, headers, bid, consumer_id, consumer_email)
        booking_id = _book(client, headers, bid, location_id, offering_id, contact_id)

        feed = client.get("/v1/me/activity", headers=consumer_headers)
        assert feed.status_code == 200, feed.text
        payload = feed.json()
        rows = payload["data"]
        assert rows, "the consumer's own booking should appear in My Activity"
        mine = [row for row in rows if row["resource_id"] == booking_id]
        assert mine, f"booking {booking_id} missing from feed: {rows}"
        entry = mine[0]
        assert entry["resource_type"] == "booking"
        assert entry["activity_type"] == "booking.created"
        assert entry["business_id"] == bid
        assert entry["business_name"], "business name should be joined in for the consumer"
        assert entry["summary"].get("booking_number")

        # The surface must be able to state its own coverage truthfully.
        assert payload["meta"]["covered_resource_types"] == ["booking"]


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_activity_tracks_booking_status_changes(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    headers, _ = owner
    consumer_headers, consumer_id, consumer_email = _new_identity()

    with TestClient(app) as client:
        bid = _create_business(client, headers)
        location_id = _primary_location_id(client, headers, bid)
        offering_id = _create_service(client, headers, bid)
        contact_id = _create_linked_contact(client, headers, bid, consumer_id, consumer_email)
        booking_id = _book(client, headers, bid, location_id, offering_id, contact_id)

        confirmed = client.post(
            f"/v1/platform/businesses/{bid}/bookings/{booking_id}/status",
            json={"status": "confirmed"},
            headers=headers,
        )
        assert confirmed.status_code == 200, confirmed.text

        feed = client.get("/v1/me/activity", headers=consumer_headers)
        assert feed.status_code == 200
        rows = [r for r in feed.json()["data"] if r["resource_id"] == booking_id]
        types = {row["activity_type"] for row in rows}
        assert "booking.confirmed" in types, rows
        confirmed_row = next(r for r in rows if r["activity_type"] == "booking.confirmed")
        assert confirmed_row["summary"]["status"] == "confirmed"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_my_activity_is_identity_scoped(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    """One consumer never sees another's activity, even in the same Business."""
    headers, _ = owner
    consumer_headers, consumer_id, consumer_email = _new_identity()
    other_headers, _, _ = _new_identity()

    with TestClient(app) as client:
        bid = _create_business(client, headers)
        location_id = _primary_location_id(client, headers, bid)
        offering_id = _create_service(client, headers, bid)
        contact_id = _create_linked_contact(client, headers, bid, consumer_id, consumer_email)
        booking_id = _book(client, headers, bid, location_id, offering_id, contact_id)

        mine = client.get("/v1/me/activity", headers=consumer_headers).json()["data"]
        assert any(row["resource_id"] == booking_id for row in mine)

        theirs = client.get("/v1/me/activity", headers=other_headers)
        assert theirs.status_code == 200
        assert all(row["resource_id"] != booking_id for row in theirs.json()["data"])


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_guest_booking_is_not_attributed_to_an_identity(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    """A booking with no linked identity projects nothing.

    This is the FL-DEC-024 boundary, asserted rather than assumed: guest
    activity is NOT silently attached to any account.
    """
    headers, _ = owner
    consumer_headers, _, _ = _new_identity()

    with TestClient(app) as client:
        bid = _create_business(client, headers)
        location_id = _primary_location_id(client, headers, bid)
        offering_id = _create_service(client, headers, bid)
        booking_id = _book(client, headers, bid, location_id, offering_id, None)

        feed = client.get("/v1/me/activity", headers=consumer_headers)
        assert feed.status_code == 200
        assert all(row["resource_id"] != booking_id for row in feed.json()["data"])


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_orders_do_not_appear_in_my_activity(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    """Orders genuinely do not feed the projection yet.

    Pins the documented gap. If Orders start projecting, this fails and the My
    Activity page's "what is not here yet" copy must be updated with it.
    """
    headers, _ = owner
    consumer_headers, consumer_id, consumer_email = _new_identity()

    with TestClient(app) as client:
        bid = _create_business(client, headers)
        location_id = _primary_location_id(client, headers, bid)
        offering_id = _create_service(client, headers, bid)
        contact_id = _create_linked_contact(client, headers, bid, consumer_id, consumer_email)

        order = client.post(
            f"/v1/platform/businesses/{bid}/orders",
            json={
                "location_id": location_id,
                "customer_contact_id": contact_id,
                "payment_method": "cod",
                "idempotency_key": str(uuid.uuid4()),
                "items": [{"offering_id": offering_id, "quantity": 1}],
            },
            headers=headers,
        )
        assert order.status_code == 200, order.text
        order_id = order.json()["data"]["id"]

        feed = client.get("/v1/me/activity", headers=consumer_headers)
        assert feed.status_code == 200
        rows = feed.json()["data"]
        assert all(row["resource_id"] != order_id for row in rows)
        assert all(row["resource_type"] == "booking" for row in rows)


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_my_activity_requires_authentication() -> None:
    with TestClient(app) as client:
        assert client.get("/v1/me/activity").status_code == 401
