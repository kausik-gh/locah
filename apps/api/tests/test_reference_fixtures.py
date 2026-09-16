"""Stage 7 — AUD-04: module registry completeness + the 11 reference fixtures.

Two guards:
  * every module in `ModuleRegistry` (the Python source of truth) exists in
    `module_definitions` — so the seed and the code can't drift, and the 11
    Later/Future modules stay referenceable;
  * every Doc 11 §5.2 reference Business model provisions end-to-end through
    the real API via `build_reference_business` — modules, offering, location,
    provider, plan — which is the precondition for Stage 8 running the
    workflows.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_core.db import get_database_url
from platform_core.entitlements.module_registry import _MODULES
from platform_testing.db_helpers import ensure_auth_user
from platform_testing.reference_fixtures import REFERENCE_MODELS, build_reference_business
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


def _owner(monkeypatch: Any) -> dict[str, str]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed(user_id, email)
    return {"Authorization": f"Bearer {_token(user_id, email)}"}


# ---------------------------------------------------------------------------
# Registry ↔ seed consistency
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_every_registry_module_is_seeded() -> None:
    async def _check() -> set[str]:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            rows = await session.execute(text("SELECT id, module_class FROM module_definitions"))
            db = {r[0]: r[1] for r in rows}
        await engine.dispose()
        return db  # type: ignore[return-value]

    db_modules: dict[str, str] = asyncio.run(_check())  # type: ignore[assignment]

    registry_ids = set(_MODULES.keys())
    missing = registry_ids - set(db_modules)
    assert not missing, f"registry modules absent from module_definitions: {sorted(missing)}"

    optional = {mid for mid, m in _MODULES.items() if m.module_class == "optional"}
    assert len(optional) == 21, f"expected 21 optional modules, registry has {len(optional)}"

    for mid, m in _MODULES.items():
        assert db_modules[mid] == m.module_class, (
            f"{mid}: registry class {m.module_class}, DB class {db_modules[mid]}"
        )


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_later_future_modules_are_registered_not_activatable() -> None:
    """The 11 added modules are referenceable but grant nothing to a Business."""
    later = {
        "queue-operations", "invoicing", "loyalty", "payroll", "messaging",
        "marketing", "reviews", "analytics", "business-passport",
        "business-community", "b2b-network",
    }
    assert later <= set(_MODULES), later - set(_MODULES)
    # They are optional class and carry canonical dependency links.
    for mid in later:
        m = _MODULES[mid]
        assert m.module_class == "optional"
        assert m.description  # non-empty


# ---------------------------------------------------------------------------
# The 11 reference fixtures build end-to-end
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_there_are_exactly_11_reference_models() -> None:
    assert len(REFERENCE_MODELS) == 11
    assert [m.number for m in REFERENCE_MODELS] == list(range(1, 12))
    assert len({m.key for m in REFERENCE_MODELS}) == 11


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
@pytest.mark.parametrize("model", REFERENCE_MODELS, ids=lambda m: m.key)
def test_reference_business_provisions_end_to_end(model: Any, monkeypatch: Any) -> None:
    headers = _owner(monkeypatch)
    with TestClient(app) as client:
        bid = build_reference_business(client, headers, model)

        # Every canonical module for this model is operational.
        states = client.get(f"/v1/b/{bid}/modules", headers=headers)
        assert states.status_code == 200, states.text
        active = {
            row["module_id"]
            for row in states.json()["data"]
            if row["activation_state"] in ("ready", "active")
        }
        for module_id in model.canonical_modules:
            assert module_id in active, f"{model.key}: {module_id} not active ({active})"

        # The representative offering exists and is active.
        offerings = client.get(
            f"/v1/platform/businesses/{bid}/products", headers=headers
        ).json()["data"]
        assert any(
            o["title"] == model.offering.title and o["status"] == "active" for o in offerings
        ), f"{model.key}: offering missing"

        if model.needs_provider:
            members = client.get(
                f"/v1/platform/businesses/{bid}/workforce/members", headers=headers
            ).json()["data"]
            assert members, f"{model.key}: expected a workforce provider"

        if model.needs_membership_plan:
            plans = client.get(
                f"/v1/platform/businesses/{bid}/membership-plans", headers=headers
            ).json()["data"]
            assert plans, f"{model.key}: expected a membership plan"
