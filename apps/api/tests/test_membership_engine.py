"""Stage 2C — Business membership engine tests."""

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
from platform_core.models import Business, BusinessMembership, PlatformAuditEvent, PlatformOutboxEvent
from platform_core.permissions import TEAM_READ, TEAM_REMOVE, TEAM_UPDATE_ROLE
from platform_core.services.business import BusinessService
from platform_core.services.identity import IdentityService
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
def owner_pair(monkeypatch: Any) -> tuple[dict[str, str], uuid.UUID]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed_user(user_id, email)
    return _headers(user_id, email), user_id


def _create_business(client: TestClient, headers: dict[str, str], name: str) -> str:
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": name, "business_type": "retail"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    business_id = cast(str, resp.json()["data"]["business"]["id"])
    return business_id


def _invite_and_activate(
    client: TestClient,
    owner_headers: dict[str, str],
    business_id: str,
    identity_id: uuid.UUID,
    role: str,
) -> str:
    invite = client.post(
        f"/v1/b/{business_id}/team/invitations",
        json={"identity_id": str(identity_id), "role": role},
        headers=owner_headers,
    )
    assert invite.status_code == 200, invite.text
    membership_id = cast(str, invite.json()["data"]["id"])
    activate = client.post(
        f"/v1/b/{business_id}/team/members/{membership_id}/activate",
        headers=owner_headers,
    )
    assert activate.status_code == 200, activate.text
    return membership_id


def _grant_permissions(
    client: TestClient,
    owner_headers: dict[str, str],
    business_id: str,
    membership_id: str,
    permissions: list[str],
) -> None:
    resp = client.post(
        f"/v1/b/{business_id}/team/members/{membership_id}/permissions",
        json={"permissions": permissions},
        headers=owner_headers,
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_list_and_get_members(owner_pair: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner_pair
    with TestClient(app) as client:
        biz = _create_business(client, headers, f"Members List {uuid.uuid4().hex[:8]}")
        listed = client.get(f"/v1/platform/businesses/{biz}/members", headers=headers)
        assert listed.status_code == 200, listed.text
        members = listed.json()["data"]
        assert len(members) == 1
        assert members[0]["role"] == "primary_owner"
        assert members[0]["status"] == "active"

        mid = members[0]["id"]
        one = client.get(f"/v1/platform/businesses/{biz}/members/{mid}", headers=headers)
        assert one.status_code == 200
        assert one.json()["data"]["id"] == mid


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_suspend_and_reactivate(owner_pair: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner_pair
    member_id = uuid.uuid4()
    member_email = f"{member_id}@example.com"
    _seed_user(member_id, member_email)
    member_headers = _headers(member_id, member_email)

    with TestClient(app) as client:
        biz = _create_business(client, headers, f"Suspend Co {uuid.uuid4().hex[:8]}")
        mid = _invite_and_activate(client, headers, biz, member_id, "member")

        suspended = client.post(
            f"/v1/platform/businesses/{biz}/members/{mid}/suspend",
            headers=headers,
        )
        assert suspended.status_code == 200
        assert suspended.json()["data"]["status"] == "suspended"

        switch_denied = client.post(
            f"/v1/platform/businesses/{biz}/switch",
            json={},
            headers=member_headers,
        )
        assert switch_denied.status_code == 403

        reactivated = client.post(
            f"/v1/platform/businesses/{biz}/members/{mid}/reactivate",
            headers=headers,
        )
        assert reactivated.status_code == 200
        assert reactivated.json()["data"]["status"] == "active"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_remove_member_and_self_leave(owner_pair: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner_pair
    member_id = uuid.uuid4()
    member_email = f"{member_id}@example.com"
    _seed_user(member_id, member_email)
    member_headers = _headers(member_id, member_email)

    with TestClient(app) as client:
        biz = _create_business(client, headers, f"Remove Co {uuid.uuid4().hex[:8]}")
        mid = _invite_and_activate(client, headers, biz, member_id, "member")

        removed = client.delete(
            f"/v1/platform/businesses/{biz}/members/{mid}",
            headers=member_headers,
        )
        assert removed.status_code == 200
        assert removed.json()["data"]["status"] == "removed"

        listed = client.get(f"/v1/platform/businesses/{biz}/members", headers=headers)
        assert all(m["id"] != mid for m in listed.json()["data"])


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_update_membership_metadata(owner_pair: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner_pair
    member_id = uuid.uuid4()
    member_email = f"{member_id}@example.com"
    _seed_user(member_id, member_email)

    with TestClient(app) as client:
        biz = _create_business(client, headers, f"Patch Co {uuid.uuid4().hex[:8]}")
        mid = _invite_and_activate(client, headers, biz, member_id, "member")

        patched = client.patch(
            f"/v1/platform/businesses/{biz}/members/{mid}",
            json={"location_scope": []},
            headers=headers,
        )
        assert patched.status_code == 200
        assert patched.json()["data"]["location_scope"] == []


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_transfer_ownership(owner_pair: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, owner_id = owner_pair
    manager_id = uuid.uuid4()
    manager_email = f"{manager_id}@example.com"
    _seed_user(manager_id, manager_email)

    with TestClient(app) as client:
        biz = _create_business(client, headers, f"Transfer Co {uuid.uuid4().hex[:8]}")
        manager_mid = _invite_and_activate(client, headers, biz, manager_id, "manager")

        transferred = client.post(
            f"/v1/platform/businesses/{biz}/members/transfer-ownership",
            json={"target_membership_id": manager_mid, "demote_to_role": "manager"},
            headers=headers,
        )
        assert transferred.status_code == 200, transferred.text
        data = transferred.json()["data"]
        assert data["new_owner"]["role"] == "primary_owner"
        assert data["new_owner"]["identity_id"] == str(manager_id)
        assert data["former_owner"]["role"] == "manager"
        assert data["former_owner"]["identity_id"] == str(owner_id)
        assert data["primary_owner_identity_id"] == str(manager_id)

        # The former owner is demoted; re-verify the role swap as the new owner.
        new_owner_headers = _headers(manager_id, manager_email)
        listed = client.get(
            f"/v1/platform/businesses/{biz}/members", headers=new_owner_headers
        )
        roles = {m["identity_id"]: m["role"] for m in listed.json()["data"]}
        assert roles[str(manager_id)] == "primary_owner"
        assert roles[str(owner_id)] == "manager"
        assert sum(1 for r in roles.values() if r == "primary_owner") == 1


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_manager_permissions(owner_pair: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner_pair
    manager_id = uuid.uuid4()
    member_id = uuid.uuid4()
    _seed_user(manager_id, f"{manager_id}@example.com")
    _seed_user(member_id, f"{member_id}@example.com")
    manager_headers = _headers(manager_id, f"{manager_id}@example.com")

    with TestClient(app) as client:
        biz = _create_business(client, headers, f"Mgr Perm {uuid.uuid4().hex[:8]}")
        manager_mid = _invite_and_activate(client, headers, biz, manager_id, "manager")
        member_mid = _invite_and_activate(client, headers, biz, member_id, "member")
        _grant_permissions(
            client,
            headers,
            biz,
            manager_mid,
            [TEAM_READ, TEAM_UPDATE_ROLE, TEAM_REMOVE],
        )

        can_list = client.get(f"/v1/platform/businesses/{biz}/members", headers=manager_headers)
        assert can_list.status_code == 200

        can_suspend = client.post(
            f"/v1/platform/businesses/{biz}/members/{member_mid}/suspend",
            headers=manager_headers,
        )
        assert can_suspend.status_code == 200

        cannot_promote_manager = client.patch(
            f"/v1/platform/businesses/{biz}/members/{member_mid}",
            json={"role": "manager"},
            headers=manager_headers,
        )
        assert cannot_promote_manager.status_code == 403


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_member_cannot_modify_memberships(owner_pair: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner_pair
    member_id = uuid.uuid4()
    other_id = uuid.uuid4()
    _seed_user(member_id, f"{member_id}@example.com")
    _seed_user(other_id, f"{other_id}@example.com")
    member_headers = _headers(member_id, f"{member_id}@example.com")

    with TestClient(app) as client:
        biz = _create_business(client, headers, f"Member Deny {uuid.uuid4().hex[:8]}")
        _invite_and_activate(client, headers, biz, member_id, "member")
        other_mid = _invite_and_activate(client, headers, biz, other_id, "member")
        _grant_permissions(client, headers, biz, other_mid, [TEAM_READ])

        denied = client.post(
            f"/v1/platform/businesses/{biz}/members/{other_mid}/suspend",
            headers=member_headers,
        )
        assert denied.status_code == 403


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_membership_failures(owner_pair: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner_pair
    other_id = uuid.uuid4()
    _seed_user(other_id, f"{other_id}@example.com")
    other_headers = _headers(other_id, f"{other_id}@example.com")

    with TestClient(app) as client:
        biz = _create_business(client, headers, f"Fail Co {uuid.uuid4().hex[:8]}")
        owner_mid = client.get(
            f"/v1/platform/businesses/{biz}/members", headers=headers
        ).json()["data"][0]["id"]

        unauth = client.get(f"/v1/platform/businesses/{biz}/members")
        assert unauth.status_code == 401

        no_membership = client.get(
            f"/v1/platform/businesses/{biz}/members", headers=other_headers
        )
        assert no_membership.status_code == 403

        unknown = client.get(
            f"/v1/platform/businesses/{biz}/members/{uuid.uuid4()}",
            headers=headers,
        )
        assert unknown.status_code == 404

        malformed = client.get(
            f"/v1/platform/businesses/{biz}/members/not-a-uuid",
            headers=headers,
        )
        assert malformed.status_code == 422

        cannot_remove_owner = client.delete(
            f"/v1/platform/businesses/{biz}/members/{owner_mid}",
            headers=headers,
        )
        assert cannot_remove_owner.status_code == 403

        member_id = uuid.uuid4()
        _seed_user(member_id, f"{member_id}@example.com")
        member_mid = _invite_and_activate(client, headers, biz, member_id, "member")

        bad_role = client.patch(
            f"/v1/platform/businesses/{biz}/members/{member_mid}",
            json={"role": "admin"},
            headers=headers,
        )
        assert bad_role.status_code == 422

        primary_role = client.patch(
            f"/v1/platform/businesses/{biz}/members/{member_mid}",
            json={"role": "primary_owner"},
            headers=headers,
        )
        assert primary_role.status_code == 403

        bad_transfer = client.post(
            f"/v1/platform/businesses/{biz}/members/transfer-ownership",
            json={"target_membership_id": member_mid},
            headers=other_headers,
        )
        assert bad_transfer.status_code == 403


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_closed_business_blocks_membership_mutations(
    owner_pair: tuple[dict[str, str], uuid.UUID],
) -> None:
    headers, _ = owner_pair
    member_id = uuid.uuid4()
    _seed_user(member_id, f"{member_id}@example.com")

    with TestClient(app) as client:
        biz = _create_business(client, headers, f"Closed Co {uuid.uuid4().hex[:8]}")
        mid = _invite_and_activate(client, headers, biz, member_id, "member")

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

        suspended = client.post(
            f"/v1/platform/businesses/{biz}/members/{mid}/suspend",
            headers=headers,
        )
        assert suspended.status_code == 409
        assert suspended.json()["error"]["details"]["gate"] == "resource_state"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_membership_audit_and_outbox(owner_pair: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner_pair
    member_id = uuid.uuid4()
    _seed_user(member_id, f"{member_id}@example.com")

    with TestClient(app) as client:
        biz = _create_business(client, headers, f"Audit Co {uuid.uuid4().hex[:8]}")
        mid = _invite_and_activate(client, headers, biz, member_id, "member")
        client.post(
            f"/v1/platform/businesses/{biz}/members/{mid}/suspend",
            headers=headers,
        )

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
                    PlatformOutboxEvent.event_type == "membership.suspended",
                )
            )
            assert outbox.scalars().first() == "membership.suspended"
            audits = await session.execute(
                select(PlatformAuditEvent.event_type).where(
                    PlatformAuditEvent.business_id == uuid.UUID(biz),
                    PlatformAuditEvent.event_type == "membership.suspended",
                )
            )
            assert audits.scalars().first() == "membership.suspended"
        await engine.dispose()

    asyncio.run(_assert())


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
async def test_membership_transaction_rollback(monkeypatch: Any) -> None:
    url = get_database_url()
    assert url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    owner_id = uuid.uuid4()
    member_id = uuid.uuid4()
    owner_email = f"rb-owner-{owner_id.hex[:8]}@test.local"
    member_email = f"rb-member-{member_id.hex[:8]}@test.local"
    async with factory() as session:
        await ensure_auth_user(session, owner_id, owner_email)
        await ensure_auth_user(session, member_id, member_email)
        await IdentityService.bootstrap_identity(session, owner_id, owner_email)
        business, _, _, _ = await BusinessService.create_business(
            session,
            identity_id=owner_id,
            display_name=f"Rollback Member {owner_id.hex[:8]}",
            business_type="retail",
            correlation_id=str(uuid.uuid4()),
        )
        membership = await TeamService.invite_member(
            session,
            business_id=business.id,
            identity_id=member_id,
            role="member",
            invited_by=owner_id,
        )
        await TeamService.activate_membership(session, membership)
        await session.commit()
        business_id = business.id
        membership_id = membership.id

    async def _fail(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("forced membership outbox failure")

    monkeypatch.setattr(OutboxService, "publish", staticmethod(_fail))

    async with factory() as session:
        business = await session.get(Business, business_id)
        assert business
        target = await TeamService.get_membership_by_id(session, business_id, membership_id)
        actor = await TeamService.get_active_membership(session, owner_id, business_id)
        assert target and actor
        with pytest.raises(RuntimeError, match="forced membership outbox failure"):
            await TeamService.suspend_membership(
                session,
                business=business,
                target=target,
                actor=actor,
                correlation_id=str(uuid.uuid4()),
            )
        await session.rollback()

    async with factory() as session:
        target = await TeamService.get_membership_by_id(session, business_id, membership_id)
        assert target
        assert target.status == "active"
        audits = await session.execute(
            select(func.count())
            .select_from(PlatformAuditEvent)
            .where(
                PlatformAuditEvent.business_id == business_id,
                PlatformAuditEvent.event_type == "membership.suspended",
            )
        )
        assert audits.scalar_one() == 0

    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
async def test_concurrent_ownership_transfer() -> None:
    url = get_database_url()
    assert url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    owner_id = uuid.uuid4()
    target_a = uuid.uuid4()
    target_b = uuid.uuid4()
    for uid, label in ((owner_id, "owner"), (target_a, "a"), (target_b, "b")):
        async with factory() as session:
            email = f"conc-{label}-{uid.hex[:6]}@test.local"
            await ensure_auth_user(session, uid, email)
            await IdentityService.bootstrap_identity(session, uid, email)
            await session.commit()

    async with factory() as session:
        business, _, _, _ = await BusinessService.create_business(
            session,
            identity_id=owner_id,
            display_name=f"Concurrent Transfer {owner_id.hex[:8]}",
            business_type="retail",
            correlation_id=str(uuid.uuid4()),
        )
        mid_a = await TeamService.invite_member(
            session,
            business_id=business.id,
            identity_id=target_a,
            role="manager",
            invited_by=owner_id,
        )
        mid_b = await TeamService.invite_member(
            session,
            business_id=business.id,
            identity_id=target_b,
            role="member",
            invited_by=owner_id,
        )
        await TeamService.activate_membership(session, mid_a)
        await TeamService.activate_membership(session, mid_b)
        await session.commit()
        business_id = business.id
        mid_a_id = mid_a.id
        mid_b_id = mid_b.id

    async def _transfer(target_mid: uuid.UUID) -> None:
        async with factory() as session:
            await TeamService.transfer_primary_ownership(
                session,
                business_id=business_id,
                actor_identity_id=owner_id,
                target_membership_id=target_mid,
                correlation_id=str(uuid.uuid4()),
            )
            await session.commit()

    results = await asyncio.gather(
        _transfer(mid_a_id),
        _transfer(mid_b_id),
        return_exceptions=True,
    )
    successes = [r for r in results if r is None]
    failures = [r for r in results if isinstance(r, Exception)]
    assert len(successes) == 1
    assert len(failures) == 1

    async with factory() as session:
        biz = await session.get(Business, business_id)
        assert biz
        owners = await session.execute(
            select(BusinessMembership).where(
                BusinessMembership.business_id == business_id,
                BusinessMembership.role == "primary_owner",
                BusinessMembership.status == "active",
                BusinessMembership.deleted_at.is_(None),
            )
        )
        owner_rows = list(owners.scalars().all())
        assert len(owner_rows) == 1
        assert str(biz.primary_owner_identity_id) == str(owner_rows[0].identity_id)

    await engine.dispose()


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_direct_invite_emits_membership_created_event(
    owner_pair: tuple[dict[str, str], uuid.UUID],
) -> None:
    """`POST /team/invitations` must be visible to event consumers.

    The direct-invite path used to write a membership row and publish nothing,
    so it was invisible to Notifications, Audit, and every other event consumer
    while the email-invitation path was not. Both now emit `membership.created`,
    distinguished by the payload's `source`.
    """
    headers, owner_id = owner_pair
    member_id = uuid.uuid4()
    _seed_user(member_id, f"{member_id}@example.com")

    with TestClient(app) as client:
        biz = _create_business(client, headers, f"Direct Invite {uuid.uuid4().hex[:8]}")
        invite = client.post(
            f"/v1/b/{biz}/team/invitations",
            json={"identity_id": str(member_id), "role": "member"},
            headers=headers,
        )
        assert invite.status_code == 200, invite.text
        membership_id = cast(str, invite.json()["data"]["id"])

    async def _assert() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            events = (
                await session.execute(
                    select(PlatformOutboxEvent).where(
                        PlatformOutboxEvent.business_id == uuid.UUID(biz),
                        PlatformOutboxEvent.event_type == "membership.created",
                    )
                )
            ).scalars().all()
            direct = [
                e
                for e in events
                if (e.payload or {}).get("membership_id") == membership_id
            ]
            assert direct, f"no membership.created for the direct invite: {events}"
            payload = direct[0].payload
            assert payload["source"] == "direct_invite"
            assert payload["identity_id"] == str(member_id)
            assert payload["role"] == "member"
            assert payload["status"] == "pending"

            audits = (
                await session.execute(
                    select(PlatformAuditEvent).where(
                        PlatformAuditEvent.business_id == uuid.UUID(biz),
                        PlatformAuditEvent.resource_id == uuid.UUID(membership_id),
                        PlatformAuditEvent.event_type == "membership.created",
                    )
                )
            ).scalars().all()
            assert audits, "direct invite left no audit trail"
            assert audits[0].action == "invite_member"
            assert audits[0].actor_identity_id == owner_id
        await engine.dispose()

    asyncio.run(_assert())
