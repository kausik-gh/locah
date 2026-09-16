"""Shared SKIP LOCKED claiming and lease utilities for all worker lanes."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

LEASE_SECONDS = 120


async def claim_outbox_batch(
    session: AsyncSession, worker_id: str, limit: int = 10
) -> list[Any]:
    """Claim pending/failed/expired-lease outbox events."""
    result = await session.execute(
        text("""
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
                ORDER BY next_attempt_at
                FOR UPDATE SKIP LOCKED
                LIMIT :limit
            )
            RETURNING *
        """),
        {"worker_id": worker_id, "limit": limit, "lease_seconds": LEASE_SECONDS},
    )
    return list(result.mappings())


async def claim_job_batch(
    session: AsyncSession, worker_id: str, limit: int = 10
) -> list[Any]:
    """Claim pending/failed/expired-lease async jobs."""
    result = await session.execute(
        text("""
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
                ORDER BY next_attempt_at
                FOR UPDATE SKIP LOCKED
                LIMIT :limit
            )
            RETURNING *
        """),
        {"worker_id": worker_id, "limit": limit, "lease_seconds": LEASE_SECONDS},
    )
    return list(result.mappings())


async def claim_due_schedules(
    session: AsyncSession, limit: int = 10
) -> list[Any]:
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
