"""Order domain service (Stage 6)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ValidationError
from platform_core.gates import assert_business_accepts_commerce, assert_business_mutable
from platform_core.models import OrderLineItem, OrderStatusHistory, SalesOrder
from platform_core.resolvers.customer_resolver import CustomerResolver
from platform_core.resolvers.location_resolver import LocationResolver
from platform_core.resolvers.offering_resolver import OfferingResolver
from platform_core.resolvers.order_resolver import OrderResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.customer_timeline import CustomerTimelineService
from platform_core.services.inventory import InventoryService
from platform_core.services.order_calculation import calculate_line, calculate_order_totals
from platform_core.services.outbox import OutboxService
from platform_core.validation.order import validate_create_payload, validate_patch_payload


class OrderService:
    @staticmethod
    def serialize_order(order: SalesOrder) -> dict[str, Any]:
        return cast(dict[str, Any], OrderResolver.serialize_order(order))

    @staticmethod
    async def serialize_order_with_items(
        session: AsyncSession,
        order: SalesOrder,
    ) -> dict[str, Any]:
        items = await OrderResolver.load_line_items(session, order_id=order.id)
        return OrderResolver.serialize_order_detail(order, line_items=items)

    @staticmethod
    def _generate_order_number() -> str:
        return f"ORD-{uuid.uuid4().hex[:8].upper()}"

    @staticmethod
    async def _build_line_item(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        order_id: uuid.UUID,
        sort_order: int,
        raw: dict[str, Any],
    ) -> OrderLineItem:
        offering = await OfferingResolver.resolve(
            session,
            business_id=business_id,
            offering_id=raw["offering_id"],
        )
        if offering.status != "active":
            raise ValidationError(
                "Product is not active",
                details={"offering_id": str(offering.id), "status": offering.status},
            )
        title = offering.title
        sku = offering.sku
        unit_price = raw.get("unit_price")
        tax_rate = offering.tax_rate
        variant_id = raw.get("variant_id")
        if variant_id:
            variant = await OfferingResolver.resolve_variant(
                session, business_id=business_id, variant_id=variant_id
            )
            if variant.offering_id != offering.id:
                raise ValidationError("Variant does not belong to product")
            title = f"{offering.title} — {variant.name}"
            sku = variant.sku or sku
            if unit_price is None and variant.price_amount is not None:
                unit_price = variant.price_amount
        if unit_price is None:
            unit_price = offering.price_amount
        if unit_price is None:
            raise ValidationError(
                "Unit price is required",
                details={"offering_id": str(offering.id)},
            )
        price = Decimal(str(unit_price))
        rate = Decimal(str(tax_rate)) if tax_rate is not None else None
        totals = calculate_line(unit_price=price, quantity=raw["quantity"], tax_rate=rate)
        return OrderLineItem(
            business_id=business_id,
            order_id=order_id,
            offering_id=offering.id,
            variant_id=variant_id,
            title=title,
            sku=sku,
            unit_price=float(price),
            quantity=raw["quantity"],
            tax_rate=float(rate) if rate is not None else None,
            line_subtotal=float(totals["line_subtotal"]),
            line_tax=float(totals["line_tax"]),
            line_total=float(totals["line_total"]),
            track_inventory=offering.track_inventory,
            sort_order=sort_order,
        )

    @staticmethod
    async def _reserve_line_items(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        order: SalesOrder,
        line_items: list[OrderLineItem],
        actor_id: uuid.UUID,
        correlation_id: str,
        actor_context: str = "business",
    ) -> None:
        for item in line_items:
            if not item.track_inventory:
                continue
            await InventoryService.reserve_for_order(
                session,
                business_id=business_id,
                offering_id=item.offering_id,
                location_id=order.location_id,
                variant_id=item.variant_id,
                quantity=item.quantity,
                actor_id=actor_id,
                correlation_id=correlation_id,
                order_id=order.id,
                reason=f"Order {order.order_number} reservation",
                actor_context=actor_context,
            )
            item.quantity_reserved = item.quantity

    @staticmethod
    async def _publish_created(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        order: SalesOrder,
        line_items: list[OrderLineItem],
        actor_id: uuid.UUID,
        correlation_id: str,
        actor_context: str = "business",
    ) -> None:
        after = OrderResolver.serialize_order_detail(order, line_items=line_items)
        payload: dict[str, Any] = {
            "business_id": str(business_id),
            "order_id": str(order.id),
            "order_number": order.order_number,
            "customer_contact_id": (
                str(order.customer_contact_id) if order.customer_contact_id else None
            ),
            "total_amount": float(order.total_amount),
            "items": [OrderResolver.serialize_line_item(i) for i in line_items],
            "after": after,
        }
        await OutboxService.publish(
            session,
            event_type="order.created",
            payload=payload,
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="order.created",
            actor_identity_id=actor_id,
            actor_context=actor_context,
            business_id=business_id,
            resource_type="order",
            resource_id=order.id,
            action="created",
            before_state=None,
            after_state=after,
        )
        if order.customer_contact_id:
            await CustomerTimelineService.record_entry(
                session,
                business_id=business_id,
                contact_id=order.customer_contact_id,
                activity_type="order.created",
                resource_type="order",
                resource_id=order.id,
                location_id=order.location_id,
                summary={
                    "order_number": order.order_number,
                    "total_amount": float(order.total_amount),
                    "status": order.status,
                },
            )

    @staticmethod
    async def list_for_business(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        status: str | None = None,
        search: str | None = None,
        customer_contact_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
    ) -> list[SalesOrder]:
        query = select(SalesOrder).where(
            SalesOrder.business_id == business_id,
            SalesOrder.deleted_at.is_(None),
        )
        if status:
            query = query.where(SalesOrder.status == status)
        if customer_contact_id:
            query = query.where(SalesOrder.customer_contact_id == customer_contact_id)
        if location_id:
            query = query.where(SalesOrder.location_id == location_id)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.where(
                or_(
                    SalesOrder.order_number.ilike(pattern),
                    SalesOrder.internal_reference.ilike(pattern),
                )
            )
        query = query.order_by(SalesOrder.created_at.desc())
        return list((await session.execute(query)).scalars().all())

    @staticmethod
    async def create_order(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
        actor_context: str = "business",
    ) -> SalesOrder:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="create order")
        # Doc 04 §6.1: a suspended Business cannot receive orders. Standing
        # (`status`) is a separate axis from lifecycle (`state`) — both apply.
        assert_business_accepts_commerce(business.status, action="create order")
        validated = validate_create_payload(payload)
        if validated["idempotency_key"]:
            existing = await session.execute(
                select(SalesOrder).where(
                    SalesOrder.business_id == business_id,
                    SalesOrder.idempotency_key == validated["idempotency_key"],
                    SalesOrder.deleted_at.is_(None),
                )
            )
            found = existing.scalars().first()
            if found:
                return found

        await LocationResolver.resolve(
            session, business_id=business_id, location_id=validated["location_id"]
        )
        if validated["customer_contact_id"]:
            await CustomerResolver.resolve(
                session,
                business_id=business_id,
                contact_id=validated["customer_contact_id"],
            )

        order = SalesOrder(
            business_id=business_id,
            location_id=validated["location_id"],
            customer_contact_id=validated["customer_contact_id"],
            order_number=OrderService._generate_order_number(),
            payment_method=validated["payment_method"],
            payment_status=(
                "pending_offline"
                if validated["payment_method"] in {"cod", "pay_at_business", "pay_later"}
                else "pending"
            ),
            currency=validated["currency"],
            internal_reference=validated["internal_reference"],
            idempotency_key=validated["idempotency_key"],
        )
        session.add(order)
        await session.flush()

        line_items: list[OrderLineItem] = []
        for idx, item_raw in enumerate(validated["items"]):
            item = await OrderService._build_line_item(
                session,
                business_id=business_id,
                order_id=order.id,
                sort_order=idx,
                raw=item_raw,
            )
            session.add(item)
            line_items.append(item)
        await session.flush()

        totals = calculate_order_totals(
            [OrderResolver.serialize_line_item(i) for i in line_items],
            discount_amount=validated["discount_amount"],
        )
        order.subtotal = float(totals["subtotal"])
        order.tax_amount = float(totals["tax_amount"])
        order.discount_amount = float(totals["discount_amount"])
        order.total_amount = float(totals["total_amount"])

        await OrderService._reserve_line_items(
            session,
            business_id=business_id,
            order=order,
            line_items=line_items,
            actor_id=actor_id,
            correlation_id=correlation_id,
            actor_context=actor_context,
        )

        history = OrderStatusHistory(
            business_id=business_id,
            order_id=order.id,
            from_status=None,
            to_status="pending",
            actor_identity_id=actor_id,
            reason="Order created",
        )
        session.add(history)
        await session.flush()

        await OrderService._publish_created(
            session,
            business_id=business_id,
            order=order,
            line_items=line_items,
            actor_id=actor_id,
            correlation_id=correlation_id,
            actor_context=actor_context,
        )
        return order

    @staticmethod
    async def patch_order(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        order_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
        expected_version: int | None = None,
    ) -> SalesOrder:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="update order")
        order = await OrderResolver.resolve_mutable(
            session, business_id=business_id, order_id=order_id
        )
        if expected_version is not None and order.version != expected_version:
            raise ConflictError(
                "Stale order version",
                details={
                    "expected_version": expected_version,
                    "current_version": order.version,
                },
            )
        before_items = await OrderResolver.load_line_items(session, order_id=order.id)
        before = OrderResolver.serialize_order_detail(order, line_items=before_items)
        patch = validate_patch_payload(payload)
        for key, value in patch.items():
            setattr(order, key, value)
        order.version += 1
        await session.flush()
        after_items = await OrderResolver.load_line_items(session, order_id=order.id)
        after = OrderResolver.serialize_order_detail(order, line_items=after_items)
        await OutboxService.publish(
            session,
            event_type="order.updated",
            payload={
                "business_id": str(business_id),
                "order_id": str(order.id),
                "after": after,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="order.updated",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="order",
            resource_id=order.id,
            action="updated",
            before_state=before,
            after_state=after,
        )
        return order

    @staticmethod
    async def get_status_history(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        order_id: uuid.UUID,
    ) -> list[OrderStatusHistory]:
        await OrderResolver.resolve(session, business_id=business_id, order_id=order_id)
        return await OrderResolver.load_status_history(session, order_id=order_id)
