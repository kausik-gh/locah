"""Fan-out and per-subscriber delivery semantics.

The property under test is the one the old event-level retry could not hold:
a failing subscriber must not cause a succeeding subscriber's handler to run
twice. Everything else here supports that.
"""

import json
import os
import uuid
from collections.abc import AsyncGenerator, Generator
from types import ModuleType
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from platform_core.db import get_database_url
from platform_core.events import registry
from platform_core.events.catalogue import UnknownEventType, assert_known_event_type
from platform_core.events.registry import EventContext, EventSubscriber, PermanentEventError
from platform_worker.outbox_consumer import poll_and_dispatch_outbox, poll_and_run_deliveries

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")


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


@pytest.fixture
def isolated_registry() -> Generator[ModuleType, None, None]:
    """Swap in a registry containing only this test's subscribers.

    The real subscribers reach into Marketplace and Fulfilment; these tests are
    about the delivery machinery, not about them.
    """
    saved_subs = dict(registry._SUBSCRIBERS)
    saved_by_type = {k: list(v) for k, v in registry._BY_EVENT_TYPE.items()}
    saved_import = registry._import_done

    registry._SUBSCRIBERS.clear()
    registry._BY_EVENT_TYPE.clear()
    registry._import_done = True  # suppress the real subscriber import

    yield registry

    registry._SUBSCRIBERS.clear()
    registry._SUBSCRIBERS.update(saved_subs)
    registry._BY_EVENT_TYPE.clear()
    registry._BY_EVENT_TYPE.update(saved_by_type)
    registry._import_done = saved_import


async def _publish_raw(
    session: AsyncSession, event_type: str, payload: dict[str, Any] | None = None
) -> uuid.UUID:
    """Insert an outbox event directly.

    Bypasses OutboxService so these tests need no business, identity or
    notification fan-out — only an event for the consumer to pick up.
    """
    result = await session.execute(
        text("""
            INSERT INTO platform_outbox_events (event_type, payload, status)
            VALUES (:event_type, CAST(:payload AS jsonb), 'pending')
            RETURNING id
        """),
        {"event_type": event_type, "payload": json.dumps(payload or {})},
    )
    event_id: uuid.UUID = result.scalar_one()
    await session.commit()
    return event_id


async def _run(session: AsyncSession, worker: str, event_id: uuid.UUID, rounds: int = 6) -> None:
    """Drive both worker passes over this test's event only.

    Scoping by id matters on the shared hosted database: an unscoped poll
    claims oldest-first across the whole table, so it would process other
    suites' pending events under this test's stubbed subscriber registry and
    quietly complete them without running their real subscribers.
    """
    ids = [str(event_id)]
    for _ in range(rounds):
        await poll_and_dispatch_outbox(session, worker, event_ids=ids)
        await poll_and_run_deliveries(session, worker, event_ids=ids)


async def _event_status(session: AsyncSession, event_id: uuid.UUID) -> str:
    result = await session.execute(
        text("SELECT status FROM platform_outbox_events WHERE id = :id"), {"id": str(event_id)}
    )
    return str(result.scalar_one())


async def _deliveries(session: AsyncSession, event_id: uuid.UUID) -> dict[str, dict[str, Any]]:
    result = await session.execute(
        text("""
            SELECT subscriber_id, status, attempt_count, last_error
            FROM platform_event_deliveries WHERE event_id = :id
        """),
        {"id": str(event_id)},
    )
    return {row["subscriber_id"]: dict(row) for row in result.mappings()}


# --------------------------------------------------------------------------


def test_catalogue_rejects_unknown_event_type() -> None:
    assert_known_event_type("order.created")  # does not raise
    with pytest.raises(UnknownEventType):
        assert_known_event_type("order.craeted")


def test_duplicate_subscriber_id_is_refused(isolated_registry: ModuleType) -> None:
    async def handler(session: AsyncSession, event: EventContext) -> None:
        """Never invoked — these tests only exercise registration."""
        return None

    isolated_registry.register(EventSubscriber("dupe.test", frozenset({"order.created"}), handler))
    with pytest.raises(ValueError, match="Duplicate event subscriber id"):
        isolated_registry.register(
            EventSubscriber("dupe.test", frozenset({"order.updated"}), handler)
        )


def test_subscribing_to_an_uncatalogued_event_is_refused(isolated_registry: ModuleType) -> None:
    async def handler(session: AsyncSession, event: EventContext) -> None:
        """Never invoked — these tests only exercise registration."""
        return None

    with pytest.raises(UnknownEventType):
        isolated_registry.register(
            EventSubscriber("typo.test", frozenset({"order.craeted"}), handler)
        )


@pytest.mark.asyncio
async def test_event_with_no_subscribers_completes(
    db_session: AsyncSession, isolated_registry: ModuleType
) -> None:
    """Nobody listening is a completed event, not a dead letter.

    This is what lets a capability publish its own events before anything
    consumes them — the old allowlist dead-lettered them instead.
    """
    event_id = await _publish_raw(db_session, "booking.created")

    await _run(db_session, "test-nosub", event_id)

    assert await _event_status(db_session, event_id) == "completed"
    assert await _deliveries(db_session, event_id) == {}


@pytest.mark.asyncio
async def test_failing_subscriber_does_not_rerun_a_succeeding_one(
    db_session: AsyncSession, isolated_registry: ModuleType
) -> None:
    """The regression the old design could not prevent.

    Under event-level retry, `flaky` failing would re-deliver the event and run
    `steady` a second time. Here `steady` runs exactly once no matter how often
    `flaky` is retried.
    """
    steady_calls: list[uuid.UUID] = []
    flaky_calls: list[uuid.UUID] = []

    async def steady(session: AsyncSession, event: EventContext) -> None:
        steady_calls.append(event.event_id)

    async def flaky(session: AsyncSession, event: EventContext) -> None:
        flaky_calls.append(event.event_id)
        raise RuntimeError("provider unavailable")

    isolated_registry.register(
        EventSubscriber("test.steady", frozenset({"booking.confirmed"}), steady)
    )
    isolated_registry.register(
        EventSubscriber("test.flaky", frozenset({"booking.confirmed"}), flaky, max_attempts=3)
    )

    event_id = await _publish_raw(
        db_session, "booking.confirmed", {"booking_id": str(uuid.uuid4())}
    )

    await _run(db_session, "test-indep", event_id)

    rows = await _deliveries(db_session, event_id)
    assert set(rows) == {"test.steady", "test.flaky"}
    assert rows["test.steady"]["status"] == "completed"
    assert rows["test.flaky"]["status"] == "failed"
    assert "provider unavailable" in (rows["test.flaky"]["last_error"] or "")

    # The whole point: one call, despite the sibling failing and rescheduling.
    assert len(steady_calls) == 1
    assert len(flaky_calls) == 1

    # And the event stays open while a delivery is still due to retry.
    assert await _event_status(db_session, event_id) != "completed"


@pytest.mark.asyncio
async def test_permanent_error_dead_letters_immediately(
    db_session: AsyncSession, isolated_registry: ModuleType
) -> None:
    calls: list[uuid.UUID] = []

    async def unusable(session: AsyncSession, event: EventContext) -> None:
        calls.append(event.event_id)
        raise PermanentEventError("payload can never be accepted")

    isolated_registry.register(
        EventSubscriber("test.permanent", frozenset({"lead.won"}), unusable, max_attempts=5)
    )

    event_id = await _publish_raw(db_session, "lead.won")

    await _run(db_session, "test-perm", event_id)

    rows = await _deliveries(db_session, event_id)
    assert rows["test.permanent"]["status"] == "dead_letter"
    # max_attempts is 5, but a permanent error must not burn four more tries.
    assert len(calls) == 1

    # A dead-lettered delivery still settles its event — nothing is left open.
    assert await _event_status(db_session, event_id) == "completed"

    delivery_id = await db_session.scalar(
        text("SELECT id FROM platform_event_deliveries WHERE event_id = :id"),
        {"id": str(event_id)},
    )
    recorded = await db_session.scalar(
        text("""
            SELECT event_type FROM platform_dead_letter_events
            WHERE source_table = 'platform_event_deliveries' AND source_id = :id
        """),
        {"id": str(delivery_id)},
    )
    # The subscriber that gave up is named in the dead-letter row, not only in
    # the log line — it is the first thing anyone triaging asks.
    assert recorded == "lead.won@test.permanent"


@pytest.mark.asyncio
async def test_sql_failure_in_a_handler_does_not_poison_the_transaction(
    db_session: AsyncSession, isolated_registry: ModuleType
) -> None:
    """A handler failing on SQL must still get its failure recorded.

    Without a savepoint around each handler, the aborted Postgres transaction
    makes every subsequent statement fail — including the UPDATE that marks the
    delivery failed and the one that completes its sibling. The delivery would
    be left leased and the batch would make no progress at all.
    """

    async def bad_sql(session: AsyncSession, event: EventContext) -> None:
        await session.execute(text("SELECT * FROM a_table_that_does_not_exist"))

    async def neighbour(session: AsyncSession, event: EventContext) -> None:
        await session.execute(text("SELECT 1"))

    isolated_registry.register(
        EventSubscriber("test.bad_sql", frozenset({"lead.lost"}), bad_sql, max_attempts=2)
    )
    isolated_registry.register(
        EventSubscriber("test.neighbour", frozenset({"lead.lost"}), neighbour)
    )

    event_id = await _publish_raw(db_session, "lead.lost")

    await _run(db_session, "test-sql", event_id)

    rows = await _deliveries(db_session, event_id)
    assert rows["test.neighbour"]["status"] == "completed"
    assert rows["test.bad_sql"]["status"] in ("failed", "dead_letter")
    assert "does not exist" in (rows["test.bad_sql"]["last_error"] or "").lower()


@pytest.mark.asyncio
async def test_fan_out_is_idempotent(
    db_session: AsyncSession, isolated_registry: ModuleType
) -> None:
    """Re-claiming an event after a lease expires must not double-deliver."""
    calls: list[uuid.UUID] = []

    async def once(session: AsyncSession, event: EventContext) -> None:
        calls.append(event.event_id)

    isolated_registry.register(EventSubscriber("test.once", frozenset({"lead.qualified"}), once))

    event_id = await _publish_raw(db_session, "lead.qualified")

    ids = [str(event_id)]

    # Fan out, then put the event back to 'pending' and fan out again — what an
    # expired lease re-claimed mid-fan-out looks like.
    await poll_and_dispatch_outbox(db_session, "test-idem", event_ids=ids)
    assert await _deliveries(db_session, event_id), "fan-out created no delivery"

    await db_session.execute(
        text("""
            UPDATE platform_outbox_events
            SET status = 'pending', leased_until = NULL, leased_by = NULL
            WHERE id = :id
        """),
        {"id": str(event_id)},
    )
    await db_session.commit()
    await poll_and_dispatch_outbox(db_session, "test-idem", event_ids=ids)

    rows = await _deliveries(db_session, event_id)
    assert list(rows) == ["test.once"], "fan-out created a duplicate delivery"

    await poll_and_run_deliveries(db_session, "test-idem", event_ids=ids)
    assert (await _deliveries(db_session, event_id))["test.once"]["status"] == "completed"
    assert len(calls) == 1
