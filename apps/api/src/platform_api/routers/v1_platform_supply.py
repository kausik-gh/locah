"""Buying, expenses and donations.

These routes sit on the supply services. They do not collect customer payments
and they do not change stock except through a goods receipt, which the service
posts to inventory.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.permissions import (
    DONATIONS_READ,
    DONATIONS_WRITE,
    EXPENSES_READ,
    EXPENSES_WRITE,
    PROCUREMENT_APPROVE,
    PROCUREMENT_CREATE,
    PROCUREMENT_READ,
    PROCUREMENT_RECEIVE,
)
from platform_core.procurement.service import SupplyService

router = APIRouter(prefix="/v1/platform/businesses", tags=["supply"])


def _plain(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


class PrepareBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supplier_id: UUID
    offering_id: UUID
    demand: int = Field(gt=0, le=1_000_000)
    location_id: UUID | None = None
    pack_size: int = Field(default=1, ge=1, le=10_000)
    moq: int = Field(default=1, ge=1, le=1_000_000)


class ReceiveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    location_id: UUID
    received_quantity: int = Field(ge=0, le=1_000_000)
    damaged_quantity: int = Field(default=0, ge=0, le=1_000_000)
    idempotency_key: str = Field(min_length=4, max_length=80)


class SupplierBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    contact_name: str | None = None
    phone: str | None = None
    connection: str = "off_network"
    credit_days: int = Field(default=0, ge=0, le=365)


class ExpenseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str = Field(min_length=1, max_length=80)
    amount_paise: int = Field(ge=0, le=10_000_000_000)
    method: str = "cash"
    payee: str | None = None
    notes: str | None = None
    petty_cash: bool = False


class RecipeLineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_offering_id: UUID
    quantity_per: float = Field(gt=0, le=100000)
    yield_ratio: float = Field(default=1, gt=0, le=100)


class RecipeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offering_id: UUID
    name: str | None = Field(default=None, max_length=120)
    lines: list[RecipeLineBody] = Field(min_length=1, max_length=60)


class CauseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)


class GiftBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cause_id: UUID
    donor_name: str = Field(min_length=1, max_length=160)
    amount_paise: int = Field(gt=0, le=10_000_000_000)
    payment_id: UUID | None = None


@router.get("/{business_id}/buying")
async def buying_home(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(PROCUREMENT_READ, "procurement")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await SupplyService.buying_home(session, business_id, None)
    return {"data": _plain(data), "meta": {"correlation_id": actor.request.correlation_id}}


@router.get("/{business_id}/buying/incoming")
async def incoming_demand(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(PROCUREMENT_READ, "procurement")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await SupplyService.incoming_demand(session, business_id, None)
    return {"data": _plain(data), "meta": {"correlation_id": actor.request.correlation_id}}


@router.post("/{business_id}/buying/prepare")
async def prepare_order(
    business_id: UUID,
    body: PrepareBody,
    actor: BusinessActorContext = Depends(require_business_actor(PROCUREMENT_CREATE, "procurement")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await SupplyService.prepare_order(
        session, business_id, actor.request.identity_id, body.model_dump(), None,
    )
    await session.commit()
    return {"data": _plain(data), "meta": {"correlation_id": actor.request.correlation_id}}


@router.post("/{business_id}/buying/requisitions/{requisition_id}/approve")
async def approve_requisition(
    business_id: UUID,
    requisition_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(PROCUREMENT_APPROVE, "procurement")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await SupplyService.approve_requisition(
        session, business_id, actor.request.identity_id, requisition_id,
        buyer_label="This business", item_label="Item", permissions=None,
    )
    await session.commit()
    return {"data": _plain(data), "meta": {"correlation_id": actor.request.correlation_id}}


@router.post("/{business_id}/buying/purchase-orders/{purchase_order_id}/approve")
async def approve_order(
    business_id: UUID,
    purchase_order_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(PROCUREMENT_APPROVE, "procurement")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await SupplyService.approve_purchase_order(
        session, business_id, actor.request.identity_id, purchase_order_id, None,
    )
    await SupplyService.send_purchase_order(
        session, business_id, actor.request.identity_id, purchase_order_id,
        buyer_label="This business", item_label="Item", permissions=None,
    )
    await session.commit()
    return {"data": _plain(data), "meta": {"correlation_id": actor.request.correlation_id}}


@router.post("/{business_id}/buying/purchase-orders/{purchase_order_id}/receive")
async def receive_order(
    business_id: UUID,
    purchase_order_id: UUID,
    body: ReceiveBody,
    actor: BusinessActorContext = Depends(require_business_actor(PROCUREMENT_RECEIVE, "procurement")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await SupplyService.receive_goods(
        session, business_id, actor.request.identity_id, purchase_order_id, body.model_dump(), None, None,
    )
    await session.commit()
    return {"data": _plain(data), "meta": {"correlation_id": actor.request.correlation_id}}


@router.post("/{business_id}/suppliers")
async def create_supplier(
    business_id: UUID,
    body: SupplierBody,
    actor: BusinessActorContext = Depends(require_business_actor(PROCUREMENT_CREATE, "procurement")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await SupplyService.create_supplier(
        session, business_id, actor.request.identity_id, body.model_dump(), None,
    )
    await session.commit()
    return {"data": _plain(data), "meta": {"correlation_id": actor.request.correlation_id}}


@router.get("/{business_id}/recipes")
async def list_recipes(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(PROCUREMENT_READ, "recipes")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await SupplyService.list_boms(session, business_id, None)
    return {"data": _plain(data), "meta": {"correlation_id": actor.request.correlation_id}}


@router.put("/{business_id}/recipes")
async def save_recipe(
    business_id: UUID,
    body: RecipeBody,
    actor: BusinessActorContext = Depends(require_business_actor(PROCUREMENT_CREATE, "recipes")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """One recipe per dish; saving again replaces its ingredients. The kitchen's
    finished preparations use it (kitchen.preparation.completed → stock, once)."""
    payload = body.model_dump(mode="json")
    data = await SupplyService.save_bom(session, business_id, payload, None)
    await session.commit()
    return {"data": _plain(data), "meta": {"correlation_id": actor.request.correlation_id}}


@router.get("/{business_id}/expenses/summary")
async def expense_summary(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(EXPENSES_READ, "expenses")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await SupplyService.expense_totals(session, business_id, None)
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.post("/{business_id}/expenses")
async def record_expense(
    business_id: UUID,
    body: ExpenseBody,
    actor: BusinessActorContext = Depends(require_business_actor(EXPENSES_WRITE, "expenses")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await SupplyService.record_expense(
        session, business_id, actor.request.identity_id, body.model_dump(), None,
    )
    await session.commit()
    return {"data": _plain(data), "meta": {"correlation_id": actor.request.correlation_id}}


@router.get("/{business_id}/donations")
async def donations(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(DONATIONS_READ, "donations")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    causes = await SupplyService.list_causes(session, business_id, None)
    gifts = await SupplyService.list_gifts(session, business_id, None)
    return {
        "data": {"causes": _plain(causes), "gifts": _plain(gifts)},
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/donations/causes")
async def open_cause(
    business_id: UUID,
    body: CauseBody,
    actor: BusinessActorContext = Depends(require_business_actor(DONATIONS_WRITE, "donations")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await SupplyService.open_cause(session, business_id, body.name, None)
    await session.commit()
    return {"data": _plain(data), "meta": {"correlation_id": actor.request.correlation_id}}


@router.post("/{business_id}/donations/gifts")
async def receive_gift(
    business_id: UUID,
    body: GiftBody,
    actor: BusinessActorContext = Depends(require_business_actor(DONATIONS_WRITE, "donations")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await SupplyService.receive_donation(session, business_id, body.model_dump(), None)
    await session.commit()
    return {"data": _plain(data), "meta": {"correlation_id": actor.request.correlation_id}}
