"""Provider-agnostic search interface (Doc 10 §13.2, Doc 12 §14.1)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import Float, Select, and_, case, cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import (
    Business,
    MarketplaceBusinessProjection,
    MarketplaceOfferingProjection,
)

MBP = MarketplaceBusinessProjection

# Capability filters a visitor can ask for. Each maps to the flag the
# projection carries; "order" additionally needs something live to order.
CAPABILITY_FILTERS = ("order", "book", "enquire", "join")

_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


@dataclass(frozen=True)
class BusinessQuery:
    text: str | None = None
    # A hard filter: only listings in this city, locality or PIN.
    area: str | None = None
    family: str | None = None
    category: str | None = None
    business_type: str | None = None
    capabilities: tuple[str, ...] = ()
    # Where the visitor is, for ordering only — never a filter by itself.
    near: tuple[float, float] | None = None
    within_km: float | None = None
    sort: str = "relevance"  # relevance | nearest | newest | name
    limit: int = 20
    offset: int = 0
    only_ids: tuple[Any, ...] = ()


@dataclass
class BusinessHits:
    rows: list[tuple[MarketplaceBusinessProjection, float | None]] = field(default_factory=list)
    total: int = 0
    # "all" when every word matched; "any" when nothing matched every word
    # and the results match some of them.
    match: str = "all"


def _tokens(text: str | None) -> list[str]:
    return [t for t in _TOKEN.findall((text or "").lower())][:8]


def _tsquery(tokens: list[str], joiner: str) -> Any:
    # Tokens are letters and digits only, so they cannot break to_tsquery's
    # syntax. Words of three letters or more also match as prefixes, which is
    # what makes "bak" find a bakery while someone is still typing.
    parts = [f"{t}:*" if len(t) >= 3 else t for t in tokens]
    return func.to_tsquery("english", f" {joiner} ".join(parts))


def live_business_ids() -> Select[Any]:
    """Businesses that may be listed right now.

    The same live facts evaluate_live_eligibility_bulk checks, applied inside
    the query so LIMIT counts only listable rows. It reads `businesses`
    through its public RLS arm, which yields in-good-standing rows only.
    """
    return select(Business.id).where(
        Business.deleted_at.is_(None),
        Business.state == "active",
        Business.status == "in_good_standing",
        Business.visibility == "discoverable",
    )


def distance_expr(near: tuple[float, float]) -> Any:
    """Kilometres from `near`, equirectangular — ample for ordering a list."""
    lat0, lng0 = near
    kx = 111.2 * math.cos(math.radians(lat0))
    lat = cast(MBP.lat, Float)
    lng = cast(MBP.lng, Float)
    return func.sqrt(
        func.power((lat - literal(lat0)) * 111.2, 2) + func.power((lng - literal(lng0)) * kx, 2)
    )


@runtime_checkable
class SearchDiscoveryProvider(Protocol):
    async def find_businesses(self, session: AsyncSession, query: BusinessQuery) -> BusinessHits: ...

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

    # ---- filters ----------------------------------------------------------

    @staticmethod
    def _filtered(query: BusinessQuery, *, skip_taxonomy: bool = False) -> Select[Any]:
        stmt: Select[Any] = select(MBP).where(
            MBP.is_discoverable.is_(True),
            MBP.business_id.in_(live_business_ids()),
        )
        if query.only_ids:
            stmt = stmt.where(MBP.business_id.in_(list(query.only_ids)))
        if query.business_type:
            stmt = stmt.where(MBP.business_type == query.business_type)
        if not skip_taxonomy:
            if query.family:
                stmt = stmt.where(MBP.category_family == query.family)
            if query.category:
                stmt = stmt.where(MBP.category == query.category)
        if query.area and query.area.strip():
            area = query.area.strip()
            if area.isdigit():
                stmt = stmt.where(MBP.postal_code == area)
            else:
                like = f"%{area}%"
                stmt = stmt.where(or_(MBP.city.ilike(like), MBP.locality.ilike(like)))
        for capability in query.capabilities:
            if capability not in CAPABILITY_FILTERS:
                continue
            stmt = stmt.where(MBP.capability_flags[capability].astext == "true")
            if capability == "order":
                stmt = stmt.where(MBP.offering_count > 0)
        if query.near and query.within_km:
            stmt = stmt.where(MBP.lat.is_not(None), distance_expr(query.near) <= query.within_km)
        return stmt

    @staticmethod
    def _text_condition(tokens: list[str], raw: str, joiner: str) -> Any:
        by_name = MBP.display_name.ilike(f"%{raw}%")
        if joiner == "&":
            return or_(MBP.search_vector.op("@@")(_tsquery(tokens, "&")), by_name)
        # Any-word fallback: a listing must still match at least half of the
        # meaningful words, so "zzz no such marketplace term" does not return
        # everything that mentions "marketplace".
        words = [t for t in tokens if len(t) >= 3] or tokens
        hits = sum(
            (case((MBP.search_vector.op("@@")(_tsquery([w], "&")), 1), else_=0) for w in words),
            literal(0),
        )
        return or_(hits >= math.ceil(len(words) / 2), by_name)

    async def find_businesses(self, session: AsyncSession, query: BusinessQuery) -> BusinessHits:
        tokens = _tokens(query.text)
        raw = (query.text or "").strip()[:120]
        base = self._filtered(query)
        match = "all"
        text_cond = None
        if tokens:
            text_cond = self._text_condition(tokens, raw, "&")
            total = (
                await session.execute(select(func.count()).select_from(base.where(text_cond).subquery()))
            ).scalar_one()
            if total == 0 and len(tokens) > 1:
                text_cond = self._text_condition(tokens, raw, "|")
                match = "any"
                total = (
                    await session.execute(
                        select(func.count()).select_from(base.where(text_cond).subquery())
                    )
                ).scalar_one()
            base = base.where(text_cond)
        else:
            total = (
                await session.execute(select(func.count()).select_from(base.subquery()))
            ).scalar_one()

        distance = distance_expr(query.near) if query.near else None
        proximity = (
            case((MBP.lat.is_(None), literal(0.0)), else_=1.0 / (1.0 + distance / 15.0))
            if distance is not None
            else literal(0.0)
        )
        columns = [MBP, distance.label("distance_km") if distance is not None else literal(None).label("distance_km")]
        stmt = base.with_only_columns(*columns)

        order: list[Any] = []
        if query.sort == "nearest" and distance is not None:
            order = [distance.asc().nulls_last()]
        elif query.sort == "newest":
            order = [MBP.published_at.desc().nulls_last()]
        elif query.sort == "name":
            order = [MBP.display_name.asc()]
        elif tokens:
            ts = _tsquery(tokens, "&" if match == "all" else "|")
            name_bonus = case(
                (func.lower(MBP.display_name) == raw.lower(), 1.0),
                (MBP.display_name.ilike(f"{raw}%"), 0.5),
                else_=0.0,
            )
            order = [(func.ts_rank(MBP.search_vector, ts, 1) + name_bonus + 0.35 * proximity).desc()]
        elif distance is not None:
            order = [distance.asc().nulls_last()]
        # Deterministic tail: newest published, then by name, then by id.
        order += [MBP.published_at.desc().nulls_last(), MBP.display_name.asc(), MBP.business_id.asc()]
        stmt = stmt.order_by(*order).offset(max(0, query.offset)).limit(query.limit)
        rows = [
            (row[0], float(row[1]) if row[1] is not None else None)
            for row in (await session.execute(stmt)).all()
        ]
        return BusinessHits(rows=rows, total=int(total or 0), match=match)

    async def facets(self, session: AsyncSession, query: BusinessQuery) -> dict[str, Any]:
        """Counts for the filters, over what the rest of the query matches.

        Family and category counts ignore the family/category filter itself,
        so choosing "Food & Drink" still shows how many are in each other
        family. Capability counts respect everything.
        """
        tokens = _tokens(query.text)
        raw = (query.text or "").strip()[:120]
        loose = self._filtered(query, skip_taxonomy=True)
        tight = self._filtered(query)
        if tokens:
            cond = self._text_condition(tokens, raw, "&")
            if (
                await session.execute(select(func.count()).select_from(loose.where(cond).subquery()))
            ).scalar_one() == 0 and len(tokens) > 1:
                cond = self._text_condition(tokens, raw, "|")
            loose = loose.where(cond)
            tight = tight.where(cond)
        sub = loose.subquery()
        family_rows = (
            await session.execute(
                select(sub.c.category_family, sub.c.category, func.count())
                .group_by(sub.c.category_family, sub.c.category)
            )
        ).all()
        families: dict[str, int] = {}
        categories: dict[str, int] = {}
        for family_id, category_id, count in family_rows:
            if family_id:
                families[family_id] = families.get(family_id, 0) + int(count)
            if category_id:
                categories[category_id] = categories.get(category_id, 0) + int(count)
        tsub = tight.subquery()
        capability_counts: dict[str, int] = {}
        for capability in CAPABILITY_FILTERS:
            cond = tsub.c.capability_flags[capability].astext == "true"
            if capability == "order":
                cond = and_(cond, tsub.c.offering_count > 0)
            capability_counts[capability] = int(
                (
                    await session.execute(select(func.count()).select_from(tsub).where(cond))
                ).scalar_one()
            )
        return {"families": families, "categories": categories, "capabilities": capability_counts}

    async def search_businesses(
        self,
        session: AsyncSession,
        *,
        query: str | None,
        location: str | None,
        business_type: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        hits = await self.find_businesses(
            session,
            BusinessQuery(text=query, area=location, business_type=business_type, limit=limit),
        )
        return [self._serialize_business(row) for row, _ in hits.rows]

    async def search_offerings(
        self,
        session: AsyncSession,
        *,
        query: str | None,
        location: str | None,
        offering_type: str | None,
        limit: int,
        family: str | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(MarketplaceOfferingProjection, MBP.slug)
            .join(MBP, MBP.business_id == MarketplaceOfferingProjection.business_id)
            .where(
                MarketplaceOfferingProjection.is_active.is_(True),
                MBP.is_discoverable.is_(True),
                MBP.business_id.in_(live_business_ids()),
            )
        )
        if offering_type:
            stmt = stmt.where(MarketplaceOfferingProjection.offering_type == offering_type)
        if family:
            stmt = stmt.where(MBP.category_family == family)
        if category:
            stmt = stmt.where(MBP.category == category)
        if location and location.strip():
            like = f"%{location.strip()}%"
            stmt = stmt.where(or_(MBP.city.ilike(like), MBP.locality.ilike(like)))
        tokens = _tokens(query)
        if tokens:
            ts_query = _tsquery(tokens, "&")
            stmt = stmt.where(MarketplaceOfferingProjection.search_vector.op("@@")(ts_query))
            stmt = stmt.order_by(
                func.ts_rank(MarketplaceOfferingProjection.search_vector, ts_query).desc(),
                MarketplaceOfferingProjection.title.asc(),
            )
        else:
            stmt = stmt.order_by(MarketplaceOfferingProjection.title.asc())
        stmt = stmt.limit(limit)
        rows = (await session.execute(stmt)).all()
        return [self._serialize_offering(offering, business_slug=slug) for offering, slug in rows]


def get_search_provider() -> PostgresGinSearchProvider:
    return PostgresGinSearchProvider()
