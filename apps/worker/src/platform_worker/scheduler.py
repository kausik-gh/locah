"""Scheduled job lane — materialize due schedules into platform_async_jobs."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_worker.claiming import claim_due_schedules


def _payload_as_json(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    return json.dumps(payload if payload is not None else {})


def _correlation_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    raw = payload.get("correlation_id")
    if raw is None:
        return None
    try:
        return str(uuid.UUID(str(raw)))
    except (ValueError, TypeError):
        return None


async def materialize_due_schedules(session: AsyncSession, worker_id: str) -> int:
    """
    Convert due pending scheduled jobs into async jobs in one transaction.

    Marks each schedule as `materialized` with `materialized_job_id` set.
    """
    due = await claim_due_schedules(session)
    if not due:
        return 0

    materialized = 0
    for schedule in due:
        schedule_id = schedule["id"]
        job_id = uuid.uuid4()
        schedule_type = str(schedule["schedule_type"])
        payload = schedule.get("payload")
        correlation = _correlation_id(payload if isinstance(payload, dict) else None)

        await session.execute(
            text("""
                INSERT INTO platform_async_jobs (
                    id,
                    business_id,
                    job_type,
                    payload,
                    correlation_id,
                    causation_id,
                    status,
                    next_attempt_at
                )
                VALUES (
                    :id,
                    :business_id,
                    :job_type,
                    CAST(:payload AS jsonb),
                    :correlation_id,
                    :causation_id,
                    'pending',
                    now()
                )
            """),
            {
                "id": str(job_id),
                "business_id": str(schedule["business_id"]) if schedule.get("business_id") else None,
                "job_type": schedule_type,
                "payload": _payload_as_json(payload),
                "correlation_id": correlation,
                "causation_id": str(schedule_id),
            },
        )
        await session.execute(
            text("""
                UPDATE platform_scheduled_jobs
                SET status = 'materialized',
                    materialized_job_id = :job_id
                WHERE id = :id
                  AND status = 'pending'
            """),
            {"id": str(schedule_id), "job_id": str(job_id)},
        )
        materialized += 1

    await session.commit()
    return materialized
