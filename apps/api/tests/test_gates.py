"""Distinct capability-gate codes (Doc 11 §17.1 / Doc 12 §8.9 / §10.6)."""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_core.exceptions import (
    EntitlementRequired,
    LocationAccessDenied,
    ModuleNotActive,
    PermissionDenied,
    ResourceNotFound,
    ResourceStateDenied,
)
from platform_core.gates import assert_business_mutable, assert_resource_allows
from platform_core.db import get_database_url
from platform_testing.db_helpers import ensure_auth_user
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"


def _make_token(sub: str, email: str) -> str:
    return jwt.encode(
        {
            "sub": sub,
            "email": email,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


def test_five_gates_have_distinct_error_codes() -> None:
    permission = PermissionDenied("business.update")
    entitlement = EntitlementRequired("orders")
    module = ModuleNotActive("orders")
    location = LocationAccessDenied()
    resource = ResourceStateDenied("business", "closed", action="update")

    codes = {
        permission.code,
        entitlement.code,
        module.code,
        location.code,
        resource.code,
    }
    assert codes == {
        "PERMISSION_DENIED",
        "ENTITLEMENT_REQUIRED",
        "MODULE_NOT_ACTIVE",
        "LOCATION_ACCESS_DENIED",
        "CONFLICT",
    }
    assert resource.detail["details"]["gate"] == "resource_state"
    # RESOURCE_NOT_FOUND remains a separate resource-visibility code.
    assert ResourceNotFound("Business").code == "RESOURCE_NOT_FOUND"
    assert ResourceNotFound("Business").code != resource.code


def test_assert_resource_allows_rejects_disallowed_state() -> None:
    with pytest.raises(ResourceStateDenied) as exc:
        assert_resource_allows(
            resource="business",
            current_state="closed",
            allowed_states={"draft", "active"},
            action="update",
        )
    assert exc.value.code == "CONFLICT"
    assert exc.value.detail["details"]["gate"] == "resource_state"


def test_assert_business_mutable_allows_active() -> None:
    assert_business_mutable("active", action="update")


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required for integration")
def test_closed_business_update_returns_conflict(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"

    import asyncio

    async def _seed() -> None:
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

    asyncio.run(_seed())
    headers = {"Authorization": f"Bearer {_make_token(str(user_id), email)}"}

    with TestClient(app) as client:
        create_resp = client.post(
            "/v1/platform/businesses",
            json={"display_name": "Closeable Co"},
            headers=headers,
        )
        assert create_resp.status_code == 200
        business_id = create_resp.json()["data"]["business"]["id"]

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
                    {"id": business_id},
                )
                await session.commit()
            await engine.dispose()

        asyncio.run(_close())

        patch_resp = client.patch(
            f"/v1/b/{business_id}",
            json={"display_name": "Should Fail"},
            headers=headers,
        )
        assert patch_resp.status_code == 409
        body = patch_resp.json()
        assert body["error"]["code"] == "CONFLICT"
        assert body["error"]["details"]["gate"] == "resource_state"
        assert body["error"]["details"]["state"] == "closed"
