"""Provider-agnostic search interface (Doc 10 §13.2, Doc 12 §14.1)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import MarketplaceBusinessProjection, MarketplaceOfferingProjection


@runtime_checkable
class SearchDiscoveryProvider(Protocol):
    async def search_businesses(
        self,
        session: AsyncSession,
        *,
        query: str | None,
        location: str | None,
        business_type: str | None,
        limit: int,
    ) -> list[dict[str, Any]]: ...

    async def search_offerings(
        self,
        session: AsyncSession,
        *,
        query: str | None,
        location: str | None,
        offering_type: str | None,
        limit: int,
    ) -> list[dict[str, Any]]: ...


class PostgresGinSearchProvider:
    """First Launch implementation — PostgreSQL FTS + GIN (FL-DEC-014)."""

    @staticmethod
    def _serialize_business(row: MarketplaceBusinessProjection) -> dict[str, Any]:
        return {
            "result_type": "business",
            "business_id": str(row.business_id),
            "slug": row.slug,
            "display_name": row.display_name,
            "description": row.description,
            "business_type": row.business_type,
            "city": row.city,
            "primary_category": row.primary_category,
            "tags": list(row.tags or []),
            "capability_flags": row.capability_flags or {},
            "logo_asset_id": str(row.logo_asset_id) if row.logo_asset_id else None,
        }

    @staticmethod
    def _serialize_offering(
        row: MarketplaceOfferingProjection, *, business_slug: str | None = None
    ) -> dict[str, Any]:
        return {
            "result_type": "offering",
            "id": str(row.id),
            "business_id": str(row.business_id),
            "business_slug": business_slug,
            "offering_type": row.offering_type,
            "title": row.title,
            "description": row.description,
            "price_from": float(row.price_from) if row.price_from is not None else None,
            "currency": row.currency,
            "category": row.category,
        }

    async def search_businesses(
        self,
        session: AsyncSession,
        *,
        query: str | None,
        location: str | None,
        business_type: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        stmt: Select[Any] = select(MarketplaceBusinessProjection).where(
            MarketplaceBusinessProjection.is_discoverable.is_(True)
        )
        if business_type:
            stmt = stmt.where(MarketplaceBusinessProjection.business_type == business_type)
        if location:
            stmt = stmt.where(
                MarketplaceBusinessProjection.city.ilike(f"%{location.strip()}%")
            )
        if query and query.strip():
            ts_query = func.plainto_tsquery("english", query.strip())
            stmt = stmt.where(MarketplaceBusinessProjection.search_vector.op("@@")(ts_query))
            stmt = stmt.order_by(
                func.ts_rank(MarketplaceBusinessProjection.search_vector, ts_query).desc(),
                MarketplaceBusinessProjection.display_name.asc(),
            )
        else:
            stmt = stmt.order_by(MarketplaceBusinessProjection.display_name.asc())
        stmt = stmt.limit(limit)
        rows = (await session.execute(stmt)).scalars().all()
        return [self._serialize_business(r) for r in rows]

    async def search_offerings(
        self,
        session: AsyncSession,
        *,
        query: str | None,
        location: str | None,
        offering_type: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(MarketplaceOfferingProjection, MarketplaceBusinessProjection.slug)
            .join(
                MarketplaceBusinessProjection,
                MarketplaceBusinessProjection.business_id
                == MarketplaceOfferingProjection.business_id,
            )
            .where(
                MarketplaceOfferingProjection.is_active.is_(True),
                MarketplaceBusinessProjection.is_discoverable.is_(True),
            )
        )
        if offering_type:
            stmt = stmt.where(MarketplaceOfferingProjection.offering_type == offering_type)
        if location:
            stmt = stmt.where(
                MarketplaceBusinessProjection.city.ilike(f"%{location.strip()}%")
            )
        if query and query.strip():
            ts_query = func.plainto_tsquery("english", query.strip())
            stmt = stmt.where(
                or_(
                    MarketplaceOfferingProjection.search_vector.op("@@")(ts_query),
                    MarketplaceBusinessProjection.search_vector.op("@@")(ts_query),
                )
            )
            stmt = stmt.order_by(
                func.ts_rank(MarketplaceOfferingProjection.search_vector, ts_query).desc()
            )
        else:
            stmt = stmt.order_by(MarketplaceOfferingProjection.title.asc())
        stmt = stmt.limit(limit)
        rows = (await session.execute(stmt)).all()
        return [self._serialize_offering(offering, business_slug=slug) for offering, slug in rows]


def get_search_provider() -> SearchDiscoveryProvider:
    return PostgresGinSearchProvider()
