"""Order lifecycle and status transitions (Stage 6)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError
from platform_core.gates import assert_business_mutable
from platform_core.models import OrderLineItem, OrderStatusHistory, SalesOrder
from platform_core.resolvers.order_resolver import OrderResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.customer_timeline import CustomerTimelineService
from platform_core.services.inventory import InventoryService
from platform_core.services.outbox import OutboxService
from platform_core.validation.order import STATUS_EVENT_MAP, validate_status_transition_payload


class OrderLifecycleService:
    @staticmethod
    async def _record_history(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        order_id: uuid.UUID,
        from_status: str | None,
        to_status: str,
        actor_id: uuid.UUID,
        reason: str | None,
    ) -> OrderStatusHistory:
        entry = OrderStatusHistory(
            business_id=business_id,
            order_id=order_id,
            from_status=from_status,
            to_status=to_status,
            actor_identity_id=actor_id,
            reason=reason,
        )
        session.add(entry)
        await session.flush()
        return entry

    @staticmethod
    async def _release_line_reservations(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        order: SalesOrder,
        line_items: list[OrderLineItem],
        actor_id: uuid.UUID,
        correlation_id: str,
        reason: str,
    ) -> None:
        for item in line_items:
            if not item.track_inventory:
                continue
            pending = item.quantity_reserved - item.quantity_deducted
            if pending <= 0:
                continue
            await InventoryService.release_reservation_for_order(
                session,
                business_id=business_id,
                offering_id=item.offering_id,
                location_id=order.location_id,
                variant_id=item.variant_id,
                quantity=pending,
                actor_id=actor_id,
                correlation_id=correlation_id,
                order_id=order.id,
                reason=reason,
            )
            item.quantity_reserved -= pending

    @staticmethod
    async def _deduct_line_stock(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        order: SalesOrder,
        line_items: list[OrderLineItem],
        actor_id: uuid.UUID,
        correlation_id: str,
    ) -> None:
        for item in line_items:
            if not item.track_inventory:
                continue
            pending = item.quantity - item.quantity_deducted
            if pending <= 0:
                continue
            await InventoryService.deduct_reserved_for_order(
                session,
                business_id=business_id,
                offering_id=item.offering_id,
                location_id=order.location_id,
                variant_id=item.variant_id,
                quantity=pending,
                actor_id=actor_id,
                correlation_id=correlation_id,
                order_id=order.id,
                reason=f"Order {order.order_number} completed",
            )
            item.quantity_deducted += pending
            item.quantity_reserved = max(item.quantity_reserved - pending, 0)

    @staticmethod
    async def _publish_status_change(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        order: SalesOrder,
        actor_id: uuid.UUID,
        correlation_id: str,
        before_state: dict[str, Any],
        after_state: dict[str, Any],
        to_status: str,
        reason: str | None,
    ) -> None:
        event_type = STATUS_EVENT_MAP.get(to_status, "order.updated")
        payload: dict[str, Any] = {
            "business_id": str(business_id),
            "order_id": str(order.id),
            "order_number": order.order_number,
            "status": order.status,
            "customer_contact_id": (
                str(order.customer_contact_id) if order.customer_contact_id else None
            ),
            "total_amount": float(order.total_amount),
            "reason": reason,
            "after": after_state,
        }
        await OutboxService.publish(
            session,
            event_type=event_type,
            payload=payload,
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await OutboxService.publish(
            session,
            event_type="order.updated",
            payload=payload,
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type=event_type,
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="order",
            resource_id=order.id,
            action=to_status,
            before_state=before_state,
            after_state=after_state,
        )
        if order.customer_contact_id:
            await CustomerTimelineService.record_entry(
                session,
                business_id=business_id,
                contact_id=order.customer_contact_id,
                activity_type=f"order.{to_status}",
                resource_type="order",
                resource_id=order.id,
                location_id=order.location_id,
                summary={
                    "order_number": order.order_number,
                    "status": to_status,
                    "total_amount": float(order.total_amount),
                },
            )

    @staticmethod
    def _check_version(order: SalesOrder, expected_version: int | None) -> None:
        if expected_version is None:
            return
        if order.version != expected_version:
            raise ConflictError(
                "Stale order version",
                details={
                    "expected_version": expected_version,
                    "current_version": order.version,
                },
            )

    @staticmethod
    async def transition_status(
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
        assert_business_mutable(business.state, action="update order status")
        order = await OrderResolver.resolve(session, business_id=business_id, order_id=order_id)
        OrderLifecycleService._check_version(order, expected_version)
        validated = validate_status_transition_payload(payload, current_status=order.status)
        target = validated["status"]
        reason = validated["reason"]
        line_items = await OrderResolver.load_line_items(session, order_id=order.id)
        before = OrderResolver.serialize_order_detail(order, line_items=line_items)
        from_status = order.status

        if target in {"cancelled", "rejected"}:
            await OrderLifecycleService._release_line_reservations(
                session,
                business_id=business_id,
                order=order,
                line_items=line_items,
                actor_id=actor_id,
                correlation_id=correlation_id,
                reason=reason or target,
            )
            order.cancellation_reason = reason
            order.cancelled_by = actor_id

        if target == "completed":
            await OrderLifecycleService._deduct_line_stock(
                session,
                business_id=business_id,
                order=order,
                line_items=line_items,
                actor_id=actor_id,
                correlation_id=correlation_id,
            )
            if order.payment_method in {"cod", "pay_at_business", "pay_later"}:
                if order.payment_status == "pending":
                    order.payment_status = "pending_offline"

        order.status = target
        order.version += 1
        await session.flush()
        await OrderLifecycleService._record_history(
            session,
            business_id=business_id,
            order_id=order.id,
            from_status=from_status,
            to_status=target,
            actor_id=actor_id,
            reason=reason,
        )
        after = OrderResolver.serialize_order_detail(order, line_items=line_items)
        await OrderLifecycleService._publish_status_change(
            session,
            business_id=business_id,
            order=order,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state=after,
            to_status=target,
            reason=reason,
        )
        return order
