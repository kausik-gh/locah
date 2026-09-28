"""Verified reviews: business actions and the customer's one-use interaction link.

Only a completed interaction mints a link. A business can reply, feature and
report, but cannot change the reviewer's words, rating or moderation state.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.context_resolver import bind_public_context
from platform_core.exceptions import ResourceNotFound
from platform_core.models import BusinessModuleState
from platform_core.permissions import CUSTOMERS_READ, REVIEWS_MANAGE, REVIEWS_READ, REVIEWS_REPLY
from platform_core.services.business import BusinessService
from platform_core.services.reviews import ReviewService

router = APIRouter(prefix="/v1/platform/businesses", tags=["reviews"])
public_router = APIRouter(prefix="/v1/public/websites", tags=["reviews-public"])
MODULE = "reviews"
ACTIVE = frozenset({"enabled", "ready", "active"})


class PhotoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    media_type: Literal["image/jpeg", "image/png", "image/webp"]
    data_base64: str = Field(max_length=2_100_000)


class ReviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: int = Field(ge=1, le=5)
    body: str | None = Field(default=None, max_length=2000)
    photos: list[PhotoInput] = Field(default_factory=list, max_length=3)


class ReviewUpdateBody(ReviewBody):
    remove_photo_ids: list[UUID] = Field(default_factory=list, max_length=3)


class ReplyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str | None = Field(default=None, max_length=1000)


class FeatureBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    featured: bool


class ReportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=60)
    note: str | None = Field(default=None, max_length=500)


class AppealBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = Field(min_length=5, max_length=1000)


def _meta(actor: BusinessActorContext) -> dict[str, str]:
    return {"correlation_id": actor.request.correlation_id}


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"


async def _public_business(session: AsyncSession, slug: str) -> UUID:
    business = await BusinessService.get_by_slug(session, slug)
    if business is None or business.deleted_at is not None or business.visibility == "private":
        raise ResourceNotFound("Reviews")
    await bind_public_context(session, business.id)
    state = (await session.execute(select(BusinessModuleState).where(
        BusinessModuleState.business_id == business.id,
        BusinessModuleState.module_id == MODULE,
    ))).scalars().first()
    if state is None or state.activation_state not in ACTIVE:
        raise ResourceNotFound("Reviews")
    return UUID(str(business.id))


@router.get("/{business_id}/reviews")
async def business_reviews(
    business_id: UUID,
    view: Literal["all", "reply", "low", "featured", "reported", "removed"] = "all",
    actor: BusinessActorContext = Depends(require_business_actor(REVIEWS_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await ReviewService.business_list(
        session, business_id, view=view,
        can_see_contact=CUSTOMERS_READ in actor.request.effective_permissions,
    )
    return {"data": data, "meta": _meta(actor)}


@router.put("/{business_id}/reviews/{review_id}/reply")
async def reply(
    business_id: UUID, review_id: UUID, body: ReplyBody,
    actor: BusinessActorContext = Depends(require_business_actor(REVIEWS_REPLY, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    review = await ReviewService.reply(session, business_id, review_id, actor.request.identity_id, body.body)
    data = await ReviewService.serialize(session, review, public=False)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.put("/{business_id}/reviews/{review_id}/feature")
async def feature(
    business_id: UUID, review_id: UUID, body: FeatureBody,
    actor: BusinessActorContext = Depends(require_business_actor(REVIEWS_MANAGE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    review = await ReviewService.feature(session, business_id, review_id, actor.request.identity_id, body.featured)
    data = await ReviewService.serialize(session, review, public=False)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/reviews/{review_id}/report")
async def report(
    business_id: UUID, review_id: UUID, body: ReportBody,
    actor: BusinessActorContext = Depends(require_business_actor(REVIEWS_MANAGE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    report_ = await ReviewService.report(session, business_id, review_id, actor.request.identity_id,
                                         body.reason, body.note)
    await session.commit()
    return {"data": {"id": str(report_.id), "status": report_.status}, "meta": _meta(actor)}


@router.get("/{business_id}/reviews/photos/{photo_id}")
async def business_photo(
    business_id: UUID, photo_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(REVIEWS_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    content, media_type = await ReviewService.photo(session, business_id, photo_id)
    return Response(content=content, media_type=media_type,
                    headers={"Cache-Control": "no-store, private", "X-Robots-Tag": "noindex, nofollow"})


@public_router.get("/{slug}/reviews")
async def public_reviews(
    slug: str,
    featured: bool = False,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    business_id = await _public_business(session, slug)
    data = await ReviewService.public_reviews(session, business_id, featured=featured, limit=limit, offset=offset)
    return {"data": data, "meta": {}}


@public_router.get("/{slug}/reviews/photos/{photo_id}")
async def public_photo(
    slug: str, photo_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    business_id = await _public_business(session, slug)
    content, media_type = await ReviewService.photo(session, business_id, photo_id)
    return Response(content=content, media_type=media_type)


@public_router.get("/{slug}/review/{token}")
async def reviewer_view(
    slug: str, token: str, response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    _no_store(response)
    return {"data": await ReviewService.reviewer_view(session, slug, token), "meta": {}}


@public_router.post("/{slug}/review/{token}")
async def write_review(
    slug: str, token: str, body: ReviewBody, response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    _no_store(response)
    data = await ReviewService.write(session, slug, token, rating=body.rating, body=body.body,
                                     photos=[p.model_dump() for p in body.photos])
    await session.commit()
    return {"data": data, "meta": {}}


@public_router.put("/{slug}/review/{token}")
async def update_review(
    slug: str, token: str, body: ReviewUpdateBody, response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    _no_store(response)
    data = await ReviewService.update_by_reviewer(
        session, slug, token, rating=body.rating, body=body.body,
        remove_photo_ids=[str(p) for p in body.remove_photo_ids],
        photos=[p.model_dump() for p in body.photos],
    )
    await session.commit()
    return {"data": data, "meta": {}}


@public_router.post("/{slug}/review/{token}/decline")
async def decline_review(
    slug: str, token: str, response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    _no_store(response)
    data = await ReviewService.decline(session, slug, token)
    await session.commit()
    return {"data": data, "meta": {}}


@public_router.post("/{slug}/review/{token}/appeal")
async def appeal_review(
    slug: str, token: str, body: AppealBody, response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    _no_store(response)
    data = await ReviewService.appeal(session, slug, token, body.note)
    await session.commit()
    return {"data": data, "meta": {}}


@public_router.get("/{slug}/review/{token}/photos/{photo_id}")
async def own_photo(
    slug: str, token: str, photo_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    view = await ReviewService.reviewer_view(session, slug, token)
    review = view.get("review")
    if review is None:
        raise ResourceNotFound("Photo")
    inv, _ = await ReviewService._by_token(session, slug, token)
    content, media_type = await ReviewService.photo(session, inv.business_id, photo_id,
                                                    own_review_id=UUID(review["id"]))
    return Response(content=content, media_type=media_type,
                    headers={"Cache-Control": "no-store, private", "X-Robots-Tag": "noindex, nofollow"})
