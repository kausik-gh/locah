"""Stage 3 — Location & People Kernel tests."""

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
from platform_core.models import PlatformAuditEvent, PlatformOutboxEvent
from platform_core.permissions import LOCATIONS_READ, WORKFORCE_READ
from platform_core.authorization.resolver import AuthorizationService
from platform_testing.db_helpers import ensure_auth_user
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"


def _token(sub: uuid.UUID, email: str) -> str:
    return jwt.encode(
        {
            "sub": str(sub),
            "email": email,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
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


def _create_business(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"Stage3 Co {uuid.uuid4().hex[:8]}", "business_type": "retail"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    business_id = cast(str, resp.json()["data"]["business"]["id"])
    # Gate [7] (Doc 12 SS8.9): optional-module operations require an active module.
    for module_id in ("workforce",):
        enabled = client.post(
            f"/v1/b/{business_id}/modules/{module_id}/enable", headers=headers
        )
        assert enabled.status_code == 200, enabled.text
    return business_id


def _primary_location_id(client: TestClient, headers: dict[str, str], business_id: str) -> str:
    resp = client.get(f"/v1/platform/businesses/{business_id}/locations", headers=headers)
    assert resp.status_code == 200, resp.text
    for loc in resp.json()["data"]:
        if loc["is_primary"]:
            return cast(str, loc["id"])
    raise AssertionError("primary location missing")


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_location_crud_and_primary_rules(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)
    primary_id = _primary_location_id(client, headers, business_id)

    branch_resp = client.post(
        f"/v1/platform/businesses/{business_id}/locations",
        json={"name": "Downtown Branch", "timezone": "America/New_York", "internal_code": "DT-01"},
        headers=headers,
    )
    assert branch_resp.status_code == 200, branch_resp.text
    branch_id = branch_resp.json()["data"]["id"]
    assert branch_resp.json()["data"]["status"] == "active"

    archive_primary = client.post(
        f"/v1/platform/businesses/{business_id}/locations/{primary_id}/archive",
        json={},
        headers=headers,
    )
    assert archive_primary.status_code == 422, archive_primary.text

    set_primary = client.post(
        f"/v1/platform/businesses/{business_id}/locations/{branch_id}/set-primary",
        json={},
        headers=headers,
    )
    assert set_primary.status_code == 200, set_primary.text
    assert set_primary.json()["data"]["is_primary"] is True

    old_primary = client.get(
        f"/v1/platform/businesses/{business_id}/locations/{primary_id}", headers=headers
    )
    assert old_primary.json()["data"]["is_primary"] is False

    archive_old = client.post(
        f"/v1/platform/businesses/{business_id}/locations/{primary_id}/archive",
        json={},
        headers=headers,
    )
    assert archive_old.status_code == 200, archive_old.text
    assert archive_old.json()["data"]["status"] == "archived"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_employee_assign_transfer_deactivate(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)
    primary_id = _primary_location_id(client, headers, business_id)

    branch_resp = client.post(
        f"/v1/platform/businesses/{business_id}/locations",
        json={"name": "Uptown Branch"},
        headers=headers,
    )
    branch_id = branch_resp.json()["data"]["id"]

    emp_resp = client.post(
        f"/v1/platform/businesses/{business_id}/employees",
        json={
            "display_name": "Alex Provider",
            "designation": "Stylist",
            "location_ids": [primary_id],
            "primary_location_id": primary_id,
        },
        headers=headers,
    )
    assert emp_resp.status_code == 200, emp_resp.text
    employee_id = emp_resp.json()["data"]["id"]
    assert len(emp_resp.json()["data"]["location_assignments"]) == 1

    assign_resp = client.post(
        f"/v1/platform/businesses/{business_id}/employees/{employee_id}/locations",
        json={"location_id": branch_id, "is_primary": False},
        headers=headers,
    )
    assert assign_resp.status_code == 200, assign_resp.text

    transfer_resp = client.post(
        f"/v1/platform/businesses/{business_id}/employees/{employee_id}/transfer",
        json={
            "from_location_id": primary_id,
            "to_location_id": branch_id,
            "set_primary": True,
        },
        headers=headers,
    )
    assert transfer_resp.status_code == 200, transfer_resp.text
    assignments = transfer_resp.json()["data"]["location_assignments"]
    assert any(a["location_id"] == branch_id and a["is_primary"] for a in assignments)
    assert not any(a["location_id"] == primary_id for a in assignments)

    deactivate_resp = client.post(
        f"/v1/platform/businesses/{business_id}/employees/{employee_id}/deactivate",
        json={},
        headers=headers,
    )
    assert deactivate_resp.status_code == 200, deactivate_resp.text
    assert deactivate_resp.json()["data"]["status"] == "inactive"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_location_outbox_and_audit_on_create(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)

    resp = client.post(
        f"/v1/platform/businesses/{business_id}/locations",
        json={"name": "Audit Branch"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    location_id = uuid.UUID(resp.json()["data"]["id"])

    async def _check() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            outbox = await session.execute(
                select(PlatformOutboxEvent).where(
                    PlatformOutboxEvent.business_id == uuid.UUID(business_id),
                    PlatformOutboxEvent.event_type == "location.created",
                )
            )
            assert outbox.scalars().first() is not None
            audit = await session.execute(
                select(PlatformAuditEvent).where(
                    PlatformAuditEvent.business_id == uuid.UUID(business_id),
                    PlatformAuditEvent.resource_type == "location",
                    PlatformAuditEvent.resource_id == location_id,
                )
            )
            assert audit.scalars().first() is not None
        await engine.dispose()

    asyncio.run(_check())


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_business_isolation_for_locations(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_a = _create_business(client, headers)
    business_b = _create_business(client, headers)

    loc_a = client.post(
        f"/v1/platform/businesses/{business_a}/locations",
        json={"name": "A Branch"},
        headers=headers,
    ).json()["data"]["id"]

    cross_get = client.get(
        f"/v1/platform/businesses/{business_b}/locations/{loc_a}", headers=headers
    )
    assert cross_get.status_code == 404


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_authorization_owner_has_workforce_permissions(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, owner_id = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)

    async def _check() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            perms = await AuthorizationService.effective_permissions(
                session, uuid.UUID(business_id), owner_id
            )
            assert LOCATIONS_READ in perms
            assert WORKFORCE_READ in perms
        await engine.dispose()

    asyncio.run(_check())

    listed = client.get(f"/v1/platform/businesses/{business_id}/employees", headers=headers)
    assert listed.status_code == 200, listed.text
