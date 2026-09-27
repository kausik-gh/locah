"""Deterministic Cashfree adapter contracts; no provider or AI network calls."""

from __future__ import annotations

import base64
import hashlib
import hmac
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
import uuid

import pytest

from platform_core.exceptions import ValidationError
from platform_core.payments.cashfree import CashfreePaymentProvider
from platform_core.payments.commission import calculate_split


def _provider() -> CashfreePaymentProvider:
    return CashfreePaymentProvider(client_id="TEST_id", client_secret="TEST_secret")


def test_sandbox_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASHFREE_ENV", "production")
    monkeypatch.setenv("CASHFREE_CLIENT_ID", "TEST_id")
    monkeypatch.setenv("CASHFREE_CLIENT_SECRET", "TEST_secret")
    with pytest.raises(ValidationError):
        CashfreePaymentProvider.from_environment()


def test_raw_body_webhook_signature() -> None:
    provider = _provider()
    raw = b'{"amount":170.00}'
    timestamp = "1760000000"
    signature = base64.b64encode(
        hmac.new(b"TEST_secret", timestamp.encode() + raw, hashlib.sha256).digest()
    ).decode()
    assert provider.verify_webhook(timestamp=timestamp, raw_body=raw, signature=signature)
    assert not provider.verify_webhook(
        timestamp=timestamp, raw_body=b'{"amount":170.0}', signature=signature
    )
    assert not provider.verify_webhook(timestamp="", raw_body=raw, signature=signature)


@pytest.mark.asyncio
async def test_merchant_order_has_server_split(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider()
    captured: dict[str, Any] = {}

    async def fake_request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        captured.update({"method": method, "path": path, **kwargs})
        return {"order_id": "locah_123", "payment_session_id": "session"}

    monkeypatch.setattr(provider, "_request", fake_request)
    await provider.create_order(
        order_id="locah_123", amount=Decimal("1000.00"), currency="INR",
        customer_id="customer_1", customer_name="Test Buyer",
        customer_email="test@example.com", customer_phone="9999999999",
        vendor_id="vendor_a", vendor_amount=Decimal("900.00"),
    )
    assert captured["path"] == "/orders"
    assert uuid.UUID(captured["idempotency_key"])
    assert captured["body"]["order_splits"] == [
        {"vendor_id": "vendor_a", "amount": 900.0}
    ]


def test_commission_is_versioned_configuration() -> None:
    rule = SimpleNamespace(
        percentage_bps=500, fixed_amount=0,
        minimum_amount=None, maximum_amount=None,
    )
    assert calculate_split(Decimal("1000.00"), rule) == (
        Decimal("50.00"), Decimal("950.00")
    )
    rule.percentage_bps = 0
    assert calculate_split(Decimal("1000.00"), rule) == (
        Decimal("0.00"), Decimal("1000.00")
    )
    rule.fixed_amount = 2000
    with pytest.raises(ValidationError):
        calculate_split(Decimal("1000.00"), rule)


@pytest.mark.asyncio
async def test_refund_split_and_idempotency(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider()
    captured: dict[str, Any] = {}

    async def fake_request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        captured.update({"method": method, "path": path, **kwargs})
        return {"refund_id": "LR123", "refund_status": "PENDING"}

    monkeypatch.setattr(provider, "_request", fake_request)
    await provider.create_refund(
        order_id="locah_123", refund_id="LR123", amount=Decimal("100.00"),
        note="Customer request", vendor_id="vendor_a", vendor_amount=Decimal("90.00"),
    )
    assert captured["body"]["refund_splits"] == [
        {"vendor_id": "vendor_a", "amount": 90.0}
    ]
    assert uuid.UUID(captured["idempotency_key"])
