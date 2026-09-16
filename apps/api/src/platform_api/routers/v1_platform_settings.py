from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.permissions import SETTINGS_READ, SETTINGS_UPDATE
from platform_core.services.business_settings import BusinessSettingsService

router = APIRouter(prefix="/v1/platform/businesses", tags=["settings"])


class VersionedPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int | None = Field(default=None, ge=1)


class RegionalSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timezone: str | None = None
    locale: str | None = None
    language: str | None = None
    currency: str | None = None
    country: str | None = None


class NotificationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transactional_email: bool | None = None
    transactional_in_app: bool | None = None
    marketing_email: bool | None = None


class PatchSettingsRequest(VersionedPatch):
    regional: RegionalSettings | None = None
    notifications: NotificationSettings | None = None
    timezone: str | None = None
    locale: str | None = None
    language: str | None = None
    currency: str | None = None
    country: str | None = None


class PatchProfileRequest(VersionedPatch):
    display_name: str | None = None
    description: str | None = None
    tagline: str | None = None
    website_url: str | None = None
    contact: dict[str, Any] | None = None
    social_links: dict[str, str] | None = None


class PatchBrandingRequest(VersionedPatch):
    display_name: str | None = None
    logo_asset_id: UUID | None = None
    cover_asset_id: UUID | None = None
    tagline: str | None = None
    brand_color: str | None = None
    font_theme: str | None = None


class PatchPreferencesRequest(VersionedPatch):
    visibility: str | None = None
    onboarding_completed: bool | None = None
    date_format: str | None = None
    time_format: str | None = None
    measurement_system: str | None = None
    default_dashboard: str | None = None


def _patch_payload(body: BaseModel) -> dict[str, Any]:
    return body.model_dump(exclude_unset=True)


@router.get("/{business_id}/settings")
async def get_settings(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(SETTINGS_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await BusinessSettingsService.get_settings(session, business_id)
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.patch("/{business_id}/settings")
async def patch_settings(
    business_id: UUID,
    body: PatchSettingsRequest,
    actor: BusinessActorContext = Depends(require_business_actor(SETTINGS_UPDATE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    payload = _patch_payload(body)
    version = payload.pop("version", None)
    data = await BusinessSettingsService.patch_settings(
        session,
        business_id=business_id,
        raw=payload,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        expected_version=version,
    )
    await session.commit()
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.get("/{business_id}/profile")
async def get_profile(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(SETTINGS_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await BusinessSettingsService.get_profile(session, business_id)
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.patch("/{business_id}/profile")
async def patch_profile(
    business_id: UUID,
    body: PatchProfileRequest,
    actor: BusinessActorContext = Depends(require_business_actor(SETTINGS_UPDATE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    payload = _patch_payload(body)
    version = payload.pop("version", None)
    data = await BusinessSettingsService.patch_profile(
        session,
        business_id=business_id,
        raw=payload,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        expected_version=version,
    )
    await session.commit()
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.get("/{business_id}/branding")
async def get_branding(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(SETTINGS_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await BusinessSettingsService.get_branding(session, business_id)
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.patch("/{business_id}/branding")
async def patch_branding(
    business_id: UUID,
    body: PatchBrandingRequest,
    actor: BusinessActorContext = Depends(require_business_actor(SETTINGS_UPDATE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    payload = _patch_payload(body)
    version = payload.pop("version", None)
    data = await BusinessSettingsService.patch_branding(
        session,
        business_id=business_id,
        raw=payload,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        expected_version=version,
    )
    await session.commit()
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.get("/{business_id}/preferences")
async def get_preferences(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(SETTINGS_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await BusinessSettingsService.get_preferences(session, business_id)
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.patch("/{business_id}/preferences")
async def patch_preferences(
    business_id: UUID,
    body: PatchPreferencesRequest,
    actor: BusinessActorContext = Depends(require_business_actor(SETTINGS_UPDATE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    payload = _patch_payload(body)
    version = payload.pop("version", None)
    data = await BusinessSettingsService.patch_preferences(
        session,
        business_id=business_id,
        raw=payload,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        expected_version=version,
    )
    await session.commit()
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}
