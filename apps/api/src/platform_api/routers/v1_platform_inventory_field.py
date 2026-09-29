"""Inventory field APIs: transfers, van stock, job consumption, client stock, customer assets.

The jobs lane calls consume and return-unused. This router does not import jobs.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.permissions import CUSTOMERS_READ, CUSTOMERS_UPDATE, INVENTORY_ADJUST, INVENTORY_APPROVE, INVENTORY_READ
from platform_core.services.inventory_field import InventoryFieldService

router = APIRouter(prefix="/v1/platform/businesses", tags=["inventory-field"])
INVENTORY = "inventory"
CUSTOMERS = "customer-relationships"


def _meta(actor: BusinessActorContext) -> dict[str, str]:
    return {"correlation_id": actor.request.correlation_id}


def _scope(actor: BusinessActorContext) -> list[UUID] | None:
    return actor.actor_membership.location_scope


class LineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offering_id: UUID
    variant_id: UUID | None = None
    quantity: int = Field(ge=1, le=100_000_000)


class TransferBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_location_id: UUID
    destination_location_id: UUID
    lines: list[LineBody] = Field(min_length=1, max_length=40)
    requires_approval: bool = False
    note: str | None = Field(default=None, max_length=300)
    idempotency_key: str = Field(min_length=8, max_length=80)


class KeyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=8, max_length=80)


class JobBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID
    job_ref: UUID
    lines: list[LineBody] = Field(min_length=1, max_length=40)
    idempotency_key: str = Field(min_length=8, max_length=80)


class ClientStockBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID
    customer_id: UUID
    offering_id: UUID
    variant_id: UUID | None = None
    quantity: int = Field(ge=1, le=100_000_000)
    direction: Literal["inward", "outward"]
    note: str | None = Field(default=None, max_length=300)
    idempotency_key: str = Field(min_length=8, max_length=80)


class AssetBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: UUID
    asset_kind: Literal["vehicle", "device", "ac_unit", "machine", "pet", "policy", "other"]
    label: str = Field(min_length=1, max_length=160)
    identifier: str | None = Field(default=None, max_length=80)
    traits: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=500)
    idempotency_key: str | None = Field(default=None, max_length=80)


async def _commit(session: AsyncSession, actor: BusinessActorContext, data: Any) -> dict[str, Any]:
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.get("/{business_id}/inventory/transfers")
async def list_transfers(
    business_id: UUID,
    status: str | None = Query(default=None),
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_READ, INVENTORY)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await InventoryFieldService.list_transfers(session, business_id, _scope(actor), status=status)
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/inventory/transfers")
async def request_transfer(
    business_id: UUID,
    body: TransferBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_ADJUST, INVENTORY)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await InventoryFieldService.request_transfer(
        session, business_id, actor.request.identity_id, body.model_dump(mode="json"), _scope(actor))
    return await _commit(session, actor, data)


@router.post("/{business_id}/inventory/transfers/{transfer_id}/approve")
async def approve_transfer(
    business_id: UUID,
    transfer_id: UUID,
    body: KeyBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_APPROVE, INVENTORY)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await InventoryFieldService.approve(
        session, business_id, actor.request.identity_id, transfer_id, body.model_dump(), _scope(actor))
    return await _commit(session, actor, data)


@router.post("/{business_id}/inventory/transfers/{transfer_id}/send")
async def send_transfer(
    business_id: UUID,
    transfer_id: UUID,
    body: KeyBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_ADJUST, INVENTORY)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await InventoryFieldService.send(
        session, business_id, actor.request.identity_id, transfer_id, body.model_dump(), _scope(actor))
    return await _commit(session, actor, data)


@router.post("/{business_id}/inventory/transfers/{transfer_id}/receive")
async def receive_transfer(
    business_id: UUID,
    transfer_id: UUID,
    body: KeyBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_ADJUST, INVENTORY)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await InventoryFieldService.receive(
        session, business_id, actor.request.identity_id, transfer_id, body.model_dump(), _scope(actor))
    return await _commit(session, actor, data)


@router.get("/{business_id}/inventory/vans")
async def van_board(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_READ, INVENTORY)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await InventoryFieldService.van_board(session, business_id, _scope(actor))
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/inventory/jobs/consume")
async def consume_for_job(
    business_id: UUID,
    body: JobBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_ADJUST, INVENTORY)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await InventoryFieldService.consume_for_job(
        session, business_id, actor.request.identity_id, body.model_dump(mode="json"), _scope(actor))
    return await _commit(session, actor, data)


@router.post("/{business_id}/inventory/jobs/return-unused")
async def return_unused(
    business_id: UUID,
    body: JobBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_ADJUST, INVENTORY)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await InventoryFieldService.return_unused(
        session, business_id, actor.request.identity_id, body.model_dump(mode="json"), _scope(actor))
    return await _commit(session, actor, data)


@router.get("/{business_id}/inventory/client-stock")
async def list_client_stock(
    business_id: UUID,
    customer_id: UUID | None = Query(default=None),
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_READ, INVENTORY)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await InventoryFieldService.list_client_stock(
        session, business_id, _scope(actor), customer_id=customer_id)
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/inventory/client-stock")
async def move_client_stock(
    business_id: UUID,
    body: ClientStockBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_ADJUST, INVENTORY)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await InventoryFieldService.move_client_stock(
        session, business_id, actor.request.identity_id, body.model_dump(mode="json"), _scope(actor))
    return await _commit(session, actor, data)


@router.get("/{business_id}/customer-assets")
async def list_assets(
    business_id: UUID,
    customer_id: UUID | None = Query(default=None),
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_READ, CUSTOMERS)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await InventoryFieldService.list_assets(session, business_id, customer_id=customer_id)
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/customer-assets")
async def record_asset(
    business_id: UUID,
    body: AssetBody,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_UPDATE, CUSTOMERS)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await InventoryFieldService.record_asset(
        session, business_id, actor.request.identity_id, body.model_dump(mode="json"))
    return await _commit(session, actor, data)
