"""Inbound payment webhook ingestion (Stage 9, Doc 12 §18.6)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_service_db_session
from platform_core.services.payment_webhook import PaymentWebhookService

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


@router.post("/payments/{provider}")
async def ingest_payment_webhook(
    provider: str,
    request: Request,
    session: AsyncSession = Depends(get_service_db_session),
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
) -> dict[str, Any]:
    correlation_id = x_correlation_id or str(uuid.uuid4())
    raw_body = await request.body()
    headers = {k: v for k, v in request.headers.items()}
    result = await PaymentWebhookService.process_webhook(
        session,
        provider=provider,
        raw_body=raw_body,
        headers=headers,
        correlation_id=correlation_id,
    )
    await session.commit()
    return {"data": result, "meta": {"correlation_id": correlation_id}}
