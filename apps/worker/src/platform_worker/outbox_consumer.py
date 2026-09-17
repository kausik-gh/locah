"""Outbox consumer — fan an event out to its subscribers, one delivery each.

Two passes, deliberately separate:

  1. `poll_and_dispatch_outbox` claims pending events and materialises a
     delivery row per registered subscriber. An event with no subscribers is
     complete immediately; that is the normal case for most event types.
  2. `poll_and_run_deliveries` claims due deliveries and runs their handlers.
     Each delivery retries on its own clock, so one failing subscriber neither
     blocks nor re-runs the others.

Splitting them is what makes the retry safe. When delivery state lived on the
event, retrying an event re-ran every handler for it, so a second subscriber
would have made retries double-apply the first one's work.

Adding a subscriber does not touch this file. See
`platform_core.events.subscribers`.
"""

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.events.registry import EventContext, PermanentEventError, subscribers_for
from platform_core.logging import get_logger
from platform_worker.claiming import LEASE_SECONDS, claim_outbox_batch

logger = get_logger("platform_worker.outbox")


def _payload_of(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return {}
    return payload if isinstance(payload, dict) else {}


# --------------------------------------------------------------------------
# Pass 1 — fan out
# --------------------------------------------------------------------------


async def _fan_out(session: AsyncSession, event: dict[str, Any]) -> int:
    """Create one delivery row per subscriber. Returns how many are outstanding.

    ON CONFLICT DO NOTHING against the (event_id, subscriber_id) unique key: a
    lease that expired midway through fan-out gets re-claimed and re-runs this,
    and must not produce a second delivery for a subscriber that already has one.
    """
    subscribers = subscribers_for(str(event["event_type"]))
    if not subscribers:
        return 0

    for subscriber in subscribers:
        await session.execute(
            text("""
                INSERT INTO platform_event_deliveries
                    (event_id, subscriber_id, event_type, business_id, max_attempts)
                VALUES (:event_id, :subscriber_id, :event_type, :business_id, :max_attempts)
                ON CONFLICT (event_id, subscriber_id) DO NOTHING
            """),
            {
                "event_id": str(event["id"]),
                "subscriber_id": subscriber.subscriber_id,
                "event_type": event["event_type"],
                "business_id": str(event["business_id"]) if event.get("business_id") else None,
                "max_attempts": subscriber.max_attempts,
            },
        )
    return len(subscribers)


async def poll_and_dispatch_outbox(
    session: AsyncSession, worker_id: str, event_ids: list[str] | None = None
) -> int:
    """Claim due outbox events and fan them out to their subscribers.

    Returns the number of events fanned out. `event_ids` is test isolation —
    see `claim_outbox_batch`.
    """
    events = await claim_outbox_batch(session, worker_id, event_ids=event_ids)
    if not events:
        return 0

    processed = 0
    for event in events:
        event_id = str(event["id"])
        try:
            # Savepoint for the same reason as the delivery loop below: a failed
            # INSERT must not poison the transaction that records the failure.
            async with session.begin_nested():
                outstanding = await _fan_out(session, dict(event))
            if outstanding == 0:
                # Nobody is listening. That is a complete event, not a failure:
                # events exist to be available, and most are consumed later or
                # only by analytics.
                await session.execute(
                    text("""
                        UPDATE platform_outbox_events
                        SET status = 'completed', processed_at = now(),
                            leased_until = NULL, leased_by = NULL
                        WHERE id = :id
                    """),
                    {"id": event_id},
                )
            else:
                # Stays 'processing' and leaseless until every delivery is
                # terminal; `_settle_event` closes it out.
                await session.execute(
                    text("""
                        UPDATE platform_outbox_events
                        SET leased_until = NULL, leased_by = NULL
                        WHERE id = :id
                    """),
                    {"id": event_id},
                )
            processed += 1
        except Exception as exc:
            # Fan-out itself failing is an infrastructure problem, not a handler
            # problem — the event keeps the outbox's own retry budget.
            attempt = int(event.get("attempt_count", 0)) + 1
            max_attempts = int(event.get("max_attempts", 5))
            if attempt >= max_attempts:
                logger.error(
                    "outbox.fan_out_dead_letter",
                    event_id=event_id,
                    event_type=event.get("event_type", ""),
                    attempt=attempt,
                    error=str(exc),
                )
                await _dead_letter_event(session, dict(event), str(exc))
            else:
                logger.warning(
                    "outbox.fan_out_retry",
                    event_id=event_id,
                    event_type=event.get("event_type", ""),
                    attempt=attempt,
                    error=str(exc),
                )
                await _retry_event(session, event_id, attempt, str(exc))
    await session.commit()
    return processed


# --------------------------------------------------------------------------
# Pass 2 — run the handlers
# --------------------------------------------------------------------------


async def _claim_delivery_batch(
    session: AsyncSession, worker_id: str, limit: int = 10, event_ids: list[str] | None = None
) -> list[Any]:
    """Claim due deliveries, joining the event so the handler gets its payload.

    `event_ids` is test isolation — see `claim_outbox_batch`.
    """
    id_filter = "AND event_id = ANY(CAST(:event_ids AS uuid[]))" if event_ids else ""
    result = await session.execute(
        text(f"""
            UPDATE platform_event_deliveries d
            SET status = 'processing',
                leased_until = now() + make_interval(secs => :lease_seconds),
                leased_by = :worker_id
            FROM platform_outbox_events e
            WHERE d.event_id = e.id
              AND d.id IN (
                SELECT id
                FROM platform_event_deliveries
                WHERE (
                        status IN ('pending', 'failed')
                        OR (status = 'processing' AND leased_until < now())
                    )
                  AND next_attempt_at <= now()
                  AND (leased_until IS NULL OR leased_until < now())
                  {id_filter}
                ORDER BY next_attempt_at
                FOR UPDATE SKIP LOCKED
                LIMIT :limit
            )
            RETURNING d.id, d.event_id, d.subscriber_id, d.event_type,
                      d.business_id, d.attempt_count, d.max_attempts,
                      e.payload AS payload, e.correlation_id AS correlation_id
        """),
        {
            "worker_id": worker_id,
            "limit": limit,
            "lease_seconds": LEASE_SECONDS,
            **({"event_ids": event_ids} if event_ids else {}),
        },
    )
    return list(result.mappings())


async def _complete_delivery(session: AsyncSession, delivery_id: str) -> None:
    await session.execute(
        text("""
            UPDATE platform_event_deliveries
            SET status = 'completed', processed_at = now(),
                leased_until = NULL, leased_by = NULL, last_error = NULL
            WHERE id = :id
        """),
        {"id": delivery_id},
    )


async def _retry_delivery(
    session: AsyncSession, delivery_id: str, attempt: int, error: str
) -> None:
    backoff = min(2**attempt * 30, 3600)
    await session.execute(
        text("""
            UPDATE platform_event_deliveries
            SET status = 'failed',
                attempt_count = :attempt,
                next_attempt_at = now() + make_interval(secs => :backoff),
                last_error = :error,
                leased_until = NULL, leased_by = NULL
            WHERE id = :id
        """),
        {"id": delivery_id, "attempt": attempt, "backoff": backoff, "error": error},
    )


async def _dead_letter_delivery(
    session: AsyncSession, delivery: dict[str, Any], error: str
) -> None:
    await session.execute(
        text("""
            UPDATE platform_event_deliveries
            SET status = 'dead_letter', last_error = :error, processed_at = now(),
                leased_until = NULL, leased_by = NULL
            WHERE id = :id
        """),
        {"id": str(delivery["id"]), "error": error},
    )
    payload = delivery.get("payload") or {}
    if isinstance(payload, dict):
        payload = json.dumps(payload)
    await session.execute(
        text("""
            INSERT INTO platform_dead_letter_events
                (source_table, source_id, event_type, payload, final_error, attempt_count)
            VALUES ('platform_event_deliveries', :id, :event_type,
                    CAST(:payload AS jsonb), :error, :attempt_count)
        """),
        {
            "id": str(delivery["id"]),
            # Which subscriber gave up is the first question anyone asks, so it
            # belongs in the dead-letter row, not only in the log line.
            "event_type": f"{delivery['event_type']}@{delivery['subscriber_id']}",
            "payload": payload,
            "error": error,
            "attempt_count": int(delivery.get("attempt_count", 0)) + 1,
        },
    )


async def _settle_event(session: AsyncSession, event_id: str) -> None:
    """Complete the parent event once no delivery of it is still outstanding.

    'dead_letter' counts as settled: the delivery has given up and is recorded,
    and holding its event open forever would only hide the ones still working.
    """
    await session.execute(
        text("""
            UPDATE platform_outbox_events
            SET status = 'completed', processed_at = now(),
                leased_until = NULL, leased_by = NULL
            WHERE id = :id
              AND status <> 'completed'
              AND NOT EXISTS (
                  SELECT 1 FROM platform_event_deliveries
                  WHERE event_id = :id
                    AND status NOT IN ('completed', 'dead_letter')
              )
        """),
        {"id": event_id},
    )


async def poll_and_run_deliveries(
    session: AsyncSession, worker_id: str, event_ids: list[str] | None = None
) -> int:
    """Claim due deliveries and run each subscriber's handler.

    Returns the number of deliveries that reached a terminal state. `event_ids`
    is test isolation — see `claim_outbox_batch`.
    """
    deliveries = await _claim_delivery_batch(session, worker_id, event_ids=event_ids)
    if not deliveries:
        return 0

    settled = 0
    for row in deliveries:
        delivery = dict(row)
        delivery_id = str(delivery["id"])
        subscriber_id = str(delivery["subscriber_id"])
        attempt = int(delivery.get("attempt_count", 0)) + 1

        from platform_core.events.registry import get_subscriber

        subscriber = get_subscriber(subscriber_id)
        if subscriber is None:
            # A subscriber that was removed or renamed while its deliveries
            # were in flight. Retrying can never find it.
            logger.error(
                "outbox.subscriber_missing",
                delivery_id=delivery_id,
                subscriber_id=subscriber_id,
                event_type=delivery.get("event_type", ""),
            )
            await _dead_letter_delivery(
                session, delivery, f"No registered subscriber {subscriber_id!r}"
            )
            await _settle_event(session, str(delivery["event_id"]))
            settled += 1
            continue

        context = EventContext(
            event_id=delivery["event_id"],
            event_type=str(delivery["event_type"]),
            payload=_payload_of(delivery),
            business_id=delivery.get("business_id"),
            correlation_id=(
                str(delivery["correlation_id"]) if delivery.get("correlation_id") else None
            ),
            attempt=attempt,
        )

        try:
            # SAVEPOINT per handler. A handler that fails on a SQL error leaves
            # the Postgres transaction aborted, and every later statement in it
            # — including the UPDATE that records the failure — errors with
            # "current transaction is aborted". Rolling back to a savepoint
            # discards only that handler's writes and leaves the session usable,
            # so the delivery's own retry bookkeeping can still be written and
            # the sibling deliveries in this batch still run.
            async with session.begin_nested():
                await subscriber.handler(session, context)
            await _complete_delivery(session, delivery_id)
            settled += 1
        except PermanentEventError as exc:
            logger.error(
                "outbox.delivery_permanent_failure",
                delivery_id=delivery_id,
                subscriber_id=subscriber_id,
                event_type=context.event_type,
                error=str(exc),
            )
            await _dead_letter_delivery(session, delivery, str(exc))
            settled += 1
        except Exception as exc:
            max_attempts = int(delivery.get("max_attempts", 5))
            if attempt >= max_attempts:
                logger.error(
                    "outbox.delivery_dead_letter",
                    delivery_id=delivery_id,
                    subscriber_id=subscriber_id,
                    event_type=context.event_type,
                    business_id=str(delivery.get("business_id") or ""),
                    attempt=attempt,
                    error=str(exc),
                )
                await _dead_letter_delivery(session, delivery, str(exc))
                settled += 1
            else:
                logger.warning(
                    "outbox.delivery_retry_scheduled",
                    delivery_id=delivery_id,
                    subscriber_id=subscriber_id,
                    event_type=context.event_type,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    error=str(exc),
                )
                await _retry_delivery(session, delivery_id, attempt, str(exc))

        await _settle_event(session, str(delivery["event_id"]))

    await session.commit()
    return settled


async def _retry_event(
    session: AsyncSession, event_id: str, attempt_count: int, error: str
) -> None:
    backoff = min(2**attempt_count * 30, 3600)
    await session.execute(
        text("""
            UPDATE platform_outbox_events
            SET status = 'failed',
                attempt_count = :attempt_count,
                next_attempt_at = now() + make_interval(secs => :backoff),
                last_error = :error,
                leased_until = NULL,
                leased_by = NULL
            WHERE id = :id
        """),
        {"id": event_id, "attempt_count": attempt_count, "backoff": backoff, "error": error},
    )


async def _dead_letter_event(session: AsyncSession, event: dict[str, Any], error: str) -> None:
    await session.execute(
        text("""
            UPDATE platform_outbox_events
            SET status = 'dead_letter', last_error = :error, leased_until = NULL, leased_by = NULL
            WHERE id = :id
        """),
        {"id": str(event["id"]), "error": error},
    )
    payload = event.get("payload") or {}
    if isinstance(payload, dict):
        payload = json.dumps(payload)
    await session.execute(
        text("""
            INSERT INTO platform_dead_letter_events
                (source_table, source_id, event_type, payload, final_error, attempt_count)
            VALUES ('platform_outbox_events', :id, :event_type,
                    CAST(:payload AS jsonb), :error, :attempt_count)
        """),
        {
            "id": str(event["id"]),
            "event_type": event["event_type"],
            "payload": payload,
            "error": error,
            "attempt_count": event.get("attempt_count", 0),
        },
    )
