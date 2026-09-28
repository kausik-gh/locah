"""Super Admin review moderation; no Business role can reach these routes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_service_db_session
from platform_api.dependencies import require_super_admin
from platform_core.context import RequestContext
from platform_core.services.reviews import ReviewService
from platform_core.models import ReviewPhoto
from platform_core.exceptions import ResourceNotFound

router = APIRouter(prefix="/v1/admin/reviews", tags=["admin-reviews"])


class DecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=500)


class RemoveBody(DecisionBody):
    reason: str = Field(min_length=1, max_length=60)


class AppealBody(DecisionBody):
    restore: bool


class RedactBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spans: list[str] = Field(min_length=1, max_length=20)


def _meta(ctx: RequestContext) -> dict[str, str]:
    return {"correlation_id": ctx.correlation_id}


@router.get("/queue")
async def queue(
    ctx: RequestContext = Depends(require_super_admin()),
    session: AsyncSession = Depends(get_service_db_session),
) -> dict[str, Any]:
    return {"data": await ReviewService.queue(session), "meta": _meta(ctx)}


@router.post("/reports/{report_id}/dismiss")
async def dismiss_report(
    report_id: UUID, body: DecisionBody,
    ctx: RequestContext = Depends(require_super_admin()),
    session: AsyncSession = Depends(get_service_db_session),
) -> dict[str, Any]:
    await ReviewService.dismiss_report(session, report_id, ctx.identity_id, body.note)
    await session.commit()
    return {"data": {"id": str(report_id), "status": "dismissed"}, "meta": _meta(ctx)}


@router.post("/{review_id}/remove")
async def remove(
    review_id: UUID, body: RemoveBody,
    ctx: RequestContext = Depends(require_super_admin()),
    session: AsyncSession = Depends(get_service_db_session),
) -> dict[str, Any]:
    review = await ReviewService.remove(session, review_id, ctx.identity_id, body.reason, body.note)
    data = await ReviewService.serialize(session, review, public=False)
    await session.commit()
    return {"data": data, "meta": _meta(ctx)}


@router.post("/{review_id}/appeal")
async def decide_appeal(
    review_id: UUID, body: AppealBody,
    ctx: RequestContext = Depends(require_super_admin()),
    session: AsyncSession = Depends(get_service_db_session),
) -> dict[str, Any]:
    review = await ReviewService.decide_appeal(session, review_id, ctx.identity_id,
                                               restore=body.restore, note=body.note)
    data = await ReviewService.serialize(session, review, public=False)
    await session.commit()
    return {"data": data, "meta": _meta(ctx)}


@router.post("/{review_id}/redact")
async def redact(
    review_id: UUID, body: RedactBody,
    ctx: RequestContext = Depends(require_super_admin()),
    session: AsyncSession = Depends(get_service_db_session),
) -> dict[str, Any]:
    review = await ReviewService.redact(session, review_id, ctx.identity_id, body.spans)
    data = await ReviewService.serialize(session, review, public=False)
    await session.commit()
    return {"data": data, "meta": _meta(ctx)}


@router.post("/photos/{photo_id}/remove")
async def remove_photo(
    photo_id: UUID,
    ctx: RequestContext = Depends(require_super_admin()),
    session: AsyncSession = Depends(get_service_db_session),
) -> dict[str, Any]:
    await ReviewService.remove_photo(session, photo_id, ctx.identity_id)
    await session.commit()
    return {"data": {"id": str(photo_id), "removed": True}, "meta": _meta(ctx)}


@router.get("/photos/{photo_id}")
async def moderation_photo(
    photo_id: UUID,
    ctx: RequestContext = Depends(require_super_admin()),
    session: AsyncSession = Depends(get_service_db_session),
) -> Response:
    photo = (await session.execute(select(ReviewPhoto).where(ReviewPhoto.id == photo_id))).scalars().first()
    if photo is None:
        raise ResourceNotFound("Review photo")
    content, media_type = await ReviewService.photo(session, photo.business_id, photo_id,
                                                    own_review_id=photo.review_id)
    return Response(content=content, media_type=media_type,
                    headers={"Cache-Control": "no-store, private", "X-Robots-Tag": "noindex, nofollow"})
