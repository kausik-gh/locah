"""Offerings catalog lookup resolver (Stage 5)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ResourceNotFound, ResourceStateDenied
from platform_core.models import Offering, OfferingCategory, OfferingVariant


class OfferingResolver:
    @staticmethod
    async def resolve_category(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        category_id: uuid.UUID,
    ) -> OfferingCategory:
        result = await session.execute(
            select(OfferingCategory).where(
                OfferingCategory.id == category_id,
                OfferingCategory.business_id == business_id,
                OfferingCategory.deleted_at.is_(None),
            )
        )
        category = result.scalars().first()
        if category is None:
            raise ResourceNotFound("Product category")
        return category

    @staticmethod
    async def resolve(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        offering_id: uuid.UUID,
    ) -> Offering:
        result = await session.execute(
            select(Offering).where(
                Offering.id == offering_id,
                Offering.business_id == business_id,
                Offering.deleted_at.is_(None),
            )
        )
        offering = result.scalars().first()
        if offering is None:
            raise ResourceNotFound("Product")
        return offering

    @staticmethod
    async def resolve_variant(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        variant_id: uuid.UUID,
    ) -> OfferingVariant:
        result = await session.execute(
            select(OfferingVariant).where(
                OfferingVariant.id == variant_id,
                OfferingVariant.business_id == business_id,
                OfferingVariant.deleted_at.is_(None),
            )
        )
        variant = result.scalars().first()
        if variant is None:
            raise ResourceNotFound("Product variant")
        return variant

    @staticmethod
    def require_operable(offering: Offering, *, action: str = "update") -> None:
        if offering.status == "archived":
            raise ResourceStateDenied(
                "product",
                offering.status,
                action=action,
                allowed_states=["draft", "active"],
            )

    @staticmethod
    async def resolve_operable(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        offering_id: uuid.UUID,
        action: str = "update",
    ) -> Offering:
        offering = await OfferingResolver.resolve(
            session, business_id=business_id, offering_id=offering_id
        )
        OfferingResolver.require_operable(offering, action=action)
        return offering

    @staticmethod
    def serialize_category(category: OfferingCategory) -> dict[str, Any]:
        return {
            "id": str(category.id),
            "business_id": str(category.business_id),
            "name": category.name,
            "slug": category.slug,
            "parent_id": str(category.parent_id) if category.parent_id else None,
            "sort_order": category.sort_order,
            "status": category.status,
            "version": category.version,
            "created_at": category.created_at.isoformat(),
            "updated_at": category.updated_at.isoformat(),
        }

    @staticmethod
    def serialize_offering(offering: Offering) -> dict[str, Any]:
        return {
            "id": str(offering.id),
            "business_id": str(offering.business_id),
            "category_id": str(offering.category_id) if offering.category_id else None,
            "offering_type": offering.offering_type,
            "title": offering.title,
            "description": offering.description,
            "sku": offering.sku,
            "barcode": offering.barcode,
            "status": offering.status,
            "price_type": offering.price_type,
            "price_amount": float(offering.price_amount) if offering.price_amount is not None else None,
            "currency": offering.currency,
            "unit_of_measure": offering.unit_of_measure,
            "tax_rate": float(offering.tax_rate) if offering.tax_rate is not None else None,
            "track_inventory": offering.track_inventory,
            "low_stock_threshold": offering.low_stock_threshold,
            "visibility": offering.visibility,
            "image_asset_ids": [str(a) for a in (offering.image_asset_ids or [])],
            "version": offering.version,
            "created_at": offering.created_at.isoformat(),
            "updated_at": offering.updated_at.isoformat(),
        }

    @staticmethod
    def serialize_variant(variant: OfferingVariant) -> dict[str, Any]:
        return {
            "id": str(variant.id),
            "business_id": str(variant.business_id),
            "offering_id": str(variant.offering_id),
            "name": variant.name,
            "sku": variant.sku,
            "barcode": variant.barcode,
            "price_amount": float(variant.price_amount) if variant.price_amount is not None else None,
            "sort_order": variant.sort_order,
            "status": variant.status,
            "version": variant.version,
            "created_at": variant.created_at.isoformat(),
            "updated_at": variant.updated_at.isoformat(),
        }
