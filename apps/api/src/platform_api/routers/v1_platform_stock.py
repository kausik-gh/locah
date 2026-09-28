"""Stock depth (Capability Universe §15.1) — P1-10A.

The work behind one stock number: receive (batch, expiry, serials, cost,
buying unit), wastage with a reason, cutting runs against owner-entered yields,
counts whose variances need approval, reorder levels, expiry and warranty
lookup. Location-scoped staff see and change only their locations (server
check here, restrictive RLS underneath).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.exceptions import ConflictError, OutsideLocationScope, ResourceNotFound, ValidationError
from platform_core.models import InventorySerial, Offering, OrderLineItem, SalesOrder
from platform_core.permissions import (
    CUSTOMERS_READ,
    INVENTORY_ADJUST,
    INVENTORY_APPROVE,
    INVENTORY_COST,
    INVENTORY_READ,
    OFFERINGS_UPDATE,
    ORDERS_UPDATE_STATUS,
)
from platform_core.stock.ledger import clean_serials
from platform_core.stock.service import StockService

router = APIRouter(prefix="/v1/platform/businesses", tags=["stock"])
MODULE = "inventory"


def _meta(actor: BusinessActorContext) -> dict[str, str]:
    return {"correlation_id": actor.request.correlation_id}


def _scope(actor: BusinessActorContext) -> list[UUID] | None:
    return cast(list[UUID] | None, actor.actor_membership.location_scope)


def _can(actor: BusinessActorContext, permission: str) -> bool:
    return permission in actor.request.effective_permissions


class ReceiveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID
    offering_id: UUID
    variant_id: UUID | None = None
    quantity: int | None = Field(default=None, ge=1, le=100_000_000)
    buy_unit: str | None = Field(default=None, max_length=30)
    buy_quantity: int | None = Field(default=None, ge=1, le=1_000_000)
    total_cost_paise: int | None = Field(default=None, ge=0, le=10_000_000_000)
    batch_code: str | None = Field(default=None, max_length=60)
    expires_on: date | None = None
    serials: list[str] | str | None = None
    note: str | None = Field(default=None, max_length=200)


class WastageBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_record_id: UUID
    quantity: int | None = Field(default=None, ge=1, le=100_000_000)
    reason_code: Literal["expired", "damaged", "trim_loss", "spoiled", "theft", "sample", "other"]
    batch_id: UUID | None = None
    serials: list[str] | str | None = None
    note: str | None = Field(default=None, max_length=200)


class WriteOffBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=200)


class YieldBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_offering_id: UUID
    output_offering_id: UUID
    yield_percent: float = Field(gt=0, le=100)
    note: str | None = Field(default=None, max_length=200)


class OutputLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offering_id: UUID
    quantity: int = Field(ge=0, le=100_000_000)


class ConvertBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID
    source_offering_id: UUID
    source_quantity: int = Field(ge=1, le=100_000_000)
    outputs: list[OutputLine] = Field(min_length=1, max_length=12)
    note: str | None = Field(default=None, max_length=300)
    idempotency_key: str | None = Field(default=None, max_length=80)


class ReorderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reorder_min: int | None = Field(default=None, ge=0)
    reorder_max: int | None = Field(default=None, ge=0)


class BuyUnit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=30)
    quantity: int = Field(ge=1, le=100_000_000)


class ItemBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    track_inventory: bool | None = None
    batch_tracked: bool | None = None
    serial_tracked: bool | None = None
    warranty_months: int | None = Field(default=None, ge=0, le=240)
    buy_units: list[BuyUnit] | None = Field(default=None, max_length=6)


class CountBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID
    category_id: UUID | None = None
    label: str | None = Field(default=None, max_length=120)


class CountLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_record_id: UUID
    counted_quantity: int | None = Field(default=None, ge=0, le=100_000_000)


class CountLinesBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: list[CountLine] = Field(min_length=1, max_length=500)


class DecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approve: bool
    note: str | None = Field(default=None, max_length=300)


class OrderSerialsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: UUID
    serials: list[str] | str


# ------------------------------------------------------------------ reading
@router.get("/{business_id}/stock/profile")
async def stock_profile(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await StockService.profile(session, business_id)
    data["can"] = {"adjust": _can(actor, INVENTORY_ADJUST), "approve": _can(actor, INVENTORY_APPROVE),
                   "cost": _can(actor, INVENTORY_COST), "setup": _can(actor, OFFERINGS_UPDATE)}
    return {"data": data, "meta": _meta(actor)}


@router.get("/{business_id}/stock")
async def stock_overview(
    business_id: UUID,
    location_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None, max_length=80),
    status: Literal["available", "low_stock", "out_of_stock"] | None = Query(default=None),
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    scope = _scope(actor)
    if location_id is not None and scope is not None and location_id not in scope:
        raise OutsideLocationScope()
    data = await StockService.overview(session, business_id, allowed=scope, location_id=location_id, q=q,
                                       status=status, can_see_cost=_can(actor, INVENTORY_COST))
    return {"data": data, "meta": _meta(actor)}


@router.get("/{business_id}/stock/items")
async def stock_items(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return {"data": await StockService.items(session, business_id), "meta": _meta(actor)}


@router.get("/{business_id}/stock/records/{record_id}")
async def stock_record(
    business_id: UUID, record_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await StockService.record_detail(session, business_id, record_id, _scope(actor),
                                            can_see_cost=_can(actor, INVENTORY_COST))
    return {"data": data, "meta": _meta(actor)}


@router.get("/{business_id}/stock/expiring")
async def stock_expiring(
    business_id: UUID, days: int = Query(default=30, ge=0, le=365), location_id: UUID | None = Query(default=None),
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await StockService.expiring(session, business_id, allowed=_scope(actor), days=days,
                                       location_id=location_id)
    return {"data": data, "meta": _meta(actor)}


@router.get("/{business_id}/stock/serials/{serial}")
async def serial_lookup(
    business_id: UUID, serial: str,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await StockService.serial_lookup(session, business_id, serial,
                                            can_see_customer=_can(actor, CUSTOMERS_READ))
    return {"data": data, "meta": _meta(actor)}


@router.get("/{business_id}/stock/wastage")
async def wastage_summary(
    business_id: UUID, days: int = Query(default=30, ge=1, le=365),
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await StockService.wastage_summary(session, business_id, _scope(actor), days=days,
                                              can_see_cost=_can(actor, INVENTORY_COST))
    return {"data": data, "meta": _meta(actor)}


@router.get("/{business_id}/stock/yields")
async def list_yields(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return {"data": await StockService.list_yields(session, business_id), "meta": _meta(actor)}


@router.get("/{business_id}/stock/conversions")
async def list_conversions(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return {"data": await StockService.recent_conversions(session, business_id, _scope(actor)),
            "meta": _meta(actor)}


@router.get("/{business_id}/stock/counts")
async def list_counts(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return {"data": await StockService.list_counts(session, business_id, _scope(actor)), "meta": _meta(actor)}


@router.get("/{business_id}/stock/counts/{count_id}")
async def get_count(
    business_id: UUID, count_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await StockService.get_count(session, business_id, count_id, _scope(actor),
                                        blind=not _can(actor, INVENTORY_APPROVE))
    return {"data": data, "meta": _meta(actor)}


# ------------------------------------------------------------------ changing
async def _commit(session: AsyncSession, actor: BusinessActorContext, data: Any) -> dict[str, Any]:
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/stock/receipts")
async def receive(
    business_id: UUID, body: ReceiveBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_ADJUST, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    # What it cost comes off the supplier's bill, so whoever receives may enter
    # it; only inventory.cost may read stock value back (§7.2 store keeper).
    data = await StockService.receive(session, business_id, actor.request.identity_id, body.model_dump(),
                                      _scope(actor))
    return await _commit(session, actor, data)


@router.post("/{business_id}/stock/wastage")
async def record_wastage(
    business_id: UUID, body: WastageBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_ADJUST, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await StockService.record_wastage(session, business_id, actor.request.identity_id, body.model_dump(),
                                             _scope(actor))
    return await _commit(session, actor, data)


@router.post("/{business_id}/stock/batches/{batch_id}/write-off")
async def write_off_batch(
    business_id: UUID, batch_id: UUID, body: WriteOffBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_ADJUST, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await StockService.write_off_batch(session, business_id, actor.request.identity_id, batch_id,
                                              body.note, _scope(actor))
    return await _commit(session, actor, data)


@router.put("/{business_id}/stock/yields")
async def set_yield(
    business_id: UUID, body: YieldBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_ADJUST, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await StockService.set_yield(session, business_id, actor.request.identity_id, body.model_dump())
    return await _commit(session, actor, data)


@router.post("/{business_id}/stock/conversions")
async def convert(
    business_id: UUID, body: ConvertBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_ADJUST, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await StockService.convert(session, business_id, actor.request.identity_id, body.model_dump(),
                                      _scope(actor))
    return await _commit(session, actor, data)


@router.patch("/{business_id}/stock/records/{record_id}/reorder")
async def set_reorder(
    business_id: UUID, record_id: UUID, body: ReorderBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_ADJUST, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await StockService.set_reorder(session, business_id, actor.request.identity_id, record_id,
                                          body.reorder_min, body.reorder_max, _scope(actor))
    return await _commit(session, actor, data)


@router.patch("/{business_id}/stock/items/{offering_id}")
async def configure_item(
    business_id: UUID, offering_id: UUID, body: ItemBody,
    actor: BusinessActorContext = Depends(require_business_actor(OFFERINGS_UPDATE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await StockService.configure_item(session, business_id, actor.request.identity_id, offering_id,
                                             body.model_dump(exclude_unset=True))
    return await _commit(session, actor, data)


@router.post("/{business_id}/stock/counts")
async def start_count(
    business_id: UUID, body: CountBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_ADJUST, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await StockService.start_count(session, business_id, actor.request.identity_id, body.model_dump(),
                                          _scope(actor))
    return await _commit(session, actor, data)


@router.put("/{business_id}/stock/counts/{count_id}/lines")
async def record_count(
    business_id: UUID, count_id: UUID, body: CountLinesBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_ADJUST, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await StockService.record_count(session, business_id, actor.request.identity_id, count_id,
                                           [line.model_dump() for line in body.lines], _scope(actor))
    return await _commit(session, actor, data)


@router.post("/{business_id}/stock/counts/{count_id}/submit")
async def submit_count(
    business_id: UUID, count_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_ADJUST, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await StockService.submit_count(session, business_id, actor.request.identity_id, count_id, _scope(actor))
    return await _commit(session, actor, data)


@router.post("/{business_id}/stock/counts/{count_id}/decision")
async def decide_count(
    business_id: UUID, count_id: UUID, body: DecisionBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_APPROVE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await StockService.decide_count(session, business_id, actor.request.identity_id, count_id,
                                           body.approve, body.note, _scope(actor))
    return await _commit(session, actor, data)


@router.post("/{business_id}/stock/orders/{order_id}/serials")
async def assign_order_serials(
    business_id: UUID, order_id: UUID, body: OrderSerialsBody,
    actor: BusinessActorContext = Depends(require_business_actor(ORDERS_UPDATE_STATUS, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Serial numbers for an online order's line, recorded while packing; they
    are marked sold when the order completes (§15.1 serial captured at sale)."""
    order = await session.get(SalesOrder, order_id)
    if order is None or order.business_id != business_id:
        raise ResourceNotFound("Order")
    scope = _scope(actor)
    if scope is not None and order.location_id not in scope:
        raise OutsideLocationScope()
    line = await session.get(OrderLineItem, body.line_id)
    if line is None or line.order_id != order.id:
        raise ResourceNotFound("Order line")
    offering = await session.get(Offering, line.offering_id)
    if offering is None or not offering.serial_tracked:
        raise ValidationError("This item does not keep serial numbers")
    if order.status in {"completed", "cancelled"}:
        raise ConflictError("Serials are recorded before the order completes")
    serials = clean_serials(body.serials)
    if len(serials) > int(line.stock_quantity):
        raise ValidationError(f"{line.stock_quantity} unit(s) on this line")
    for serial in serials:
        row = (await session.execute(select(InventorySerial).where(
            InventorySerial.business_id == business_id, InventorySerial.offering_id == offering.id,
            InventorySerial.serial == serial))).scalars().first()
        if row is None or row.status != "in_stock" or row.location_id != order.location_id:
            raise ValidationError(f"Serial {serial} is not in stock at this location")
    line.serials = serials
    await session.flush()
    return await _commit(session, actor, {"line_id": str(line.id), "serials": serials})
