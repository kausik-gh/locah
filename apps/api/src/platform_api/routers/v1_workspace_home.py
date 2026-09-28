"""The Workspace home for whoever is signed in (Business OS Guide §3; Capability
Universe §7.2): the bands that answer their role's question, from real data
within their permissions and location scope."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_member
from platform_core.services.module_readiness import module_states
from platform_core.services.role_home import RoleHomeService

router = APIRouter(prefix="/v1/platform/businesses", tags=["workspace-home"])


@router.get("/{business_id}/home")
async def home(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_member()),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    from platform_core.authorization.resolver import AuthorizationService

    permissions = frozenset(await AuthorizationService.effective_permissions(
        session, business_id=business_id, identity_id=actor.request.identity_id))
    live = {k for k, v in (await module_states(session, business_id)).items() if v in ("enabled", "ready", "active")}
    data = await RoleHomeService.compose(session, actor.business, actor.actor_membership, permissions, live)
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}
