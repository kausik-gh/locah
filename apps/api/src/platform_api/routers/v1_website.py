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
from platform_core.services.website_generation import WebsiteGenerationService
from platform_core.services.website_publish import WebsitePublishService
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
