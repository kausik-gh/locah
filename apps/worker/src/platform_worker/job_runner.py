"""Asynchronous job lane — claim, execute, retry, dead-letter."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_worker.claiming import claim_job_batch


def _payload_as_dict(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        loaded = json.loads(payload)
        return loaded if isinstance(loaded, dict) else {}
    return {}


def _payload_as_json(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    return json.dumps(payload if payload is not None else {})


async def _already_processed(session: AsyncSession, job_id: str, handler: str) -> bool:
    result = await session.execute(
        text("""
            SELECT 1 FROM platform_processed_events
            WHERE event_id = :event_id AND handler = :handler
            LIMIT 1
        """),
        {"event_id": job_id, "handler": handler},
    )
    return result.first() is not None


async def _record_processed(session: AsyncSession, job_id: str, handler: str) -> None:
    await session.execute(
        text("""
            INSERT INTO platform_processed_events (event_id, handler)
            VALUES (:event_id, :handler)
            ON CONFLICT (event_id, handler) DO NOTHING
        """),
        {"event_id": job_id, "handler": handler},
    )


async def _execute_job(session: AsyncSession, job: dict[str, Any]) -> None:
    """Dispatch known job types; unknown types acknowledge without side effects."""
    payload = _payload_as_dict(job.get("payload"))
    if payload.get("__force_fail"):
        message = str(payload.get("__force_fail_message") or "forced job failure")
        raise RuntimeError(message)

    job_type = str(job.get("job_type") or "")
    if job_type == "website.generate":
        from uuid import UUID

        from platform_core.services.website_generation import WebsiteGenerationService

        generation_job_id = payload.get("generation_job_id")
        if not generation_job_id:
            raise RuntimeError("website.generate payload missing generation_job_id")
        await WebsiteGenerationService.execute_job(
            session,
            generation_job_id=UUID(str(generation_job_id)),
            correlation_id=str(payload.get("correlation_id") or job.get("id")),
        )
    elif job_type == "marketplace.reconcile":
        from platform_core.services.marketplace_indexing import MarketplaceIndexingService

        await MarketplaceIndexingService.reconcile_all(
            session,
            correlation_id=str(payload.get("correlation_id") or job.get("id")),
            limit=int(payload.get("limit") or 100),
        )
    elif job_type == "marketplace.reindex":
        from uuid import UUID

        from platform_core.services.marketplace_indexing import MarketplaceIndexingService

        business_id = payload.get("business_id")
        if not business_id:
            raise RuntimeError("marketplace.reindex payload missing business_id")
        await MarketplaceIndexingService.reindex_business(
            session,
            business_id=UUID(str(business_id)),
            correlation_id=str(payload.get("correlation_id") or job.get("id")),
            trigger="async_job",
        )


async def _mark_completed(session: AsyncSession, job_id: str) -> None:
    await session.execute(
        text("""
            UPDATE platform_async_jobs
            SET status = 'completed',
                completed_at = now(),
                leased_until = NULL,
                leased_by = NULL,
                last_error = NULL
            WHERE id = :id
        """),
        {"id": job_id},
    )


async def _mark_retry(
    session: AsyncSession, job_id: str, attempt_count: int, error: str
) -> None:
    backoff = min(2**attempt_count * 30, 3600)
    await session.execute(
        text("""
            UPDATE platform_async_jobs
            SET status = 'failed',
                attempt_count = :attempt_count,
                next_attempt_at = now() + make_interval(secs => :backoff),
                last_error = :error,
                leased_until = NULL,
                leased_by = NULL
            WHERE id = :id
        """),
        {
            "id": job_id,
            "attempt_count": attempt_count,
            "backoff": backoff,
            "error": error,
        },
    )


async def _mark_dead_letter(session: AsyncSession, job: dict[str, Any], error: str) -> None:
    attempt_count = int(job.get("attempt_count", 0)) + 1
    await session.execute(
        text("""
            UPDATE platform_async_jobs
            SET status = 'dead_letter',
                attempt_count = :attempt_count,
                last_error = :error,
                leased_until = NULL,
                leased_by = NULL
            WHERE id = :id
        """),
        {"id": job["id"], "attempt_count": attempt_count, "error": error},
    )
    await session.execute(
        text("""
            INSERT INTO platform_dead_letter_events
                (source_table, source_id, event_type, payload, final_error, attempt_count)
            VALUES (
                'platform_async_jobs',
                :id,
                :event_type,
                CAST(:payload AS jsonb),
                :error,
                :attempt_count
            )
        """),
        {
            "id": job["id"],
            "event_type": job.get("job_type", "unknown"),
            "payload": _payload_as_json(job.get("payload")),
            "error": error,
            "attempt_count": attempt_count,
        },
    )


async def poll_and_execute_jobs(session: AsyncSession, worker_id: str) -> int:
    """Claim and process a batch of async jobs. Returns jobs transitioned this poll."""
    jobs = await claim_job_batch(session, worker_id)
    if not jobs:
        return 0

    processed = 0
    for job in jobs:
        job_id = str(job["id"])
        job_type = str(job.get("job_type") or "unknown")
        handler = f"job_runner.{job_type}"
        try:
            if await _already_processed(session, job_id, handler):
                await _mark_completed(session, job_id)
                processed += 1
                continue

            await _execute_job(session, dict(job))
            await _record_processed(session, job_id, handler)
            await _mark_completed(session, job_id)
            processed += 1
        except Exception as exc:
            attempt = int(job.get("attempt_count", 0)) + 1
            max_attempts = int(job.get("max_attempts", 5))
            if attempt >= max_attempts:
                await _mark_dead_letter(session, dict(job), str(exc))
            else:
                await _mark_retry(session, job_id, attempt, str(exc))
    await session.commit()
    return processed
