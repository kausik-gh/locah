"""Product category service (Stage 5)."""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ResourceStateDenied
from platform_core.gates import assert_business_mutable
from platform_core.models import OfferingCategory
from platform_core.resolvers.offering_resolver import OfferingResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService
from platform_core.validation.offering import validate_category_create_payload, validate_category_patch_payload


class CategoryService:
    @staticmethod
    def serialize(category: OfferingCategory) -> dict[str, Any]:
        return cast(dict[str, Any], OfferingResolver.serialize_category(category))

    @staticmethod
    def _check_version(category: OfferingCategory, expected_version: int | None) -> None:
        if expected_version is None:
            return
        if category.version != expected_version:
            raise ConflictError(
                "Stale category version",
                details={
                    "expected_version": expected_version,
                    "current_version": category.version,
                },
            )

    @staticmethod
    async def _publish(
        session: AsyncSession,
        *,
        event_type: str,
        audit_action: str,
        business_id: uuid.UUID,
        category: OfferingCategory,
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
                "category_id": str(category.id),
                "version": category.version,
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
            resource_type="product_category",
            resource_id=category.id,
            action=audit_action,
            before_state=before_state,
            after_state=after_state,
        )

    @staticmethod
    async def _assert_unique_slug(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        slug: str,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        query = select(OfferingCategory.id).where(
            OfferingCategory.business_id == business_id,
            OfferingCategory.slug == slug,
            OfferingCategory.deleted_at.is_(None),
        )
        if exclude_id:
            query = query.where(OfferingCategory.id != exclude_id)
        if (await session.execute(query)).scalars().first():
            raise ConflictError(
                "Category slug already exists",
                details={"slug": slug},
            )

    @staticmethod
    async def list_for_business(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        status: str | None = None,
        search: str | None = None,
    ) -> list[OfferingCategory]:
        query = select(OfferingCategory).where(
            OfferingCategory.business_id == business_id,
            OfferingCategory.deleted_at.is_(None),
        )
        if status:
            query = query.where(OfferingCategory.status == status)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.where(OfferingCategory.name.ilike(pattern))
        query = query.order_by(OfferingCategory.sort_order, OfferingCategory.name)
        return list((await session.execute(query)).scalars().all())

    @staticmethod
    async def create_category(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> OfferingCategory:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="create product category")
        validated = validate_category_create_payload(payload)
        if validated["parent_id"]:
            await OfferingResolver.resolve_category(
                session,
                business_id=business_id,
                category_id=validated["parent_id"],
            )
        await CategoryService._assert_unique_slug(
            session, business_id=business_id, slug=validated["slug"]
        )
        category = OfferingCategory(
            business_id=business_id,
            name=validated["name"],
            slug=validated["slug"],
            parent_id=validated["parent_id"],
            sort_order=validated["sort_order"],
        )
        session.add(category)
        await session.flush()
        after = CategoryService.serialize(category)
        await CategoryService._publish(
            session,
            event_type="product_category.created",
            audit_action="created",
            business_id=business_id,
            category=category,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=None,
            after_state=after,
        )
        return category

    @staticmethod
    async def patch_category(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        category_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
        expected_version: int | None = None,
    ) -> OfferingCategory:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="update product category")
        category = await OfferingResolver.resolve_category(
            session, business_id=business_id, category_id=category_id
        )
        if category.status == "archived":
            raise ResourceStateDenied(
                "product_category",
                category.status,
                action="update",
                allowed_states=["active"],
            )
        CategoryService._check_version(category, expected_version)
        before = CategoryService.serialize(category)
        validated = validate_category_patch_payload(payload)
        if "slug" in validated:
            await CategoryService._assert_unique_slug(
                session,
                business_id=business_id,
                slug=validated["slug"],
                exclude_id=category.id,
            )
        if validated.get("parent_id"):
            if validated["parent_id"] == category.id:
                raise ConflictError("Category cannot be its own parent")
            await OfferingResolver.resolve_category(
                session,
                business_id=business_id,
                category_id=validated["parent_id"],
            )
        for key, value in validated.items():
            setattr(category, key, value)
        category.version += 1
        await session.flush()
        after = CategoryService.serialize(category)
        await CategoryService._publish(
            session,
            event_type="product_category.updated",
            audit_action="updated",
            business_id=business_id,
            category=category,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state=after,
        )
        return category

    @staticmethod
    async def archive_category(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        category_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        expected_version: int | None = None,
    ) -> OfferingCategory:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="archive product category")
        category = await OfferingResolver.resolve_category(
            session, business_id=business_id, category_id=category_id
        )
        CategoryService._check_version(category, expected_version)
        before = CategoryService.serialize(category)
        category.status = "archived"
        category.version += 1
        await session.flush()
        after = CategoryService.serialize(category)
        await CategoryService._publish(
            session,
            event_type="product_category.archived",
            audit_action="archived",
            business_id=business_id,
            category=category,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state=after,
        )
        return category
