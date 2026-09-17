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

    # Claim this event by id rather than draining the queue ahead of it.
    # claim_outbox_batch is oldest-due-first across the whole shared database,
    # so an unscoped poll has to chew through every pending row the rest of the
    # suite left behind before reaching this one — which a bounded retry loop
    # never manages, and which under `pytest -n` it can never win at all,
    # because the other workers keep adding rows faster than it drains them.
    await poll_and_dispatch_outbox(db_session, "test-worker", event_ids=[str(event_id)])

    db_session.expire_all()
    result = await db_session.execute(
        select(PlatformOutboxEvent).where(PlatformOutboxEvent.id == event_id)
    )
    event = result.scalars().first()
    assert event is not None
    # business.created has no registered subscriber, so fan-out completes it
    # outright — an event nobody listens to is delivered, not dead-lettered.
    assert event.status == "completed"
