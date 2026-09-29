"""Row Level Security for loyalty and marketing tables.

Queried as platform_api, the role the API uses. The database owner bypasses
RLS, so the service tests do not prove this. Fails if TEST_DATABASE_URL is
missing rather than skipping.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from platform_core.db import get_database_url

GROWTH_TABLES = (
    "loyalty_programs",
    "loyalty_accounts",
    "loyalty_ledger",
    "stamp_programs",
    "stamp_cards",
    "stamp_rewards",
    "stamp_awards",
    "referral_codes",
    "referral_relationships",
    "gift_vouchers",
    "gift_voucher_transactions",
    "marketing_offers",
    "marketing_campaigns",
    "marketing_broadcast_recipients",
    "marketing_frequency_log",
    "marketing_touchpoints",
    "marketing_conversions",
    "marketing_meta_configurations",
)


def _url() -> str:
    url = get_database_url() or ""
    if not url:
        pytest.fail("Growth RLS tests require TEST_DATABASE_URL on local Postgres")
    return url.replace("postgresql://", "postgresql+asyncpg://", 1) if url.startswith("postgresql://") else url


async def _business(session: AsyncSession, label: str) -> uuid.UUID:
    business_id = uuid.uuid4()
    owner = uuid.uuid4()
    await session.execute(
        text("insert into auth.users (id, email) values (:id, :email)"),
        {"id": owner, "email": f"{owner.hex[:12]}@example.com"},
    )
    await session.execute(
        text(
            "insert into businesses (id, slug, display_name, state, primary_owner_identity_id, business_type) "
            "values (:id, :slug, :name, 'draft', :owner, 'other')"
        ),
        {
            "id": business_id,
            "slug": f"rls-growth-{label}-{business_id.hex[:8]}",
            "name": f"RLS {label}",
            "owner": owner,
        },
    )
    return business_id


@pytest.mark.asyncio
async def test_growth_tables_are_isolated_by_business() -> None:
    engine = create_async_engine(_url(), poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            business_a = await _business(session, "a")
            business_b = await _business(session, "b")
            await session.execute(
                text(
                    "insert into loyalty_programs (business_id, name, points_per_rupee, redemption_rupees_per_point) "
                    "values (:a, 'A', 1, 0.25), (:b, 'B', 1, 0.25)"
                ),
                {"a": business_a, "b": business_b},
            )
            await session.execute(
                text("insert into marketing_offers (business_id, code, name, kind, discount_value) "
                     "values (:a, 'AAA', 'Offer A', 'percentage_discount', 10), "
                     "(:b, 'BBB', 'Offer B', 'percentage_discount', 10)"),
                {"a": business_a, "b": business_b},
            )
            await session.execute(text("set local role platform_api"))
            await session.execute(
                text("select set_config('app.current_business_id', :a, true)"),
                {"a": str(business_a)},
            )

            programs = (await session.execute(text("select name from loyalty_programs"))).scalars().all()
            offers = (await session.execute(text("select code from marketing_offers"))).scalars().all()
            assert programs == ["A"]
            assert offers == ["AAA"]

            changed = await session.execute(
                text("update marketing_offers set name = 'hijacked' where business_id = :b returning id"),
                {"b": business_b},
            )
            assert changed.all() == []
            with pytest.raises(DBAPIError, match="row-level security"):
                await session.execute(
                    text(
                        "insert into loyalty_programs (business_id, name, points_per_rupee, redemption_rupees_per_point) "
                        "values (:b, 'smuggled', 1, 0.25)"
                    ),
                    {"b": business_b},
                )
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_growth_tables_are_empty_without_a_business_context() -> None:
    engine = create_async_engine(_url(), poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            business_id = await _business(session, "solo")
            await session.execute(
                text(
                    "insert into loyalty_programs (business_id, name, points_per_rupee, redemption_rupees_per_point) "
                    "values (:b, 'Solo', 1, 0.25)"
                ),
                {"b": business_id},
            )
            await session.execute(
                text("insert into marketing_meta_configurations (business_id, monthly_spend_cap_paise) values (:b, 100)"),
                {"b": business_id},
            )
            await session.execute(text("set local role platform_api"))
            for table in GROWTH_TABLES:
                count = (await session.execute(text(f"select count(*) from {table}"))).scalar_one()
                assert count == 0, table
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_anonymous_role_cannot_read_growth_tables() -> None:
    engine = create_async_engine(_url(), poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            business_id = await _business(session, "anon")
            await session.execute(
                text(
                    "insert into loyalty_programs (business_id, name, points_per_rupee, redemption_rupees_per_point) "
                    "values (:b, 'Hidden', 1, 0.25)"
                ),
                {"b": business_id},
            )
            await session.execute(text("set local role anon"))
            try:
                async with session.begin_nested():
                    count = (await session.execute(text("select count(*) from loyalty_programs"))).scalar_one()
            except DBAPIError as exc:
                assert "permission denied" in str(exc)
            else:
                # anon may hold a grant and still see nothing, because no business is bound.
                assert int(count) == 0
            await session.rollback()
    finally:
        await engine.dispose()
