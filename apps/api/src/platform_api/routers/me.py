from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.auth import get_current_user, RequestContext as LegacyContext
from platform_api.db import get_db_session
from platform_core.services.identity import IdentityService

router = APIRouter(prefix="/me", tags=["identity"])


class ProfileResponse(BaseModel):
    id: str
    auth_user_id: str
    email: str
    display_name: str | None
    avatar_url: str | None


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = None
    avatar_url: str | None = None


@router.get("", response_model=ProfileResponse)
async def get_me(
    context: LegacyContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    identity = await IdentityService.bootstrap_identity(
        session, context.auth_user_id, context.email
    )
    await session.commit()
    await session.refresh(identity)
    return ProfileResponse(
        id=str(identity.id),
        auth_user_id=str(identity.supabase_user_id),
        email=identity.email,
        display_name=identity.display_name,
        avatar_url=identity.avatar_url,
    )


@router.patch("", response_model=ProfileResponse)
async def update_me(
    update_data: ProfileUpdateRequest,
    context: LegacyContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    identity = await IdentityService.update_profile(
        session,
        context.auth_user_id,
        display_name=update_data.display_name,
        avatar_url=update_data.avatar_url,
    )
    if not identity:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Profile not found")
    await session.commit()
    await session.refresh(identity)
    return ProfileResponse(
        id=str(identity.id),
        auth_user_id=str(identity.supabase_user_id),
        email=identity.email,
        display_name=identity.display_name,
        avatar_url=identity.avatar_url,
    )
