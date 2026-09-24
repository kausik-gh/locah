"""Public Marketplace search, discovery and profile (Doc 11 §13.1, Doc 12 §14).

No endpoint here records who asked. Personal signals (`fam`, `cat`,
`searched`, `used`) arrive with the request, shape that one response and are
not stored.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_core.services.marketplace_search import (
    MarketplaceSearchService,
    Signals,
    VisitorPlace,
)

router = APIRouter(prefix="/v1/public", tags=["marketplace"])


def _place(near: str | None, place: str | None) -> VisitorPlace | None:
    """`near=lat,lng` (a browser position) or `place=` (a town or PIN)."""
    if near:
        try:
            lat_s, lng_s = near.split(",", 1)
            return MarketplaceSearchService.resolve_place(lat=float(lat_s), lng=float(lng_s))
        except ValueError:
            return None
    return MarketplaceSearchService.resolve_place(q=place)


def _counts(raw: str | None, *, limit: int = 8) -> dict[str, int]:
    """`food-drink:3,fitness:1` → {"food-drink": 3, "fitness": 1}."""
    out: dict[str, int] = {}
    for part in (raw or "").split(",")[:limit]:
        key, _, value = part.partition(":")
        key = key.strip()[:40]
        if not key:
            continue
        try:
            out[key] = max(1, min(int(value or 1), 50))
        except ValueError:
            out[key] = 1
    return out


def _uuids(raw: str | None, *, limit: int = 20) -> list[uuid.UUID]:
    out: list[uuid.UUID] = []
    for part in (raw or "").split(",")[:limit]:
        try:
            out.append(uuid.UUID(part.strip()))
        except ValueError:
            continue
    return out


@router.get("/search")
async def public_search(
    q: str | None = Query(default=None, max_length=200),
    location: str | None = Query(default=None, max_length=120),
    type: str | None = Query(default=None, alias="type", max_length=80),
    family: str | None = Query(default=None, max_length=40),
    category: str | None = Query(default=None, max_length=40),
    can: list[str] = Query(default=[]),
    near: str | None = Query(default=None, max_length=40),
    place: str | None = Query(default=None, max_length=80),
    sort: str = Query(default="relevance", max_length=20),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0, le=1000),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await MarketplaceSearchService.search(
        session,
        q=q,
        location=location,
        type_=type,
        limit=limit,
        offset=offset,
        family=family,
        category=category,
        capabilities=tuple(c for value in can for c in value.split(",") if c)[:4],
        place=_place(near, place),
        sort=sort,
    )
    return {"data": data, "meta": {"count": data["counts"]["businesses"] + data["counts"]["offerings"]}}


@router.get("/discover")
async def public_discover(
    near: str | None = Query(default=None, max_length=40),
    place: str | None = Query(default=None, max_length=80),
    fam: str | None = Query(default=None, max_length=400),
    cat: str | None = Query(default=None, max_length=400),
    searched: list[str] = Query(default=[]),
    used: str | None = Query(default=None, max_length=800),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    signals = Signals(
        families=_counts(fam),
        categories=_counts(cat),
        searched=[s.strip()[:60] for s in searched if s.strip()][:3],
        used_business_ids=_uuids(used),
    )
    data = await MarketplaceSearchService.discover(
        session, place=_place(near, place), signals=signals
    )
    return {"data": data, "meta": {}}


@router.get("/categories")
async def public_categories(session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    return {"data": await MarketplaceSearchService.categories(session), "meta": {}}


@router.get("/places")
async def public_places(
    q: str | None = Query(default=None, max_length=80),
    near: str | None = Query(default=None, max_length=40),
) -> dict[str, Any]:
    """Resolve a town, a PIN or rounded coordinates; suggest towns as typed.

    Reference data only — nothing is looked up with a third party and
    nothing is logged beyond the request line itself.
    """
    resolved = _place(near, q)
    return {
        "data": {
            "resolved": {
                "label": resolved.label,
                "lat": resolved.lat,
                "lng": resolved.lng,
                "precision": resolved.precision,
            }
            if resolved
            else None,
            "suggestions": MarketplaceSearchService.suggest_places(q) if q and not near else [],
        },
        "meta": {},
    }


@router.get("/businesses/{slug}")
async def marketplace_business_profile(
    slug: str,
    near: str | None = Query(default=None, max_length=40),
    place: str | None = Query(default=None, max_length=80),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await MarketplaceSearchService.get_marketplace_profile(
        session, slug=slug, place=_place(near, place)
    )
    return {"data": data, "meta": {}}
