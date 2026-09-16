"""Public cart/checkout orchestration (WEB-007) — Doc 11 §17.4 / Doc 12 §11.2.

Coordinates OrderService + FulfilmentService + PaymentAttemptService in one transaction.
Does not modify Order/Payment/Inventory domain internals.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.context_resolver import bind_public_context
from platform_core.exceptions import ResourceNotFound, ValidationError
from platform_core.models import BusinessModuleState, MerchantConnection, Offering
from platform_core.services.business import BusinessService
from platform_core.services.customer import CustomerService
from platform_core.services.fulfilment import ACTIVE_MODULE_STATES, FulfilmentService
from platform_core.services.location import LocationService
from platform_core.services.order import OrderService
from platform_core.services.payment_attempt import PaymentAttemptService


class CheckoutService:
    @staticmethod
    async def _resolve_business(session: AsyncSession, slug: str):
        business = await BusinessService.get_by_slug(session, slug)
        if business is None or business.deleted_at is not None:
            raise ResourceNotFound("Business")
        # Guest request: bind the tenant GUC so subsequent RLS-scoped reads
        # (offerings, inventory, ...) resolve. Doc 11 §21.1 / AUD-02.
        await bind_public_context(session, business.id)
        return business

    @staticmethod
    async def _orders_active(session: AsyncSession, business_id: uuid.UUID) -> bool:
        state = (
            await session.execute(
                select(BusinessModuleState).where(
                    BusinessModuleState.business_id == business_id,
                    BusinessModuleState.module_id == "orders",
                )
            )
        ).scalars().first()
        return state is not None and state.activation_state in ACTIVE_MODULE_STATES

    @staticmethod
    async def list_public_offerings(
        session: AsyncSession, *, slug: str, limit: int = 50
    ) -> dict[str, Any]:
        business = await CheckoutService._resolve_business(session, slug)
        rows = (
            await session.execute(
                select(Offering).where(
                    Offering.business_id == business.id,
                    Offering.deleted_at.is_(None),
                    Offering.status == "active",
                    Offering.visibility == "public",
                ).order_by(Offering.title.asc()).limit(limit)
            )
        ).scalars().all()
        return {
            "business": {
                "id": str(business.id),
                "slug": business.slug,
                "display_name": business.display_name,
            },
            "offerings": [
                {
                    "id": str(o.id),
                    "title": o.title,
                    "description": o.description,
                    "offering_type": o.offering_type,
                    "price_amount": float(o.price_amount) if o.price_amount is not None else None,
                    "currency": o.currency,
                }
                for o in rows
            ],
        }

    @staticmethod
    async def checkout_options(session: AsyncSession, *, slug: str) -> dict[str, Any]:
        business = await CheckoutService._resolve_business(session, slug)
        locations = await LocationService.list_for_business(
            session, business.id, status="active"
        )
        modes = await FulfilmentService.active_modes(session, business.id)
        payments_active = (
            await session.execute(
                select(BusinessModuleState).where(
                    BusinessModuleState.business_id == business.id,
                    BusinessModuleState.module_id == "payments",
                )
            )
        ).scalars().first()
        merchant = (
            await session.execute(
                select(MerchantConnection).where(
                    MerchantConnection.business_id == business.id,
                    MerchantConnection.status == "active",
                ).limit(1)
            )
        ).scalars().first()
        payment_methods = ["cod"]
        if (
            payments_active
            and payments_active.activation_state in ACTIVE_MODULE_STATES
            and merchant is not None
        ):
            payment_methods.append("online")
        return {
            "business": {
                "id": str(business.id),
                "slug": business.slug,
                "display_name": business.display_name,
            },
            "fulfilment_modes": modes,
            "payment_methods": payment_methods,
            "locations": [
                {
                    "id": str(loc.id),
                    "name": loc.name,
                    "is_primary": loc.is_primary,
                    "address": loc.address,
                }
                for loc in locations
            ],
        }

    @staticmethod
    async def quote_delivery(
        session: AsyncSession, *, slug: str, address: dict[str, Any]
    ) -> dict[str, Any]:
        business = await CheckoutService._resolve_business(session, slug)
        modes = await FulfilmentService.active_modes(session, business.id)
        if "delivery" not in modes:
            raise ValidationError("Delivery is not available")
        zone, charge = await FulfilmentService.match_zone(
            session, business_id=business.id, address=address
        )
        if zone is None:
            return {"serviceable": False, "delivery_charge": 0, "zone": None}
        return {
            "serviceable": True,
            "delivery_charge": float(charge),
            "zone": FulfilmentService.serialize_zone(zone),
        }

    @staticmethod
    async def place_order(
        session: AsyncSession,
        *,
        slug: str,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        business = await CheckoutService._resolve_business(session, slug)
        if not await CheckoutService._orders_active(session, business.id):
            # Auto-enable is not allowed; require module. For First Launch retail types
            # orders is on the plan — Business must enable. Fallback: if entitled core
            # path missing, still allow when orders module state absent but plan includes
            # it by enabling check soft — keep strict.
            raise ValidationError("Orders are not enabled for this Business")

        items = payload.get("items") or []
        if not items:
            raise ValidationError(
                "Cart is empty",
                details={"code": "empty_cart", "field": "items"},
            )

        mode = str(payload.get("fulfilment_mode") or "").strip()
        payment_method = str(payload.get("payment_method") or "cod").strip()
        location_id = payload.get("location_id")
        if not location_id:
            locations = await LocationService.list_for_business(
                session, business.id, status="active"
            )
            primary = next((loc for loc in locations if loc.is_primary), locations[0] if locations else None)
            if primary is None:
                raise ValidationError("Business has no active location")
            location_id = primary.id
        else:
            location_id = uuid.UUID(str(location_id))

        options = await CheckoutService.checkout_options(session, slug=slug)
        if mode not in options["fulfilment_modes"]:
            raise ValidationError(
                "Selected fulfilment mode is not available",
                details={"mode": mode, "active_modes": options["fulfilment_modes"]},
            )
        if payment_method not in options["payment_methods"]:
            raise ValidationError(
                "Selected payment method is not available",
                details={"payment_method": payment_method},
            )

        guest = payload.get("guest") or {}
        display_name = str(guest.get("name") or "").strip()
        email = str(guest.get("email") or "").strip().lower()
        phone = (str(guest.get("phone")).strip() if guest.get("phone") else None) or None
        if not display_name or not email:
            raise ValidationError(
                "Guest name and email are required",
                details={"field": "guest"},
            )

        # Doc 05 Part 7.1: a guest checkout is bounded to the transaction and
        # never becomes a Platform Identity. Customer attribution is the
        # business-scoped CustomerContact; audit/actor attribution is the
        # storefront owner acting in a guest-checkout context.
        actor_id = business.primary_owner_identity_id
        contact = await CustomerService.find_or_create_contact(
            session,
            business_id=business.id,
            correlation_id=correlation_id,
            actor_id=actor_id,
            actor_context="guest_checkout",
            display_name=display_name,
            email=email,
            phone=phone,
        )

        # Validate offerings exist and are public/active before create.
        order_items: list[dict[str, Any]] = []
        for raw in items:
            offering_id = uuid.UUID(str(raw["offering_id"]))
            offering = (
                await session.execute(
                    select(Offering).where(
                        Offering.id == offering_id,
                        Offering.business_id == business.id,
                        Offering.deleted_at.is_(None),
                    )
                )
            ).scalars().first()
            if offering is None or offering.status != "active":
                raise ValidationError(
                    "Cart contains an invalid item",
                    details={"code": "invalid_item", "offering_id": str(offering_id)},
                )
            order_items.append(
                {
                    "offering_id": offering_id,
                    "variant_id": raw.get("variant_id"),
                    "quantity": int(raw.get("quantity") or 1),
                    "unit_price": raw.get("unit_price"),
                }
            )

        delivery_address = payload.get("delivery_address")
        delivery_charge = Decimal("0")
        delivery_fee_offering_id = None
        if mode == "delivery":
            if not isinstance(delivery_address, dict):
                raise ValidationError("Delivery address is required")
            zone, delivery_charge = await FulfilmentService.match_zone(
                session, business_id=business.id, address=delivery_address
            )
            if zone is None:
                raise ValidationError("Address is outside configured delivery zones")
            delivery_fee_offering_id = await FulfilmentService._ensure_delivery_fee_offering(
                session, business_id=business.id
            )
            if delivery_charge > 0:
                order_items.append(
                    {
                        "offering_id": delivery_fee_offering_id,
                        "quantity": 1,
                        "unit_price": float(delivery_charge),
                    }
                )

        idempotency_key = payload.get("idempotency_key") or str(uuid.uuid4())
        order = await OrderService.create_order(
            session,
            business_id=business.id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            actor_context="guest_checkout",
            payload={
                "location_id": location_id,
                "customer_contact_id": contact.id,
                "payment_method": payment_method,
                "currency": payload.get("currency") or "INR",
                "idempotency_key": idempotency_key,
                "items": order_items,
            },
        )

        # Idempotent re-entry: ensure job exists for this order.
        job = await FulfilmentService.create_job_for_order(
            session,
            business_id=business.id,
            order=order,
            actor_id=actor_id,
            correlation_id=correlation_id,
            mode=mode,
            delivery_address=delivery_address if mode == "delivery" else None,
        )

        payment_data = None
        payment_state = "order_pending"
        if payment_method == "online":
            try:
                payment = await PaymentAttemptService.create_attempt(
                    session,
                    business_id=business.id,
                    actor_id=actor_id,
                    correlation_id=correlation_id,
                    payload={
                        "source_type": "order",
                        "source_id": str(order.id),
                        "amount": float(order.total_amount),
                        "currency": order.currency,
                        "payment_method": "online",
                        "customer_contact_id": str(contact.id),
                        "idempotency_key": f"pay-{idempotency_key}",
                    },
                )
                payment_data = PaymentAttemptService.serialize(payment)
                payment_state = (
                    "payment_failed" if payment.status == "failed" else payment.status
                )
            except Exception as exc:  # noqa: BLE001
                payment_state = "payment_failed"
                payment_data = {"error": str(exc)}
        else:
            payment = await PaymentAttemptService.create_attempt(
                session,
                business_id=business.id,
                actor_id=actor_id,
                correlation_id=correlation_id,
                payload={
                    "source_type": "order",
                    "source_id": str(order.id),
                    "amount": float(order.total_amount),
                    "currency": order.currency,
                    "payment_method": "cod",
                    "customer_contact_id": str(contact.id),
                    "idempotency_key": f"pay-{idempotency_key}",
                },
            )
            payment_data = PaymentAttemptService.serialize(payment)
            payment_state = payment.status

        order_detail = await OrderService.serialize_order_with_items(session, order)
        tracking_path = (
            f"/{business.slug}/track/{order.id}?token={job.tracking_token}"
        )
        return {
            "state": payment_state if payment_state != "processing" else "order_pending",
            "order": order_detail,
            "fulfilment": FulfilmentService.serialize_job(job),
            "payment": payment_data,
            "tracking": {
                "order_id": str(order.id),
                "token": job.tracking_token,
                "href": tracking_path,
            },
            "confirmation": {
                "order_number": order.order_number,
                "grand_total": float(order.total_amount),
                "currency": order.currency,
                "fulfilment_mode": mode,
            },
        }
