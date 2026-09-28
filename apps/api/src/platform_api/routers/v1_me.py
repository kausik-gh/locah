from typing import Any
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import get_request_context
from platform_core.context import RequestContext
from platform_core.services.consumer_activity import ConsumerActivityService
from platform_core.services.identity import IdentityService
from platform_core.services.invoicing import share_token
from platform_core.services.reviews import review_token

router = APIRouter(prefix="/v1/me", tags=["identity"])


class ProfileResponse(BaseModel):
    id: str
    email: str
    display_name: str | None
    avatar_url: str | None


class ContextResponse(BaseModel):
    identity_id: str
    active_context: str
    business_id: str | None
    location_id: str | None
    is_super_admin: bool
    permissions: list[str]
    entitled_modules: list[str]
    module_states: dict[str, str]
    default_business_id: str | None = None
    last_business_id: str | None = None
    primary_business_id: str | None = None


@router.get("")
async def get_me_v1(
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    identity = await IdentityService.get_by_id(session, ctx.identity_id)
    await session.commit()
    return {
        "data": ProfileResponse(
            id=str(ctx.identity_id),
            email=ctx.email,
            display_name=identity.display_name if identity else ctx.display_name,
            avatar_url=identity.avatar_url if identity else None,
        ).model_dump(),
        "meta": {"correlation_id": ctx.correlation_id},
    }


@router.get("/context")
async def get_context(
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    prefs = await IdentityService.get_consumer_preferences(session, ctx.identity_id)
    return {
        "data": ContextResponse(
            identity_id=str(ctx.identity_id),
            active_context=ctx.active_context.value,
            business_id=str(ctx.business_id) if ctx.business_id else None,
            location_id=str(ctx.location_id) if ctx.location_id else None,
            is_super_admin=ctx.is_super_admin,
            permissions=sorted(ctx.effective_permissions),
            entitled_modules=sorted(ctx.effective_entitlements.modules),
            module_states={k: v.activation_state for k, v in ctx.module_states.items()},
            default_business_id=prefs.get("default_business_id"),
            last_business_id=prefs.get("last_business_id"),
            primary_business_id=prefs.get("primary_business_id"),
        ).model_dump(),
        "meta": {"correlation_id": ctx.correlation_id},
    }


@router.get("/activity")
async def get_my_activity(
    resource_type: str | None = Query(default=None),
    business_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """My Activity — the caller's own consumer-side activity (Doc 09 ACC-011).

    Identity-scoped, not Business-scoped: this is the consumer surface, and it
    must stay separate from the Business Workspace (Doc 11 §17.7 exit: "My
    Activity remains separate from Workspace"). No Business permission is
    consulted and none is required — the rows belong to the caller.

    Coverage is bookings and review invitations for linked customers. Orders and Payments do not write to
    `consumer_activity_projections` yet, and guest activity is not linked to an
    account pending FL-DEC-024, so this feed is deliberately partial rather
    than padded with data it cannot truthfully claim.
    """
    # Verified-email guest history joins this identity first (Doc 12: verified
    # identifiers only); idempotent, so every visit is safe.
    from platform_core.services.customer_account import CustomerAccountService

    if await CustomerAccountService.link_verified(session, ctx.identity_id):
        await session.commit()
    activities = await ConsumerActivityService.list_for_identity(
        session,
        identity_id=ctx.identity_id,
        resource_type=resource_type,
        business_id=business_id,
        limit=limit,
    )
    # The projection is identity-scoped. Derive the one-use action link only
    # for an invitation whose newest activity is still an open request; never
    # expose review credentials on a business-scoped or public list.
    seen_reviews: set[str] = set()
    for item in activities:
        summary = item.get("summary") or {}
        slug = summary.get("business_slug")
        if isinstance(slug, str) and item["resource_type"] != "review_invitation":
            item["account_url"] = f"/{slug}/account"
            finished = summary.get("status") in ("completed", "cancelled", "rejected")
            if item["resource_type"] == "order" and summary.get("tracking_token") and not finished:
                item["action_url"] = f"/{slug}/track/{item['resource_id']}?token={summary['tracking_token']}"
            elif item["resource_type"] == "bill":
                item["action_url"] = f"/{slug}/bill/{share_token(UUID(item['business_id']), UUID(item['resource_id']))}"
            summary.pop("tracking_token", None)
        if item["resource_type"] != "review_invitation":
            continue
        key = item["resource_id"]
        if key in seen_reviews:
            continue
        seen_reviews.add(key)
        if item["activity_type"] != "review.requested":
            continue
        summary = item.get("summary") or {}
        slug = summary.get("business_slug")
        expires = summary.get("expires_at")
        if not isinstance(slug, str) or not isinstance(expires, str):
            continue
        try:
            if datetime.fromisoformat(expires) <= datetime.now(timezone.utc):
                continue
            item["action_url"] = f"/{slug}/review/{review_token(UUID(item['business_id']), UUID(key))}"
        except (ValueError, TypeError):
            continue
    return {
        "data": activities,
        "meta": {
            "correlation_id": ctx.correlation_id,
            "count": len(activities),
            # Named so the consumer UI can state its own limits truthfully
            # instead of implying an empty feed means no activity happened.
            "covered_resource_types": ["order", "booking", "bill", "quote", "membership", "review_invitation"],
        },
    }



# ---------------------------------------------------------------- one business's "My account" (Founder §12)
async def _public_business(session: AsyncSession, slug: str) -> Any:
    from platform_core.exceptions import ResourceNotFound
    from platform_core.services.business import BusinessService

    business = await BusinessService.get_by_slug(session, slug)
    if business is None or business.deleted_at is not None or business.visibility == "private":
        raise ResourceNotFound("Business")
    return business


@router.get("/businesses/{slug}/account")
async def my_account_with_business(
    slug: str,
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Everything this signed-in customer has with one business — orders,
    bookings, bills, khata, quotes, memberships — for "My account" on that
    business's website. Identity-scoped: only contacts linked to the caller."""
    from platform_core.services.customer_account import CustomerAccountService

    if await CustomerAccountService.link_verified(session, ctx.identity_id):
        await session.commit()
    business = await _public_business(session, slug)
    data = await CustomerAccountService.account(session, business, ctx.identity_id)
    await session.commit()
    return {"data": data, "meta": {"correlation_id": ctx.correlation_id}}


@router.get("/businesses/{slug}/orders/{order_id}/reorder")
async def reorder_lines(
    slug: str,
    order_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Order again (§12.3 "Repeat last order" on the website): the lines of one
    of the caller's orders at today's price, and which can no longer be bought."""
    from platform_core.services.customer_account import CustomerAccountService

    business = await _public_business(session, slug)
    data = await CustomerAccountService.reorder(session, business, ctx.identity_id, order_id)
    return {"data": data, "meta": {"correlation_id": ctx.correlation_id}}
