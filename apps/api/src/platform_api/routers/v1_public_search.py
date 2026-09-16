"""Public Marketplace search and profile (Doc 11 §13.1, Doc 12 §14)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_core.services.marketplace_search import MarketplaceSearchService

router = APIRouter(prefix="/v1/public", tags=["marketplace"])


@router.get("/search")
async def public_search(
    q: str | None = Query(default=None, max_length=200),
    location: str | None = Query(default=None, max_length=120),
    type: str | None = Query(default=None, alias="type", max_length=80),
    limit: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await MarketplaceSearchService.search(
        session, q=q, location=location, type_=type, limit=limit
    )
    return {"data": data, "meta": {"count": data["counts"]["businesses"] + data["counts"]["offerings"]}}


@router.get("/businesses/{slug}")
async def marketplace_business_profile(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await MarketplaceSearchService.get_marketplace_profile(session, slug=slug)
    return {"data": data, "meta": {}}
