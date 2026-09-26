"""The business taxonomy, read-only (Capability Universe §4.4: one registry, one endpoint).

Public data — every business kind LOCAH knows, and a deterministic,
spelling-tolerant search over it for the "What kind of business?" picker.
Nothing is stored and nobody is identified.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from platform_core.catalog.taxonomy import catalogue, search

router = APIRouter(prefix="/v1/public/taxonomy", tags=["taxonomy"])


@router.get("")
async def taxonomy() -> dict[str, Any]:
    return {"data": catalogue()}


@router.get("/search")
async def taxonomy_search(q: str = Query("", max_length=80)) -> dict[str, Any]:
    return {"data": search(q, limit=8)}
