"""Minimal Razorpay client — credential verification only.

This is deliberately *not* a payments integration. The one call it makes is a
safe, read-only authenticated GET used to confirm an owner's Key ID / Key
Secret actually work before the connection is marked `active`. Real payment
processing (orders, capture, refunds, webhooks) is separate, larger work.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

_BASE_URL = "https://api.razorpay.com/v1"
_TIMEOUT = httpx.Timeout(10.0)


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    detail: str


async def verify_key_pair(key_id: str, key_secret: str) -> VerificationResult:
    """Confirm a Razorpay key pair by making one authenticated read call.

    `GET /payments?count=1` needs only the standard API key auth and does not
    change anything. Razorpay returns 401 for a bad key pair, 200 otherwise.
    """
    key_id = key_id.strip()
    key_secret = key_secret.strip()
    if not key_id or not key_secret:
        return VerificationResult(False, "Key ID and Key Secret are both required.")
    if not key_id.startswith(("rzp_test_", "rzp_live_")):
        return VerificationResult(
            False,
            "That does not look like a Razorpay Key ID (expected rzp_test_... or rzp_live_...).",
        )

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_BASE_URL}/payments",
                params={"count": 1},
                auth=(key_id, key_secret),
            )
    except httpx.TimeoutException:
        return VerificationResult(False, "Razorpay did not respond in time. Try again.")
    except httpx.HTTPError as exc:
        return VerificationResult(False, f"Could not reach Razorpay: {exc}")

    if resp.status_code == 200:
        return VerificationResult(True, "Razorpay credentials verified.")
    if resp.status_code == 401:
        return VerificationResult(
            False, "Razorpay rejected these credentials (401). Check the Key ID and Key Secret."
        )
    body = resp.text[:200]
    return VerificationResult(
        False, f"Razorpay returned {resp.status_code} while verifying: {body}"
    )
