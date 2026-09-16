"""Stage 7 Section 6 — Super Admin support surface (Doc 09 ADM-*, Doc 11 §17.7).

The governing requirement is Doc 11 §17.7 exit: "Admin can inspect and support
without silent impersonation". Two things follow, and both are asserted here:

  * a non-admin must never reach any /v1/admin route;
  * an Admin inspecting an identified Business must leave an attributed audit
    trail — `admin.*` event type, `actor_context="admin"`, actor is the Admin's
    own identity, never the Business owner's.

`test_admin_inspection_is_never_attributed_to_the_owner` is the direct
non-impersonation assertion.
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


def _actor() -> tuple[dict[str, str], uuid.UUID, str]:
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed(user_id, email)
    return {"Authorization": f"Bearer {_token(user_id, email)}"}, user_id, email


def _grant_super_admin(identity_id: uuid.UUID) -> None:
    async def _run() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await session.execute(
                text("""
                    INSERT INTO platform_admin_grants (identity_id, granted_by, reason)
                    VALUES (:iid, :iid, 'stage 7 admin support test')
                """),
                {"iid": str(identity_id)},
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(_run())


def _audit_rows(business_id: str, event_prefix: str) -> list[dict[str, Any]]:
    async def _run() -> list[dict[str, Any]]:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            result = await session.execute(
                text("""
                    SELECT event_type, actor_identity_id, actor_context, action
                    FROM platform_audit_events
                    WHERE business_id = :bid AND event_type LIKE :prefix
                """),
                {"bid": business_id, "prefix": f"{event_prefix}%"},
            )
            rows = [
                {
                    "event_type": r.event_type,
                    "actor_identity_id": str(r.actor_identity_id),
                    "actor_context": r.actor_context,
                    "action": r.action,
                }
                for r in result
            ]
        await engine.dispose()
        return rows

    return asyncio.run(_run())


@pytest.fixture
def owner(monkeypatch: Any) -> tuple[dict[str, str], uuid.UUID]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    headers, user_id, _ = _actor()
    return headers, user_id


@pytest.fixture
def admin(monkeypatch: Any) -> tuple[dict[str, str], uuid.UUID]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    headers, user_id, _ = _actor()
    _grant_super_admin(user_id)
    return headers, user_id


def _create_business(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"Admin Target {uuid.uuid4().hex[:8]}", "business_type": "retail"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    business_id = cast(str, resp.json()["data"]["business"]["id"])
    enabled = client.post(f"/v1/b/{business_id}/modules/orders/enable", headers=headers)
    assert enabled.status_code == 200, enabled.text
    return business_id


ADMIN_ROUTES = [
    ("GET", "/v1/admin/businesses"),
    ("GET", "/v1/admin/audit"),
    ("GET", "/v1/admin/system/health"),
    ("GET", "/v1/admin/marketplace/indexing"),
]


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
def test_non_admin_cannot_reach_admin_routes(
    owner: tuple[dict[str, str], uuid.UUID], method: str, path: str
) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        resp = client.request(method, path, headers=headers)
        assert resp.status_code == 403, resp.text
        assert resp.json()["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
def test_unauthenticated_cannot_reach_admin_routes(method: str, path: str) -> None:
    with TestClient(app) as client:
        assert client.request(method, path).status_code == 401


# ---------------------------------------------------------------------------
# ADM-002 / ADM-003 / ADM-008
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_admin_can_search_businesses(
    owner: tuple[dict[str, str], uuid.UUID], admin: tuple[dict[str, str], uuid.UUID]
) -> None:
    owner_headers, _ = owner
    admin_headers, _ = admin
    with TestClient(app) as client:
        bid = _create_business(client, owner_headers)
        detail = client.get(f"/v1/b/{bid}", headers=owner_headers).json()["data"]

        found = client.get(
            "/v1/admin/businesses", params={"query": detail["display_name"]}, headers=admin_headers
        )
        assert found.status_code == 200, found.text
        rows = found.json()["data"]
        assert any(row["id"] == bid for row in rows), rows
        row = next(r for r in rows if r["id"] == bid)
        # All three axes visible to Admin (Doc 03 §1.6).
        assert {"state", "status", "visibility"} <= set(row)


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_admin_support_view_returns_modules_and_locations(
    owner: tuple[dict[str, str], uuid.UUID], admin: tuple[dict[str, str], uuid.UUID]
) -> None:
    owner_headers, owner_id = owner
    admin_headers, _ = admin
    with TestClient(app) as client:
        bid = _create_business(client, owner_headers)

        view = client.get(f"/v1/admin/businesses/{bid}/support", headers=admin_headers)
        assert view.status_code == 200, view.text
        data = view.json()["data"]
        assert data["business"]["id"] == bid
        assert data["business"]["primary_owner_identity_id"] == str(owner_id)
        assert any(m["module_id"] == "orders" for m in data["modules"])
        assert data["locations"], "a new Business has a primary location"
        assert data["active_member_count"] >= 1


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_admin_support_view_404s_for_unknown_business(
    admin: tuple[dict[str, str], uuid.UUID],
) -> None:
    admin_headers, _ = admin
    with TestClient(app) as client:
        resp = client.get(
            f"/v1/admin/businesses/{uuid.uuid4()}/support", headers=admin_headers
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Non-impersonation — the Doc 11 §17.7 exit criterion
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_admin_inspection_is_never_attributed_to_the_owner(
    owner: tuple[dict[str, str], uuid.UUID], admin: tuple[dict[str, str], uuid.UUID]
) -> None:
    """Doc 11 §17.7: "Admin can inspect and support without silent impersonation"."""
    owner_headers, owner_id = owner
    admin_headers, admin_id = admin
    with TestClient(app) as client:
        bid = _create_business(client, owner_headers)

        viewed = client.get(f"/v1/admin/businesses/{bid}/support", headers=admin_headers)
        assert viewed.status_code == 200, viewed.text

        rows = _audit_rows(bid, "admin.")
        assert rows, "an Admin support view must leave an audit trail"
        entry = next(r for r in rows if r["event_type"] == "admin.business.support_viewed")
        # Attributed to the Admin, in the admin context, never the owner.
        assert entry["actor_identity_id"] == str(admin_id)
        assert entry["actor_identity_id"] != str(owner_id)
        assert entry["actor_context"] == "admin"


# ---------------------------------------------------------------------------
# ADM-018 audit search / ADM-019 system health
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_admin_audit_search_filters(
    owner: tuple[dict[str, str], uuid.UUID], admin: tuple[dict[str, str], uuid.UUID]
) -> None:
    owner_headers, _ = owner
    admin_headers, admin_id = admin
    with TestClient(app) as client:
        bid = _create_business(client, owner_headers)
        client.get(f"/v1/admin/businesses/{bid}/support", headers=admin_headers)

        scoped = client.get(
            "/v1/admin/audit", params={"business_id": bid}, headers=admin_headers
        )
        assert scoped.status_code == 200, scoped.text
        events = scoped.json()["data"]
        assert events
        assert all(e["business_id"] == bid for e in events)

        by_context = client.get(
            "/v1/admin/audit",
            params={"business_id": bid, "actor_context": "admin"},
            headers=admin_headers,
        )
        assert by_context.status_code == 200
        admin_events = by_context.json()["data"]
        assert admin_events
        assert all(e["actor_context"] == "admin" for e in admin_events)
        assert all(e["actor_identity_id"] == str(admin_id) for e in admin_events)

        by_prefix = client.get(
            "/v1/admin/audit",
            params={"business_id": bid, "event_type": "admin."},
            headers=admin_headers,
        )
        assert by_prefix.status_code == 200
        assert all(e["event_type"].startswith("admin.") for e in by_prefix.json()["data"])


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_admin_system_health_exposes_failure_surfaces(
    admin: tuple[dict[str, str], uuid.UUID],
) -> None:
    """Doc 11 §17.7: dead-letter and processing failures must be visible."""
    admin_headers, _ = admin
    with TestClient(app) as client:
        resp = client.get("/v1/admin/system/health", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert {
            "dead_letters",
            "outbox_by_status",
            "failed_jobs",
            "failing_event_types",
        } <= set(data)
        assert isinstance(data["dead_letters"], list)
        assert isinstance(data["outbox_by_status"], list)
