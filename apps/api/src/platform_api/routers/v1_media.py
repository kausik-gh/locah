"""Media upload APIs (Doc 12 §15.3).

Two steps, so the API never handles binary content:

    POST /v1/b/{business_id}/media/upload-url   -> signed URL + pending asset
    POST /v1/b/{business_id}/media/{asset_id}/complete

The permission is resolved from the declared `purpose` (see
`MediaService.PURPOSE_PERMISSIONS`) rather than being fixed per route, so a
website image needs `website.edit`, an offering image needs `offerings.update`,
and so on — all canonical permissions, no new `media.*` identifier invented.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import (
    get_request_context,
    resolve_business_actor,
    resolve_business_member,
    security,
)
from platform_core.context import RequestContext
from platform_core.exceptions import AuthenticationRequired, PermissionDenied
from platform_core.permissions import WEBSITE_READ
from platform_core.services.media import MediaService

router = APIRouter(prefix="/v1/b", tags=["media"])


class UploadUrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: str
    mime_type: str
    size_bytes: int | None = Field(default=None, ge=0)
    original_filename: str | None = None
    alt_text: str | None = None


def _raw_jwt(credentials: HTTPAuthorizationCredentials | None) -> str:
    if credentials is None or not credentials.credentials:
        raise AuthenticationRequired("Missing bearer token")
    return credentials.credentials


@router.post("/{business_id}/media/upload-url")
async def create_upload_url(
    business_id: UUID,
    body: UploadUrlRequest,
    ctx: RequestContext = Depends(get_request_context),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    # Permission depends on what the asset is for, so it is resolved per request
    # rather than baked into the route decorator.
    permission = MediaService.permission_for(body.purpose)
    actor = await resolve_business_actor(business_id, permission, ctx, session)

    data = await MediaService.request_upload(
        session,
        business_id=business_id,
        identity_id=actor.request.identity_id,
        supabase_user_id=actor.request.supabase_user_id,
        user_jwt=_raw_jwt(credentials),
        purpose=body.purpose,
        mime_type=body.mime_type,
        size_bytes=body.size_bytes,
        original_filename=body.original_filename,
        alt_text=body.alt_text,
    )
    await session.commit()
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.post("/{business_id}/media/{asset_id}/complete")
async def complete_upload(
    business_id: UUID,
    asset_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    # Two stages, so the caller cannot pick their own permission. Stage 1 is
    # membership only (no permission), which is enough to look the asset up
    # within this Business; stage 2 requires the permission for the purpose
    # STORED on the asset, never one supplied in the request. Doing it this way
    # round avoids demanding an unrelated permission (e.g. website.read) from
    # someone completing an offering image.
    actor = await resolve_business_member(business_id, ctx, session)
    stored = await MediaService.get(session, business_id=business_id, asset_id=asset_id)
    required = MediaService.permission_for(str(stored.get("purpose") or ""))
    if required not in actor.request.effective_permissions:
        raise PermissionDenied(required)

    data = await MediaService.complete_upload(
        session,
        business_id=business_id,
        asset_id=asset_id,
        actor_id=actor.request.identity_id,
    )
    await session.commit()
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.get("/{business_id}/media")
async def list_media(
    business_id: UUID,
    purpose: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    # Reading a Business's own media library rides on website.read, the
    # broadest read permission every Website editor already holds.
    actor = await resolve_business_actor(business_id, WEBSITE_READ, ctx, session)
    data = await MediaService.list_for_business(
        session, business_id=business_id, purpose=purpose, limit=limit
    )
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}
