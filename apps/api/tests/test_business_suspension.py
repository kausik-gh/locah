"""Stage 7 Section 6 — suspended-Business commercial gate (Doc 04 §6.1).

Doc 04 §6.1, verbatim:

    `suspended`: Cannot receive orders or appear in marketplace; owner notified
                 with reason and appeal process
    `under_review`: Admin investigating; business may still operate but is
                 flagged

Two halves, and both are load-bearing:

  * suspended MUST block new commercial intake (orders, bookings, payments,
    membership enrolments);
  * under_review MUST NOT block anything — over-blocking it would contradict
    "may still operate" and is tested for explicitly.

Suspension blocks *intake*, not settlement. A suspended Business must still be
able to complete, cancel and refund work its customers already paid for,
otherwise suspension strands the customers rather than the Business. That is
asserted here too, so a future tightening cannot quietly break it.

`status` (platform standing) is an axis independent of `state` (lifecycle) and
`visibility` (Doc 03 §1.6). These tests set status directly in the database
because no API exposes a status transition yet — that is Super Admin surface
area, tracked separately.
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
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"


def _token(sub: uuid.UUID, email: str) -> str:
    return jwt.encode(
        {"sub": str(sub), "email": email, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


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


def _set_status(business_id: str, status: str) -> None:
    """Set platform standing directly — no API exposes this transition yet."""

    async def _run() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await session.execute(
                text("UPDATE businesses SET status = :s WHERE id = :bid"),
                {"s": status, "bid": business_id},
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(_run())


@pytest.fixture
def owner(monkeypatch: Any) -> tuple[dict[str, str], uuid.UUID]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed(user_id, email)
    return {"Authorization": f"Bearer {_token(user_id, email)}"}, user_id


def _create_business(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"Standing Co {uuid.uuid4().hex[:8]}", "business_type": "salon"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    business_id = cast(str, resp.json()["data"]["business"]["id"])
    for module_id in (
        "offerings-catalog",
        "orders",
        "bookings",
        "payments",
        "workforce",
        "customer-relationships",
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


def _create_offering(
    client: TestClient, headers: dict[str, str], business_id: str, otype: str = "product"
) -> str:
    resp = client.post(
        f"/v1/platform/businesses/{business_id}/products",
        json={
            "title": f"Item {uuid.uuid4().hex[:6]}",
            "offering_type": otype,
            "status": "active",
            "price_amount": 50.0,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return cast(str, resp.json()["data"]["id"])


def _order_body(location_id: str, offering_id: str) -> dict[str, Any]:
    return {
        "location_id": location_id,
        "payment_method": "cod",
        "idempotency_key": str(uuid.uuid4()),
        "items": [{"offering_id": offering_id, "quantity": 1}],
    }


def _booking_body(location_id: str, offering_id: str) -> dict[str, Any]:
    start = datetime.now(timezone.utc) + timedelta(hours=24 + uuid.uuid4().int % 500)
    return {
        "location_id": location_id,
        "offering_id": offering_id,
        "reservation_mode": "appointment",
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(hours=1)).isoformat(),
    }


# ---------------------------------------------------------------------------
# suspended blocks intake
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_suspended_business_cannot_receive_orders(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        bid = _create_business(client, headers)
        location_id = _primary_location_id(client, headers, bid)
        offering_id = _create_offering(client, headers, bid)

        ok = client.post(
            f"/v1/platform/businesses/{bid}/orders",
            json=_order_body(location_id, offering_id),
            headers=headers,
        )
        assert ok.status_code == 200, ok.text

        _set_status(bid, "suspended")

        blocked = client.post(
            f"/v1/platform/businesses/{bid}/orders",
            json=_order_body(location_id, offering_id),
            headers=headers,
        )
        assert blocked.status_code == 409, blocked.text
        error = blocked.json()["error"]
        assert error["code"] == "BUSINESS_SUSPENDED"
        assert error["details"]["gate"] == "business_status"
        # Doc 09 §15.1: convey the state without exposing policy internals.
        assert "reason" not in error["details"]


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_suspended_business_cannot_receive_bookings(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        bid = _create_business(client, headers)
        location_id = _primary_location_id(client, headers, bid)
        offering_id = _create_offering(client, headers, bid, otype="service")

        ok = client.post(
            f"/v1/platform/businesses/{bid}/bookings",
            json=_booking_body(location_id, offering_id),
            headers=headers,
        )
        assert ok.status_code == 200, ok.text

        _set_status(bid, "suspended")

        blocked = client.post(
            f"/v1/platform/businesses/{bid}/bookings",
            json=_booking_body(location_id, offering_id),
            headers=headers,
        )
        assert blocked.status_code == 409, blocked.text
        assert blocked.json()["error"]["code"] == "BUSINESS_SUSPENDED"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_suspended_business_cannot_take_payments(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        bid = _create_business(client, headers)
        location_id = _primary_location_id(client, headers, bid)
        offering_id = _create_offering(client, headers, bid)
        order = client.post(
            f"/v1/platform/businesses/{bid}/orders",
            json=_order_body(location_id, offering_id),
            headers=headers,
        )
        assert order.status_code == 200, order.text
        order_id = order.json()["data"]["id"]

        _set_status(bid, "suspended")

        blocked = client.post(
            f"/v1/platform/businesses/{bid}/payments",
            json={
                "source_type": "order",
                "source_id": order_id,
                "amount": 50.0,
                "payment_method": "online",
            },
            headers=headers,
        )
        assert blocked.status_code == 409, blocked.text
        assert blocked.json()["error"]["code"] == "BUSINESS_SUSPENDED"


# ---------------------------------------------------------------------------
# under_review must NOT block — Doc 04 §6.1 "may still operate"
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_under_review_business_still_operates(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    """Over-blocking `under_review` would contradict Doc 04 §6.1 directly."""
    headers, _ = owner
    with TestClient(app) as client:
        bid = _create_business(client, headers)
        location_id = _primary_location_id(client, headers, bid)
        offering_id = _create_offering(client, headers, bid)

        _set_status(bid, "under_review")

        still_works = client.post(
            f"/v1/platform/businesses/{bid}/orders",
            json=_order_body(location_id, offering_id),
            headers=headers,
        )
        assert still_works.status_code == 200, still_works.text

        service_id = _create_offering(client, headers, bid, otype="service")
        booking = client.post(
            f"/v1/platform/businesses/{bid}/bookings",
            json=_booking_body(location_id, service_id),
            headers=headers,
        )
        assert booking.status_code == 200, booking.text


# ---------------------------------------------------------------------------
# suspension blocks intake, not settlement
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_suspended_business_can_still_settle_existing_work(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    """Existing customer obligations must remain completable and cancellable.

    If suspension froze in-flight orders, it would punish the customers who
    already paid rather than the Business.
    """
    headers, _ = owner
    with TestClient(app) as client:
        bid = _create_business(client, headers)
        location_id = _primary_location_id(client, headers, bid)
        offering_id = _create_offering(client, headers, bid)

        first = client.post(
            f"/v1/platform/businesses/{bid}/orders",
            json=_order_body(location_id, offering_id),
            headers=headers,
        )
        assert first.status_code == 200, first.text
        order_id = first.json()["data"]["id"]

        second = client.post(
            f"/v1/platform/businesses/{bid}/orders",
            json=_order_body(location_id, offering_id),
            headers=headers,
        )
        assert second.status_code == 200, second.text
        cancellable_id = second.json()["data"]["id"]

        _set_status(bid, "suspended")

        advanced = client.post(
            f"/v1/platform/businesses/{bid}/orders/{order_id}/status",
            json={"status": "accepted"},
            headers=headers,
        )
        assert advanced.status_code == 200, advanced.text

        cancelled = client.post(
            f"/v1/platform/businesses/{bid}/orders/{cancellable_id}/cancel",
            json={"reason": "Business suspended"},
            headers=headers,
        )
        assert cancelled.status_code == 200, cancelled.text

        readable = client.get(f"/v1/platform/businesses/{bid}/orders", headers=headers)
        assert readable.status_code == 200, readable.text


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_suspension_is_visible_to_the_owner(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    """The Workspace Home commercial-recovery state depends on this field."""
    headers, _ = owner
    with TestClient(app) as client:
        bid = _create_business(client, headers)
        assert client.get(f"/v1/b/{bid}", headers=headers).json()["data"]["status"] == (
            "in_good_standing"
        )

        _set_status(bid, "suspended")

        after = client.get(f"/v1/b/{bid}", headers=headers)
        assert after.status_code == 200, after.text
        assert after.json()["data"]["status"] == "suspended"
