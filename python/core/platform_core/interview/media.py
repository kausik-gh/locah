"""Opt-in decorative artwork. Never synthesize photos of actual staff/products."""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.interview.models import MediaReference, now
from platform_core.models import WebsitePage, WebsiteSection, WebsiteVersion
from platform_core.services.media import MediaService
from platform_core.website.image_generation import GeneratedImage, generate_image_bytes


class InterviewImageAdapter(Protocol):
    async def generate(self, prompt: str) -> GeneratedImage | None: ...


class ExistingImageAdapter:
    async def generate(self, prompt: str) -> GeneratedImage | None:
        return await generate_image_bytes(prompt, timeout_seconds=45)


async def generate_interview_hero(session: AsyncSession, *, business_id: UUID, actor_id: UUID,
                                  generation_job_id: UUID, adapter: InterviewImageAdapter | None = None) -> None:
    from platform_core.services.business_interview import BusinessInterviewService
    business = await BusinessInterviewService.load_business(session, business_id)
    bp = BusinessInterviewService.read(business)
    request = next((r for r in bp.media_generation_requests if r.role == "hero" and r.status == "queued"), None)
    if request is None or bp.completion_state.generation_job_id != generation_job_id:
        return
    # Never tell a provider to invent actual rooms, treatments, staff or products.
    template = bp.template_preferences.template_id or "minimal"
    generated = await (adapter or ExistingImageAdapter()).generate(
        f"Abstract decorative website cover illustration. Design direction: {template}. "
        "Layered organic shapes and subtle paper texture. No text, people, buildings, logos, "
        "products, medical imagery, or depictions of a real business."
    )
    business = await BusinessInterviewService.load_business(session, business_id, lock=True)
    bp = BusinessInterviewService.read(business)
    request = next((r for r in bp.media_generation_requests if r.role == "hero" and r.status == "queued"), None)
    if request is None or bp.completion_state.generation_job_id != generation_job_id:
        return
    if generated is None:
        request.status = "failed"
        request.reason = "Artwork could not be generated. Your website is usable without it."
    else:
        asset = await MediaService.persist_generated(session, business_id=business_id, actor_id=actor_id,
            purpose="website", mime_type=generated.mime_type, body=generated.bytes,
            alt_text="AI-generated abstract decorative artwork", original_filename="cover-artwork.jpg")
        request.status = "ready"
        request.asset_id = UUID(asset["id"])
        bp.media_assets.append(MediaReference(asset_id=request.asset_id, role="hero",
            label="AI-generated cover artwork", source="AI_GENERATED"))
        draft = (await session.execute(select(WebsiteVersion).where(
            WebsiteVersion.business_id == business_id, WebsiteVersion.version_type == "draft",
            WebsiteVersion.superseded_at.is_(None), WebsiteVersion.generation_job_id == generation_job_id,
        ).with_for_update().execution_options(populate_existing=True))).scalars().first()
        if draft:
            hero = (await session.execute(select(WebsiteSection).join(WebsitePage).where(
                WebsitePage.website_version_id == draft.id, WebsiteSection.section_type_id == "hero",
            ).order_by(WebsitePage.sort_order, WebsiteSection.sort_order))).scalars().first()
            if hero and not (hero.content or {}).get("image_asset_id"):
                hero.content = {**(hero.content or {}), "image_asset_id": asset["id"]}
                draft.updated_at = now()
    bp.revision += 1
    await BusinessInterviewService.save(session, business, bp)
