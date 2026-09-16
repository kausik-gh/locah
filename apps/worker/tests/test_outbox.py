import os
import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from platform_core.db import get_database_url
from platform_core.models import PlatformOutboxEvent
from platform_core.services.business import BusinessService
from platform_core.services.identity import IdentityService
from platform_testing.db_helpers import ensure_auth_user
from platform_worker.outbox_consumer import poll_and_dispatch_outbox


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    url = get_database_url()
    if not url:
        pytest.skip("DATABASE_URL not configured")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
async def test_outbox_worker_processes_event(db_session: AsyncSession) -> None:
    # Same shared-database backlog concern as apps/worker/tests/test_jobs.py's
    # _drain_backlog: claim_outbox_batch claims the oldest-due LIMIT 10 rows
    # system-wide, and this suite runs apps/api's tests (which write outbox
    # events on every business/membership/order/etc. action but never
    # dispatch them — only a worker test's own poll does) before this file.
    # By the time this test runs, hundreds of older pending rows can already
    # be queued ahead of the one event this test creates, so a bounded
    # single-digit retry loop never reaches it. Drain first.
    for _ in range(200):
        if await poll_and_dispatch_outbox(db_session, "test-outbox-drain") == 0:
            break

    identity_id = uuid.uuid4()
    await ensure_auth_user(db_session, identity_id, f"worker-{identity_id.hex[:8]}@test.local")
    await IdentityService.bootstrap_identity(
        db_session, identity_id, f"worker-{identity_id.hex[:8]}@test.local"
    )
    business, _, _, _ = await BusinessService.create_business(
        db_session,
        identity_id=identity_id,
        display_name=f"Worker Test {identity_id.hex[:8]}",
        correlation_id=str(uuid.uuid4()),
    )
    await db_session.commit()

    result = await db_session.execute(
        select(PlatformOutboxEvent).where(
            PlatformOutboxEvent.business_id == business.id,
            PlatformOutboxEvent.event_type == "business.created",
        )
    )
    event = result.scalars().first()
    assert event is not None
    event_id = event.id

    for _ in range(10):
        await poll_and_dispatch_outbox(db_session, "test-worker")
        db_session.expire_all()
        result = await db_session.execute(
            select(PlatformOutboxEvent).where(PlatformOutboxEvent.id == event_id)
        )
        event = result.scalars().first()
        assert event is not None
        if event.status == "completed":
            break

    assert event.status == "completed"
