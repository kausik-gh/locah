"""Website APIs (Stage 2 — Doc 12 §11 / §12)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.permissions import WEBSITE_EDIT, WEBSITE_PUBLISH, WEBSITE_READ
from platform_core.resolvers.website_resolver import WebsiteResolver
from platform_core.services.business import BusinessService
from platform_core.services.website import PageService, SectionService, WebsiteService, WebsiteVersionService
from platform_core.services.website_composition import (
    WebsiteCompositionService,
    WebsiteTemplateService,
)
from platform_core.services.website_generation import WebsiteGenerationService
from platform_core.services.website_publish import WebsitePublishService
from platform_core.services.website_images import WebsiteImageService
from platform_core.website.questionnaire import get_questionnaire

router = APIRouter(prefix="/v1/b", tags=["website"])


class GenerateWebsiteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intake: dict[str, Any] | None = None


class PatchPageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    is_published: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)


class PatchSectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: dict[str, Any] | None = None
    layout_variant: str | None = None
    is_visible: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)


class PatchThemeNavRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    navigation: list[dict[str, Any]] | None = None
    theme: dict[str, Any] | None = None


@router.get("/{business_id}/website/generation")
async def latest_generation(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(WEBSITE_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    job = await WebsiteGenerationService.latest_job(session, business_id=business_id)
    return {
        "data": WebsiteGenerationService.serialize_job(job) if job is not None else None,
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/website/questionnaire")
async def website_questionnaire(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(WEBSITE_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    business = await BusinessService.get_by_id(session, business_id)
    return {
        "data": get_questionnaire(business.business_type),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/website/generate")
async def generate_website(
    business_id: UUID,
    body: GenerateWebsiteRequest | None = None,
    actor: BusinessActorContext = Depends(require_business_actor(WEBSITE_EDIT)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    job = await WebsiteGenerationService.enqueue_generation(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        auto=False,
        intake=body.intake if body else None,
    )
    await session.commit()
    return {
        "data": WebsiteGenerationService.serialize_job(job),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/website")
async def get_website(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(WEBSITE_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await WebsiteService.get_aggregate(session, business_id=business_id)
    return {
        "data": data,
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.patch("/{business_id}/website/pages/{page_id}")
async def patch_page(
    business_id: UUID,
    page_id: UUID,
    body: PatchPageRequest,
    actor: BusinessActorContext = Depends(require_business_actor(WEBSITE_EDIT)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    page = await PageService.patch_page(
        session,
        business_id=business_id,
        page_id=page_id,
        actor_id=actor.request.identity_id,
        payload=body.model_dump(exclude_unset=True),
    )
    await session.commit()
    return {
        "data": WebsiteResolver.serialize_page(page),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.patch("/{business_id}/website/sections/{section_id}")
async def patch_section(
    business_id: UUID,
    section_id: UUID,
    body: PatchSectionRequest,
    actor: BusinessActorContext = Depends(require_business_actor(WEBSITE_EDIT)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    section = await SectionService.patch_section(
        session,
        business_id=business_id,
        section_id=section_id,
        actor_id=actor.request.identity_id,
        payload=body.model_dump(exclude_unset=True),
    )
    await session.commit()
    return {
        "data": WebsiteResolver.serialize_section(section),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/website/sections/{section_id}/generate-image")
async def generate_section_image(
    business_id: UUID,
    section_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(WEBSITE_EDIT)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    result = await WebsiteImageService.generate_section_image(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        section_id=section_id,
    )
    await session.commit()
    return {"data": result, "meta": {"correlation_id": actor.request.correlation_id}}


@router.patch("/{business_id}/website/theme")
async def patch_theme_navigation(
    business_id: UUID,
    body: PatchThemeNavRequest,
    actor: BusinessActorContext = Depends(require_business_actor(WEBSITE_EDIT)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    draft = await WebsiteVersionService.update_draft_chrome(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        navigation=body.navigation,
        theme=body.theme,
    )
    await session.commit()
    return {
        "data": WebsiteResolver.serialize_version(draft),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/website/preview-token")
async def get_preview_token(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(WEBSITE_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await WebsitePublishService.create_preview_token(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
    )
    return {
        "data": data,
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/website/publish")
async def publish_website(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(WEBSITE_PUBLISH)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await WebsitePublishService.publish(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
    )
    await session.commit()
    return {
        "data": data,
        "meta": {"correlation_id": actor.request.correlation_id},
    }


class AddSectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_type_id: str = Field(min_length=1, max_length=60)
    content: dict[str, Any] | None = None
    layout_variant: str | None = None
    # Index among the sections a person can see, not a raw sort_order: the
    # editor knows "third from the top", never the numbering behind it.
    position: int | None = Field(default=None, ge=0)


class ReorderSectionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_ids: list[UUID] = Field(min_length=1, max_length=40)


@router.get("/{business_id}/website/section-types")
async def list_section_types(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(WEBSITE_EDIT)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """What this business may add to a page — and what it may not, with the reason.

    Unavailable types are returned rather than filtered out, so the editor can
    say "Menu needs your offerings catalogue" instead of silently lacking a
    control the owner has seen on somebody else's site.
    """
    types = await WebsiteCompositionService.available_section_types(
        session, business_id=business_id
    )
    return {
        "data": {"section_types": types},
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/website/pages/{page_id}/sections")
async def add_section(
    business_id: UUID,
    page_id: UUID,
    body: AddSectionRequest,
    actor: BusinessActorContext = Depends(require_business_actor(WEBSITE_EDIT)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    section = await WebsiteCompositionService.add_section(
        session,
        business_id=business_id,
        page_id=page_id,
        actor_id=actor.request.identity_id,
        section_type_id=body.section_type_id,
        content=body.content,
        layout_variant=body.layout_variant,
        position=body.position,
    )
    await session.commit()
    return {
        "data": WebsiteResolver.serialize_section(section),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/website/sections/{section_id}/duplicate")
async def duplicate_section(
    business_id: UUID,
    section_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(WEBSITE_EDIT)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    section = await WebsiteCompositionService.duplicate_section(
        session,
        business_id=business_id,
        section_id=section_id,
        actor_id=actor.request.identity_id,
    )
    await session.commit()
    return {
        "data": WebsiteResolver.serialize_section(section),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.delete("/{business_id}/website/sections/{section_id}")
async def remove_section(
    business_id: UUID,
    section_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(WEBSITE_EDIT)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    page_id = await WebsiteCompositionService.remove_section(
        session,
        business_id=business_id,
        section_id=section_id,
        actor_id=actor.request.identity_id,
    )
    await session.commit()
    return {
        "data": {"removed": str(section_id), "page_id": str(page_id)},
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/website/pages/{page_id}/sections/reorder")
async def reorder_sections(
    business_id: UUID,
    page_id: UUID,
    body: ReorderSectionsRequest,
    actor: BusinessActorContext = Depends(require_business_actor(WEBSITE_EDIT)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    sections = await WebsiteCompositionService.reorder_sections(
        session,
        business_id=business_id,
        page_id=page_id,
        actor_id=actor.request.identity_id,
        section_ids=list(body.section_ids),
    )
    await session.commit()
    return {
        "data": {"sections": [WebsiteResolver.serialize_section(s) for s in sections]},
        "meta": {"correlation_id": actor.request.correlation_id},
    }


class ApplyTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(min_length=1, max_length=60)


@router.get("/{business_id}/website/templates")
async def list_templates(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(WEBSITE_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Templates this business can start from, best fit first.

    Every template is returned, not only the matching ones: a caterer may want
    the editorial layout, and filtering it out would be the platform deciding
    taste on the owner's behalf. Ones whose modules are off come back marked,
    with the module named.
    """
    data = await WebsiteTemplateService.list_for_business(session, business_id=business_id)
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.post("/{business_id}/website/templates/apply")
async def apply_template(
    business_id: UUID,
    body: ApplyTemplateRequest,
    actor: BusinessActorContext = Depends(require_business_actor(WEBSITE_EDIT)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Replace the draft with a template.

    This discards the current draft, which is the honest meaning of "use this
    one instead". A published site keeps serving what it published until the
    owner publishes again.
    """
    await WebsiteTemplateService.apply(
        session,
        business_id=business_id,
        template_id=body.template_id,
        actor_id=actor.request.identity_id,
    )
    await session.commit()
    aggregate = await WebsiteService.get_aggregate(session, business_id=business_id)
    return {"data": aggregate, "meta": {"correlation_id": actor.request.correlation_id}}
