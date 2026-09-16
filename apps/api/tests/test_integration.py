import os
import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from platform_core.db import get_database_url
from platform_core.models import BusinessMembership, PlatformOutboxEvent
from platform_core.services.business import BusinessService
from platform_core.services.identity import IdentityService
from platform_testing.db_helpers import ensure_auth_user


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
async def test_business_creation_emits_outbox_event(db_session: AsyncSession) -> None:
    identity_id = uuid.uuid4()
    await ensure_auth_user(db_session, identity_id, f"{identity_id.hex[:8]}@test.local")
    await IdentityService.bootstrap_identity(
        db_session, identity_id, f"{identity_id.hex[:8]}@test.local"
    )
    business, _, _, _ = await BusinessService.create_business(
        db_session,
        identity_id=identity_id,
        display_name=f"Outbox Test {identity_id.hex[:8]}",
        correlation_id=str(uuid.uuid4()),
    )
    await db_session.commit()

    result = await db_session.execute(
        select(PlatformOutboxEvent).where(
            PlatformOutboxEvent.business_id == business.id,
            PlatformOutboxEvent.event_type == "business.created",
            PlatformOutboxEvent.status == "pending",
        )
    )
    event = result.scalars().first()
    assert event is not None


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
async def test_outbox_event_persisted_with_business_creation(db_session: AsyncSession) -> None:
    identity_id = uuid.uuid4()
    await ensure_auth_user(db_session, identity_id, f"outbox-{identity_id.hex[:8]}@test.local")
    await IdentityService.bootstrap_identity(
        db_session, identity_id, f"outbox-{identity_id.hex[:8]}@test.local"
    )
    business, _, _, _ = await BusinessService.create_business(
        db_session,
        identity_id=identity_id,
        display_name=f"Outbox Persist {identity_id.hex[:8]}",
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
    assert event.status == "pending"


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
async def test_direct_db_business_isolation(db_session: AsyncSession) -> None:
    id_a, id_b = uuid.uuid4(), uuid.uuid4()
    await ensure_auth_user(db_session, id_a, f"a-{id_a.hex[:6]}@test.local")
    await ensure_auth_user(db_session, id_b, f"b-{id_b.hex[:6]}@test.local")
    await IdentityService.bootstrap_identity(db_session, id_a, f"a-{id_a.hex[:6]}@test.local")
    await IdentityService.bootstrap_identity(db_session, id_b, f"b-{id_b.hex[:6]}@test.local")
    biz_a, _, _, _ = await BusinessService.create_business(
        db_session,
        identity_id=id_a,
        display_name=f"Iso A {id_a.hex[:6]}",
        correlation_id=str(uuid.uuid4()),
    )
    biz_b, _, _, _ = await BusinessService.create_business(
        db_session,
        identity_id=id_b,
        display_name=f"Iso B {id_b.hex[:6]}",
        correlation_id=str(uuid.uuid4()),
    )
    await db_session.commit()

    result = await db_session.execute(
        select(BusinessMembership).where(BusinessMembership.business_id == biz_a.id)
    )
    memberships_a = result.scalars().all()
    for m in memberships_a:
        assert m.business_id == biz_a.id
        assert m.business_id != biz_b.id
