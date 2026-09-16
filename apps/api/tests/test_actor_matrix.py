"""Stage 7 Section 6 — systematic actor/context matrix (Doc 11 §19.2).

This file exists because of AUD-06 and AUD-07. Those findings established that
the existing suite had NOT been testing role-based access: every actor test
granted explicit permissions first, so "a Manager can do X" was never actually
verified — only "an actor holding hand-picked grants can do X".

These tests deliberately do NOT grant permissions before asserting, except
where a test says so in its name. They therefore pin down what each actor can
*actually* do today, including where that is currently nothing. When
FL-DEC-013/FL-DEC-019 close and role defaults land, the assertions marked
AUD-07 will start failing — that is the point. They are the tripwire that
turns AUD-07 from a note into something the suite enforces.

Doc 11 §19.2 requires these actors at minimum. Coverage here:

  * unauthenticated consumer .................. covered
  * authenticated consumer (no membership) .... covered
  * Business Primary Owner .................... covered
  * Manager (no explicit grants) .............. covered — AUD-07 tripwire
  * Member with explicit grants ............... covered
  * Location-scoped Member .................... covered
  * invited but not activated user ............ covered
  * suspended/removed member .................. covered
  * attributed Platform Super Admin ........... covered in test_admin_support.py
  * expired/suspended Entitlement ............. NOT covered — no API sets it
  * enabled-but-incomplete module config ...... NOT reachable — no First Launch
                                                module declares a config schema,
                                                so enable_module goes straight
                                                to `active`
  * provider disconnected/restricted .......... NOT covered — needs a provider
                                                fixture (FL-DEC-006)

The three uncovered rows are recorded here rather than silently omitted, so
the gap is visible in the same place as the coverage.
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
from platform_core.permissions import ORDERS_READ
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


@pytest.fixture
def owner(monkeypatch: Any) -> tuple[dict[str, str], uuid.UUID]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    headers, user_id, _ = _actor()
    return headers, user_id


def _create_business(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"Matrix Co {uuid.uuid4().hex[:8]}", "business_type": "retail"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    business_id = cast(str, resp.json()["data"]["business"]["id"])
    for module_id in ("offerings-catalog", "orders", "customer-relationships"):
        enabled = client.post(f"/v1/b/{business_id}/modules/{module_id}/enable", headers=headers)
        assert enabled.status_code == 200, enabled.text
    return business_id


def _invite_membership(
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
    return cast(str, invite.json()["data"]["id"])


def _activate(
    client: TestClient, owner_headers: dict[str, str], business_id: str, membership_id: str
) -> None:
    resp = client.post(
        f"/v1/b/{business_id}/team/members/{membership_id}/activate", headers=owner_headers
    )
    assert resp.status_code == 200, resp.text


def _grant(
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


ORDERS = "/v1/platform/businesses/{bid}/orders"


# ---------------------------------------------------------------------------
# Unauthenticated / non-member
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_unauthenticated_consumer_is_refused(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        bid = _create_business(client, headers)
        resp = client.get(ORDERS.format(bid=bid))
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_authenticated_consumer_without_membership_is_refused(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    headers, _ = owner
    consumer_headers, _, _ = _actor()
    with TestClient(app) as client:
        bid = _create_business(client, headers)
        resp = client.get(ORDERS.format(bid=bid), headers=consumer_headers)
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "MEMBERSHIP_REQUIRED"


# ---------------------------------------------------------------------------
# Primary Owner
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_primary_owner_has_full_access(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    with TestClient(app) as client:
        bid = _create_business(client, headers)
        assert client.get(ORDERS.format(bid=bid), headers=headers).status_code == 200
        assert client.get(f"/v1/platform/businesses/{bid}/members", headers=headers).status_code == 200


# ---------------------------------------------------------------------------
# Manager / Member without grants — the AUD-07 tripwire
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
@pytest.mark.parametrize("role", ["manager", "member"])
def test_role_defaults_currently_grant_nothing(
    owner: tuple[dict[str, str], uuid.UUID], role: str
) -> None:
    """AUD-07 tripwire — asserts the CURRENT (broken) behaviour on purpose.

    `_MANAGER_BASE` and `_MEMBER_BASE` in role_registry.py are both empty, so
    an activated Manager or Member holds no permissions at all. This test
    documents that as executable fact.

    WHEN FL-DEC-013/FL-DEC-019 CLOSE AND ROLE DEFAULTS LAND, THIS TEST WILL
    FAIL. That is intended: update it to assert the new defaults rather than
    deleting it.
    """
    headers, _ = owner
    actor_headers, actor_id, _ = _actor()
    with TestClient(app) as client:
        bid = _create_business(client, headers)
        membership_id = _invite_membership(client, headers, bid, actor_id, role)
        _activate(client, headers, bid, membership_id)

        resp = client.get(ORDERS.format(bid=bid), headers=actor_headers)
        assert resp.status_code == 403, (
            f"{role} unexpectedly has orders.read — if role defaults were just "
            f"introduced, update this AUD-07 tripwire instead of removing it"
        )
        assert resp.json()["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_member_with_explicit_grant_gains_exactly_that_permission(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    headers, _ = owner
    member_headers, member_id, _ = _actor()
    with TestClient(app) as client:
        bid = _create_business(client, headers)
        membership_id = _invite_membership(client, headers, bid, member_id, "member")
        _activate(client, headers, bid, membership_id)
        _grant(client, headers, bid, membership_id, [ORDERS_READ])

        assert client.get(ORDERS.format(bid=bid), headers=member_headers).status_code == 200
        # The grant is exactly one permission — it does not spill into Team.
        team = client.get(f"/v1/platform/businesses/{bid}/members", headers=member_headers)
        assert team.status_code == 403, "orders.read must not confer team.read"


# ---------------------------------------------------------------------------
# Invited-but-not-activated, suspended, removed
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_invited_but_not_activated_has_no_access(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    headers, _ = owner
    invitee_headers, invitee_id, _ = _actor()
    with TestClient(app) as client:
        bid = _create_business(client, headers)
        membership_id = _invite_membership(client, headers, bid, invitee_id, "member")
        _grant(client, headers, bid, membership_id, [ORDERS_READ])  # granted but pending

        resp = client.get(ORDERS.format(bid=bid), headers=invitee_headers)
        assert resp.status_code == 403, resp.text
        # Membership gate [4] must fire before the permission gate [8]: a
        # pending member is not a member, regardless of what they were granted.
        assert resp.json()["error"]["code"] == "MEMBERSHIP_REQUIRED"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_suspended_member_loses_access(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    member_headers, member_id, _ = _actor()
    with TestClient(app) as client:
        bid = _create_business(client, headers)
        membership_id = _invite_membership(client, headers, bid, member_id, "member")
        _activate(client, headers, bid, membership_id)
        _grant(client, headers, bid, membership_id, [ORDERS_READ])
        assert client.get(ORDERS.format(bid=bid), headers=member_headers).status_code == 200

        suspend = client.post(
            f"/v1/platform/businesses/{bid}/members/{membership_id}/suspend", headers=headers
        )
        assert suspend.status_code == 200, suspend.text

        after = client.get(ORDERS.format(bid=bid), headers=member_headers)
        assert after.status_code == 403
        assert after.json()["error"]["code"] == "MEMBERSHIP_REQUIRED"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_removed_member_loses_access(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    member_headers, member_id, _ = _actor()
    with TestClient(app) as client:
        bid = _create_business(client, headers)
        membership_id = _invite_membership(client, headers, bid, member_id, "member")
        _activate(client, headers, bid, membership_id)
        _grant(client, headers, bid, membership_id, [ORDERS_READ])

        removed = client.delete(
            f"/v1/platform/businesses/{bid}/members/{membership_id}", headers=headers
        )
        assert removed.status_code in (200, 204), removed.text

        after = client.get(ORDERS.format(bid=bid), headers=member_headers)
        assert after.status_code == 403
        assert after.json()["error"]["code"] == "MEMBERSHIP_REQUIRED"


# ---------------------------------------------------------------------------
# Location-scoped member
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_location_scoped_member_is_recorded_and_readable(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    """A Location-scoped membership must carry its scope through the API.

    This asserts the scope survives round-tripping, which is the precondition
    for Location leakage enforcement (Doc 11 §21.1 "permission and Location
    leakage tests pass"). Per-record Location filtering on list endpoints is a
    separate concern and is NOT claimed here.
    """
    headers, _ = owner
    scoped_headers, scoped_id, _ = _actor()
    with TestClient(app) as client:
        bid = _create_business(client, headers)
        locations = client.get(
            f"/v1/platform/businesses/{bid}/locations", headers=headers
        ).json()["data"]
        primary_id = next(loc["id"] for loc in locations if loc["is_primary"])

        membership_id = _invite_membership(client, headers, bid, scoped_id, "member")
        _activate(client, headers, bid, membership_id)
        scoped = client.patch(
            f"/v1/platform/businesses/{bid}/members/{membership_id}",
            json={"location_scope": [primary_id]},
            headers=headers,
        )
        assert scoped.status_code == 200, scoped.text
        _grant(client, headers, bid, membership_id, [ORDERS_READ])

        detail = client.get(
            f"/v1/platform/businesses/{bid}/members/{membership_id}", headers=headers
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["data"]["location_scope"] == [primary_id]

        assert client.get(ORDERS.format(bid=bid), headers=scoped_headers).status_code == 200


# ---------------------------------------------------------------------------
# Cross-Business isolation (Doc 11 §21.1)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_membership_in_one_business_grants_nothing_in_another(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    headers, _ = owner
    other_owner_headers, _, _ = _actor()
    member_headers, member_id, _ = _actor()
    with TestClient(app) as client:
        mine = _create_business(client, headers)
        theirs = _create_business(client, other_owner_headers)

        membership_id = _invite_membership(client, headers, mine, member_id, "member")
        _activate(client, headers, mine, membership_id)
        _grant(client, headers, mine, membership_id, [ORDERS_READ])

        assert client.get(ORDERS.format(bid=mine), headers=member_headers).status_code == 200
        leaked = client.get(ORDERS.format(bid=theirs), headers=member_headers)
        assert leaked.status_code == 403
        assert leaked.json()["error"]["code"] == "MEMBERSHIP_REQUIRED"
