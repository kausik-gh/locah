"""Bookable resource allocation — the invariants, at the database level.

These deliberately exercise the constraint rather than the service's happy
path. A booking engine that only rejects double-bookings when the application
remembers to look is not one you can run a hotel on.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from platform_core.db import get_database_url
from platform_core.exceptions import ConflictError, ValidationError
from platform_core.models import BookingAllocation, BookingResource
from platform_core.services.booking_allocation import (
    AllocationRequest,
    BookingAllocationService,
)
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")

BASE = datetime(2027, 3, 1, 9, 0, tzinfo=timezone.utc)


def _url() -> str:
    url = get_database_url()
    assert url
    return str(url).replace("postgresql://", "postgresql+asyncpg://", 1)


def _factory() -> Any:
    engine = create_async_engine(_url(), echo=False, poolclass=NullPool)
    return engine, async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _tenant(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """Borrow an existing business/location purely to satisfy foreign keys.

    Every row these tests create is rolled back or deleted; nothing here is
    meant to survive, and no existing business data is modified.
    """
    row = (
        await session.execute(
            text(
                """
                SELECT b.id, l.id FROM businesses b
                JOIN business_locations l ON l.business_id = b.id
                WHERE b.deleted_at IS NULL LIMIT 1
                """
            )
        )
    ).first()
    assert row is not None, "no business/location available to anchor the test"
    return row[0], row[1]


async def _make_resource(
    session: AsyncSession,
    business_id: uuid.UUID,
    location_id: uuid.UUID,
    **kwargs: Any,
) -> BookingResource:
    resource = BookingResource(
        business_id=business_id,
        location_id=location_id,
        resource_type=kwargs.pop("resource_type", "room"),
        name=kwargs.pop("name", f"R-{uuid.uuid4().hex[:8]}"),
        **kwargs,
    )
    session.add(resource)
    await session.flush()
    return resource


@pytest.fixture
async def tenant_session():
    """A session whose writes are rolled back, so the suite leaves no residue."""
    engine, factory = _factory()
    async with factory() as session:
        business_id, location_id = await _tenant(session)
        yield session, business_id, location_id
        await session.rollback()
    await engine.dispose()


# ---------------------------------------------------------------- exclusive


@pytest.mark.asyncio
async def test_exclusive_resource_rejects_overlap(tenant_session: Any) -> None:
    session, business_id, location_id = tenant_session
    room = await _make_resource(session, business_id, location_id, allocation_mode="exclusive")

    await BookingAllocationService.allocate(
        session,
        business_id=business_id,
        booking_id=None,
        kind="blackout",
        requests=[AllocationRequest(resource_id=room.id)],
        starts_at=BASE,
        ends_at=BASE + timedelta(hours=2),
    )

    with pytest.raises(ConflictError):
        await BookingAllocationService.allocate(
            session,
            business_id=business_id,
            booking_id=None,
            kind="blackout",
            requests=[AllocationRequest(resource_id=room.id)],
            starts_at=BASE + timedelta(hours=1),
            ends_at=BASE + timedelta(hours=3),
        )


@pytest.mark.asyncio
async def test_adjacent_bookings_do_not_overlap(tenant_session: Any) -> None:
    """Half-open ranges are what let checkout and checkin share a day.

    If the range were closed, an 11:00 checkout would block an 11:00 checkin and
    every hotel would lose a night's occupancy on every changeover.
    """
    session, business_id, location_id = tenant_session
    room = await _make_resource(
        session, business_id, location_id, allocation_mode="exclusive", granularity="date_range"
    )

    for offset in (0, 2, 4):
        await BookingAllocationService.allocate(
            session,
            business_id=business_id,
            booking_id=None,
            kind="blackout",
            requests=[AllocationRequest(resource_id=room.id)],
            starts_at=BASE + timedelta(days=offset),
            ends_at=BASE + timedelta(days=offset + 2),
        )

    held = (
        (
            await session.execute(
                select(BookingAllocation).where(BookingAllocation.resource_id == room.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(held) == 3


@pytest.mark.asyncio
async def test_buffers_extend_the_occupied_window(tenant_session: Any) -> None:
    """Turnaround is enforced by the same constraint, not by a separate check."""
    session, business_id, location_id = tenant_session
    chair = await _make_resource(
        session,
        business_id,
        location_id,
        resource_type="chair",
        allocation_mode="exclusive",
        buffer_after_minutes=15,
    )

    await BookingAllocationService.allocate(
        session,
        business_id=business_id,
        booking_id=None,
        kind="blackout",
        requests=[AllocationRequest(resource_id=chair.id)],
        starts_at=BASE,
        ends_at=BASE + timedelta(minutes=30),
    )

    # Starts when the previous booking ended, but inside its cleanup window.
    with pytest.raises(ConflictError):
        await BookingAllocationService.allocate(
            session,
            business_id=business_id,
            booking_id=None,
            kind="blackout",
            requests=[AllocationRequest(resource_id=chair.id)],
            starts_at=BASE + timedelta(minutes=30),
            ends_at=BASE + timedelta(minutes=60),
        )

    # Clear of it.
    await BookingAllocationService.allocate(
        session,
        business_id=business_id,
        booking_id=None,
        kind="blackout",
        requests=[AllocationRequest(resource_id=chair.id)],
        starts_at=BASE + timedelta(minutes=45),
        ends_at=BASE + timedelta(minutes=75),
    )


@pytest.mark.asyncio
async def test_blackout_blocks_booking_without_extra_code(tenant_session: Any) -> None:
    """A blackout is an allocation, so the constraint already covers it."""
    session, business_id, location_id = tenant_session
    car = await _make_resource(
        session, business_id, location_id, resource_type="vehicle", allocation_mode="exclusive"
    )

    await BookingAllocationService.allocate(
        session,
        business_id=business_id,
        booking_id=None,
        kind="blackout",
        requests=[AllocationRequest(resource_id=car.id)],
        starts_at=BASE,
        ends_at=BASE + timedelta(days=1),
    )

    with pytest.raises(ConflictError):
        await BookingAllocationService.allocate(
            session,
            business_id=business_id,
            booking_id=None,
            kind="blackout",
            requests=[AllocationRequest(resource_id=car.id)],
            starts_at=BASE + timedelta(hours=4),
            ends_at=BASE + timedelta(hours=6),
        )


# ------------------------------------------------------------------- pooled


@pytest.mark.asyncio
async def test_pooled_resource_allows_concurrent_claims_until_full(tenant_session: Any) -> None:
    session, business_id, location_id = tenant_session
    klass = await _make_resource(
        session,
        business_id,
        location_id,
        resource_type="class_pool",
        allocation_mode="pooled",
        capacity=10,
    )

    for _ in range(2):
        await BookingAllocationService.allocate(
            session,
            business_id=business_id,
            booking_id=None,
            kind="blackout",
            requests=[AllocationRequest(resource_id=klass.id, quantity=4)],
            starts_at=BASE,
            ends_at=BASE + timedelta(hours=1),
        )

    used = await BookingAllocationService.pooled_usage(
        session, resource_id=klass.id, starts_at=BASE, ends_at=BASE + timedelta(hours=1)
    )
    assert used == 8

    with pytest.raises(ConflictError):
        await BookingAllocationService.allocate(
            session,
            business_id=business_id,
            booking_id=None,
            kind="blackout",
            requests=[AllocationRequest(resource_id=klass.id, quantity=3)],
            starts_at=BASE,
            ends_at=BASE + timedelta(hours=1),
        )


@pytest.mark.asyncio
async def test_party_size_is_a_fit_constraint_not_a_pool(tenant_session: Any) -> None:
    """A four-top is exclusive; its seat count limits who may take it."""
    session, business_id, location_id = tenant_session
    table = await _make_resource(
        session,
        business_id,
        location_id,
        resource_type="table",
        allocation_mode="exclusive",
        max_party_size=4,
    )

    with pytest.raises(ValidationError):
        await BookingAllocationService.allocate(
            session,
            business_id=business_id,
            booking_id=None,
            kind="blackout",
            requests=[AllocationRequest(resource_id=table.id)],
            starts_at=BASE,
            ends_at=BASE + timedelta(hours=1),
            party_size=6,
        )

    # A party of two still takes the whole table, not two of four seats.
    await BookingAllocationService.allocate(
        session,
        business_id=business_id,
        booking_id=None,
        kind="blackout",
        requests=[AllocationRequest(resource_id=table.id)],
        starts_at=BASE,
        ends_at=BASE + timedelta(hours=1),
        party_size=2,
    )
    with pytest.raises(ConflictError):
        await BookingAllocationService.allocate(
            session,
            business_id=business_id,
            booking_id=None,
            kind="blackout",
            requests=[AllocationRequest(resource_id=table.id)],
            starts_at=BASE,
            ends_at=BASE + timedelta(hours=1),
            party_size=2,
        )


# -------------------------------------------------------------- concurrency


@pytest.mark.asyncio
async def test_two_concurrent_transactions_cannot_both_take_one_resource() -> None:
    """The invariant under genuine concurrency, not sequential calls.

    Both transactions read availability before either commits — the case an
    application-level check cannot win. Exactly one must survive, and the loser
    must fail on the constraint rather than on a lock timeout or a deadlock.
    """
    engine, factory = _factory()
    created: list[uuid.UUID] = []
    try:
        async with factory() as setup:
            business_id, location_id = await _tenant(setup)
            room = await _make_resource(
                setup, business_id, location_id, allocation_mode="exclusive"
            )
            created.append(room.id)
            await setup.commit()

        start = BASE + timedelta(days=30)
        end = start + timedelta(hours=2)
        barrier = asyncio.Barrier(2)

        async def contender() -> str:
            async with factory() as session:
                try:
                    # Both sessions reach this point before either inserts.
                    await barrier.wait()
                    await BookingAllocationService.allocate(
                        session,
                        business_id=business_id,
                        booking_id=None,
                        kind="blackout",
                        requests=[AllocationRequest(resource_id=room.id)],
                        starts_at=start,
                        ends_at=end,
                    )
                    await session.commit()
                    return "won"
                except ConflictError:
                    await session.rollback()
                    return "conflict"
                except Exception as exc:  # noqa: BLE001 - reported, not swallowed
                    await session.rollback()
                    return f"other:{type(exc).__name__}"

        outcomes = await asyncio.gather(contender(), contender())
        assert sorted(outcomes) == ["conflict", "won"], outcomes

        async with factory() as check:
            held = (
                (
                    await check.execute(
                        select(BookingAllocation).where(
                            BookingAllocation.resource_id == room.id,
                            BookingAllocation.released_at.is_(None),
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(held) == 1, "two transactions both claimed one exclusive resource"
    finally:
        async with factory() as cleanup:
            for resource_id in created:
                await cleanup.execute(
                    text("DELETE FROM bookings_booking_allocations WHERE resource_id = :r"),
                    {"r": str(resource_id)},
                )
                await cleanup.execute(
                    text("DELETE FROM bookings_resources WHERE id = :r"), {"r": str(resource_id)}
                )
            await cleanup.commit()
        await engine.dispose()


# ------------------------------------------------------------------ release


@pytest.mark.asyncio
async def test_release_frees_the_slot_and_keeps_the_record(tenant_session: Any) -> None:
    session, business_id, location_id = tenant_session
    room = await _make_resource(session, business_id, location_id, allocation_mode="exclusive")
    booking_id = None

    allocations = await BookingAllocationService.allocate(
        session,
        business_id=business_id,
        booking_id=booking_id,
        kind="blackout",
        requests=[AllocationRequest(resource_id=room.id)],
        starts_at=BASE,
        ends_at=BASE + timedelta(hours=1),
    )
    allocations[0].released_at = datetime.now(timezone.utc)
    await session.flush()

    # Freed for rebooking...
    await BookingAllocationService.allocate(
        session,
        business_id=business_id,
        booking_id=booking_id,
        kind="blackout",
        requests=[AllocationRequest(resource_id=room.id)],
        starts_at=BASE,
        ends_at=BASE + timedelta(hours=1),
    )

    # ...without erasing who held it.
    rows = (
        (
            await session.execute(
                select(BookingAllocation).where(BookingAllocation.resource_id == room.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert sum(1 for r in rows if r.released_at is not None) == 1


# ------------------------------------------------------------------ tenancy


@pytest.mark.asyncio
async def test_resource_lookup_is_tenant_scoped(tenant_session: Any) -> None:
    """A resource id from another business must not resolve."""
    session, business_id, location_id = tenant_session
    room = await _make_resource(session, business_id, location_id, allocation_mode="exclusive")

    other_business = uuid.uuid4()
    with pytest.raises(Exception) as excinfo:
        await BookingAllocationService.load_resource(
            session, business_id=other_business, resource_id=room.id
        )
    assert "not found" in str(excinfo.value).lower() or "Bookable resource" in str(excinfo.value)


@pytest.mark.asyncio
async def test_allocation_requires_exactly_one_subject(tenant_session: Any) -> None:
    session, business_id, _ = tenant_session
    with pytest.raises(ValidationError):
        await BookingAllocationService.allocate(
            session,
            business_id=business_id,
            booking_id=None,
            kind="blackout",
            requests=[AllocationRequest()],
            starts_at=BASE,
            ends_at=BASE + timedelta(hours=1),
        )


@pytest.mark.asyncio
async def test_end_must_follow_start(tenant_session: Any) -> None:
    session, business_id, location_id = tenant_session
    room = await _make_resource(session, business_id, location_id, allocation_mode="exclusive")
    with pytest.raises(ValidationError):
        await BookingAllocationService.allocate(
            session,
            business_id=business_id,
            booking_id=None,
            kind="blackout",
            requests=[AllocationRequest(resource_id=room.id)],
            starts_at=BASE,
            ends_at=BASE,
        )
