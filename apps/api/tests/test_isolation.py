"""Mandatory tenant-isolation and privilege-path tests (Doc 12 §7.5)."""

import os
import uuid
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from platform_core.db import get_database_url
from platform_testing.db_helpers import ensure_auth_user

TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"


def _make_token(user_id: uuid.UUID, email: str) -> str:
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": email,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def client(monkeypatch: Any) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    with TestClient(app) as test_client:
        yield test_client


def _seed_user(user_id: uuid.UUID, email: str) -> None:
    import asyncio

    async def _run() -> None:
        url = get_database_url()
        if not url:
            return
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await ensure_auth_user(session, user_id, email)
            await session.commit()
        await engine.dispose()

    asyncio.run(_run())


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_ordinary_member_cannot_access_admin_endpoints(
    client: TestClient, monkeypatch: Any
) -> None:
    owner_id = uuid.uuid4()
    owner_email = f"{owner_id}@example.com"
    _seed_user(owner_id, owner_email)
    owner_headers = {"Authorization": f"Bearer {_make_token(owner_id, owner_email)}"}

    create_resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": "Admin Gate Test"},
        headers=owner_headers,
    )
    assert create_resp.status_code == 200
    business_id = create_resp.json()["data"]["business"]["id"]

    response = client.get(f"/v1/admin/businesses/{business_id}", headers=owner_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_super_admin_action_is_attributed(client: TestClient, monkeypatch: Any) -> None:
    admin_id = uuid.uuid4()
    admin_email = f"{admin_id}@example.com"
    owner_id = uuid.uuid4()
    owner_email = f"{owner_id}@example.com"
    _seed_user(admin_id, admin_email)
    _seed_user(owner_id, owner_email)

    import asyncio

    async def _grant_admin() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            from platform_core.services.identity import IdentityService

            await IdentityService.bootstrap_identity(session, admin_id, admin_email)
            await session.execute(
                text(
                    "INSERT INTO platform_admin_grants (identity_id, granted_by, reason) "
                    "VALUES (:id, :id, 'test grant')"
                ),
                {"id": str(admin_id)},
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(_grant_admin())

    owner_headers = {"Authorization": f"Bearer {_make_token(owner_id, owner_email)}"}
    create_resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": "Super Admin Audit"},
        headers=owner_headers,
    )
    business_id = create_resp.json()["data"]["business"]["id"]

    admin_headers = {"Authorization": f"Bearer {_make_token(admin_id, admin_email)}"}
    inspect = client.get(f"/v1/admin/businesses/{business_id}", headers=admin_headers)
    assert inspect.status_code == 200

    async def _check_audit() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            result = await session.execute(
                text(
                    "SELECT actor_identity_id, event_type FROM platform_audit_events "
                    "WHERE business_id = :bid AND event_type = 'admin.business.inspected' "
                    "ORDER BY occurred_at DESC LIMIT 1"
                ),
                {"bid": str(business_id)},
            )
            row = result.first()
            assert row is not None
            assert str(row.actor_identity_id) == str(admin_id)
        await engine.dispose()

    asyncio.run(_check_audit())


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_location_scoped_member_denied_for_unauthorized_location(client: TestClient) -> None:
    owner_id = uuid.uuid4()
    member_id = uuid.uuid4()
    owner_email = f"{owner_id}@example.com"
    member_email = f"{member_id}@example.com"
    _seed_user(owner_id, owner_email)
    _seed_user(member_id, member_email)

    owner_headers = {"Authorization": f"Bearer {_make_token(owner_id, owner_email)}"}
    create_resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": "Location Scope Shop"},
        headers=owner_headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    business_id = create_resp.json()["data"]["business"]["id"]
    primary_location_id = create_resp.json()["data"]["business"]["primary_location"]["id"]

    second_loc = client.post(
        f"/v1/b/{business_id}/locations",
        json={"name": "Branch B", "timezone": "UTC"},
        headers=owner_headers,
    )
    assert second_loc.status_code == 200
    branch_b_id = second_loc.json()["data"]["id"]

    invite = client.post(
        f"/v1/b/{business_id}/team/invitations",
        json={"identity_id": str(member_id), "role": "member"},
        headers=owner_headers,
    )
    membership_id = invite.json()["data"]["id"]

    activate = client.post(
        f"/v1/b/{business_id}/team/members/{membership_id}/activate",
        headers=owner_headers,
    )
    assert activate.status_code == 200

    grant = client.post(
        f"/v1/b/{business_id}/team/members/{membership_id}/permissions",
        json={"permissions": ["locations.read"]},
        headers=owner_headers,
    )
    assert grant.status_code == 200

    import asyncio

    async def _scope_member() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await session.execute(
                text(
                    "UPDATE business_memberships SET location_scope = ARRAY[:loc]::uuid[] "
                    "WHERE id = :mid"
                ),
                {"loc": str(primary_location_id), "mid": str(membership_id)},
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(_scope_member())

    member_headers = {
        "Authorization": f"Bearer {_make_token(member_id, member_email)}",
        "X-Location-Id": branch_b_id,
    }
    denied = client.get(f"/v1/b/{business_id}/locations", headers=member_headers)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "LOCATION_ACCESS_DENIED"
