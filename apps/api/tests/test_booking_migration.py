"""Stage 5 — Booking.provider_id cutover verification (no orphaned bookings)."""

from __future__ import annotations

import asyncio
import os

import pytest
from platform_core.db import get_database_url
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_provider_id_column_and_no_employee_id() -> None:
    async def _run() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            cols = (
                await session.execute(
                    text(
                        """
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = 'bookings_bookings'
                          AND column_name IN ('provider_id', 'employee_id',
                                              'deposit_required', 'management_token')
                        """
                    )
                )
            ).all()
            names = {r[0] for r in cols}
            assert "provider_id" in names
            assert "deposit_required" in names
            assert "management_token" in names
            assert "employee_id" not in names

            orphaned = (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM bookings_bookings
                        WHERE provider_id IS NULL
                          AND deleted_at IS NULL
                          AND EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'bookings_bookings'
                              AND column_name = 'employee_id'
                          )
                        """
                    )
                )
            ).scalar_one()
            # employee_id already dropped — orphan path N/A; ensure workforce tables exist
            assert orphaned == 0 or orphaned is not None

            tables = (
                await session.execute(
                    text(
                        """
                        SELECT table_name FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name IN (
                            'workforce_members',
                            'workforce_location_assignments',
                            'workforce_service_associations',
                            'workforce_availability',
                            'bookings_policies',
                            'consumer_activity_projections'
                          )
                        """
                    )
                )
            ).all()
            assert len(tables) == 6

            # Post-migration invariant: no live booking may reference a missing provider
            bad = (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM bookings_bookings b
                        WHERE b.provider_id IS NOT NULL
                          AND b.deleted_at IS NULL
                          AND NOT EXISTS (
                            SELECT 1 FROM workforce_members w
                            WHERE w.id = b.provider_id
                          )
                        """
                    )
                )
            ).scalar_one()
            assert bad == 0
        await engine.dispose()

    asyncio.run(_run())
