"""Website lookup resolver (Stage 2)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ResourceNotFound
from platform_core.models import (
    Website,
    WebsitePage,
    WebsiteSection,
    WebsiteSectionType,
    WebsiteVersion,
)


class WebsiteResolver:
    @staticmethod
    async def resolve_website(
        session: AsyncSession, *, business_id: uuid.UUID
    ) -> Website:
        result = await session.execute(
            select(Website).where(Website.business_id == business_id)
        )
        website = result.scalars().first()
        if website is None:
            raise ResourceNotFound("Website")
        return website

    @staticmethod
    async def resolve_draft_version(
        session: AsyncSession, *, business_id: uuid.UUID, website_id: uuid.UUID
    ) -> WebsiteVersion:
        # AUD-08: the live draft is the one not yet superseded. A partial unique
        # index guarantees there is at most one, so this needs no ordering and
        # cannot pick the wrong row under a created_at tie.
        result = await session.execute(
            select(WebsiteVersion).where(
                WebsiteVersion.website_id == website_id,
                WebsiteVersion.business_id == business_id,
                WebsiteVersion.version_type == "draft",
                WebsiteVersion.superseded_at.is_(None),
            )
        )
        version = result.scalars().first()
        if version is None:
            raise ResourceNotFound("Website draft")
        return version

    @staticmethod
    async def resolve_page(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        page_id: uuid.UUID,
    ) -> WebsitePage:
        result = await session.execute(
            select(WebsitePage).where(
                WebsitePage.id == page_id,
                WebsitePage.business_id == business_id,
            )
        )
        page = result.scalars().first()
        if page is None:
            raise ResourceNotFound("Website page")
        return page

    @staticmethod
    async def resolve_section(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        section_id: uuid.UUID,
    ) -> WebsiteSection:
        result = await session.execute(
            select(WebsiteSection).where(
                WebsiteSection.id == section_id,
                WebsiteSection.business_id == business_id,
            )
        )
        section = result.scalars().first()
        if section is None:
            raise ResourceNotFound("Website section")
        return section

    @staticmethod
    async def load_section_type(
        session: AsyncSession, section_type_id: str
    ) -> WebsiteSectionType | None:
        result = await session.execute(
            select(WebsiteSectionType).where(WebsiteSectionType.id == section_type_id)
        )
        return result.scalars().first()

    @staticmethod
    async def list_pages(
        session: AsyncSession, *, version_id: uuid.UUID
    ) -> list[WebsitePage]:
        result = await session.execute(
            select(WebsitePage)
            .where(WebsitePage.website_version_id == version_id)
            .order_by(WebsitePage.sort_order.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_sections(
        session: AsyncSession, *, page_id: uuid.UUID
    ) -> list[WebsiteSection]:
        result = await session.execute(
            select(WebsiteSection)
            .where(WebsiteSection.page_id == page_id)
            .order_by(WebsiteSection.sort_order.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    def serialize_section(section: WebsiteSection) -> dict[str, Any]:
        return {
            "id": str(section.id),
            "page_id": str(section.page_id),
            "section_type_id": section.section_type_id,
            "layout_variant": section.layout_variant,
            "content": section.content or {},
            "module_binding": section.module_binding,
            "sort_order": section.sort_order,
            "is_visible": section.is_visible,
            "updated_at": section.updated_at.isoformat() if section.updated_at else None,
        }

    @staticmethod
    def serialize_page(
        page: WebsitePage, sections: list[WebsiteSection] | None = None
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": str(page.id),
            "website_version_id": str(page.website_version_id),
            "slug": page.slug,
            "title": page.title,
            "page_type": page.page_type,
            "seo_title": page.seo_title,
            "seo_description": page.seo_description,
            "is_published": page.is_published,
            "sort_order": page.sort_order,
            "updated_at": page.updated_at.isoformat() if page.updated_at else None,
        }
        if sections is not None:
            data["sections"] = [WebsiteResolver.serialize_section(s) for s in sections]
        return data

    @staticmethod
    def serialize_version(version: WebsiteVersion) -> dict[str, Any]:
        return {
            "id": str(version.id),
            "website_id": str(version.website_id),
            "version_type": version.version_type,
            "navigation": version.navigation,
            "theme": version.theme,
            "generated_by": version.generated_by,
            "generation_job_id": (
                str(version.generation_job_id) if version.generation_job_id else None
            ),
            "published_at": version.published_at.isoformat() if version.published_at else None,
            "created_at": version.created_at.isoformat() if version.created_at else None,
            "updated_at": version.updated_at.isoformat() if version.updated_at else None,
        }

    @staticmethod
    def serialize_website(website: Website) -> dict[str, Any]:
        return {
            "id": str(website.id),
            "business_id": str(website.business_id),
            "status": website.status,
            "published_version_id": (
                str(website.published_version_id) if website.published_version_id else None
            ),
            "custom_domain": website.custom_domain,
            "created_at": website.created_at.isoformat() if website.created_at else None,
            "updated_at": website.updated_at.isoformat() if website.updated_at else None,
        }
