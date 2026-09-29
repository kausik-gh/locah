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
    PROCUREMENT_CREATE,
    PROCUREMENT_READ,
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
