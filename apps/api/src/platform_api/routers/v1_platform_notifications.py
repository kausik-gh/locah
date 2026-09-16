"""Core Notifications APIs (Stage 7 — Doc 09 CORE-015).

`core-notifications` is a Platform Core group, always entitled, so gates [6]
Entitlement and [7] module-state never apply here (AUD-01 rule).

Every route is scoped to the *calling* identity. There is no route to read
another member's notifications: a notification belonging to someone else
resolves as 404, never 403, so its existence does not leak (Doc 09 ACC-011).

Because of that self-scoping, the inbox routes use `require_business_member()`
— gates [1]-[5] only, no gate [8]. A member must be able to read notifications
addressed to them, and under AUD-07 a new invitee or lead assignee holds no
grants at all; gating a personal inbox behind a delegated permission would make
those notifications structurally undeliverable. What *reaches* an inbox is
still permission-gated per resource at fan-out. Writing preferences keeps gate
[8] on `notifications.manage_preferences`.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import (
    BusinessActorContext,
    require_business_actor,
    require_business_member,
)
from platform_core.permissions import NOTIFICATIONS_MANAGE_PREFERENCES
from platform_core.services.notification import NotificationService

router = APIRouter(prefix="/v1/platform/businesses", tags=["notifications"])


class SetPreferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    in_app_enabled: bool


@router.get("/{business_id}/notifications")
async def list_notifications(
    business_id: UUID,
    unread_only: bool = Query(default=False),
    category: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    actor: BusinessActorContext = Depends(require_business_member()),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    identity_id = actor.request.identity_id
    notifications = await NotificationService.list_for_recipient(
        session,
        business_id=business_id,
        identity_id=identity_id,
        unread_only=unread_only,
        category=category,
        limit=limit,
    )
    unread = await NotificationService.unread_count(
        session, business_id=business_id, identity_id=identity_id
    )
    return {
        "data": [NotificationService.serialize(n) for n in notifications],
        "meta": {
            "correlation_id": actor.request.correlation_id,
            "count": len(notifications),
            "unread_count": unread,
        },
    }


@router.get("/{business_id}/notifications/unread-count")
async def unread_count(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_member()),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    unread = await NotificationService.unread_count(
        session, business_id=business_id, identity_id=actor.request.identity_id
    )
    return {
        "data": {"unread_count": unread},
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/notifications/{notification_id}/read")
async def mark_read(
    business_id: UUID,
    notification_id: UUID,
    actor: BusinessActorContext = Depends(require_business_member()),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    notification = await NotificationService.mark_read(
        session,
        business_id=business_id,
        identity_id=actor.request.identity_id,
        notification_id=notification_id,
    )
    await session.commit()
    return {
        "data": NotificationService.serialize(notification),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/notifications/read-all")
async def mark_all_read(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_member()),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    updated = await NotificationService.mark_all_read(
        session, business_id=business_id, identity_id=actor.request.identity_id
    )
    await session.commit()
    return {
        "data": {"marked_read": updated},
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/notification-preferences")
async def list_preferences(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_member()),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    prefs = await NotificationService.list_preferences(
        session, business_id=business_id, identity_id=actor.request.identity_id
    )
    return {
        "data": prefs,
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.put("/{business_id}/notification-preferences")
async def set_preference(
    business_id: UUID,
    body: SetPreferenceRequest,
    actor: BusinessActorContext = Depends(
        require_business_actor(NOTIFICATIONS_MANAGE_PREFERENCES)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    pref = await NotificationService.set_preference(
        session,
        business_id=business_id,
        identity_id=actor.request.identity_id,
        category=body.category,
        in_app_enabled=body.in_app_enabled,
    )
    await session.commit()
    return {
        "data": NotificationService.serialize_preference(pref),
        "meta": {"correlation_id": actor.request.correlation_id},
    }
