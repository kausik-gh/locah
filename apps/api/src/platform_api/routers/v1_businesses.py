from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import get_request_context
from platform_core.context import RequestContext
from platform_core.services.business import BusinessService
from platform_core.services.identity import IdentityService

router = APIRouter(prefix="/v1/platform/businesses", tags=["business"])


class CreateBusinessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(..., min_length=1, max_length=200)
    business_type: str | None = None
    # The kind of business the owner picked (search-first taxonomy). A seed for
    # the interview and recommendations — never a module grant.
    category_key: str | None = Field(default=None, max_length=40)
    subcategory_key: str | None = Field(default=None, max_length=60)
    slug: str | None = None
    logo_asset_id: UUID | None = None
    timezone: str | None = None
    currency: str | None = None
    country: str | None = None
    language: str | None = None


class StartConversationRequest(BaseModel):
    """Create Business by talking: everything is optional."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=200)
    category_key: str | None = Field(default=None, max_length=40)
    subcategory_key: str | None = Field(default=None, max_length=60)


class SwitchBusinessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    set_as_default: bool = False


class BusinessSummary(BaseModel):
    id: str
    slug: str
    display_name: str
    state: str
    visibility: str
    business_type: str | None = None


@router.post("")
async def create_business(
    body: CreateBusinessRequest,
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    business, location, membership, profile = await BusinessService.create_business(
        session,
        identity_id=ctx.identity_id,
        correlation_id=ctx.correlation_id,
        payload=body.model_dump(exclude_none=True),
    )
    await session.commit()
    prefs = await IdentityService.get_consumer_preferences(session, ctx.identity_id)
    hydrated: dict[str, Any] = BusinessService.hydrate_create_response(
        business=business,
        location=location,
        membership=membership,
        profile=profile,
        correlation_id=ctx.correlation_id,
        preferences=prefs,
    )
    return hydrated


@router.post("/start")
async def start_conversation(
    body: StartConversationRequest,
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Start (or resume an untouched) Business to talk to LOCAH about.

    No form first: a name and a category are welcome but not required. The
    interview asks for the name if it was not given.
    """
    business, created = await BusinessService.start_conversation(
        session,
        identity_id=ctx.identity_id,
        correlation_id=ctx.correlation_id,
        display_name=body.display_name,
        category_key=body.category_key,
        subcategory_key=body.subcategory_key,
    )
    await session.commit()
    return {"data": {"business": {"id": str(business.id), "slug": business.slug,
                                  "display_name": business.display_name}, "created": created},
            "meta": {"correlation_id": ctx.correlation_id}}


@router.post("/{business_id}/switch")
async def switch_business(
    business_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
    body: SwitchBusinessRequest = SwitchBusinessRequest(),
) -> dict[str, Any]:
    """Switch active Business context for the authenticated identity (Stage 2B)."""
    result: dict[str, Any] = await BusinessService.switch_business(
        session,
        identity_id=ctx.identity_id,
        business_id=business_id,
        correlation_id=ctx.correlation_id,
        set_as_default=body.set_as_default,
    )
    await session.commit()
    return result


@router.get("")
async def list_businesses(
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    businesses = await BusinessService.list_for_identity(session, ctx.identity_id)
    return {
        "data": [
            BusinessSummary(
                id=str(b.id),
                slug=b.slug,
                display_name=b.display_name,
                state=b.state,
                visibility=b.visibility,
                business_type=b.business_type,
            ).model_dump()
            for b in businesses
        ],
        "meta": {"correlation_id": ctx.correlation_id},
    }
