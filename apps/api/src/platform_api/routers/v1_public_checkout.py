"""Public checkout + order tracking (WEB-007 / WEB-008) — Doc 12 §11.2."""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_core.services.checkout import CheckoutService
from platform_core.services.fulfilment import FulfilmentService

router = APIRouter(prefix="/v1/public", tags=["checkout"])


class GuestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    email: str
    phone: str | None = None


class CheckoutItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offering_id: UUID
    variant_id: UUID | None = None
    quantity: int = Field(default=1, ge=1, le=100)
    unit_price: float | None = None


class PlaceOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CheckoutItem]
    fulfilment_mode: str
    payment_method: str = "cod"
    location_id: UUID | None = None
    delivery_address: dict[str, Any] | None = None
    guest: GuestPayload
    currency: str = "INR"
    idempotency_key: str | None = None


class QuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delivery_address: dict[str, Any]


@router.get("/websites/{slug}/offerings")
async def public_offerings(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await CheckoutService.list_public_offerings(session, slug=slug)
    return {"data": data, "meta": {"count": len(data["offerings"])}}


@router.get("/websites/{slug}/checkout/options")
async def checkout_options(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await CheckoutService.checkout_options(session, slug=slug)
    return {"data": data, "meta": {}}


@router.post("/websites/{slug}/checkout/quote")
async def checkout_quote(
    slug: str,
    body: QuoteRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await CheckoutService.quote_delivery(
        session, slug=slug, address=body.delivery_address
    )
    return {"data": data, "meta": {}}


@router.post("/websites/{slug}/checkout")
async def place_checkout_order(
    slug: str,
    body: PlaceOrderRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await CheckoutService.place_order(
        session,
        slug=slug,
        correlation_id=str(uuid.uuid4()),
        payload=body.model_dump(mode="json"),
    )
    await session.commit()
    return {"data": data, "meta": {}}


@router.get("/orders/{order_id}/tracking")
async def public_order_tracking(
    order_id: UUID,
    token: str = Query(..., min_length=8),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await FulfilmentService.get_tracking(
        session, order_id=order_id, token=token
    )
    return {"data": data, "meta": {}}
