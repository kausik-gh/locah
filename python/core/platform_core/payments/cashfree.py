"""Cashfree Payment Gateway adapter. Sandbox-only until a separate go-live pass.

No application service should construct Cashfree requests or handle credentials.
The order split is supplied by server-side commercial policy, never the client.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import uuid
from decimal import Decimal
from typing import Any, cast

import httpx

from platform_core.exceptions import ValidationError


class CashfreePaymentProvider:
    def __init__(self, *, client_id: str, client_secret: str, api_version: str = "2025-01-01"):
        if not client_id or not client_secret:
            raise ValidationError("Cashfree sandbox credentials are not configured")
        self._client_id = client_id
        self._client_secret = client_secret
        self._api_version = api_version
        self._base_url = "https://sandbox.cashfree.com/pg"

    @classmethod
    def from_environment(cls) -> "CashfreePaymentProvider":
        if os.getenv("CASHFREE_ENV", "").strip().lower() != "sandbox":
            raise ValidationError("Cashfree payments require sandbox configuration")
        client_id = os.getenv("CASHFREE_CLIENT_ID", "").strip()
        if client_id and not client_id.startswith("TEST_"):
            raise ValidationError("Cashfree sandbox requires a TEST_ client ID")
        return cls(
            client_id=client_id,
            client_secret=os.getenv("CASHFREE_CLIENT_SECRET", "").strip(),
            api_version=os.getenv("CASHFREE_API_VERSION", "2025-01-01").strip(),
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        headers = {
            "x-client-id": self._client_id,
            "x-client-secret": self._client_secret,
            "x-api-version": self._api_version,
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["x-idempotency-key"] = idempotency_key
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.request(
                    method, f"{self._base_url}{path}", headers=headers, json=body
                )
        except httpx.HTTPError as exc:
            raise ValidationError("Cashfree sandbox is unavailable") from exc
        if not response.is_success:
            # Provider error bodies can echo PII. Keep them out of API responses
            # and logs; status alone is enough for the owner-facing state.
            provider_code = None
            try:
                candidate = response.json().get("code")
                if isinstance(candidate, str) and re.fullmatch(r"[a-zA-Z0-9_]{1,80}", candidate):
                    provider_code = candidate
            except (ValueError, AttributeError):
                pass
            raise ValidationError(
                "Cashfree sandbox rejected the request",
                details={"provider_status": response.status_code, "provider_code": provider_code},
            )
        result = response.json()
        if not isinstance(result, (dict, list)):
            raise ValidationError("Cashfree returned an invalid response")
        return cast(dict[str, Any] | list[dict[str, Any]], result)

    async def create_vendor(
        self,
        *,
        vendor_id: str,
        name: str,
        email: str,
        phone: str,
        kyc_details: dict[str, Any],
        bank: dict[str, str],
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            await self._request(
                "POST",
                "/easy-split/vendors",
                body={
                    "vendor_id": vendor_id,
                    "status": "ACTIVE",
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "verify_account": True,
                    "dashboard_access": False,
                    "kyc_details": kyc_details,
                    "bank": bank,
                },
            idempotency_key=str(uuid.uuid5(uuid.NAMESPACE_URL, f"locah:vendor:{vendor_id}")),
            ),
        )

    async def fetch_vendor(self, vendor_id: str) -> dict[str, Any]:
        return cast(dict[str, Any], await self._request("GET", f"/easy-split/vendors/{vendor_id}"))

    async def create_order(
        self,
        *,
        order_id: str,
        amount: Decimal,
        currency: str,
        customer_id: str,
        customer_name: str,
        customer_email: str,
        customer_phone: str,
        vendor_id: str | None = None,
        vendor_amount: Decimal | None = None,
        notify_url: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "order_id": order_id,
            "order_amount": float(amount),
            "order_currency": currency,
            "customer_details": {
                "customer_id": customer_id,
                "customer_name": customer_name,
                "customer_email": customer_email,
                "customer_phone": customer_phone,
            },
        }
        if vendor_id is not None:
            if vendor_amount is None or vendor_amount <= 0 or vendor_amount > amount:
                raise ValidationError("Invalid Cashfree vendor split")
            body["order_splits"] = [{"vendor_id": vendor_id, "amount": float(vendor_amount)}]
        if notify_url:
            body["order_meta"] = {"notify_url": notify_url}
        return cast(
            dict[str, Any],
            await self._request(
            "POST", "/orders", body=body,
            idempotency_key=str(uuid.uuid5(uuid.NAMESPACE_URL, f"locah:order:{order_id}")),
            ),
        )

    async def fetch_order(self, order_id: str) -> dict[str, Any]:
        return cast(dict[str, Any], await self._request("GET", f"/orders/{order_id}"))

    async def fetch_payments(self, order_id: str) -> list[dict[str, Any]]:
        return cast(
            list[dict[str, Any]], await self._request("GET", f"/orders/{order_id}/payments")
        )

    async def create_refund(
        self,
        *,
        order_id: str,
        refund_id: str,
        amount: Decimal,
        note: str,
        vendor_id: str | None = None,
        vendor_amount: Decimal | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "refund_id": refund_id,
            "refund_amount": float(amount),
            "refund_note": note,
            "refund_speed": "STANDARD",
        }
        if vendor_id is not None:
            if vendor_amount is None or vendor_amount < 0 or vendor_amount > amount:
                raise ValidationError("Invalid Cashfree refund split")
            body["refund_splits"] = [{"vendor_id": vendor_id, "amount": float(vendor_amount)}]
        return cast(
            dict[str, Any],
            await self._request(
                "POST",
                f"/orders/{order_id}/refunds",
                body=body,
                idempotency_key=str(uuid.uuid5(uuid.NAMESPACE_URL, f"locah:refund:{refund_id}")),
            ),
        )

    async def fetch_refund(self, order_id: str, refund_id: str) -> dict[str, Any]:
        return cast(
            dict[str, Any], await self._request("GET", f"/orders/{order_id}/refunds/{refund_id}")
        )

    def verify_webhook(self, *, timestamp: str, raw_body: bytes, signature: str) -> bool:
        if not timestamp or not signature:
            return False
        digest = hmac.new(
            self._client_secret.encode("utf-8"),
            timestamp.encode("utf-8") + raw_body,
            hashlib.sha256,
        ).digest()
        expected = base64.b64encode(digest).decode("ascii")
        return hmac.compare_digest(expected, signature)
