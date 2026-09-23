"""Fill missing Website/Offering images after structured generation.

Runs as `media.generate_website_images`. Never writes an external URL into
section content. If Grok Imagine or Storage is unavailable, the draft stays
as copy-only — the renderer already handles a missing picture.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.logging import get_logger
from platform_core.models import Business, BusinessProfile, Offering, WebsitePage, WebsiteSection, WebsiteVersion
from platform_core.services.media import MediaService
from platform_core.website.image_generation import (
    generate_image_bytes,
    hero_prompt,
    offering_prompt,
)

_log = get_logger("website.images")
_MAX_OFFERING_IMAGES = 6


class WebsiteImageService:
    @staticmethod
    async def fill_missing(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
    ) -> dict[str, Any]:
        business = await session.get(Business, business_id)
        if business is None:
            return {"ok": False, "reason": "business_missing"}
        profile = (
            await session.execute(
                select(BusinessProfile).where(BusinessProfile.business_id == business_id)
            )
        ).scalars().first()
        display_name = business.display_name
        business_type = business.business_type
        description = profile.description if profile else None

        hero = await WebsiteImageService._fill_hero(
            session,
            business_id=business_id,
            actor_id=actor_id,
            display_name=display_name,
            business_type=business_type,
            description=description,
        )
        offerings = await WebsiteImageService._fill_offerings(
            session,
            business_id=business_id,
            actor_id=actor_id,
            display_name=display_name,
            business_type=business_type,
        )
        _log.info(
            "website.images.filled",
            business_id=str(business_id),
            correlation_id=correlation_id,
            hero=hero,
            offerings=offerings,
        )
        return {"ok": True, "hero": hero, "offerings": offerings}

    @staticmethod
    async def generate_section_image(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        section_id: uuid.UUID,
    ) -> dict[str, Any]:
        business = await session.get(Business, business_id)
        if business is None:
            return {"ok": False, "reason": "business_missing"}
        profile = (
            await session.execute(
                select(BusinessProfile).where(BusinessProfile.business_id == business_id)
            )
        ).scalars().first()
        section = await session.get(WebsiteSection, section_id)
        if section is None:
            return {"ok": False, "reason": "section_missing"}
        prompt = hero_prompt(
            display_name=business.display_name,
            business_type=business.business_type,
            description=profile.description if profile else None,
        )
        generated = await generate_image_bytes(prompt, aspect_ratio="16:9")
        if generated is None:
            return {
                "ok": False,
                "reason": "generation_unavailable",
                "detail": "Image generation did not return a picture. You can upload one instead.",
            }
        asset = await MediaService.persist_generated(
            session,
            business_id=business_id,
            actor_id=actor_id,
            purpose="website",
            mime_type=generated.mime_type,
            body=generated.bytes,
            alt_text="AI-generated decorative artwork",
            original_filename="generated-hero.jpg",
        )
        content = dict(section.content or {})
        content["image_asset_id"] = asset["id"]
        section.content = content
        flag_modified(section, "content")
        await session.flush()
        return {"ok": True, "asset": asset}

    @staticmethod
    async def _fill_hero(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        display_name: str,
        business_type: str | None,
        description: str | None,
    ) -> str:
        draft = (
            await session.execute(
                select(WebsiteVersion).where(
                    WebsiteVersion.business_id == business_id,
                    WebsiteVersion.version_type == "draft",
                    WebsiteVersion.superseded_at.is_(None),
                )
            )
        ).scalars().first()
        if draft is None:
            return "no_draft"
        sections = (
            await session.execute(
                select(WebsiteSection)
                .join(WebsitePage, WebsitePage.id == WebsiteSection.page_id)
                .where(
                    WebsitePage.website_version_id == draft.id,
                    WebsiteSection.section_type_id.in_(("hero", "about")),
                )
            )
        ).scalars().all()
        target = None
        for section in sections:
            content = section.content or {}
            if not content.get("image_asset_id"):
                target = section
                break
        if target is None:
            return "already_present"
        generated = await generate_image_bytes(
            hero_prompt(
                display_name=display_name,
                business_type=business_type,
                description=description,
            ),
            aspect_ratio="16:9",
        )
        if generated is None:
            return "generation_failed"
        try:
            asset = await MediaService.persist_generated(
                session,
                business_id=business_id,
                actor_id=actor_id,
                purpose="website",
                mime_type=generated.mime_type,
                body=generated.bytes,
                alt_text="AI-generated decorative artwork",
                original_filename="generated-hero.jpg",
            )
        except Exception as exc:  # noqa: BLE001
            _log.warning("website.images.hero_persist_failed", error=str(exc)[:300])
            return "persist_failed"
        content = dict(target.content or {})
        content["image_asset_id"] = asset["id"]
        target.content = content
        flag_modified(target, "content")
        await session.flush()
        return "generated"

    @staticmethod
    async def _fill_offerings(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        display_name: str,
        business_type: str | None,
    ) -> dict[str, int]:
        rows = (
            await session.execute(
                select(Offering).where(
                    Offering.business_id == business_id,
                    Offering.deleted_at.is_(None),
                    Offering.status != "archived",
                )
            )
        ).scalars().all()
        generated_count = 0
        skipped = 0
        failed = 0
        for offering in rows:
            if generated_count >= _MAX_OFFERING_IMAGES:
                skipped += 1
                continue
            existing = list(offering.image_asset_ids or [])
            if existing:
                skipped += 1
                continue
            generated = await generate_image_bytes(
                offering_prompt(
                    display_name=display_name,
                    business_type=business_type,
                    title=offering.title,
                    description=offering.description,
                ),
                aspect_ratio="1:1",
            )
            if generated is None:
                failed += 1
                continue
            try:
                asset = await MediaService.persist_generated(
                    session,
                    business_id=business_id,
                    actor_id=actor_id,
                    purpose="offering",
                    mime_type=generated.mime_type,
                    body=generated.bytes,
                    alt_text=f"AI illustration: {offering.title}",
                    original_filename=f"generated-{offering.id}.jpg",
                )
            except Exception as exc:  # noqa: BLE001
                _log.warning("website.images.offering_persist_failed", error=str(exc)[:300])
                failed += 1
                continue
            offering.image_asset_ids = [uuid.UUID(asset["id"])]
            flag_modified(offering, "image_asset_ids")
            generated_count += 1
        await session.flush()
        return {"generated": generated_count, "skipped": skipped, "failed": failed}
