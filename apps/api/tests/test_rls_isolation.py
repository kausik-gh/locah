"""Row Level Security, exercised as the roles that are actually subject to it.

The rest of the suite connects as the database owner, which bypasses RLS —
so it proves the API's own checks, not the database's. Here the same
migrations are queried as `platform_api` (the API's RLS-enforcing role) and
as `anon` (a public Supabase request), to prove the second line of defence:

* a request bound to Business A cannot read, change or insert Business B's
  rows — whatever the API code does;
* an anonymous request sees only what is deliberately public (discoverable
  Marketplace listings, catalogue data) and nothing else.

Runs against the local test database only (the database guard refuses
remote URLs).
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from platform_core.db import get_database_url

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")


def _url() -> str:
    url = get_database_url() or ""
    return url.replace("postgresql://", "postgresql+asyncpg://", 1) if url.startswith("postgresql://") else url


async def _seed(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """Two businesses, each with one private customer contact."""
    ids = []
    for label in ("A", "B"):
        business_id = uuid.uuid4()
        owner = uuid.uuid4()
        await session.execute(text(
            "insert into auth.users (id, email) values (:id, :email)"), {"id": owner, "email": f"{owner}@example.com"})
        await session.execute(text(
            "insert into businesses (id, slug, display_name, state, primary_owner_identity_id, business_type) "
            "values (:id, :slug, :name, 'draft', :owner, 'other')"),
            {"id": business_id, "slug": f"rls-{label.lower()}-{business_id.hex[:8]}", "name": f"RLS {label}",
             "owner": owner})
        await session.execute(text(
            "insert into customer_relationships_contacts (business_id, display_name) values (:b, :n)"),
            {"b": business_id, "n": f"Private customer of {label}"})
        ids.append(business_id)
    return ids[0], ids[1]


@pytest.mark.asyncio
async def test_a_business_cannot_see_or_touch_another_business_rows() -> None:
    engine = create_async_engine(_url(), poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            a, b = await _seed(session)
            await session.execute(text("set local role platform_api"))
            await session.execute(text("select set_config('app.current_business_id', :a, true)"), {"a": str(a)})
            seen = (await session.execute(text(
                "select distinct business_id from customer_relationships_contacts"))).scalars().all()
            assert seen == [a]
            changed = await session.execute(text(
                "update customer_relationships_contacts set display_name = 'hijacked' where business_id = :b "
                "returning id"), {"b": b})
            assert changed.all() == []
            with pytest.raises(DBAPIError, match="row-level security"):
                await session.execute(text(
                    "insert into customer_relationships_contacts (business_id, display_name) values (:b, 'x')"),
                    {"b": b})
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_without_a_business_context_the_api_role_sees_no_tenant_rows() -> None:
    engine = create_async_engine(_url(), poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            await _seed(session)
            await session.execute(text("set local role platform_api"))
            for table in ("customer_relationships_contacts", "orders_orders", "payments_payment_attempts",
                          "website_sections", "media_assets", "bookings_bookings"):
                count = (await session.execute(text(f"select count(*) from {table}"))).scalar_one()
                assert count == 0, table
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_anonymous_requests_see_only_what_is_deliberately_public() -> None:
    engine = create_async_engine(_url(), poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            await _seed(session)
            await session.execute(text("set local role anon"))

            async def visible(table: str) -> int | None:
                """Rows anon can see, or None when anon has no grant at all (both mean "not exposed").

                Supabase grants anon every public table and relies on RLS; the
                local shim grants nothing. Either way, private rows stay hidden.
                """
                try:
                    async with session.begin_nested():
                        return int((await session.execute(text(f"select count(*) from {table}"))).scalar_one())
                except DBAPIError as exc:
                    assert "permission denied" in str(exc), exc
                    return None

            for table in ("businesses", "customer_relationships_contacts", "orders_orders", "platform_identities",
                          "business_memberships", "payments_payment_attempts", "website_versions", "media_assets",
                          "platform_outbox_events", "platform_async_jobs", "platform_audit_events"):
                assert await visible(table) in {0, None}, table
            await session.rollback()
    finally:
        await engine.dispose()
