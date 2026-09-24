"""Website preview tokens and publish lifecycle (Doc 12 §11.5–§11.6)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ValidationError
from platform_core.gates import assert_business_mutable
from platform_core.models import BusinessProfile, WebsitePage, WebsiteSection, WebsiteVersion
from platform_core.secrets import resolve_signing_secret
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
        # Refuses the development default outside development: this signs the
        # token that lets a caller read an unpublished draft, so a constant
        # anyone can read in this repo would defeat the preview boundary.
        return str(
            resolve_signing_secret(
                "WEBSITE_PREVIEW_SECRET",
                "preview-dev-secret",
                fallback_env="SUPABASE_JWT_SECRET",
            )
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
                        content=dict(section.content or {}),
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
        return dict(aggregate)

    @staticmethod
    async def load_public_page(
        session: AsyncSession,
        *,
        slug: str,
        page_slug: str | None = None,
        preview_token: str | None = None,
    ) -> dict[str, Any]:
        from platform_core.exceptions import ResourceNotFound

        # A preview token has to be verified BEFORE the Business is looked up.
        #
        # `businesses_api_select` only exposes a Business to an unbound caller
        # once it is unlisted or discoverable. A Business that has never been
        # published is private, so resolving it first meant preview 404'd for
        # exactly the case preview exists to serve — the owner checking a draft
        # before making it public.
        #
        # Binding the tenant context from the token's own `business_id` does not
        # weaken that policy: it satisfies the `id = current_business_id()` arm
        # the policy already grants. The token is platform-signed, short-lived,
        # names one Business, and is only minted for someone holding
        # WEBSITE_READ on it. The claim is still checked against the resolved
        # Business below, so a token for one tenant cannot open another's slug.
        claims: dict[str, Any] | None = None
        if preview_token:
            claims = WebsitePublishService.verify_preview_token(preview_token)
            token_business_id = claims.get("business_id")
            if token_business_id:
                await bind_public_context(session, uuid.UUID(str(token_business_id)))

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
        if claims is not None:
            if claims.get("business_id") != str(business.id):
                raise ValidationError("Preview token does not match business")
            result = await session.execute(
                select(WebsiteVersion).where(
                    WebsiteVersion.id == uuid.UUID(claims["draft_version_id"]),
                    WebsiteVersion.business_id == business.id,
                )
            )
            version = result.scalars().first()
            # A token pins the draft that existed when it was minted, and
            # personalisation replaces that draft a few seconds later — so the
            # owner's "Open full size" showed the site from before Locah finished
            # writing it. The token proves who may preview this business; what
            # they preview is its draft as it is now.
            if version is None or version.superseded_at is not None:
                current = await session.execute(
                    select(WebsiteVersion).where(
                        WebsiteVersion.business_id == business.id,
                        WebsiteVersion.version_type == "draft",
                        WebsiteVersion.superseded_at.is_(None),
                    )
                )
                version = current.scalars().first() or version
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
        from platform_core.marketplace.eligibility import capability_flags

        # A section renders a "buy" or "book" control only where the module
        # behind it is actually on. Without this the renderer decided from the
        # section type alone, which is a guess about the business rather than a
        # fact about it.
        capabilities = await capability_flags(session, business.id)

        return {
            "business": {
                "id": str(business.id),
                "slug": business.slug,
                "display_name": business.display_name,
                "business_type": business.business_type,
                # Only the fields a visitor can use: a number to call or
                # WhatsApp and an email, exactly as the owner published them.
                "contact": await _public_contact(session, business.id),
            },
            "capabilities": capabilities,
            "website": WebsiteResolver.serialize_website(website),
            "version": WebsiteResolver.serialize_version(version),
            "page": serialized_page,
            "navigation": version.navigation,
            "theme": await _theme_with_logo(session, business.id, version.theme),
            "is_preview": is_preview,
            "cache_control": "no-store" if is_preview else "public",
        }


async def _theme_with_logo(session: Any, business_id: Any, theme: Any) -> dict[str, Any]:
    """The business's own logo in the site header.

    The page renderer shows `theme.logo_url`, but nothing put it there: a logo
    the owner uploaded or asked Locah to draw lived on the Business Profile and
    never reached the site. It is resolved at render time, so a logo that
    arrives after the build appears without rebuilding. The business's own
    brand only — never a LOCAH mark.
    """
    from platform_core.models import MediaAsset

    result: dict[str, Any] = dict(theme or {})
    if result.get("logo_url"):
        return result
    logo_id = (
        await session.execute(
            select(BusinessProfile.logo_asset_id).where(BusinessProfile.business_id == business_id)
        )
    ).scalar()
    if not logo_id:
        return result
    asset = (
        await session.execute(
            select(MediaAsset).where(
                MediaAsset.id == logo_id,
                MediaAsset.business_id == business_id,
                MediaAsset.status == "ready",
                MediaAsset.deleted_at.is_(None),
            )
        )
    ).scalars().first()
    if asset is not None and asset.public_url:
        result["logo_url"] = asset.public_url
    return result


async def _public_contact(session: Any, business_id: Any) -> dict[str, str]:
    from sqlalchemy import select as _select

    from platform_core.models import BusinessProfile

    profile = (
        await session.execute(_select(BusinessProfile).where(BusinessProfile.business_id == business_id))
    ).scalars().first()
    raw = (profile.contact if profile and isinstance(profile.contact, dict) else {}) or {}
    return {
        key: str(raw[key])
        for key in ("phone", "whatsapp", "email")
        if isinstance(raw.get(key), str) and raw.get(key)
    }
