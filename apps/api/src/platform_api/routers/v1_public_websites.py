"""Public website read API for apps/web rendering (Doc 12 §11.3)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_core.services.website_publish import WebsitePublishService

router = APIRouter(prefix="/v1/public/websites", tags=["public-websites"])


@router.get("/{slug}")
async def get_public_home(
    slug: str,
    response: Response,
    preview_token: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await WebsitePublishService.load_public_page(
        session, slug=slug, page_slug=None, preview_token=preview_token
    )
    if data.get("cache_control") == "no-store":
        response.headers["Cache-Control"] = "no-store"
    return {"data": data, "meta": {}}


@router.get("/{slug}/pages/{page_slug}")
async def get_public_page(
    slug: str,
    page_slug: str,
    response: Response,
    preview_token: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await WebsitePublishService.load_public_page(
        session, slug=slug, page_slug=page_slug, preview_token=preview_token
    )
    if data.get("cache_control") == "no-store":
        response.headers["Cache-Control"] = "no-store"
    return {"data": data, "meta": {}}
