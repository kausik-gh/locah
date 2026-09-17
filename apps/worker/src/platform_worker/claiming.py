"""Shared SKIP LOCKED claiming and lease utilities for all worker lanes."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

LEASE_SECONDS = 120


async def claim_outbox_batch(
    session: AsyncSession, worker_id: str, limit: int = 10, event_ids: list[str] | None = None
) -> list[Any]:
    """Claim pending/failed/expired-lease outbox events.

    `event_ids` is optional isolation for tests, the same role `job_type` plays
    in `claim_job_batch`. Production callers omit it so a worker drains the
    whole lane. A test that omits it claims oldest-first across the entire
    shared database, which means it processes other suites' leftover events
    under whatever subscriber registry that test happens to have installed —
    quietly completing real events without running their real subscribers.
    """
    id_filter = "AND id = ANY(CAST(:event_ids AS uuid[]))" if event_ids else ""
    result = await session.execute(
        text(f"""
            UPDATE platform_outbox_events
            SET status = 'processing',
                leased_until = now() + make_interval(secs => :lease_seconds),
                leased_by = :worker_id
            WHERE id IN (
                SELECT id
                FROM platform_outbox_events
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
            RETURNING *
        """),
        {
            "worker_id": worker_id,
            "limit": limit,
            "lease_seconds": LEASE_SECONDS,
            **({"event_ids": event_ids} if event_ids else {}),
        },
    )
    return list(result.mappings())


async def claim_job_batch(
    session: AsyncSession, worker_id: str, limit: int = 10, job_type: str | None = None
) -> list[Any]:
    """Claim pending/failed/expired-lease async jobs.

    `job_type` is optional isolation for tests. Production callers omit it so
    a worker processes the whole lane.
    """
    type_filter = "AND job_type = :job_type" if job_type else ""
    result = await session.execute(
        text(f"""
            UPDATE platform_async_jobs
            SET status = 'processing',
                leased_until = now() + make_interval(secs => :lease_seconds),
                leased_by = :worker_id
            WHERE id IN (
                SELECT id
                FROM platform_async_jobs
                WHERE (
                        status IN ('pending', 'failed')
                        OR (status = 'processing' AND leased_until < now())
                    )
                  AND next_attempt_at <= now()
                  AND (leased_until IS NULL OR leased_until < now())
                  {type_filter}
                ORDER BY next_attempt_at
                FOR UPDATE SKIP LOCKED
                LIMIT :limit
            )
            RETURNING *
        """),
        {
            "worker_id": worker_id,
            "limit": limit,
            "lease_seconds": LEASE_SECONDS,
            **({"job_type": job_type} if job_type else {}),
        },
    )
    return list(result.mappings())


async def claim_due_schedules(session: AsyncSession, limit: int = 10) -> list[Any]:
    """Lock due pending scheduled jobs for materialization (same transaction)."""
    result = await session.execute(
        text("""
            SELECT *
            FROM platform_scheduled_jobs
            WHERE status = 'pending'
              AND run_at <= now()
            ORDER BY run_at
            FOR UPDATE SKIP LOCKED
            LIMIT :limit
        """),
        {"limit": limit},
    )
    return list(result.mappings())
