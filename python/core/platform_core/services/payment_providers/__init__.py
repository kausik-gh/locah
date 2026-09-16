"""Payment provider adapter skeleton (Stage 1 — no live provider integration)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class PaymentProviderCapabilities:
    supports_refunds: bool = False
    supports_recurring: bool = False
    supports_webhooks: bool = False


class PaymentProviderAdapter(ABC):
    """Abstract payment provider contract for Stage 4+ commerce flows."""

    provider_id: str

    @abstractmethod
    def capabilities(self) -> PaymentProviderCapabilities:
        raise NotImplementedError

    @abstractmethod
    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def initiate_payment(
        self,
        *,
        business_id: UUID,
        amount_minor: int,
        currency: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        raise NotImplementedError


class StubPaymentProvider(PaymentProviderAdapter):
    """Stage 1 placeholder — records capability contract only."""

    provider_id = "stub"

    def capabilities(self) -> PaymentProviderCapabilities:
        return PaymentProviderCapabilities()

    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        return False

    async def initiate_payment(
        self,
        *,
        business_id: UUID,
        amount_minor: int,
        currency: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return {
            "provider": self.provider_id,
            "status": "not_configured",
            "business_id": str(business_id),
            "idempotency_key": idempotency_key,
        }
