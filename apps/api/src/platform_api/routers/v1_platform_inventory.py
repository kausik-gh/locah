"""Platform inventory APIs (Stage 5)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.permissions import INVENTORY_ADJUST, INVENTORY_EXPORT, INVENTORY_READ
from platform_core.services.inventory import InventoryService

router = APIRouter(prefix="/v1/platform/businesses", tags=["inventory"])


class VersionedBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int | None = Field(default=None, ge=1)


class AdjustInventoryRequest(VersionedBody):
    offering_id: UUID
    location_id: UUID
    variant_id: UUID | None = None
    quantity_delta: int
    movement_type: str = "adjustment"
    reason: str


class OpeningStockRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offering_id: UUID
    location_id: UUID
    variant_id: UUID | None = None
    quantity: int = Field(ge=0)
    reason: str | None = None


@router.get("/{business_id}/inventory")
async def list_inventory(
    business_id: UUID,
    location_id: UUID | None = Query(default=None),
    offering_id: UUID | None = Query(default=None),
    stock_status: str | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=120),
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_READ, "inventory")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    records = await InventoryService.list_for_business(
        session,
        business_id,
        location_id=location_id,
        offering_id=offering_id,
        stock_status=stock_status,
        search=search,
    )
    return {
        "data": records,
        "meta": {"correlation_id": actor.request.correlation_id, "count": len(records)},
    }


@router.get("/{business_id}/inventory/export")
async def export_inventory(
    business_id: UUID,
    location_id: UUID | None = Query(default=None),
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_EXPORT, "inventory")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await InventoryService.export_inventory(
        session, business_id, location_id=location_id
    )
    return {
        "data": data,
        "meta": {"correlation_id": actor.request.correlation_id, "count": len(data)},
    }


@router.post("/{business_id}/inventory/adjust")
async def adjust_inventory(
    business_id: UUID,
    body: AdjustInventoryRequest,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_ADJUST, "inventory")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    record = await InventoryService.adjust_stock(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(exclude={"version"}),
        expected_version=body.version,
    )
    await session.commit()
    return {
        "data": InventoryService.serialize_record(record),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/inventory/opening-stock")
async def set_opening_stock(
    business_id: UUID,
    body: OpeningStockRequest,
    actor: BusinessActorContext = Depends(require_business_actor(INVENTORY_ADJUST, "inventory")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    record = await InventoryService.set_opening_stock(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(),
    )
    await session.commit()
    return {
        "data": InventoryService.serialize_record(record),
        "meta": {"correlation_id": actor.request.correlation_id},
    }
