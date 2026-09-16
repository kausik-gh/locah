"""Platform orders APIs (Stage 6)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.permissions import (
    ORDERS_CANCEL,
    ORDERS_CREATE,
    ORDERS_READ,
    ORDERS_UPDATE_STATUS,
)
from platform_core.resolvers.order_resolver import OrderResolver
from platform_core.services.order import OrderService
from platform_core.services.order_lifecycle import OrderLifecycleService
from platform_core.services.order_note import OrderNoteService

router = APIRouter(prefix="/v1/platform/businesses", tags=["orders"])


class VersionedBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int | None = Field(default=None, ge=1)


class OrderLineItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offering_id: UUID
    variant_id: UUID | None = None
    quantity: int = Field(ge=1)
    unit_price: float | None = Field(default=None, ge=0)


class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID
    customer_contact_id: UUID | None = None
    payment_method: str = "cod"
    currency: str = "INR"
    discount_amount: float = Field(default=0, ge=0)
    internal_reference: str | None = None
    idempotency_key: str | None = None
    items: list[OrderLineItemInput] = Field(min_length=1)


class PatchOrderRequest(VersionedBody):
    internal_reference: str | None = None
    payment_status: str | None = None


class StatusTransitionRequest(VersionedBody):
    status: str
    reason: str | None = None


class CancelOrderRequest(VersionedBody):
    reason: str


class CreateNoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str


def _patch_payload(body: BaseModel) -> dict[str, Any]:
    data = body.model_dump(exclude_unset=True)
    version = data.pop("version", None)
    return {"payload": data, "version": version}


@router.get("/{business_id}/orders")
async def list_orders(
    business_id: UUID,
    status: str | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=120),
    customer_contact_id: UUID | None = Query(default=None),
    location_id: UUID | None = Query(default=None),
    actor: BusinessActorContext = Depends(require_business_actor(ORDERS_READ, "orders")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    orders = await OrderService.list_for_business(
        session,
        business_id,
        status=status,
        search=search,
        customer_contact_id=customer_contact_id,
        location_id=location_id,
    )
    return {
        "data": [OrderService.serialize_order(o) for o in orders],
        "meta": {"correlation_id": actor.request.correlation_id, "count": len(orders)},
    }


@router.post("/{business_id}/orders")
async def create_order(
    business_id: UUID,
    body: CreateOrderRequest,
    actor: BusinessActorContext = Depends(require_business_actor(ORDERS_CREATE, "orders")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    order = await OrderService.create_order(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(),
    )
    await session.commit()
    data = await OrderService.serialize_order_with_items(session, order)
    return {
        "data": data,
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/orders/{order_id}")
async def get_order(
    business_id: UUID,
    order_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(ORDERS_READ, "orders")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    order = await OrderResolver.resolve(session, business_id=business_id, order_id=order_id)
    data = await OrderService.serialize_order_with_items(session, order)
    return {
        "data": data,
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.patch("/{business_id}/orders/{order_id}")
async def patch_order(
    business_id: UUID,
    order_id: UUID,
    body: PatchOrderRequest,
    actor: BusinessActorContext = Depends(require_business_actor(ORDERS_UPDATE_STATUS, "orders")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    parsed = _patch_payload(body)
    order = await OrderService.patch_order(
        session,
        business_id=business_id,
        order_id=order_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=parsed["payload"],
        expected_version=parsed["version"],
    )
    await session.commit()
    data = await OrderService.serialize_order_with_items(session, order)
    return {
        "data": data,
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/orders/{order_id}/status")
async def transition_order_status(
    business_id: UUID,
    order_id: UUID,
    body: StatusTransitionRequest,
    actor: BusinessActorContext = Depends(require_business_actor(ORDERS_UPDATE_STATUS, "orders")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    order = await OrderLifecycleService.transition_status(
        session,
        business_id=business_id,
        order_id=order_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(exclude={"version"}),
        expected_version=body.version,
    )
    await session.commit()
    data = await OrderService.serialize_order_with_items(session, order)
    return {
        "data": data,
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/orders/{order_id}/cancel")
async def cancel_order(
    business_id: UUID,
    order_id: UUID,
    body: CancelOrderRequest,
    actor: BusinessActorContext = Depends(require_business_actor(ORDERS_CANCEL, "orders")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    order = await OrderLifecycleService.transition_status(
        session,
        business_id=business_id,
        order_id=order_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload={"status": "cancelled", "reason": body.reason},
        expected_version=body.version,
    )
    await session.commit()
    data = await OrderService.serialize_order_with_items(session, order)
    return {
        "data": data,
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/orders/{order_id}/complete")
async def complete_order(
    business_id: UUID,
    order_id: UUID,
    body: VersionedBody,
    actor: BusinessActorContext = Depends(require_business_actor(ORDERS_UPDATE_STATUS, "orders")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    order = await OrderLifecycleService.transition_status(
        session,
        business_id=business_id,
        order_id=order_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload={"status": "completed"},
        expected_version=body.version,
    )
    await session.commit()
    data = await OrderService.serialize_order_with_items(session, order)
    return {
        "data": data,
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/orders/{order_id}/history")
async def get_order_history(
    business_id: UUID,
    order_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(ORDERS_READ, "orders")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    history = await OrderService.get_status_history(
        session, business_id=business_id, order_id=order_id
    )
    return {
        "data": [OrderResolver.serialize_status_history(h) for h in history],
        "meta": {"correlation_id": actor.request.correlation_id, "count": len(history)},
    }


@router.get("/{business_id}/orders/{order_id}/notes")
async def list_order_notes(
    business_id: UUID,
    order_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(ORDERS_READ, "orders")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    notes = await OrderNoteService.list_for_order(
        session, business_id=business_id, order_id=order_id
    )
    return {
        "data": [OrderNoteService.serialize(n) for n in notes],
        "meta": {"correlation_id": actor.request.correlation_id, "count": len(notes)},
    }


@router.post("/{business_id}/orders/{order_id}/notes")
async def create_order_note(
    business_id: UUID,
    order_id: UUID,
    body: CreateNoteRequest,
    actor: BusinessActorContext = Depends(require_business_actor(ORDERS_UPDATE_STATUS, "orders")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    note = await OrderNoteService.create_note(
        session,
        business_id=business_id,
        order_id=order_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        body=body.body,
    )
    await session.commit()
    return {
        "data": OrderNoteService.serialize(note),
        "meta": {"correlation_id": actor.request.correlation_id},
    }
