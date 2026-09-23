"""Opt-in generated artwork. Never synthesize photos of actual staff/products.

Two things an owner may ask Locah to draw, and only when they ask:

  hero  wide editorial artwork for the top of the homepage — mood and
        material for the trade, never a picture of the business itself;
  logo  a one-letter monogram, for an owner who has no logo yet.

Both are stored as ordinary media assets marked AI_GENERATED, and both lose to
anything the owner uploads: a hero section that already has a picture keeps
it, and an uploaded logo is never replaced.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.interview.capabilities import classification_seed
from platform_core.interview.models import (
    BusinessBlueprint,
    MediaGenerationRequest,
    MediaReference,
    now,
)
from platform_core.models import (
    WebsiteGenerationJob,
    WebsitePage,
    WebsiteSection,
    WebsiteVersion,
)
from platform_core.services.media import MediaService
from platform_core.website.image_generation import (
    GeneratedImage,
    generate_image_bytes,
    hero_prompt,
    logo_prompt,
)
from platform_core.website.template_registry import TEMPLATES_BY_ID


class InterviewImageAdapter(Protocol):
    async def generate(
        self, prompt: str, *, aspect_ratio: str = "16:9"
    ) -> GeneratedImage | None: ...


class ExistingImageAdapter:
    async def generate(self, prompt: str, *, aspect_ratio: str = "16:9") -> GeneratedImage | None:
        return await generate_image_bytes(prompt, aspect_ratio=aspect_ratio, timeout_seconds=45)


def _palette(bp: BusinessBlueprint) -> tuple[str, ...]:
    template = TEMPLATES_BY_ID.get(bp.template_preferences.template_id or "")
    if template is None:
        return ()
    return (template.primary_color, template.accent_color)


def prompt_for(request: MediaGenerationRequest, bp: BusinessBlueprint) -> tuple[str, str]:
    """(prompt, aspect ratio) for one request. Nothing the owner said about
    staff, rooms or products is passed on — only the trade and the colours."""
    palette = _palette(bp)
    if request.role == "logo":
        name = str(bp.identity.get("display_name").value if bp.identity.get("display_name") else "")
        return logo_prompt(initial=name, primary=palette[0] if palette else None), "1:1"
    return (
        hero_prompt(
            display_name="",
            business_type=classification_seed(bp),
            description=None,
            palette=palette,
        ),
        "16:9",
    )


def _queued(bp: BusinessBlueprint, role: str) -> MediaGenerationRequest | None:
    return next(
        (r for r in bp.media_generation_requests if r.role == role and r.status == "queued"), None
    )


async def generate_interview_media(
    session: AsyncSession,
    *,
    business_id: UUID,
    actor_id: UUID,
    generation_job_id: UUID,
    adapter: InterviewImageAdapter | None = None,
) -> None:
    from platform_core.services.business_interview import BusinessInterviewService

    business = await BusinessInterviewService.load_business(session, business_id)
    bp = BusinessInterviewService.read(business)
    if bp.completion_state.generation_job_id != generation_job_id:
        return
    work = [r for r in (_queued(bp, "hero"), _queued(bp, "logo")) if r is not None]
    if not work:
        return
    # Generate outside the row lock — a slow provider must not block the owner.
    drawn: dict[str, GeneratedImage | None] = {}
    for request in work:
        prompt, aspect = prompt_for(request, bp)
        drawn[request.role] = await (adapter or ExistingImageAdapter()).generate(
            prompt, aspect_ratio=aspect
        )

    business = await BusinessInterviewService.load_business(session, business_id, lock=True)
    bp = BusinessInterviewService.read(business)
    if bp.completion_state.generation_job_id != generation_job_id:
        return
    for role, generated in drawn.items():
        request = _queued(bp, role)
        if request is None:
            continue
        if generated is None:
            request.status = "failed"
            request.reason = (
                "The logo could not be drawn. You can upload one any time."
                if role == "logo"
                else "Artwork could not be generated. Your website is usable without it."
            )
            continue
        if role == "logo":
            await _apply_logo(session, business_id, actor_id, bp, request, generated)
        else:
            await _apply_hero(
                session, business_id, actor_id, generation_job_id, bp, request, generated
            )
    bp.revision += 1
    await BusinessInterviewService.save(session, business, bp)


async def _apply_hero(
    session: AsyncSession,
    business_id: UUID,
    actor_id: UUID,
    generation_job_id: UUID,
    bp: BusinessBlueprint,
    request: MediaGenerationRequest,
    generated: GeneratedImage,
) -> None:
    asset = await MediaService.persist_generated(
        session,
        business_id=business_id,
        actor_id=actor_id,
        purpose="website",
        mime_type=generated.mime_type,
        body=generated.bytes,
        alt_text="AI-generated decorative artwork",
        original_filename="cover-artwork.png",
    )
    request.status = "ready"
    request.asset_id = UUID(asset["id"])
    bp.media_assets.append(
        MediaReference(
            asset_id=request.asset_id,
            role="hero",
            label="AI-generated cover artwork",
            source="AI_GENERATED",
        )
    )
    # While personalization is still running the draft is not ours to touch:
    # changing it now would look like an owner edit and discard the
    # personalized site. Personalization places the artwork when it finishes.
    job = await session.get(WebsiteGenerationJob, generation_job_id)
    if job is not None and job.status in {"pending", "running"}:
        return
    await place_ready_artwork(session, business_id, bp)


async def place_ready_artwork(
    session: AsyncSession, business_id: UUID, bp: BusinessBlueprint
) -> bool:
    """Put ready generated artwork into the current draft's hero, if it has none.

    Callers hold the business row lock, then this takes the draft lock — the
    same order personalization uses — so the artwork job and personalization
    serialize, and whichever finishes second does the placing.
    """
    ready = next(
        (
            r
            for r in bp.media_generation_requests
            if r.role == "hero" and r.status == "ready" and r.asset_id
        ),
        None,
    )
    if ready is None:
        return False
    draft = (
        (
            await session.execute(
                select(WebsiteVersion)
                .where(
                    WebsiteVersion.business_id == business_id,
                    WebsiteVersion.version_type == "draft",
                    WebsiteVersion.superseded_at.is_(None),
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .first()
    )
    if draft is None:
        return False
    hero = (
        (
            await session.execute(
                select(WebsiteSection)
                .join(WebsitePage)
                .where(
                    WebsitePage.website_version_id == draft.id,
                    WebsiteSection.section_type_id == "hero",
                )
                .order_by(WebsitePage.sort_order, WebsiteSection.sort_order)
            )
        )
        .scalars()
        .first()
    )
    # A picture the owner chose — or one they put there after the build — wins.
    if hero is None or (hero.content or {}).get("image_asset_id"):
        return False
    hero.content = {**(hero.content or {}), "image_asset_id": str(ready.asset_id)}
    draft.updated_at = now()
    return True


async def _apply_logo(
    session: AsyncSession,
    business_id: UUID,
    actor_id: UUID,
    bp: BusinessBlueprint,
    request: MediaGenerationRequest,
    generated: GeneratedImage,
) -> None:
    from platform_core.services.business_settings import BusinessSettingsService

    if any(m.role == "logo" and m.source == "USER_UPLOAD" for m in bp.media_assets):
        request.status = "failed"
        request.reason = "You uploaded your own logo, so it is used instead."
        return
    asset = await MediaService.persist_generated(
        session,
        business_id=business_id,
        actor_id=actor_id,
        purpose="brand",
        mime_type=generated.mime_type,
        body=generated.bytes,
        alt_text="AI-generated monogram logo",
        original_filename="generated-logo.png",
    )
    await BusinessSettingsService.patch_branding(
        session,
        business_id=business_id,
        raw={"logo_asset_id": asset["id"]},
        actor_id=actor_id,
        correlation_id=str(uuid4()),
    )
    request.status = "ready"
    request.asset_id = UUID(asset["id"])
    bp.media_assets.append(
        MediaReference(
            asset_id=request.asset_id, role="logo", label="AI-generated logo", source="AI_GENERATED"
        )
    )
    bp.logo_state = "generated"


# Name kept for callers and jobs from before logos could be drawn.
generate_interview_hero = generate_interview_media
