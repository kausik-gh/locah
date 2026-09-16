"""Website preview tokens and publish lifecycle (Doc 12 §11.5–§11.6)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ValidationError
from platform_core.gates import assert_business_mutable
from platform_core.models import BusinessProfile, WebsitePage, WebsiteSection, WebsiteVersion
from platform_core.context_resolver import bind_public_context
from platform_core.resolvers.website_resolver import WebsiteResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService
from platform_core.services.website import WebsiteService


class WebsitePublishService:
    PREVIEW_TTL_SECONDS = 600

    @staticmethod
    def _preview_secret() -> str:
        return os.getenv("WEBSITE_PREVIEW_SECRET") or os.getenv(
            "SUPABASE_JWT_SECRET", "preview-dev-secret"
        )

    @staticmethod
    async def create_preview_token(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> dict[str, Any]:
        website = await WebsiteResolver.resolve_website(session, business_id=business_id)
        draft = await WebsiteResolver.resolve_draft_version(
            session, business_id=business_id, website_id=website.id
        )
        business = await BusinessService.get_by_id(session, business_id)
        exp = datetime.now(timezone.utc) + timedelta(
            seconds=WebsitePublishService.PREVIEW_TTL_SECONDS
        )
        token = jwt.encode(
            {
                "typ": "website_preview",
                "business_id": str(business_id),
                "website_id": str(website.id),
                "draft_version_id": str(draft.id),
                "slug": business.slug,
                "sub": str(actor_id),
                "exp": exp,
            },
            WebsitePublishService._preview_secret(),
            algorithm="HS256",
        )
        return {
            "token": token,
            "expires_at": exp.isoformat(),
            "preview_path": f"/{business.slug}?preview_token={token}",
            "draft_version_id": str(draft.id),
        }

    @staticmethod
    def verify_preview_token(token: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                WebsitePublishService._preview_secret(),
                algorithms=["HS256"],
            )
        except jwt.ExpiredSignatureError as exc:
            raise ValidationError("Preview token expired") from exc
        except jwt.InvalidTokenError as exc:
            raise ValidationError("Invalid preview token") from exc
        if payload.get("typ") != "website_preview":
            raise ValidationError("Invalid preview token type")
        return payload

    @staticmethod
    async def assert_publish_ready(
        session: AsyncSession, *, business_id: uuid.UUID, draft_id: uuid.UUID
    ) -> None:
        pages = await WebsiteResolver.list_pages(session, version_id=draft_id)
        if not pages:
            raise ValidationError("Publish requires at least one page")
        home = next((p for p in pages if p.page_type == "home" or p.slug == "home"), None)
        if home is None:
            raise ValidationError("Publish requires a home page")
        sections = await WebsiteResolver.list_sections(session, page_id=home.id)
        visible = [s for s in sections if s.is_visible]
        if not visible:
            raise ValidationError("Home page requires at least one visible section")
        hero = next((s for s in visible if s.section_type_id == "hero"), None)
        if hero is None or not (hero.content or {}).get("headline"):
            raise ValidationError("Home hero headline is required before publish")

        profile_result = await session.execute(
            select(BusinessProfile).where(BusinessProfile.business_id == business_id)
        )
        profile = profile_result.scalars().first()
        business = await BusinessService.get_by_id(session, business_id)
        if not business.display_name or not business.display_name.strip():
            raise ValidationError("Business display name is required before publish")
        if profile is None:
            raise ValidationError("Business profile is required before publish")

    @staticmethod
    async def publish(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
    ) -> dict[str, Any]:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="publish website")
        website = await WebsiteResolver.resolve_website(session, business_id=business_id)
        draft = await WebsiteResolver.resolve_draft_version(
            session, business_id=business_id, website_id=website.id
        )
        await WebsitePublishService.assert_publish_ready(
            session, business_id=business_id, draft_id=draft.id
        )

        published = WebsiteVersion(
            website_id=website.id,
            business_id=business_id,
            version_type="published",
            navigation=draft.navigation,
            theme=draft.theme,
            generated_by=draft.generated_by,
            generation_job_id=draft.generation_job_id,
            published_at=datetime.now(timezone.utc),
        )
        session.add(published)
        await session.flush()

        draft_pages = await WebsiteResolver.list_pages(session, version_id=draft.id)
        for page in draft_pages:
            new_page = WebsitePage(
                website_version_id=published.id,
                business_id=business_id,
                slug=page.slug,
                title=page.title,
                page_type=page.page_type,
                seo_title=page.seo_title,
                seo_description=page.seo_description,
                og_image_asset_id=page.og_image_asset_id,
                is_published=page.is_published,
                sort_order=page.sort_order,
            )
            session.add(new_page)
            await session.flush()
            sections = await WebsiteResolver.list_sections(session, page_id=page.id)
            for section in sections:
                session.add(
                    WebsiteSection(
                        page_id=new_page.id,
                        business_id=business_id,
                        section_type_id=section.section_type_id,
                        layout_variant=section.layout_variant,
                        content=section.content,
                        module_binding=section.module_binding,
                        sort_order=section.sort_order,
                        is_visible=section.is_visible,
                    )
                )

        website.published_version_id = published.id
        website.status = "published"
        await session.flush()

        await OutboxService.publish(
            session,
            event_type="website.published",
            payload={
                "business_id": str(business_id),
                "website_id": str(website.id),
                "published_version_id": str(published.id),
                "slug": business.slug,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="website.published",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="website",
            resource_id=website.id,
            action="published",
            after_state={
                "published_version_id": str(published.id),
                "status": website.status,
            },
        )
        aggregate = await WebsiteService.get_aggregate(session, business_id=business_id)
        return aggregate

    @staticmethod
    async def load_public_page(
        session: AsyncSession,
        *,
        slug: str,
        page_slug: str | None = None,
        preview_token: str | None = None,
    ) -> dict[str, Any]:
        from platform_core.exceptions import ResourceNotFound

        business = await BusinessService.get_by_slug(session, slug)
        if business is None or business.deleted_at is not None:
            raise ResourceNotFound("Website")
        await bind_public_context(session, business.id)

        try:
            website = await WebsiteResolver.resolve_website(session, business_id=business.id)
        except ResourceNotFound as exc:
            raise ResourceNotFound("Website") from exc

        version: WebsiteVersion | None = None
        is_preview = False
        if preview_token:
            claims = WebsitePublishService.verify_preview_token(preview_token)
            if claims.get("business_id") != str(business.id):
                raise ValidationError("Preview token does not match business")
            result = await session.execute(
                select(WebsiteVersion).where(
                    WebsiteVersion.id == uuid.UUID(claims["draft_version_id"]),
                    WebsiteVersion.business_id == business.id,
                )
            )
            version = result.scalars().first()
            is_preview = True
        else:
            if website.status != "published" or not website.published_version_id:
                raise ResourceNotFound("Website")
            result = await session.execute(
                select(WebsiteVersion).where(WebsiteVersion.id == website.published_version_id)
            )
            version = result.scalars().first()

        if version is None:
            raise ResourceNotFound("Website")

        pages = await WebsiteResolver.list_pages(session, version_id=version.id)
        target_slug = page_slug or "home"
        page = next((p for p in pages if p.slug == target_slug), None)
        if page is None and target_slug == "home":
            page = next((p for p in pages if p.page_type == "home"), None)
        if page is None or (not page.is_published and not is_preview):
            raise ResourceNotFound("Page")
        sections = await WebsiteResolver.list_sections(session, page_id=page.id)
        visible_sections = [s for s in sections if s.is_visible or is_preview]
        serialized_page = WebsiteResolver.serialize_page(page, visible_sections)
        # Asset ids -> public URLs, alongside `content` (never inside it).
        from platform_core.services.media import MediaService

        await MediaService.attach_section_asset_urls(
            session, serialized_page.get("sections") or [], business_id=business.id
        )
        return {
            "business": {
                "id": str(business.id),
                "slug": business.slug,
                "display_name": business.display_name,
                "business_type": business.business_type,
            },
            "website": WebsiteResolver.serialize_website(website),
            "version": WebsiteResolver.serialize_version(version),
            "page": serialized_page,
            "navigation": version.navigation,
            "theme": version.theme,
            "is_preview": is_preview,
            "cache_control": "no-store" if is_preview else "public",
        }
