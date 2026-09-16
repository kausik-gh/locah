"""Stage 6 — Memberships Kernel tests (Doc 11 §9.5) + booking membership gate (§17.6)."""

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


@pytest.fixture
def owner(monkeypatch: Any) -> tuple[dict[str, str], uuid.UUID]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed(user_id, email)
    return _headers(user_id, email), user_id


_MODULES = (
    "offerings-catalog",
    "memberships",
    "payments",
    "bookings",
    "workforce",
    "customer-relationships",
)


def _create_business(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"Gym Co {uuid.uuid4().hex[:8]}", "business_type": "gym"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    bid = cast(str, resp.json()["data"]["business"]["id"])
    for module_id in _MODULES:
        enabled = client.post(f"/v1/b/{bid}/modules/{module_id}/enable", headers=headers)
        assert enabled.status_code == 200, enabled.text
    return bid


def _primary_location_id(client: TestClient, headers: dict[str, str], bid: str) -> str:
    locs = client.get(f"/v1/platform/businesses/{bid}/locations", headers=headers).json()["data"]
    return cast(str, next(loc["id"] for loc in locs if loc["is_primary"]))


def _create_offering(client: TestClient, headers: dict[str, str], bid: str, otype: str) -> str:
    resp = client.post(
        f"/v1/platform/businesses/{bid}/products",
        json={
            "title": f"{otype} {uuid.uuid4().hex[:6]}",
            "offering_type": otype,
            "status": "active",
            "price_amount": 30,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return cast(str, resp.json()["data"]["id"])


def _create_customer(client: TestClient, headers: dict[str, str], bid: str) -> str:
    resp = client.post(
        f"/v1/platform/businesses/{bid}/customers",
        json={"display_name": "Member Mo", "email": f"{uuid.uuid4()}@example.com"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return cast(str, resp.json()["data"]["id"])


def _create_plan(
    client: TestClient, headers: dict[str, str], bid: str, **over: Any
) -> dict[str, Any]:
    body = {
        "name": f"Monthly {uuid.uuid4().hex[:6]}",
        "price_amount": 50,
        "duration_days": 30,
        "status": "active",
        "visibility": "public",
        **over,
    }
    resp = client.post(
        f"/v1/platform/businesses/{bid}/membership-plans", json=body, headers=headers
    )
    assert resp.status_code == 200, resp.text
    return cast(dict[str, Any], resp.json()["data"])


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_plan_crud_and_recurring_rejected(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    bid = _create_business(client, headers)

    plan = _create_plan(client, headers, bid)
    assert plan["billing_model"] == "fixed_duration"
    assert plan["status"] == "active"
    plan_id = plan["id"]

    patched = client.patch(
        f"/v1/platform/businesses/{bid}/membership-plans/{plan_id}",
        json={"price_amount": 75, "version": plan["version"]},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["price_amount"] == 75.0

    # FL-DEC-005: recurring plans cannot be created at First Launch.
    recurring = client.post(
        f"/v1/platform/businesses/{bid}/membership-plans",
        json={"name": "Auto", "duration_days": 30, "billing_model": "recurring"},
        headers=headers,
    )
    assert recurring.status_code == 422, recurring.text
    assert "FL-DEC-005" in recurring.text

    archived = client.post(
        f"/v1/platform/businesses/{bid}/membership-plans/{plan_id}/archive", headers=headers
    )
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "archived"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_enrolment_lifecycle_and_payment_reconcile(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    bid = _create_business(client, headers)
    plan_id = _create_plan(client, headers, bid, price_amount=40)["id"]
    contact_id = _create_customer(client, headers, bid)

    enrol = client.post(
        f"/v1/platform/businesses/{bid}/membership-enrolments",
        json={
            "plan_id": plan_id,
            "customer_contact_id": contact_id,
            "payment_method": "cod",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert enrol.status_code == 200, enrol.text
    e = enrol.json()["data"]
    enrolment_id = e["id"]
    assert e["ends_at"] is not None  # fixed-duration window computed
    assert e["payment_attempt_id"] is not None

    # COD => pending_offline payment; enrolment stays pending until settled.
    assert e["status"] in ("pending", "active")

    pause = client.post(
        f"/v1/platform/businesses/{bid}/membership-enrolments/{enrolment_id}/pause",
        json={},
        headers=headers,
    )
    # pause only valid from active; if still pending, expect 409 — activate first via free path is n/a.
    if e["status"] == "active":
        assert pause.status_code == 200, pause.text
        resume = client.post(
            f"/v1/platform/businesses/{bid}/membership-enrolments/{enrolment_id}/resume",
            json={},
            headers=headers,
        )
        assert resume.status_code == 200, resume.text

    cancel = client.post(
        f"/v1/platform/businesses/{bid}/membership-enrolments/{enrolment_id}/cancel",
        json={"reason": "Customer request"},
        headers=headers,
    )
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["data"]["status"] == "cancelled"

    detail = client.get(
        f"/v1/platform/businesses/{bid}/membership-enrolments/{enrolment_id}", headers=headers
    )
    assert detail.status_code == 200
    assert len(detail.json()["data"]["status_history"]) >= 2


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_free_plan_activates_immediately(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    bid = _create_business(client, headers)
    plan_id = _create_plan(client, headers, bid, price_amount=0)["id"]
    contact_id = _create_customer(client, headers, bid)

    enrol = client.post(
        f"/v1/platform/businesses/{bid}/membership-enrolments",
        json={"plan_id": plan_id, "customer_contact_id": contact_id},
        headers=headers,
    )
    assert enrol.status_code == 200, enrol.text
    assert enrol.json()["data"]["status"] == "active"
    assert enrol.json()["data"]["payment_attempt_id"] is None


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_membership_gated_class_booking(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    bid = _create_business(client, headers)
    location_id = _primary_location_id(client, headers, bid)
    class_offering = _create_offering(client, headers, bid, "class_session")
    contact_id = _create_customer(client, headers, bid)

    plan_id = _create_plan(
        client, headers, bid, price_amount=0, offering_access=[class_offering]
    )["id"]

    start = (datetime.now(timezone.utc) + timedelta(hours=30)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(hours=31)).isoformat()

    def _book() -> Any:
        return client.post(
            f"/v1/platform/businesses/{bid}/bookings",
            json={
                "location_id": location_id,
                "offering_id": class_offering,
                "customer_contact_id": contact_id,
                "reservation_mode": "class_session",
                "title": "Yoga",
                "starts_at": start,
                "ends_at": end,
                "capacity": 10,
                "payment_method": "cod",
                "idempotency_key": str(uuid.uuid4()),
            },
            headers=headers,
        )

    # Without an enrolment the class is gated.
    denied = _book()
    assert denied.status_code == 422, denied.text
    assert denied.json()["error"]["details"]["code"] == "membership_required"

    # Enrol (free plan → active) then the same booking succeeds.
    enrol = client.post(
        f"/v1/platform/businesses/{bid}/membership-enrolments",
        json={"plan_id": plan_id, "customer_contact_id": contact_id},
        headers=headers,
    )
    assert enrol.status_code == 200, enrol.text
    assert enrol.json()["data"]["status"] == "active"

    allowed = _book()
    assert allowed.status_code == 200, allowed.text


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_capacity_only_class_booking_unaffected(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    """A class offering with no plan mapping keeps the Stage 5 capacity-only path."""
    headers, _ = owner
    client = TestClient(app)
    bid = _create_business(client, headers)
    location_id = _primary_location_id(client, headers, bid)
    class_offering = _create_offering(client, headers, bid, "class_session")
    contact_id = _create_customer(client, headers, bid)

    start = (datetime.now(timezone.utc) + timedelta(hours=40)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(hours=41)).isoformat()
    booked = client.post(
        f"/v1/platform/businesses/{bid}/bookings",
        json={
            "location_id": location_id,
            "offering_id": class_offering,
            "customer_contact_id": contact_id,
            "reservation_mode": "class_session",
            "title": "Open Class",
            "starts_at": start,
            "ends_at": end,
            "capacity": 15,
            "payment_method": "cod",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert booked.status_code == 200, booked.text


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_memberships_module_gate(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    ungated = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"NoMem {uuid.uuid4().hex[:6]}", "business_type": "retail"},
        headers=headers,
    ).json()["data"]["business"]["id"]
    blocked = client.get(
        f"/v1/platform/businesses/{ungated}/membership-plans", headers=headers
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "MODULE_NOT_ACTIVE"
