"""The page a new team member opens from their join link.

The link's token is the only credential here: it reads the invitation (who
added them, the role, where) before the person has an account. Joining itself
happens through the invitation accept endpoint, signed in as the invited
email — the token alone never grants access to the business.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_core.services.staff import StaffService

router = APIRouter(prefix="/v1/public", tags=["team-join"])


@router.get("/join/{token}")
async def join_view(token: str, session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    return {"data": await StaffService.public_view(session, token)}
