"""Stage 2B — Business context switching tests."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_core.db import get_database_url
from platform_core.models import ConsumerProfile, PlatformAuditEvent, PlatformOutboxEvent
from platform_core.permissions import ROLE_PRIMARY_OWNER
from platform_core.services.business import BusinessService
from platform_core.services.identity import IdentityService
from platform_core.services.outbox import OutboxService
from platform_testing.db_helpers import ensure_auth_user
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"


def _make_token(sub: uuid.UUID | str, email: str) -> str:
    return jwt.encode(
        {
            "sub": str(sub),
            "email": email,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


def _seed_user(user_id: uuid.UUID, email: str) -> None:
    import asyncio

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
def auth_pair(monkeypatch: Any) -> tuple[dict[str, str], uuid.UUID]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed_user(user_id, email)
    return {"Authorization": f"Bearer {_make_token(user_id, email)}"}, user_id


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_switch_business_success(auth_pair: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = auth_pair
    with TestClient(app) as client:
        a = client.post(
            "/v1/platform/businesses",
            json={"display_name": "Biz A Switch", "business_type": "retail"},
            headers=headers,
        )
        assert a.status_code == 200
        biz_a = a.json()["data"]["business"]["id"]

        b = client.post(
            "/v1/platform/businesses",
            json={"display_name": "Biz B Switch", "business_type": "salon"},
            headers=headers,
        )
        assert b.status_code == 200
        biz_b = b.json()["data"]["business"]["id"]
        primary = b.json()["data"]["context"].get("is_primary_business")
        # Second create must not steal primary from first Business.
        assert primary is False or a.json()["data"]["context"]["is_primary_business"] is True

        switched = client.post(
            f"/v1/platform/businesses/{biz_a}/switch",
            json={},
            headers=headers,
        )
        assert switched.status_code == 200, switched.text
        data = switched.json()["data"]
        assert data["business"]["id"] == biz_a
        assert data["membership"]["role"] == ROLE_PRIMARY_OWNER
        assert data["membership"]["status"] == "active"
        assert data["context"]["is_current_business"] is True
        assert data["context"]["last_business_id"] == biz_a
        assert "business.read" in data["context"]["permissions"]
        assert "entitled_modules" in data["context"]
        assert "module_states" in data["context"]

        # Without set_as_default, default remains the prior default (biz_b from second create).
        assert data["context"]["default_business_id"] == biz_b
        assert data["context"]["is_default_business"] is False
        # Primary remains first business.
        assert data["context"]["primary_business_id"] == biz_a
        assert data["context"]["is_primary_business"] is True


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_switch_set_as_default(auth_pair: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = auth_pair
    with TestClient(app) as client:
        a = client.post(
            "/v1/platform/businesses",
            json={"display_name": "Default A", "business_type": "retail"},
            headers=headers,
        ).json()["data"]["business"]["id"]
        b = client.post(
            "/v1/platform/businesses",
            json={"display_name": "Default B", "business_type": "gym"},
            headers=headers,
        ).json()["data"]["business"]["id"]

        switched = client.post(
            f"/v1/platform/businesses/{a}/switch",
            json={"set_as_default": True},
            headers=headers,
        )
        assert switched.status_code == 200
        ctx = switched.json()["data"]["context"]
        assert ctx["default_business_id"] == a
        assert ctx["is_default_business"] is True
        assert ctx["last_business_id"] == a
        assert ctx["primary_business_id"] == a  # primary immutable from first create
        assert b  # silence unused


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_restore_default_then_last(auth_pair: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, user_id = auth_pair
    with TestClient(app) as client:
        a = client.post(
            "/v1/platform/businesses",
            json={"display_name": "Restore A", "business_type": "retail"},
            headers=headers,
        ).json()["data"]["business"]["id"]
        b = client.post(
            "/v1/platform/businesses",
            json={"display_name": "Restore B", "business_type": "cafe"},
            headers=headers,
        ).json()["data"]["business"]["id"]

        # Make A last but keep B as default (second create set default=B).
        client.post(f"/v1/platform/businesses/{a}/switch", json={}, headers=headers)

        restored = client.get(
            "/v1/me/context",
            headers={**headers, "X-Operating-Context": "business"},
        )
        assert restored.status_code == 200
        assert restored.json()["data"]["business_id"] == b  # default wins
        assert restored.json()["data"]["default_business_id"] == b
        assert restored.json()["data"]["last_business_id"] == a

        # Clear default; restore should use last.
        import asyncio

        async def _clear_default() -> None:
            url = get_database_url()
            assert url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            engine = create_async_engine(url, echo=False, poolclass=NullPool)
            factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with factory() as session:
                identity = await IdentityService.get_by_id(session, user_id)
                assert identity
                prefs = await IdentityService.get_consumer_preferences(session, identity.id)
                prefs.pop("default_business_id", None)

                result = await session.execute(
                    select(ConsumerProfile).where(ConsumerProfile.identity_id == identity.id)
                )
                profile = result.scalars().first()
                assert profile
                profile.preferences = prefs
                await session.commit()
            await engine.dispose()

        asyncio.run(_clear_default())

        restored_last = client.get(
            "/v1/me/context",
            headers={**headers, "X-Operating-Context": "business"},
        )
        assert restored_last.status_code == 200
        assert restored_last.json()["data"]["business_id"] == a
        assert restored_last.json()["data"]["default_business_id"] is None


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_restore_neither_returns_no_business_context(
    auth_pair: tuple[dict[str, str], uuid.UUID],
) -> None:
    headers, user_id = auth_pair
    with TestClient(app) as client:
        # Authenticated identity with no businesses / preferences
        ctx = client.get(
            "/v1/me/context",
            headers={**headers, "X-Operating-Context": "business"},
        )
        assert ctx.status_code == 200
        assert ctx.json()["data"]["active_context"] == "personal"
        assert ctx.json()["data"]["business_id"] is None


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_switch_manager_and_member_roles(
    auth_pair: tuple[dict[str, str], uuid.UUID], monkeypatch: Any
) -> None:
    owner_headers, _ = auth_pair
    manager_id = uuid.uuid4()
    member_id = uuid.uuid4()
    manager_email = f"{manager_id}@example.com"
    member_email = f"{member_id}@example.com"
    _seed_user(manager_id, manager_email)
    _seed_user(member_id, member_email)

    with TestClient(app) as client:
        biz = client.post(
            "/v1/platform/businesses",
            json={"display_name": "Role Switch Co", "business_type": "retail"},
            headers=owner_headers,
        ).json()["data"]["business"]["id"]

        for identity_id, role, email in (
            (manager_id, "manager", manager_email),
            (member_id, "member", member_email),
        ):
            invite = client.post(
                f"/v1/b/{biz}/team/invitations",
                json={"identity_id": str(identity_id), "role": role},
                headers=owner_headers,
            )
            assert invite.status_code == 200
            mid = invite.json()["data"]["id"]
            activate = client.post(
                f"/v1/b/{biz}/team/members/{mid}/activate",
                headers=owner_headers,
            )
            assert activate.status_code == 200
            if role == "member":
                grant = client.post(
                    f"/v1/b/{biz}/team/members/{mid}/permissions",
                    json={"permissions": ["business.read", "locations.read"]},
                    headers=owner_headers,
                )
                assert grant.status_code == 200

            user_headers = {"Authorization": f"Bearer {_make_token(identity_id, email)}"}
            switched = client.post(
                f"/v1/platform/businesses/{biz}/switch",
                json={},
                headers=user_headers,
            )
            assert switched.status_code == 200, switched.text
            assert switched.json()["data"]["membership"]["role"] == role
            assert switched.json()["data"]["membership"]["status"] == "active"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_switch_failures(
    auth_pair: tuple[dict[str, str], uuid.UUID], monkeypatch: Any
) -> None:
    headers, _ = auth_pair
    other_id = uuid.uuid4()
    other_email = f"{other_id}@example.com"
    _seed_user(other_id, other_email)
    other_headers = {"Authorization": f"Bearer {_make_token(other_id, other_email)}"}

    with TestClient(app) as client:
        unauth = client.post(
            f"/v1/platform/businesses/{uuid.uuid4()}/switch",
            json={},
        )
        assert unauth.status_code == 401

        biz = client.post(
            "/v1/platform/businesses",
            json={
                "display_name": f"Fail Switch Co {uuid.uuid4().hex[:8]}",
                "business_type": "retail",
            },
            headers=headers,
        ).json()["data"]["business"]["id"]

        no_membership = client.post(
            f"/v1/platform/businesses/{biz}/switch",
            json={},
            headers=other_headers,
        )
        assert no_membership.status_code == 403
        assert no_membership.json()["error"]["code"] == "MEMBERSHIP_REQUIRED"

        unknown = client.post(
            f"/v1/platform/businesses/{uuid.uuid4()}/switch",
            json={},
            headers=headers,
        )
        assert unknown.status_code == 404

        malformed = client.post(
            "/v1/platform/businesses/not-a-uuid/switch",
            json={},
            headers=headers,
        )
        assert malformed.status_code == 422

        # Pending membership cannot switch
        pending_id = uuid.uuid4()
        pending_email = f"{pending_id}@example.com"
        _seed_user(pending_id, pending_email)
        invite = client.post(
            f"/v1/b/{biz}/team/invitations",
            json={"identity_id": str(pending_id), "role": "member"},
            headers=headers,
        )
        assert invite.status_code == 200
        pending_headers = {
            "Authorization": f"Bearer {_make_token(pending_id, pending_email)}"
        }
        pending_switch = client.post(
            f"/v1/platform/businesses/{biz}/switch",
            json={},
            headers=pending_headers,
        )
        assert pending_switch.status_code == 403

        # Suspended membership
        import asyncio

        # Invite other, activate, suspend
        invite_other = client.post(
            f"/v1/b/{biz}/team/invitations",
            json={"identity_id": str(other_id), "role": "member"},
            headers=headers,
        )
        mid = invite_other.json()["data"]["id"]
        client.post(f"/v1/b/{biz}/team/members/{mid}/activate", headers=headers)

        async def _suspend_other() -> None:
            url = get_database_url()
            assert url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            engine = create_async_engine(url, echo=False, poolclass=NullPool)
            factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with factory() as session:
                await session.execute(
                    text(
                        "UPDATE business_memberships SET status = 'suspended' "
                        "WHERE identity_id = :iid AND business_id = :bid"
                    ),
                    {"iid": str(other_id), "bid": biz},
                )
                await session.commit()
            await engine.dispose()

        asyncio.run(_suspend_other())
        suspended = client.post(
            f"/v1/platform/businesses/{biz}/switch",
            json={},
            headers=other_headers,
        )
        assert suspended.status_code == 403

        # Closed business → resource gate
        async def _close() -> None:
            url = get_database_url()
            assert url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            engine = create_async_engine(url, echo=False, poolclass=NullPool)
            factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with factory() as session:
                await session.execute(
                    text("UPDATE businesses SET state = 'closed' WHERE id = :id"),
                    {"id": biz},
                )
                await session.commit()
            await engine.dispose()

        asyncio.run(_close())
        closed = client.post(
            f"/v1/platform/businesses/{biz}/switch",
            json={},
            headers=headers,
        )
        assert closed.status_code == 409
        assert closed.json()["error"]["code"] == "CONFLICT"
        assert closed.json()["error"]["details"]["gate"] == "resource_state"

        # Soft-deleted business
        async def _soft_delete() -> None:
            url = get_database_url()
            assert url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            engine = create_async_engine(url, echo=False, poolclass=NullPool)
            factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with factory() as session:
                await session.execute(
                    text(
                        "UPDATE businesses SET state = 'active', deleted_at = now() WHERE id = :id"
                    ),
                    {"id": biz},
                )
                await session.commit()
            await engine.dispose()

        asyncio.run(_soft_delete())
        deleted = client.post(
            f"/v1/platform/businesses/{biz}/switch",
            json={},
            headers=headers,
        )
        assert deleted.status_code == 404

        # Inaccessible X-Business-Id header
        denied_header = client.get(
            "/v1/me/context",
            headers={
                **other_headers,
                "X-Operating-Context": "business",
                "X-Business-Id": biz,
            },
        )
        # soft-deleted → 404 for explicit header
        assert denied_header.status_code in (403, 404)


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_switch_audit_and_outbox(auth_pair: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = auth_pair
    with TestClient(app) as client:
        biz = client.post(
            "/v1/platform/businesses",
            json={"display_name": "Audit Switch Co", "business_type": "retail"},
            headers=headers,
        ).json()["data"]["business"]["id"]
        biz2 = client.post(
            "/v1/platform/businesses",
            json={"display_name": "Audit Switch Co 2", "business_type": "salon"},
            headers=headers,
        ).json()["data"]["business"]["id"]
        resp = client.post(
            f"/v1/platform/businesses/{biz}/switch",
            json={"set_as_default": True},
            headers=headers,
        )
        assert resp.status_code == 200

    import asyncio

    async def _assert() -> None:
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
                    PlatformOutboxEvent.event_type == "business.context_switched",
                )
            )
            assert outbox.scalars().first() == "business.context_switched"
            audits = await session.execute(
                select(PlatformAuditEvent.event_type).where(
                    PlatformAuditEvent.business_id == uuid.UUID(biz)
                )
            )
            types = set(audits.scalars().all())
            assert "business.context_switched" in types
            assert "default_business_changed" in types
            assert biz2
        await engine.dispose()

    asyncio.run(_assert())


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
async def test_switch_transaction_rollback(monkeypatch: Any) -> None:
    url = get_database_url()
    assert url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    identity_id = uuid.uuid4()
    email = f"switch-rb-{identity_id.hex[:8]}@test.local"
    async with factory() as session:
        await ensure_auth_user(session, identity_id, email)
        await IdentityService.bootstrap_identity(session, identity_id, email)
        business, _, _, _ = await BusinessService.create_business(
            session,
            identity_id=identity_id,
            display_name=f"Rollback Switch {identity_id.hex[:8]}",
            business_type="retail",
            correlation_id=str(uuid.uuid4()),
        )
        await session.commit()
        business_id = business.id

    async def _fail(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("forced switch outbox failure")

    monkeypatch.setattr(OutboxService, "publish", staticmethod(_fail))

    async with factory() as session:
        with pytest.raises(RuntimeError, match="forced switch outbox failure"):
            await BusinessService.switch_business(
                session,
                identity_id=identity_id,
                business_id=business_id,
                correlation_id=str(uuid.uuid4()),
                set_as_default=True,
            )
        await session.rollback()

    async with factory() as session:
        prefs = await IdentityService.get_consumer_preferences(session, identity_id)
        # Create set default/last to business_id; failed switch with set_as_default
        # must not leave partial preference mutations from the failed txn.
        # After rollback, preferences remain as after create.
        assert prefs.get("last_business_id") == str(business_id)
        audits = await session.execute(
            select(func.count())
            .select_from(PlatformAuditEvent)
            .where(
                PlatformAuditEvent.business_id == business_id,
                PlatformAuditEvent.event_type == "business.context_switched",
            )
        )
        assert audits.scalar_one() == 0
    await engine.dispose()


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_malformed_business_header(auth_pair: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = auth_pair
    with TestClient(app) as client:
        resp = client.get(
            "/v1/me/context",
            headers={
                **headers,
                "X-Operating-Context": "business",
                "X-Business-Id": "not-a-uuid",
            },
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
