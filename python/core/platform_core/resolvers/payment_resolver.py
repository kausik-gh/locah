"""Payment lookup resolver (Stage 9)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ResourceNotFound
from platform_core.models import MerchantConnection, PaymentAttempt, PaymentRefund


class PaymentResolver:
    @staticmethod
    async def resolve_attempt(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        payment_id: uuid.UUID,
    ) -> PaymentAttempt:
        result = await session.execute(
            select(PaymentAttempt).where(
                PaymentAttempt.id == payment_id,
                PaymentAttempt.business_id == business_id,
                PaymentAttempt.deleted_at.is_(None),
            )
        )
        payment = result.scalars().first()
        if payment is None:
            raise ResourceNotFound("Payment")
        return payment

    @staticmethod
    async def resolve_merchant(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        provider: str,
    ) -> MerchantConnection | None:
        result = await session.execute(
            select(MerchantConnection).where(
                MerchantConnection.business_id == business_id,
                MerchantConnection.provider == provider,
            )
        )
        return result.scalars().first()

    @staticmethod
    def serialize_attempt(payment: PaymentAttempt) -> dict[str, Any]:
        refundable = max(float(payment.amount) - float(payment.refunded_amount), 0)
        return {
            "id": str(payment.id),
            "business_id": str(payment.business_id),
            "customer_contact_id": (
                str(payment.customer_contact_id) if payment.customer_contact_id else None
            ),
            "source_type": payment.source_type,
            "source_id": str(payment.source_id),
            "amount": float(payment.amount),
            "currency": payment.currency,
            "payment_method": payment.payment_method,
            "status": payment.status,
            "provider": payment.provider,
            "provider_reference": payment.provider_reference,
            "refunded_amount": float(payment.refunded_amount),
            "refundable_amount": refundable,
            "failure_code": payment.failure_code,
            "failure_reason": payment.failure_reason,
            "version": payment.version,
            "created_at": payment.created_at.isoformat(),
            "updated_at": payment.updated_at.isoformat(),
        }

    @staticmethod
    def serialize_refund(refund: PaymentRefund) -> dict[str, Any]:
        return {
            "id": str(refund.id),
            "payment_attempt_id": str(refund.payment_attempt_id),
            "amount": float(refund.amount),
            "status": refund.status,
            "reason": refund.reason,
            "provider_reference": refund.provider_reference,
            "failure_reason": refund.failure_reason,
            "version": refund.version,
            "created_at": refund.created_at.isoformat(),
            "updated_at": refund.updated_at.isoformat(),
        }

    @staticmethod
    def serialize_merchant(connection: MerchantConnection) -> dict[str, Any]:
        metadata = connection.provider_metadata or {}
        return {
            "id": str(connection.id),
            "business_id": str(connection.business_id),
            "provider": connection.provider,
            "status": connection.status,
            "provider_metadata": metadata,
            # Never the secret. The Key ID is not sensitive and lets the owner
            # confirm which account is connected.
            "key_id": metadata.get("key_id"),
            "has_credentials": connection.encrypted_credentials is not None,
            "last_verified_at": (
                connection.last_verified_at.isoformat()
                if connection.last_verified_at
                else None
            ),
            "verification_error": connection.verification_error,
            "version": connection.version,
            "created_at": connection.created_at.isoformat(),
            "updated_at": connection.updated_at.isoformat(),
        }
