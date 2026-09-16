"""Stage 2H — Authorization & permission resolution engine tests."""

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
from platform_core.authorization.resolver import AuthorizationService, EffectivePermissionResolver
from platform_core.db import get_database_url
from platform_core.exceptions import ValidationError
from platform_core.models import PlatformOutboxEvent
from platform_core.permissions import ORDERS_READ, PERMISSIONS_READ, ROLE_PRIMARY_OWNER
from platform_core.services.permission_engine import PermissionEngineService
from platform_core.services.team import TeamService
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
        json={"display_name": f"Auth Co {uuid.uuid4().hex[:8]}", "business_type": "retail"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return cast(str, resp.json()["data"]["business"]["id"])


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_list_roles_and_permissions(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        roles = client.get("/v1/platform/roles", headers=headers)
        assert roles.status_code == 200
        role_ids = {item["role_id"] for item in roles.json()["data"]}
        assert ROLE_PRIMARY_OWNER in role_ids

        permissions = client.get("/v1/platform/permissions", headers=headers)
        assert permissions.status_code == 200
        assert any(p["permission_id"] == ORDERS_READ for p in permissions.json()["data"])


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_effective_permissions_and_snapshot(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        biz = _create_business(client, headers)
        effective = client.get(
            f"/v1/platform/businesses/{biz}/permissions/effective", headers=headers
        )
        assert effective.status_code == 200, effective.text
        perms = effective.json()["data"]["effective_permissions"]
        assert PERMISSIONS_READ in perms

        snapshot = client.get(
            f"/v1/platform/businesses/{biz}/permissions/snapshot", headers=headers
        )
        assert snapshot.status_code == 200
        data = snapshot.json()["data"]
        assert "capability_summary" in data
        assert data["capability_summary"]["use_inventory"] is True


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_authorization_decision(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, owner_id = owner
    with TestClient(app) as client:
        biz = _create_business(client, headers)

    async def _assert() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            allowed = await AuthorizationService.authorize(
                session,
                business_id=uuid.UUID(biz),
                identity_id=owner_id,
                permission=PERMISSIONS_READ,
            )
            assert allowed.allowed is True
            with pytest.raises(ValidationError):
                await AuthorizationService.authorize(
                    session,
                    business_id=uuid.UUID(biz),
                    identity_id=owner_id,
                    permission="not.real.permission",
                )
        await engine.dispose()

    asyncio.run(_assert())


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_permission_matrix(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        biz = _create_business(client, headers)
        matrix = client.get(
            f"/v1/platform/businesses/{biz}/permissions/matrix", headers=headers
        )
        assert matrix.status_code == 200
        assert ROLE_PRIMARY_OWNER in matrix.json()["data"]["matrix"]


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_permission_failures(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    other_id = uuid.uuid4()
    _seed(other_id, f"{other_id}@example.com")
    other_headers = _headers(other_id, f"{other_id}@example.com")

    with TestClient(app) as client:
        biz = _create_business(client, headers)
        members = client.get(f"/v1/platform/businesses/{biz}/members", headers=headers)
        owner_membership_id = members.json()["data"][0]["id"]

        unauth = client.get(f"/v1/platform/businesses/{biz}/permissions/effective")
        assert unauth.status_code == 401

        denied = client.get(
            f"/v1/platform/businesses/{biz}/permissions/effective", headers=other_headers
        )
        assert denied.status_code == 403

        bad_override = client.patch(
            f"/v1/platform/businesses/{biz}/members/{owner_membership_id}/permissions/overrides",
            json={"grants": ["not.a.permission"]},
            headers=headers,
        )
        assert bad_override.status_code == 422

        owner_override = client.patch(
            f"/v1/platform/businesses/{biz}/members/{owner_membership_id}/permissions/overrides",
            json={"denials": [ORDERS_READ]},
            headers=headers,
        )
        assert owner_override.status_code == 422


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_resolver_determinism_and_team_delegate(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, owner_id = owner
    with TestClient(app) as client:
        biz = _create_business(client, headers)

    async def _assert() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            first = await PermissionEngineService.get_effective_permissions(
                session, business_id=uuid.UUID(biz), identity_id=owner_id
            )
            second = await PermissionEngineService.get_effective_permissions(
                session, business_id=uuid.UUID(biz), identity_id=owner_id
            )
            assert first == second
            membership = await TeamService.get_active_membership(
                session, owner_id, uuid.UUID(biz)
            )
            assert membership is not None
            team_perms = await TeamService.resolve_permissions(session, membership)
            resolved = await EffectivePermissionResolver.resolve(
                session, uuid.UUID(biz), owner_id
            )
            assert team_perms == resolved.effective_permissions
        await engine.dispose()

    asyncio.run(_assert())


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_member_grant_override(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, owner_id = owner
    member_id = uuid.uuid4()
    _seed(member_id, f"{member_id}@example.com")

    with TestClient(app) as client:
        biz = _create_business(client, headers)

    async def _invite() -> str:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            from platform_core.services.business import BusinessService
            from platform_core.services.invitation import InvitationService

            business = await BusinessService.get_by_id(session, uuid.UUID(biz))
            owner_membership = await TeamService.get_active_membership(
                session, owner_id, uuid.UUID(biz)
            )
            invitation = await InvitationService.create_invitation(
                session,
                business=business,
                actor=owner_membership,
                invited_email=f"{member_id}@example.com",
                invited_role="member",
                correlation_id=str(uuid.uuid4()),
            )
            await InvitationService.accept_invitation(
                session,
                business_id=uuid.UUID(biz),
                invitation_id=invitation.id,
                accepter_identity_id=member_id,
                accepter_email=f"{member_id}@example.com",
                correlation_id=str(uuid.uuid4()),
            )
            membership = await TeamService.get_active_membership(
                session, member_id, uuid.UUID(biz)
            )
            assert membership is not None
            mid = str(membership.id)
            await session.commit()
        await engine.dispose()
        return mid

    membership_id = asyncio.run(_invite())

    with TestClient(app) as client:
        patched = client.patch(
            f"/v1/platform/businesses/{biz}/members/{membership_id}/permissions/overrides",
            json={"grants": [ORDERS_READ]},
            headers=headers,
        )
        assert patched.status_code == 200, patched.text
        assert ORDERS_READ in patched.json()["data"]["effective_permissions"]

    async def _audit() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            outbox = await session.execute(
                select(PlatformOutboxEvent.event_type).where(
                    PlatformOutboxEvent.business_id == uuid.UUID(biz),
                    PlatformOutboxEvent.event_type.in_(
                        ["permission.override.created", "authorization.snapshot.updated"]
                    ),
                )
            )
            events = {row[0] for row in outbox.all()}
            assert "permission.override.created" in events
            assert "authorization.snapshot.updated" in events
        await engine.dispose()

    asyncio.run(_audit())
