"""Order lookup resolver (Stage 6)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ResourceNotFound, ResourceStateDenied
from platform_core.models import OrderLineItem, OrderNote, OrderStatusHistory, SalesOrder
from platform_core.validation.order import TERMINAL_STATUSES


class OrderResolver:
    @staticmethod
    async def resolve(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        order_id: uuid.UUID,
    ) -> SalesOrder:
        result = await session.execute(
            select(SalesOrder).where(
                SalesOrder.id == order_id,
                SalesOrder.business_id == business_id,
                SalesOrder.deleted_at.is_(None),
            )
        )
        order = result.scalars().first()
        if order is None:
            raise ResourceNotFound("Order")
        return order

    @staticmethod
    def require_mutable(order: SalesOrder, *, action: str = "update") -> None:
        if order.status in TERMINAL_STATUSES:
            raise ResourceStateDenied(
                "order",
                order.status,
                action=action,
                allowed_states=["pending", "accepted", "preparing", "ready"],
            )

    @staticmethod
    async def resolve_mutable(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        order_id: uuid.UUID,
        action: str = "update",
    ) -> SalesOrder:
        order = await OrderResolver.resolve(session, business_id=business_id, order_id=order_id)
        OrderResolver.require_mutable(order, action=action)
        return order

    @staticmethod
    async def load_line_items(
        session: AsyncSession,
        *,
        order_id: uuid.UUID,
    ) -> list[OrderLineItem]:
        result = await session.execute(
            select(OrderLineItem)
            .where(OrderLineItem.order_id == order_id)
            .order_by(OrderLineItem.sort_order, OrderLineItem.created_at)
        )
        return list(result.scalars().all())

    @staticmethod
    async def load_status_history(
        session: AsyncSession,
        *,
        order_id: uuid.UUID,
    ) -> list[OrderStatusHistory]:
        result = await session.execute(
            select(OrderStatusHistory)
            .where(OrderStatusHistory.order_id == order_id)
            .order_by(OrderStatusHistory.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    def serialize_order(order: SalesOrder) -> dict[str, Any]:
        return {
            "id": str(order.id),
            "business_id": str(order.business_id),
            "location_id": str(order.location_id),
            "customer_contact_id": (
                str(order.customer_contact_id) if order.customer_contact_id else None
            ),
            "order_number": order.order_number,
            "status": order.status,
            "payment_method": order.payment_method,
            "payment_status": order.payment_status,
            "currency": order.currency,
            "subtotal": float(order.subtotal),
            "tax_amount": float(order.tax_amount),
            "discount_amount": float(order.discount_amount),
            "total_amount": float(order.total_amount),
            "internal_reference": order.internal_reference,
            "cancellation_reason": order.cancellation_reason,
            "version": order.version,
            "created_at": order.created_at.isoformat(),
            "updated_at": order.updated_at.isoformat(),
        }

    @staticmethod
    def serialize_line_item(item: OrderLineItem) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "order_id": str(item.order_id),
            "offering_id": str(item.offering_id),
            "variant_id": str(item.variant_id) if item.variant_id else None,
            "title": item.title,
            "sku": item.sku,
            "unit_price": float(item.unit_price),
            "quantity": item.quantity,
            "tax_rate": float(item.tax_rate) if item.tax_rate is not None else None,
            "line_subtotal": float(item.line_subtotal),
            "line_tax": float(item.line_tax),
            "line_total": float(item.line_total),
            "track_inventory": item.track_inventory,
            "quantity_reserved": item.quantity_reserved,
            "quantity_deducted": item.quantity_deducted,
            "sort_order": item.sort_order,
        }

    @staticmethod
    def serialize_status_history(entry: OrderStatusHistory) -> dict[str, Any]:
        return {
            "id": str(entry.id),
            "order_id": str(entry.order_id),
            "from_status": entry.from_status,
            "to_status": entry.to_status,
            "actor_identity_id": (
                str(entry.actor_identity_id) if entry.actor_identity_id else None
            ),
            "reason": entry.reason,
            "created_at": entry.created_at.isoformat(),
        }

    @staticmethod
    def serialize_note(note: OrderNote) -> dict[str, Any]:
        return {
            "id": str(note.id),
            "order_id": str(note.order_id),
            "body": note.body,
            "author_identity_id": str(note.author_identity_id),
            "version": note.version,
            "created_at": note.created_at.isoformat(),
            "updated_at": note.updated_at.isoformat(),
        }

    @staticmethod
    def serialize_order_detail(
        order: SalesOrder,
        *,
        line_items: list[OrderLineItem],
    ) -> dict[str, Any]:
        data = OrderResolver.serialize_order(order)
        data["items"] = [OrderResolver.serialize_line_item(i) for i in line_items]
        return data
