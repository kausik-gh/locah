"""Shared helpers for Phase B (Business OS) tests.

Capability Universe §24.3: every new table ships with its RLS policy, a
cross-business isolation test and an actor-matrix row. `assert_tenant_isolated`
is that isolation test, run as the roles actually subject to RLS
(`platform_api`, `anon`), for any business-scoped table.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import jwt
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from platform_core.db import get_database_url
from platform_testing.db_helpers import ensure_auth_user

TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"


def db_url() -> str:
    url = get_database_url() or ""
    return url.replace("postgresql://", "postgresql+asyncpg://", 1) if url.startswith("postgresql://") else url


def headers_for(user_id: uuid.UUID, email: str | None = None) -> dict[str, str]:
    token = jwt.encode(
        {"sub": str(user_id), "email": email or f"{user_id}@example.com",
         "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def new_identity(monkeypatch: Any) -> tuple[uuid.UUID, dict[str, str]]:
    """A signed-in platform identity (auth user + identity row) and its headers."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"

    async def _run() -> None:
        engine = create_async_engine(db_url(), echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await ensure_auth_user(session, user_id, email)
            await session.commit()
        await engine.dispose()

    asyncio.run(_run())
    return user_id, headers_for(user_id, email)


def create_business(
    client: Any,
    headers: dict[str, str],
    *,
    category_key: str | None = None,
    subcategory_key: str | None = None,
    business_type: str = "other",
    modules: tuple[str, ...] = (),
    name: str | None = None,
) -> str:
    body: dict[str, Any] = {
        "display_name": name or f"Biz {uuid.uuid4().hex[:8]}",
        "business_type": business_type,
    }
    if category_key:
        body["category_key"] = category_key
        if subcategory_key:
            body["subcategory_key"] = subcategory_key
    resp = client.post("/v1/platform/businesses", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    business_id = cast(str, resp.json()["data"]["business"]["id"])
    for mid in modules:
        enabled = client.post(f"/v1/b/{business_id}/modules/{mid}/enable", headers=headers)
        assert enabled.status_code == 200, f"{mid}: {enabled.text}"
    return business_id


async def _two_businesses(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    ids = []
    for label in ("a", "b"):
        business_id = uuid.uuid4()
        owner = uuid.uuid4()
        await session.execute(text("insert into auth.users (id, email) values (:id, :email)"),
                              {"id": owner, "email": f"{owner}@example.com"})
        await session.execute(text(
            "insert into businesses (id, slug, display_name, state, primary_owner_identity_id, business_type) "
            "values (:id, :slug, :name, 'draft', :owner, 'other')"),
            {"id": business_id, "slug": f"iso-{label}-{business_id.hex[:8]}", "name": f"ISO {label}",
             "owner": owner})
        ids.append(business_id)
    return ids[0], ids[1]


async def assert_tenant_isolated(
    table: str,
    insert: Callable[[AsyncSession, uuid.UUID], Awaitable[None]],
    *,
    update_sql: str | None = None,
) -> None:
    """Prove RLS on `table`: bound to A, platform_api sees only A's rows, cannot
    change B's and cannot insert into B; with no business bound it sees none;
    anon sees none."""
    engine = create_async_engine(db_url(), poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            a, b = await _two_businesses(session)
            await insert(session, a)
            await insert(session, b)
            await session.execute(text("set local role platform_api"))
            await session.execute(text("select set_config('app.current_business_id', :a, true)"), {"a": str(a)})
            seen = (await session.execute(text(f"select distinct business_id from {table}"))).scalars().all()
            assert seen == [a], f"{table}: bound to A but saw {seen}"
            sql = update_sql or f"update {table} set business_id = business_id where business_id = :b returning business_id"
            changed = await session.execute(text(sql), {"b": b})
            assert changed.all() == [], f"{table}: A changed B's rows"
            await session.execute(text("savepoint before_insert"))
            try:
                await insert(session, b)
                raise AssertionError(f"{table}: A inserted a row into B")
            except DBAPIError as exc:
                assert "row-level security" in str(exc), exc
                await session.execute(text("rollback to savepoint before_insert"))
            await session.execute(text("select set_config('app.current_business_id', '', true)"))
            none = (await session.execute(text(f"select count(*) from {table}"))).scalar()
            assert none == 0, f"{table}: unbound API role saw {none} rows"
            await session.execute(text("reset role"))
            await session.execute(text("set local role anon"))
            try:
                anon = (await session.execute(text(f"select count(*) from {table}"))).scalar()
                assert anon == 0, f"{table}: anon saw {anon} rows"
            except DBAPIError as exc:  # not granted to anon at all: also private
                assert "permission denied" in str(exc), exc
            await session.rollback()
    finally:
        await engine.dispose()
