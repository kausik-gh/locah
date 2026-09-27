"""WhatsApp Cloud API webhooks (Capability Universe §9.1, §26.3 P1-07).

GET answers Meta's subscription check with the verify token; POST receives
messages, delivery statuses and coexistence echoes. Every POST must carry
Meta's X-Hub-Signature-256 over the raw body with LOCAH's app secret — an
unsigned or wrongly signed delivery is refused before anything is read.
The delivery is processed under the API role: it can find only the channel
whose phone number id it names, then works inside that business.

Activation required: until META_APP_SECRET and WHATSAPP_VERIFY_TOKEN are set,
both routes answer 404 and nothing is accepted.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_core.exceptions import PermissionDenied, ResourceNotFound, ValidationError
from platform_core.services.messaging import MessagingService

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


def _secret(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ResourceNotFound("Webhook")
    return value


def signature_ok(raw: bytes, header: str | None, secret: str) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    good = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(good, header.removeprefix("sha256="))


@router.get("/whatsapp")
async def verify(
    mode: str = Query(alias="hub.mode"), token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge", max_length=200),
) -> Response:
    expected = _secret("WHATSAPP_VERIFY_TOKEN")
    if mode != "subscribe" or not hmac.compare_digest(token, expected):
        raise PermissionDenied("webhook.verify")
    return Response(content=challenge, media_type="text/plain")


@router.post("/whatsapp")
async def receive(request: Request, session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    secret = _secret("META_APP_SECRET")
    raw = await request.body()
    if not signature_ok(raw, request.headers.get("x-hub-signature-256"), secret):
        raise PermissionDenied("webhook.signature")
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise ValidationError("Not JSON") from exc
    counts = await MessagingService.process_webhook(session, payload)
    await session.commit()
    return {"data": counts}
