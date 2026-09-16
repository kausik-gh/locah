"""Offerings / product service (Stage 5)."""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ResourceStateDenied, ValidationError
from platform_core.gates import assert_business_mutable
from platform_core.models import Offering, OfferingVariant
from platform_core.resolvers.offering_resolver import OfferingResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService
from platform_core.validation.offering import (
    OFFERING_STATUSES,
    validate_product_create_payload,
    validate_product_patch_payload,
    validate_title,
)


class OfferingService:
    @staticmethod
    def serialize(offering: Offering) -> dict[str, Any]:
        return cast(dict[str, Any], OfferingResolver.serialize_offering(offering))

    @staticmethod
    def serialize_variant(variant: OfferingVariant) -> dict[str, Any]:
        return cast(dict[str, Any], OfferingResolver.serialize_variant(variant))

    @staticmethod
    def _check_version(entity: Offering | OfferingVariant, expected_version: int | None) -> None:
        if expected_version is None:
            return
        if entity.version != expected_version:
            raise ConflictError(
                "Stale product version",
                details={
                    "expected_version": expected_version,
                    "current_version": entity.version,
                },
            )

    @staticmethod
    async def _publish_offering(
        session: AsyncSession,
        *,
        event_type: str,
        audit_action: str,
        business_id: uuid.UUID,
        offering: Offering,
        actor_id: uuid.UUID,
        correlation_id: str,
        before_state: dict[str, Any] | None,
        after_state: dict[str, Any],
    ) -> None:
        await OutboxService.publish(
            session,
            event_type=event_type,
            payload={
                "business_id": str(business_id),
                "offering_id": str(offering.id),
                "product_id": str(offering.id),
                "version": offering.version,
                "after": after_state,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type=event_type,
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="product",
            resource_id=offering.id,
            action=audit_action,
            before_state=before_state,
            after_state=after_state,
        )

    @staticmethod
    async def _assert_unique_sku(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        sku: str | None,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        if not sku:
            return
        query = select(Offering.id).where(
            Offering.business_id == business_id,
            Offering.sku == sku,
            Offering.deleted_at.is_(None),
        )
        if exclude_id:
            query = query.where(Offering.id != exclude_id)
        if (await session.execute(query)).scalars().first():
            raise ConflictError("Product SKU already exists", details={"sku": sku})

    @staticmethod
    async def _assert_unique_variant_sku(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        sku: str | None,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        if not sku:
            return
        query = select(OfferingVariant.id).where(
            OfferingVariant.business_id == business_id,
            OfferingVariant.sku == sku,
            OfferingVariant.deleted_at.is_(None),
        )
        if exclude_id:
            query = query.where(OfferingVariant.id != exclude_id)
        if (await session.execute(query)).scalars().first():
            raise ConflictError("Variant SKU already exists", details={"sku": sku})

    @staticmethod
    async def list_for_business(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        status: str | None = None,
        search: str | None = None,
        category_id: uuid.UUID | None = None,
        track_inventory: bool | None = None,
    ) -> list[Offering]:
        query = select(Offering).where(
            Offering.business_id == business_id,
            Offering.deleted_at.is_(None),
        )
        if status:
            query = query.where(Offering.status == status)
        if category_id:
            query = query.where(Offering.category_id == category_id)
        if track_inventory is not None:
            query = query.where(Offering.track_inventory.is_(track_inventory))
        if search:
            pattern = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Offering.title.ilike(pattern),
                    Offering.sku.ilike(pattern),
                    Offering.barcode.ilike(pattern),
                )
            )
        query = query.order_by(Offering.title)
        return list((await session.execute(query)).scalars().all())

    @staticmethod
    async def create_offering(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> Offering:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="create product")
        validated = validate_product_create_payload(payload)
        status = validated.pop("status", "draft")
        if status not in OFFERING_STATUSES:
            raise ValidationError("Invalid product status")
        if validated["category_id"]:
            await OfferingResolver.resolve_category(
                session,
                business_id=business_id,
                category_id=validated["category_id"],
            )
        await OfferingService._assert_unique_sku(
            session, business_id=business_id, sku=validated["sku"]
        )
        offering = Offering(
            business_id=business_id,
            status=status,
            **validated,
        )
        session.add(offering)
        await session.flush()
        after = OfferingService.serialize(offering)
        await OfferingService._publish_offering(
            session,
            event_type="offering.created",
            audit_action="created",
            business_id=business_id,
            offering=offering,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=None,
            after_state=after,
        )
        return offering

    @staticmethod
    async def patch_offering(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        offering_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
        expected_version: int | None = None,
    ) -> Offering:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="update product")
        offering = await OfferingResolver.resolve_operable(
            session, business_id=business_id, offering_id=offering_id
        )
        OfferingService._check_version(offering, expected_version)
        before = OfferingService.serialize(offering)
        validated = validate_product_patch_payload(payload)
        if validated.get("category_id"):
            await OfferingResolver.resolve_category(
                session,
                business_id=business_id,
                category_id=validated["category_id"],
            )
        if "sku" in validated:
            await OfferingService._assert_unique_sku(
                session,
                business_id=business_id,
                sku=validated["sku"],
                exclude_id=offering.id,
            )
        for key, value in validated.items():
            setattr(offering, key, value)
        offering.version += 1
        await session.flush()
        after = OfferingService.serialize(offering)
        await OfferingService._publish_offering(
            session,
            event_type="offering.updated",
            audit_action="updated",
            business_id=business_id,
            offering=offering,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state=after,
        )
        return offering

    @staticmethod
    async def archive_offering(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        offering_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        expected_version: int | None = None,
    ) -> Offering:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="archive product")
        offering = await OfferingResolver.resolve(
            session, business_id=business_id, offering_id=offering_id
        )
        OfferingService._check_version(offering, expected_version)
        before = OfferingService.serialize(offering)
        offering.status = "archived"
        offering.version += 1
        await session.flush()
        after = OfferingService.serialize(offering)
        await OfferingService._publish_offering(
            session,
            event_type="offering.archived",
            audit_action="archived",
            business_id=business_id,
            offering=offering,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state=after,
        )
        return offering

    @staticmethod
    async def restore_offering(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        offering_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        expected_version: int | None = None,
    ) -> Offering:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="restore product")
        offering = await OfferingResolver.resolve(
            session, business_id=business_id, offering_id=offering_id
        )
        if offering.status != "archived":
            raise ResourceStateDenied(
                "product",
                offering.status,
                action="restore",
                allowed_states=["archived"],
            )
        OfferingService._check_version(offering, expected_version)
        before = OfferingService.serialize(offering)
        offering.status = "draft"
        offering.version += 1
        await session.flush()
        after = OfferingService.serialize(offering)
        await OfferingService._publish_offering(
            session,
            event_type="offering.restored",
            audit_action="restored",
            business_id=business_id,
            offering=offering,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state=after,
        )
        return offering

    @staticmethod
    async def list_variants(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        offering_id: uuid.UUID,
    ) -> list[OfferingVariant]:
        await OfferingResolver.resolve(session, business_id=business_id, offering_id=offering_id)
        query = (
            select(OfferingVariant)
            .where(
                OfferingVariant.business_id == business_id,
                OfferingVariant.offering_id == offering_id,
                OfferingVariant.deleted_at.is_(None),
            )
            .order_by(OfferingVariant.sort_order, OfferingVariant.name)
        )
        return list((await session.execute(query)).scalars().all())

    @staticmethod
    async def create_variant(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        offering_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> OfferingVariant:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="create product variant")
        offering = await OfferingResolver.resolve_operable(
            session, business_id=business_id, offering_id=offering_id
        )
        name = validate_title(payload.get("name"))
        sku = payload.get("sku")
        if sku:
            sku = str(sku).strip() or None
        await OfferingService._assert_unique_variant_sku(
            session, business_id=business_id, sku=sku
        )
        variant = OfferingVariant(
            business_id=business_id,
            offering_id=offering.id,
            name=name,
            sku=sku,
            barcode=str(payload["barcode"]).strip() if payload.get("barcode") else None,
            price_amount=payload.get("price_amount"),
            sort_order=int(payload.get("sort_order") or 0),
        )
        session.add(variant)
        await session.flush()
        after = OfferingService.serialize_variant(variant)
        await OutboxService.publish(
            session,
            event_type="offering.variant.created",
            payload={
                "business_id": str(business_id),
                "offering_id": str(offering.id),
                "variant_id": str(variant.id),
                "after": after,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="offering.variant.created",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="product_variant",
            resource_id=variant.id,
            action="created",
            before_state=None,
            after_state=after,
        )
        return variant
