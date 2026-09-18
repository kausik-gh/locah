"""P0.8 end to end — resources configured and booked through the real API.

test_booking_resources.py exercises the allocation layer directly. This goes
through HTTP, so it covers permissions, entitlements, RLS under the real
platform_api role, and the booking lifecycle rather than the primitive alone.
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
pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")


def _headers(user_id: uuid.UUID, email: str) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(user_id),
            "email": email,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


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


@pytest.fixture
def owner(monkeypatch: Any) -> tuple[dict[str, str], uuid.UUID]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed(user_id, email)
    return _headers(user_id, email), user_id


@pytest.fixture
def stranger(monkeypatch: Any) -> dict[str, str]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed(user_id, email)
    return _headers(user_id, email)


def _business(client: TestClient, headers: dict[str, str], business_type: str = "salon") -> str:
    resp = client.post(
        "/v1/platform/businesses",
        json={
            "display_name": f"ResCo {uuid.uuid4().hex[:8]}",
            "business_type": business_type,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    business_id = cast(str, resp.json()["data"]["business"]["id"])
    for mid in ("workforce", "bookings", "offerings-catalog", "payments"):
        assert (
            client.post(f"/v1/b/{business_id}/modules/{mid}/enable", headers=headers).status_code
            == 200
        )
    return business_id


def _location(client: TestClient, headers: dict[str, str], business_id: str) -> str:
    resp = client.get(f"/v1/platform/businesses/{business_id}/locations", headers=headers)
    assert resp.status_code == 200, resp.text
    for loc in resp.json()["data"]:
        if loc["is_primary"]:
            return cast(str, loc["id"])
    raise AssertionError("primary location missing")


def _resource(
    client: TestClient, headers: dict[str, str], business_id: str, location_id: str, **over: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "location_id": location_id,
        "resource_type": "room",
        "name": f"Res {uuid.uuid4().hex[:6]}",
        "allocation_mode": "exclusive",
        "capacity": 1,
    }
    body.update(over)
    resp = client.post(
        f"/v1/platform/businesses/{business_id}/bookings/resources", json=body, headers=headers
    )
    assert resp.status_code == 200, resp.text
    return cast(dict[str, Any], resp.json()["data"])


def _slot(offset_days: int = 40, hour: int = 10, hours: int = 1) -> tuple[str, str]:
    start = datetime.now(timezone.utc).replace(
        hour=hour, minute=0, second=0, microsecond=0
    ) + timedelta(days=offset_days)
    return start.isoformat(), (start + timedelta(hours=hours)).isoformat()


def _book(
    client: TestClient,
    headers: dict[str, str],
    business_id: str,
    location_id: str,
    *,
    starts_at: str,
    ends_at: str,
    **over: Any,
) -> Any:
    body: dict[str, Any] = {
        "location_id": location_id,
        "title": "Test booking",
        "starts_at": starts_at,
        "ends_at": ends_at,
        "party_size": 1,
    }
    body.update(over)
    return client.post(
        f"/v1/platform/businesses/{business_id}/bookings", json=body, headers=headers
    )


# ------------------------------------------------------------------ config


def test_resource_crud_and_listing(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _business(client, headers)
    location_id = _location(client, headers, business_id)

    created = _resource(
        client, headers, business_id, location_id, resource_type="table", max_party_size=4
    )
    assert created["allocation_mode"] == "exclusive"
    assert created["capacity"] == 1

    listed = client.get(
        f"/v1/platform/businesses/{business_id}/bookings/resources", headers=headers
    )
    assert listed.status_code == 200
    assert any(r["id"] == created["id"] for r in listed.json()["data"]["resources"])

    patched = client.patch(
        f"/v1/platform/businesses/{business_id}/bookings/resources/{created['id']}",
        json={"name": "Renamed", "buffer_after_minutes": 10, "version": created["version"]},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["name"] == "Renamed"
    assert patched.json()["data"]["buffer_after_minutes"] == 10

    archived = client.delete(
        f"/v1/platform/businesses/{business_id}/bookings/resources/{created['id']}",
        headers=headers,
    )
    assert archived.status_code == 200, archived.text
    remaining = client.get(
        f"/v1/platform/businesses/{business_id}/bookings/resources", headers=headers
    ).json()["data"]["resources"]
    assert not any(r["id"] == created["id"] for r in remaining)


def test_exclusive_resource_cannot_be_configured_with_capacity(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    """An exclusive resource with capacity 5 is a contradiction, not a shortcut."""
    headers, _ = owner
    client = TestClient(app)
    business_id = _business(client, headers)
    location_id = _location(client, headers, business_id)

    resp = client.post(
        f"/v1/platform/businesses/{business_id}/bookings/resources",
        json={
            "location_id": location_id,
            "resource_type": "room",
            "name": "Contradiction",
            "allocation_mode": "exclusive",
            "capacity": 5,
        },
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


# ----------------------------------------------------------------- booking


def test_booking_claims_the_resource_and_conflicts(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _business(client, headers)
    location_id = _location(client, headers, business_id)
    room = _resource(client, headers, business_id, location_id)
    starts_at, ends_at = _slot()

    first = _book(
        client,
        headers,
        business_id,
        location_id,
        starts_at=starts_at,
        ends_at=ends_at,
        resource_ids=[room["id"]],
    )
    assert first.status_code == 200, first.text

    second = _book(
        client,
        headers,
        business_id,
        location_id,
        starts_at=starts_at,
        ends_at=ends_at,
        resource_ids=[room["id"]],
    )
    assert second.status_code == 409, second.text


def test_cancelling_releases_the_resource(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _business(client, headers)
    location_id = _location(client, headers, business_id)
    room = _resource(client, headers, business_id, location_id)
    starts_at, ends_at = _slot(offset_days=41)

    first = _book(
        client,
        headers,
        business_id,
        location_id,
        starts_at=starts_at,
        ends_at=ends_at,
        resource_ids=[room["id"]],
    )
    assert first.status_code == 200, first.text
    booking_id = first.json()["data"]["id"]

    cancelled = client.post(
        f"/v1/platform/businesses/{business_id}/bookings/{booking_id}/status",
        json={"status": "cancelled", "reason": "Test"},
        headers=headers,
    )
    assert cancelled.status_code == 200, cancelled.text

    again = _book(
        client,
        headers,
        business_id,
        location_id,
        starts_at=starts_at,
        ends_at=ends_at,
        resource_ids=[room["id"]],
    )
    assert again.status_code == 200, again.text


def test_rescheduling_moves_the_claim(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _business(client, headers)
    location_id = _location(client, headers, business_id)
    room = _resource(client, headers, business_id, location_id)
    starts_at, ends_at = _slot(offset_days=42, hour=9)
    later_start, later_end = _slot(offset_days=42, hour=14)

    created = _book(
        client,
        headers,
        business_id,
        location_id,
        starts_at=starts_at,
        ends_at=ends_at,
        resource_ids=[room["id"]],
    )
    assert created.status_code == 200, created.text
    booking_id = created.json()["data"]["id"]

    moved = client.post(
        f"/v1/platform/businesses/{business_id}/bookings/{booking_id}/reschedule",
        json={"starts_at": later_start, "ends_at": later_end},
        headers=headers,
    )
    assert moved.status_code == 200, moved.text

    # The original window is free again...
    reuse = _book(
        client,
        headers,
        business_id,
        location_id,
        starts_at=starts_at,
        ends_at=ends_at,
        resource_ids=[room["id"]],
    )
    assert reuse.status_code == 200, reuse.text

    # ...and the new one is taken.
    clash = _book(
        client,
        headers,
        business_id,
        location_id,
        starts_at=later_start,
        ends_at=later_end,
        resource_ids=[room["id"]],
    )
    assert clash.status_code == 409, clash.text


def test_pooled_capacity_is_exhausted_not_exceeded(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _business(client, headers, business_type="gym")
    location_id = _location(client, headers, business_id)
    klass = _resource(
        client,
        headers,
        business_id,
        location_id,
        resource_type="class_pool",
        allocation_mode="pooled",
        capacity=3,
    )
    starts_at, ends_at = _slot(offset_days=43)

    for _ in range(3):
        ok = _book(
            client,
            headers,
            business_id,
            location_id,
            starts_at=starts_at,
            ends_at=ends_at,
            resource_ids=[klass["id"]],
            party_size=1,
        )
        assert ok.status_code == 200, ok.text

    full = _book(
        client,
        headers,
        business_id,
        location_id,
        starts_at=starts_at,
        ends_at=ends_at,
        resource_ids=[klass["id"]],
        party_size=1,
    )
    assert full.status_code == 409, full.text


def test_client_cannot_inflate_capacity(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    """Capacity comes from configuration, whatever the request claims.

    The old path took `capacity` off the payload and then checked against it, so
    a large enough number made the check unfailable.
    """
    headers, _ = owner
    client = TestClient(app)
    business_id = _business(client, headers, business_type="gym")
    location_id = _location(client, headers, business_id)
    klass = _resource(
        client,
        headers,
        business_id,
        location_id,
        resource_type="class_pool",
        allocation_mode="pooled",
        capacity=1,
    )
    starts_at, ends_at = _slot(offset_days=44)

    first = _book(
        client,
        headers,
        business_id,
        location_id,
        starts_at=starts_at,
        ends_at=ends_at,
        resource_ids=[klass["id"]],
    )
    assert first.status_code == 200, first.text

    overreach = _book(
        client,
        headers,
        business_id,
        location_id,
        starts_at=starts_at,
        ends_at=ends_at,
        resource_ids=[klass["id"]],
        capacity=9999,
    )
    assert overreach.status_code == 409, "a request-supplied capacity overrode the configured one"


def test_inactive_resource_cannot_be_booked(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _business(client, headers)
    location_id = _location(client, headers, business_id)
    room = _resource(client, headers, business_id, location_id)
    client.patch(
        f"/v1/platform/businesses/{business_id}/bookings/resources/{room['id']}",
        json={"is_active": False},
        headers=headers,
    )
    starts_at, ends_at = _slot(offset_days=45)

    resp = _book(
        client,
        headers,
        business_id,
        location_id,
        starts_at=starts_at,
        ends_at=ends_at,
        resource_ids=[room["id"]],
    )
    assert resp.status_code == 422, resp.text


def test_party_larger_than_the_resource_is_refused(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _business(client, headers, business_type="restaurant")
    location_id = _location(client, headers, business_id)
    table = _resource(
        client, headers, business_id, location_id, resource_type="table", max_party_size=4
    )
    starts_at, ends_at = _slot(offset_days=46)

    resp = _book(
        client,
        headers,
        business_id,
        location_id,
        starts_at=starts_at,
        ends_at=ends_at,
        resource_ids=[table["id"]],
        party_size=6,
    )
    assert resp.status_code == 422, resp.text


def test_idempotent_retry_returns_the_same_booking(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    """A retried request must not consume the resource twice."""
    headers, _ = owner
    client = TestClient(app)
    business_id = _business(client, headers)
    location_id = _location(client, headers, business_id)
    room = _resource(client, headers, business_id, location_id)
    starts_at, ends_at = _slot(offset_days=47)
    key = f"idem-{uuid.uuid4().hex[:10]}"

    first = _book(
        client,
        headers,
        business_id,
        location_id,
        starts_at=starts_at,
        ends_at=ends_at,
        resource_ids=[room["id"]],
        idempotency_key=key,
    )
    assert first.status_code == 200, first.text
    retry = _book(
        client,
        headers,
        business_id,
        location_id,
        starts_at=starts_at,
        ends_at=ends_at,
        resource_ids=[room["id"]],
        idempotency_key=key,
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["data"]["id"] == first.json()["data"]["id"]


# ------------------------------------------------------------ availability


def test_availability_lists_only_free_resources(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _business(client, headers)
    location_id = _location(client, headers, business_id)
    taken = _resource(client, headers, business_id, location_id, resource_type="room")
    spare = _resource(client, headers, business_id, location_id, resource_type="room")
    starts_at, ends_at = _slot(offset_days=48)

    assert (
        _book(
            client,
            headers,
            business_id,
            location_id,
            starts_at=starts_at,
            ends_at=ends_at,
            resource_ids=[taken["id"]],
        ).status_code
        == 200
    )

    avail = client.get(
        f"/v1/platform/businesses/{business_id}/bookings/resources/availability",
        params={"starts_at": starts_at, "ends_at": ends_at, "resource_type": "room"},
        headers=headers,
    )
    assert avail.status_code == 200, avail.text
    ids = {r["resource_id"] for r in avail.json()["data"]["resources"]}
    assert spare["id"] in ids
    assert taken["id"] not in ids


# ---------------------------------------------------------------- security


def test_resources_are_tenant_isolated(
    owner: tuple[dict[str, str], uuid.UUID], stranger: dict[str, str]
) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _business(client, headers)
    location_id = _location(client, headers, business_id)
    room = _resource(client, headers, business_id, location_id)

    for resp in (
        client.get(f"/v1/platform/businesses/{business_id}/bookings/resources", headers=stranger),
        client.patch(
            f"/v1/platform/businesses/{business_id}/bookings/resources/{room['id']}",
            json={"name": "Hijacked"},
            headers=stranger,
        ),
        client.delete(
            f"/v1/platform/businesses/{business_id}/bookings/resources/{room['id']}",
            headers=stranger,
        ),
    ):
        assert resp.status_code in (403, 404), resp.text


def test_resource_endpoints_require_authentication(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _business(client, headers)
    resp = client.get(f"/v1/platform/businesses/{business_id}/bookings/resources")
    assert resp.status_code == 401, resp.text


def test_resource_from_another_business_cannot_be_booked(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    """A resource id from one business must not be usable by another."""
    headers, _ = owner
    client = TestClient(app)
    first_id = _business(client, headers)
    first_location = _location(client, headers, first_id)
    foreign = _resource(client, headers, first_id, first_location)

    second_id = _business(client, headers)
    second_location = _location(client, headers, second_id)
    starts_at, ends_at = _slot(offset_days=49)

    resp = _book(
        client,
        headers,
        second_id,
        second_location,
        starts_at=starts_at,
        ends_at=ends_at,
        resource_ids=[foreign["id"]],
    )
    assert resp.status_code == 404, resp.text
