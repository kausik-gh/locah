"""Merchant connection service (Stage 9)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.crypto import decrypt_secret, encrypt_secret
from platform_core.exceptions import ResourceNotFound, ValidationError
from platform_core.gates import assert_business_mutable
from platform_core.models import MerchantConnection
from platform_core.payments.razorpay import create_linked_account, platform_credentials, verify_key_pair
from platform_core.resolvers.payment_resolver import PaymentResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService
from platform_core.validation.payment import validate_merchant_update_payload


class MerchantService:
    @staticmethod
    def serialize(connection: MerchantConnection) -> dict[str, Any]:
        return cast(dict[str, Any], PaymentResolver.serialize_merchant(connection))

    @staticmethod
    async def get_connection(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        provider: str = "stub",
    ) -> MerchantConnection | None:
        return await PaymentResolver.resolve_merchant(
            session, business_id=business_id, provider=provider
        )

    @staticmethod
    async def upsert_connection(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> MerchantConnection:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="update merchant connection")
        validated = validate_merchant_update_payload(payload)
        existing = await PaymentResolver.resolve_merchant(
            session, business_id=business_id, provider=validated["provider"]
        )
        before = MerchantService.serialize(existing) if existing else None
        if existing:
            existing.status = validated["status"]
            existing.provider_metadata = validated["provider_metadata"]
            existing.version += 1
            connection = existing
        else:
            connection = MerchantConnection(
                business_id=business_id,
                provider=validated["provider"],
                status=validated["status"],
                provider_metadata=validated["provider_metadata"],
            )
            session.add(connection)
        await session.flush()
        after = MerchantService.serialize(connection)
        await OutboxService.publish(
            session,
            event_type="payment.merchant.updated",
            payload={
                "business_id": str(business_id),
                "provider": connection.provider,
                "after": after,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="payment.merchant.updated",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="merchant_connection",
            resource_id=connection.id,
            action="updated",
            before_state=before,
            after_state=after,
        )
        return connection

    # ------------------------------------------------------------------
    # Razorpay: store owner-supplied credentials, then verify them live.
    # ------------------------------------------------------------------
    @staticmethod
    async def connect_razorpay(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        key_id: str,
        key_secret: str,
    ) -> MerchantConnection:
        """Save the Key ID / Key Secret (secret encrypted at rest) and mark the
        connection `pending` — unverified until `verify_connection` runs."""
        key_id = (key_id or "").strip()
        key_secret = (key_secret or "").strip()
        if not key_id or not key_secret:
            raise ValidationError(
                "Both the Razorpay Key ID and Key Secret are required.",
                details={"errors": [_field_error("key_secret", "Required")]},
            )
        if not key_id.startswith(("rzp_test_", "rzp_live_")):
            raise ValidationError(
                "That does not look like a Razorpay Key ID (rzp_test_... or rzp_live_...).",
                details={"errors": [_field_error("key_id", "Invalid Razorpay Key ID")]},
            )

        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="connect Razorpay")

        existing = await PaymentResolver.resolve_merchant(
            session, business_id=business_id, provider="razorpay"
        )
        before = MerchantService.serialize(existing) if existing else None

        ciphertext = encrypt_secret(_credentials_json(key_id, key_secret))
        mode = "test" if key_id.startswith("rzp_test_") else "live"

        if existing is not None:
            connection = existing
        else:
            connection = MerchantConnection(business_id=business_id, provider="razorpay")
            session.add(connection)
        connection.status = "pending"
        connection.encrypted_credentials = ciphertext
        connection.provider_metadata = {
            "key_id": key_id,
            "mode": mode,
            "connection_mode": "merchant_keys",
        }
        connection.verification_error = None
        connection.last_verified_at = None
        connection.version = (connection.version or 0) + 1
        await session.flush()

        after = MerchantService.serialize(connection)
        await OutboxService.publish(
            session,
            event_type="payment.merchant.updated",
            payload={
                "business_id": str(business_id),
                "provider": "razorpay",
                "after": after,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="payment.merchant.updated",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="merchant_connection",
            resource_id=connection.id,
            action="razorpay_credentials_saved",
            before_state=before,
            after_state=after,
        )
        return connection

    @staticmethod
    async def verify_connection(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
    ) -> MerchantConnection:
        """Make one live Razorpay call with the stored credentials and move the
        connection to `active` or `invalid_credentials` accordingly."""
        connection = await PaymentResolver.resolve_merchant(
            session, business_id=business_id, provider="razorpay"
        )
        if connection is None or not connection.encrypted_credentials:
            raise ValidationError(
                "Connect Razorpay first — there are no stored credentials to verify.",
                details={"errors": [_field_error("razorpay", "not_connected")]},
            )

        try:
            creds = _parse_credentials_json(decrypt_secret(connection.encrypted_credentials))
        except ValueError:
            connection.status = "invalid_credentials"
            connection.verification_error = "Stored credentials could not be read."
            await session.flush()
            return connection

        before = MerchantService.serialize(connection)
        result = await verify_key_pair(creds["key_id"], creds["key_secret"])

        if result.ok:
            connection.status = "active"
            connection.verification_error = None
            connection.last_verified_at = datetime.now(timezone.utc)
        else:
            connection.status = "invalid_credentials"
            connection.verification_error = result.detail
        connection.version = (connection.version or 0) + 1
        await session.flush()

        after = MerchantService.serialize(connection)
        await OutboxService.publish(
            session,
            event_type="payment.merchant.updated",
            payload={
                "business_id": str(business_id),
                "provider": "razorpay",
                "after": after,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="payment.merchant.updated",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="merchant_connection",
            resource_id=connection.id,
            action="razorpay_verified" if result.ok else "razorpay_verification_failed",
            before_state=before,
            after_state=after,
        )
        return connection

    @staticmethod
    async def enable_platform_payments(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        contact_email: str | None = None,
    ) -> MerchantConnection:
        """Onboard this Business as a Razorpay Route linked account.

        Ordinary owners never paste API keys. Cash / pay-at-business stay
        available if Route is not enabled on the LOCAH Razorpay account.
        """
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="enable online payments")

        existing = await PaymentResolver.resolve_merchant(
            session, business_id=business_id, provider="razorpay"
        )
        before = MerchantService.serialize(existing) if existing else None
        if existing is not None:
            connection = existing
        else:
            connection = MerchantConnection(business_id=business_id, provider="razorpay")
            session.add(connection)

        metadata = dict(connection.provider_metadata or {})
        existing_account = str(metadata.get("linked_account_id") or "").strip()
        if existing_account and connection.status == "active":
            return connection

        email = (contact_email or "").strip() or f"business-{business.id.hex[:12]}@payments.locah.app"
        result = await create_linked_account(
            email=email,
            legal_business_name=business.display_name,
            reference_id=business.id.hex[:20],
            contact_name=business.display_name,
        )
        now = datetime.now(timezone.utc)
        creds = platform_credentials()
        metadata["connection_mode"] = "platform_route"
        metadata["mode"] = creds.mode if creds else "test"
        # Platform key stays on the server. Never store it as the merchant's key.
        metadata.pop("key_id", None)
        if result.ok and result.account_id:
            metadata["linked_account_id"] = result.account_id
            metadata["linked_account_status"] = result.status or "created"
            metadata.pop("external_dependency", None)
            connection.status = "active"
            connection.encrypted_credentials = None
            connection.verification_error = None
            connection.last_verified_at = now
        else:
            metadata["external_dependency"] = result.external_dependency
            connection.status = "pending"
            connection.verification_error = result.detail
            connection.last_verified_at = now
        connection.provider_metadata = metadata
        connection.version = (connection.version or 0) + 1
        await session.flush()

        after = MerchantService.serialize(connection)
        await OutboxService.publish(
            session,
            event_type="payment.merchant.updated",
            payload={
                "business_id": str(business_id),
                "provider": "razorpay",
                "after": after,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="payment.merchant.updated",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="merchant_connection",
            resource_id=connection.id,
            action="razorpay_platform_enabled" if result.ok else "razorpay_platform_enable_failed",
            before_state=before,
            after_state=after,
        )
        return connection


def _field_error(field: str, message: str) -> dict[str, str]:
    return {"field": field, "message": message}


def _credentials_json(key_id: str, key_secret: str) -> str:
    import json

    return json.dumps({"key_id": key_id, "key_secret": key_secret})


def _parse_credentials_json(raw: str) -> dict[str, str]:
    import json

    data = json.loads(raw)
    return {"key_id": str(data["key_id"]), "key_secret": str(data["key_secret"])}
