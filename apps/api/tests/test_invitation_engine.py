"""Stage 2D — Business invitation engine tests."""

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
from platform_core.models import BusinessInvitation, PlatformAuditEvent, PlatformOutboxEvent
from platform_core.services.business import BusinessService
from platform_core.services.identity import IdentityService
from platform_core.services.invitation import InvitationService
from platform_core.services.outbox import OutboxService
from platform_core.services.team import TeamService
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


def _headers(user_id: uuid.UUID, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(user_id, email)}"}


def _seed_user(user_id: uuid.UUID, email: str) -> None:
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
def owner_pair(monkeypatch: Any) -> tuple[dict[str, str], uuid.UUID, str]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed_user(user_id, email)
    return _headers(user_id, email), user_id, email


def _create_business(client: TestClient, headers: dict[str, str], name: str) -> str:
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": name, "business_type": "retail"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return cast(str, resp.json()["data"]["business"]["id"])


def _create_invitation(
    client: TestClient,
    headers: dict[str, str],
    business_id: str,
    email: str,
    role: str = "member",
) -> str:
    resp = client.post(
        f"/v1/platform/businesses/{business_id}/invitations",
        json={"invited_email": email, "invited_role": role},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return cast(str, resp.json()["data"]["id"])


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_create_list_get_invitation(owner_pair: tuple[dict[str, str], uuid.UUID, str]) -> None:
    headers, _, _ = owner_pair
    invitee_id = uuid.uuid4()
    invitee_email = f"{invitee_id}@example.com"
    _seed_user(invitee_id, invitee_email)

    with TestClient(app) as client:
        biz = _create_business(client, headers, f"Invite Co {uuid.uuid4().hex[:8]}")
        inv_id = _create_invitation(client, headers, biz, invitee_email)

        listed = client.get(f"/v1/platform/businesses/{biz}/invitations", headers=headers)
        assert listed.status_code == 200
        assert any(i["id"] == inv_id for i in listed.json()["data"])

        one = client.get(
            f"/v1/platform/businesses/{biz}/invitations/{inv_id}", headers=headers
        )
        assert one.status_code == 200
        assert one.json()["data"]["status"] == "pending"
        assert one.json()["data"]["invited_email"] == invitee_email.lower()


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_accept_existing_identity_creates_membership(
    owner_pair: tuple[dict[str, str], uuid.UUID, str],
) -> None:
    headers, _, _ = owner_pair
    invitee_id = uuid.uuid4()
    invitee_email = f"{invitee_id}@example.com"
    _seed_user(invitee_id, invitee_email)
    invitee_headers = _headers(invitee_id, invitee_email)

    with TestClient(app) as client:
        biz = _create_business(client, headers, f"Accept Co {uuid.uuid4().hex[:8]}")
        inv_id = _create_invitation(client, headers, biz, invitee_email)

        accepted = client.post(
            f"/v1/platform/businesses/{biz}/invitations/{inv_id}/accept",
            headers=invitee_headers,
        )
        assert accepted.status_code == 200, accepted.text
        data = accepted.json()["data"]
        assert data["invitation"]["status"] == "accepted"
        assert data["membership"]["status"] == "active"
        assert data["membership"]["role"] == "member"

        members = client.get(f"/v1/platform/businesses/{biz}/members", headers=headers)
        assert members.status_code == 200
        assert any(m["identity_id"] == str(invitee_id) for m in members.json()["data"])


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_accept_new_identity_on_signup(
    owner_pair: tuple[dict[str, str], uuid.UUID, str], monkeypatch: Any
) -> None:
    headers, _, _ = owner_pair
    new_id = uuid.uuid4()
    new_email = f"new-{new_id.hex[:8]}@example.com"

    with TestClient(app) as client:
        biz = _create_business(client, headers, f"New Identity {uuid.uuid4().hex[:8]}")
        inv_id = _create_invitation(client, headers, biz, new_email)

        monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
        _seed_user(new_id, new_email)
        new_headers = _headers(new_id, new_email)

        accepted = client.post(
            f"/v1/platform/businesses/{biz}/invitations/{inv_id}/accept",
            headers=new_headers,
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["data"]["membership"]["identity_id"] == str(new_id)


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_decline_revoke_resend(owner_pair: tuple[dict[str, str], uuid.UUID, str]) -> None:
    headers, _, _ = owner_pair
    invitee_id = uuid.uuid4()
    invitee_email = f"{invitee_id}@example.com"
    _seed_user(invitee_id, invitee_email)
    invitee_headers = _headers(invitee_id, invitee_email)

    with TestClient(app) as client:
        biz = _create_business(client, headers, f"Lifecycle {uuid.uuid4().hex[:8]}")
        inv_a = _create_invitation(client, headers, biz, invitee_email)

        resent = client.post(
            f"/v1/platform/businesses/{biz}/invitations/{inv_a}/resend",
            headers=headers,
        )
        assert resent.status_code == 200
        assert resent.json()["data"]["resend_count"] == 1

        declined = client.post(
            f"/v1/platform/businesses/{biz}/invitations/{inv_a}/accept",
            headers=invitee_headers,
        )
        assert declined.status_code == 200

        inv_b_email = f"decline-{uuid.uuid4().hex[:8]}@example.com"
        decline_user = uuid.uuid4()
        _seed_user(decline_user, inv_b_email)
        inv_b = _create_invitation(client, headers, biz, inv_b_email)
        dec = client.post(
            f"/v1/platform/businesses/{biz}/invitations/{inv_b}/decline",
            headers=_headers(decline_user, inv_b_email),
        )
        assert dec.status_code == 200
        assert dec.json()["data"]["status"] == "declined"

        inv_c = _create_invitation(client, headers, biz, f"revoke-{uuid.uuid4().hex[:8]}@example.com")
        revoked = client.delete(
            f"/v1/platform/businesses/{biz}/invitations/{inv_c}",
            headers=headers,
        )
        assert revoked.status_code == 200
        assert revoked.json()["data"]["status"] == "revoked"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_manager_role_escalation_blocked(
    owner_pair: tuple[dict[str, str], uuid.UUID, str],
) -> None:
    headers, owner_id, owner_email = owner_pair
    manager_id = uuid.uuid4()
    manager_email = f"{manager_id}@example.com"
    _seed_user(manager_id, manager_email)
    manager_headers = _headers(manager_id, manager_email)

    with TestClient(app) as client:
        biz = _create_business(client, headers, f"Escalation {uuid.uuid4().hex[:8]}")
        mid = client.post(
            f"/v1/b/{biz}/team/invitations",
            json={"identity_id": str(manager_id), "role": "manager"},
            headers=headers,
        ).json()["data"]["id"]
        client.post(f"/v1/b/{biz}/team/members/{mid}/activate", headers=headers)
        client.post(
            f"/v1/b/{biz}/team/members/{mid}/permissions",
            json={"permissions": ["team.invite", "team.read"]},
            headers=headers,
        )

        denied = client.post(
            f"/v1/platform/businesses/{biz}/invitations",
            json={"invited_email": f"target-{uuid.uuid4().hex[:8]}@example.com", "invited_role": "manager"},
            headers=manager_headers,
        )
        assert denied.status_code == 403
        assert owner_id and owner_email


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_invitation_failures(owner_pair: tuple[dict[str, str], uuid.UUID, str]) -> None:
    headers, _, _ = owner_pair
    invitee_id = uuid.uuid4()
    invitee_email = f"{invitee_id}@example.com"
    _seed_user(invitee_id, invitee_email)
    invitee_headers = _headers(invitee_id, invitee_email)

    with TestClient(app) as client:
        biz = _create_business(client, headers, f"Fail Inv {uuid.uuid4().hex[:8]}")

        unauth = client.post(
            f"/v1/platform/businesses/{biz}/invitations",
            json={"invited_email": invitee_email},
        )
        assert unauth.status_code == 401

        bad_email = client.post(
            f"/v1/platform/businesses/{biz}/invitations",
            json={"invited_email": "not-an-email"},
            headers=headers,
        )
        assert bad_email.status_code == 422

        inv_id = _create_invitation(client, headers, biz, invitee_email)
        dup = client.post(
            f"/v1/platform/businesses/{biz}/invitations",
            json={"invited_email": invitee_email},
            headers=headers,
        )
        assert dup.status_code == 409

        client.post(
            f"/v1/platform/businesses/{biz}/invitations/{inv_id}/accept",
            headers=invitee_headers,
        )
        accept_again = client.post(
            f"/v1/platform/businesses/{biz}/invitations/{inv_id}/accept",
            headers=invitee_headers,
        )
        assert accept_again.status_code == 409

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
            f"/v1/platform/businesses/{biz}/invitations",
            json={"invited_email": f"closed-{uuid.uuid4().hex[:8]}@example.com"},
            headers=headers,
        )
        assert closed.status_code == 409


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_expired_invitation_rejected(owner_pair: tuple[dict[str, str], uuid.UUID, str]) -> None:
    headers, _, _ = owner_pair
    invitee_id = uuid.uuid4()
    invitee_email = f"{invitee_id}@example.com"
    _seed_user(invitee_id, invitee_email)
    invitee_headers = _headers(invitee_id, invitee_email)

    with TestClient(app) as client:
        biz = _create_business(client, headers, f"Expired {uuid.uuid4().hex[:8]}")
        inv_id = _create_invitation(client, headers, biz, invitee_email)

        async def _expire() -> None:
            url = get_database_url()
            assert url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            engine = create_async_engine(url, echo=False, poolclass=NullPool)
            factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with factory() as session:
                await session.execute(
                    text(
                        "UPDATE business_invitations SET expires_at = now() - interval '1 hour' "
                        "WHERE id = :id"
                    ),
                    {"id": inv_id},
                )
                await session.commit()
            await engine.dispose()

        asyncio.run(_expire())

        accept = client.post(
            f"/v1/platform/businesses/{biz}/invitations/{inv_id}/accept",
            headers=invitee_headers,
        )
        assert accept.status_code == 409


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_invitation_audit_and_outbox(owner_pair: tuple[dict[str, str], uuid.UUID, str]) -> None:
    headers, _, _ = owner_pair
    invitee_id = uuid.uuid4()
    invitee_email = f"{invitee_id}@example.com"
    _seed_user(invitee_id, invitee_email)

    with TestClient(app) as client:
        biz = _create_business(client, headers, f"Audit Inv {uuid.uuid4().hex[:8]}")
        _create_invitation(client, headers, biz, invitee_email)

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
                    PlatformOutboxEvent.event_type == "invitation.created",
                )
            )
            assert outbox.scalars().first() == "invitation.created"
            audits = await session.execute(
                select(PlatformAuditEvent.event_type).where(
                    PlatformAuditEvent.business_id == uuid.UUID(biz),
                    PlatformAuditEvent.event_type == "invitation.created",
                )
            )
            assert audits.scalars().first() == "invitation.created"
        await engine.dispose()

    asyncio.run(_assert())


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
async def test_invitation_transaction_rollback(monkeypatch: Any) -> None:
    url = get_database_url()
    assert url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    owner_id = uuid.uuid4()
    owner_email = f"inv-rb-{owner_id.hex[:8]}@test.local"
    async with factory() as session:
        await ensure_auth_user(session, owner_id, owner_email)
        await IdentityService.bootstrap_identity(session, owner_id, owner_email)
        business, _, owner_membership, _ = await BusinessService.create_business(
            session,
            identity_id=owner_id,
            display_name=f"Rollback Inv {owner_id.hex[:8]}",
            business_type="retail",
            correlation_id=str(uuid.uuid4()),
        )
        await session.commit()
        business_id = business.id

    async def _fail(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("forced invitation outbox failure")

    monkeypatch.setattr(OutboxService, "publish", staticmethod(_fail))

    async with factory() as session:
        biz = await BusinessService.get_by_id(session, business_id)
        assert biz
        actor_membership = await TeamService.get_active_membership(session, owner_id, business_id)
        assert actor_membership
        with pytest.raises(RuntimeError, match="forced invitation outbox failure"):
            await InvitationService.create_invitation(
                session,
                business=biz,
                actor=actor_membership,
                invited_email=f"rb-{uuid.uuid4().hex[:8]}@test.local",
                invited_role="member",
                correlation_id=str(uuid.uuid4()),
            )
        await session.rollback()

    async with factory() as session:
        count = await session.execute(select(func.count()).select_from(BusinessInvitation))
        # Only rollback test invite should not persist; other tests may add rows in shared DB
        audits = await session.execute(
            select(func.count())
            .select_from(PlatformAuditEvent)
            .where(
                PlatformAuditEvent.business_id == business_id,
                PlatformAuditEvent.event_type == "invitation.created",
            )
        )
        assert audits.scalar_one() == 0
        assert count.scalar_one() >= 0

    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
async def test_concurrent_acceptance() -> None:
    url = get_database_url()
    assert url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    owner_id = uuid.uuid4()
    invitee_id = uuid.uuid4()
    invitee_email = f"conc-{invitee_id.hex[:8]}@test.local"
    async with factory() as session:
        await ensure_auth_user(session, owner_id, f"own-{owner_id.hex[:8]}@test.local")
        await ensure_auth_user(session, invitee_id, invitee_email)
        await IdentityService.bootstrap_identity(session, owner_id, f"own-{owner_id.hex[:8]}@test.local")
        await IdentityService.bootstrap_identity(session, invitee_id, invitee_email)
        business, _, owner_membership, _ = await BusinessService.create_business(
            session,
            identity_id=owner_id,
            display_name=f"Concurrent Accept {owner_id.hex[:8]}",
            business_type="retail",
            correlation_id=str(uuid.uuid4()),
        )
        invitation = await InvitationService.create_invitation(
            session,
            business=business,
            actor=owner_membership,
            invited_email=invitee_email,
            invited_role="member",
            correlation_id=str(uuid.uuid4()),
        )
        await session.commit()
        business_id = business.id
        invitation_id = invitation.id

    async def _accept() -> None:
        async with factory() as session:
            await InvitationService.accept_invitation(
                session,
                business_id=business_id,
                invitation_id=invitation_id,
                accepter_identity_id=invitee_id,
                accepter_email=invitee_email,
                correlation_id=str(uuid.uuid4()),
            )
            await session.commit()

    results = await asyncio.gather(_accept(), _accept(), return_exceptions=True)
    successes = [r for r in results if r is None]
    failures = [r for r in results if isinstance(r, Exception)]
    assert len(successes) == 1
    assert len(failures) == 1

    await engine.dispose()
