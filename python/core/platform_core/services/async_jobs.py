"""Enqueue platform async jobs into platform_async_jobs (Doc 12 §18)."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AsyncJobService:
    @staticmethod
    async def enqueue(
        session: AsyncSession,
        *,
        job_type: str,
        payload: dict[str, Any],
        business_id: uuid.UUID | None = None,
        max_attempts: int = 5,
        idempotency_key: str | None = None,
    ) -> uuid.UUID:
        job_id = uuid.uuid4()
        if os.getenv("LOCAH_JOBS_INERT") == "1":
            # Test runs: recorded like any job, executed by no worker.
            payload = {**payload, "inert": True}
        await session.execute(
            text("""
                INSERT INTO platform_async_jobs (
                    id, job_type, payload, business_id, status, max_attempts, next_attempt_at
                ) VALUES (
                    :id, :job_type, CAST(:payload AS jsonb), :business_id,
                    'pending', :max_attempts, now()
                )
            """),
            {
                "id": str(job_id),
                "job_type": job_type,
                "payload": json.dumps(payload),
                "business_id": str(business_id) if business_id else None,
                "max_attempts": max_attempts,
            },
        )
        return job_id
