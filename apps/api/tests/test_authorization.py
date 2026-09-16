import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from platform_api.main import app

from platform_testing.db_helpers import ensure_auth_user
from platform_core.db import get_database_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"


def _make_token(sub: str | None = None, email: str = "owner@example.com") -> str:
    auth_user_id = sub or str(uuid.uuid4())
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    return jwt.encode(
        {"sub": auth_user_id, "email": email, "exp": exp},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def auth_headers(monkeypatch: Any) -> dict[str, str]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = str(uuid.uuid4())
    email = f"{user_id}@example.com"
    token = _make_token(sub=user_id, email=email)
    if get_database_url():
        import asyncio

        async def _seed() -> None:
            url = get_database_url()
            if url and url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            engine = create_async_engine(url, echo=False, poolclass=NullPool)
            factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with factory() as session:
                await ensure_auth_user(session, uuid.UUID(user_id), email)
                await session.commit()
            await engine.dispose()

        asyncio.run(_seed())
    return {"Authorization": f"Bearer {token}"}


def test_unauthenticated_business_endpoint_returns_401() -> None:
    with TestClient(app) as client:
        response = client.get(f"/v1/b/{uuid.uuid4()}")
        assert response.status_code == 401
        body = response.json()
        assert body["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_business_endpoint_without_membership_returns_403_or_404(
    auth_headers: dict[str, str],
) -> None:
    with TestClient(app) as client:
        response = client.get(f"/v1/b/{uuid.uuid4()}", headers=auth_headers)
        # Non-existent business: 404; existing business without membership: 403
        assert response.status_code in (403, 404)
        if response.status_code == 403:
            assert response.json()["error"]["code"] == "MEMBERSHIP_REQUIRED"


def test_create_business_requires_auth() -> None:
    with TestClient(app) as client:
        response = client.post("/v1/platform/businesses", json={"display_name": "Test Co"})
        assert response.status_code == 401


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required for integration")
def test_tenant_isolation_wrong_business_returns_404_or_403(
    auth_headers: dict[str, str], monkeypatch: Any
) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    with TestClient(app) as client:
        # Create business A
        create_a = client.post(
            "/v1/platform/businesses",
            json={"display_name": "Business A"},
            headers=auth_headers,
        )
        assert create_a.status_code == 200
        business_a_id = create_a.json()["data"]["business"]["id"]

        # Different user token
        other_user_id = uuid.uuid4()
        other_email = f"{other_user_id}@example.com"
        import asyncio

        async def _seed_other() -> None:
            url = get_database_url()
            if url and url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            engine = create_async_engine(url, echo=False, poolclass=NullPool)
            factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with factory() as session:
                await ensure_auth_user(session, other_user_id, other_email)
                await session.commit()
            await engine.dispose()

        asyncio.run(_seed_other())
        other_token = _make_token(sub=str(other_user_id), email=other_email)
        other_headers = {"Authorization": f"Bearer {other_token}"}

        response = client.get(f"/v1/b/{business_a_id}", headers=other_headers)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "MEMBERSHIP_REQUIRED"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required for integration")
def test_primary_owner_can_access_own_business(
    auth_headers: dict[str, str], monkeypatch: Any
) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    with TestClient(app) as client:
        create_resp = client.post(
            "/v1/platform/businesses",
            json={"display_name": "My Shop"},
            headers=auth_headers,
        )
        assert create_resp.status_code == 200
        business_id = create_resp.json()["data"]["business"]["id"]

        get_resp = client.get(f"/v1/b/{business_id}", headers=auth_headers)
        assert get_resp.status_code == 200
        body = get_resp.json()["data"]
        assert body["display_name"] == "My Shop"
        # All three independent axes are exposed (Doc 03 §1.6). `status` in
        # particular is what the Workspace Home reads to render the commercial
        # recovery state — without it the UI cannot distinguish a suspended
        # Business from a healthy one.
        assert body["state"] in {"draft", "onboarding", "active", "dormant", "closed"}
        assert body["status"] == "in_good_standing"
        assert body["visibility"] in {"private", "unlisted", "discoverable"}


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required for integration")
def test_member_without_permission_denied(auth_headers: dict[str, str], monkeypatch: Any) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    member_id = uuid.uuid4()
    member_email = f"{member_id}@example.com"
    if get_database_url():
        import asyncio
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        async def _seed_member() -> None:
            url = get_database_url()
            if url and url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            engine = create_async_engine(url, echo=False, poolclass=NullPool)
            factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with factory() as session:
                await ensure_auth_user(session, member_id, member_email)
                await session.commit()
            await engine.dispose()

        asyncio.run(_seed_member())
    member_token = jwt.encode(
        {
            "sub": str(member_id),
            "email": member_email,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    member_headers = {"Authorization": f"Bearer {member_token}"}

    with TestClient(app) as client:
        create_resp = client.post(
            "/v1/platform/businesses",
            json={"display_name": "Team Shop"},
            headers=auth_headers,
        )
        business_id = create_resp.json()["data"]["business"]["id"]

        # Invite member (pending - not active yet)
        invite = client.post(
            f"/v1/b/{business_id}/team/invitations",
            json={"identity_id": str(member_id), "role": "member"},
            headers=auth_headers,
        )
        assert invite.status_code == 200

        # Member not active - should be denied
        loc_resp = client.get(f"/v1/b/{business_id}/locations", headers=member_headers)
        assert loc_resp.status_code == 403
