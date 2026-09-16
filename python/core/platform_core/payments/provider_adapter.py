"""Payment provider adapter stubs (Stage 9)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any


def verify_webhook_signature(
    provider: str,
    raw_body: bytes,
    headers: dict[str, str],
) -> bool:
    secret = os.getenv("PAYMENT_WEBHOOK_SECRET", "test-payment-webhook-secret")
    if provider == "stub":
        signature = headers.get("x-payment-signature") or headers.get("X-Payment-Signature")
        if not signature:
            return False
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    if provider == "razorpay":
        signature = headers.get("x-razorpay-signature") or headers.get("X-Razorpay-Signature")
        if not signature:
            return False
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    return False


def extract_event_id(provider: str, payload: dict[str, Any]) -> str:
    if provider_event_id := payload.get("event_id"):
        return str(provider_event_id)
    if provider == "razorpay" and payload.get("id"):
        return str(payload["id"])
    raise ValueError("Webhook payload missing event_id")


def parse_webhook_payload(raw_body: bytes) -> dict[str, Any]:
    parsed = json.loads(raw_body.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("Webhook payload must be a JSON object")
    return parsed
