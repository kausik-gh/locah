"""Business settings & configuration (Stage 2E — core-settings)."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.gates import assert_business_mutable
from platform_core.models import Business, BusinessProfile
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService
from platform_core.validation.business_settings import (
    validate_branding_fields,
    validate_media_asset_reference,
    validate_preferences_fields,
    validate_profile_fields,
    validate_regional_settings,
)


def _merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


class BusinessSettingsService:
    @staticmethod
    async def _load_business_for_update(
        session: AsyncSession, business_id: uuid.UUID
    ) -> Business:
        result = await session.execute(
            select(Business)
            .where(Business.id == business_id, Business.deleted_at.is_(None))
            .with_for_update()
        )
        business = result.scalars().first()
        if business is None:
            raise ResourceNotFound("Business")
        return business

    @staticmethod
    async def _ensure_profile(session: AsyncSession, business_id: uuid.UUID) -> BusinessProfile:
        profile = await BusinessService.get_profile(session, business_id)
        if profile is None:
            profile = BusinessProfile(
                business_id=business_id,
                contact={},
                social_links={},
            )
            session.add(profile)
            await session.flush()
        return profile

    @staticmethod
    def _check_version(business: Business, expected_version: int | None) -> None:
        if expected_version is None:
            return
        if business.version != expected_version:
            raise ConflictError(
                "Stale business version",
                details={
                    "expected_version": expected_version,
                    "current_version": business.version,
                },
            )

    @staticmethod
    async def _publish(
        session: AsyncSession,
        *,
        event_type: str,
        audit_action: str,
        business: Business,
        actor_id: uuid.UUID,
        correlation_id: str,
        before_state: dict[str, Any] | None,
        after_state: dict[str, Any],
    ) -> None:
        await OutboxService.publish(
            session,
            event_type=event_type,
            payload={
                "business_id": str(business.id),
                "version": business.version,
                "after": after_state,
            },
            business_id=business.id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type=event_type,
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business.id,
            resource_type="business",
            resource_id=business.id,
            action=audit_action,
            before_state=before_state,
            after_state=after_state,
        )

    @staticmethod
    def serialize_settings(business: Business) -> dict[str, Any]:
        settings = dict(business.settings or {})
        return {
            "regional": {
                "timezone": settings.get("timezone"),
                "locale": settings.get("locale"),
                "language": settings.get("language"),
                "currency": settings.get("currency"),
                "country": settings.get("country"),
            },
            "notifications": settings.get("notifications", {}),
            "version": business.version,
        }

    @staticmethod
    def serialize_profile(business: Business, profile: BusinessProfile) -> dict[str, Any]:
        return {
            "display_name": business.display_name,
            "description": profile.description,
            "tagline": profile.tagline,
            "contact": profile.contact or {},
            "website_url": profile.website_url,
            "social_links": profile.social_links or {},
            "completeness_score": profile.completeness_score,
            "version": business.version,
        }

    @staticmethod
    def serialize_branding(business: Business, profile: BusinessProfile) -> dict[str, Any]:
        settings = dict(business.settings or {})
        branding = dict(settings.get("branding") or {})
        return {
            "display_name": business.display_name,
            "logo_asset_id": str(profile.logo_asset_id) if profile.logo_asset_id else None,
            "cover_asset_id": str(profile.cover_asset_id) if profile.cover_asset_id else None,
            "tagline": profile.tagline,
            "brand_color": branding.get("brand_color"),
            "font_theme": branding.get("font_theme"),
            "version": business.version,
        }

    @staticmethod
    def serialize_preferences(business: Business) -> dict[str, Any]:
        settings = dict(business.settings or {})
        metadata = dict(business.metadata_ or {})
        preferences = dict(settings.get("preferences") or {})
        onboarding = dict(metadata.get("onboarding") or {})
        return {
            "visibility": business.visibility,
            "onboarding_completed": onboarding.get("completed", False),
            "date_format": preferences.get("date_format"),
            "time_format": preferences.get("time_format"),
            "measurement_system": preferences.get("measurement_system"),
            "default_dashboard": preferences.get("default_dashboard"),
            "version": business.version,
        }

    @staticmethod
    async def get_settings(session: AsyncSession, business_id: uuid.UUID) -> dict[str, Any]:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        return BusinessSettingsService.serialize_settings(business)

    @staticmethod
    async def patch_settings(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        raw: dict[str, Any],
        actor_id: uuid.UUID,
        correlation_id: str,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        business = await BusinessSettingsService._load_business_for_update(session, business_id)
        assert_business_mutable(business.state, action="update_settings")
        BusinessSettingsService._check_version(business, expected_version)

        before = BusinessSettingsService.serialize_settings(business)
        patch_body: dict[str, Any] = {}
        if "regional" in raw and isinstance(raw["regional"], dict):
            patch_body.update(raw["regional"])
        if "notifications" in raw:
            patch_body["notifications"] = raw["notifications"]
        for key in ("timezone", "currency", "country", "language", "locale"):
            if key in raw:
                patch_body[key] = raw[key]

        validated = validate_regional_settings(patch_body)
        if not validated:
            raise ValidationError("No settings fields to update")

        current = dict(business.settings or {})
        merged = _merge_dict(current, validated)
        if merged == current:
            return before

        business.settings = merged
        business.version += 1
        await session.flush()

        after = BusinessSettingsService.serialize_settings(business)
        await BusinessSettingsService._publish(
            session,
            event_type="business.settings.updated",
            audit_action="update_settings",
            business=business,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state=after,
        )
        return after

    @staticmethod
    async def get_profile(session: AsyncSession, business_id: uuid.UUID) -> dict[str, Any]:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        profile = await BusinessSettingsService._ensure_profile(session, business_id)
        return BusinessSettingsService.serialize_profile(business, profile)

    @staticmethod
    async def patch_profile(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        raw: dict[str, Any],
        actor_id: uuid.UUID,
        correlation_id: str,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        business = await BusinessSettingsService._load_business_for_update(session, business_id)
        profile = await BusinessSettingsService._ensure_profile(session, business_id)
        assert_business_mutable(business.state, action="update_profile")
        BusinessSettingsService._check_version(business, expected_version)

        before = BusinessSettingsService.serialize_profile(business, profile)
        validated = validate_profile_fields(raw)
        if not validated:
            raise ValidationError("No profile fields to update")

        changed = False
        if "display_name" in validated:
            if business.display_name != validated["display_name"]:
                business.display_name = validated["display_name"]
                changed = True
        for field in ("description", "tagline", "website_url", "contact", "social_links"):
            if field in validated and getattr(profile, field) != validated[field]:
                setattr(profile, field, validated[field])
                changed = True

        if not changed:
            return before

        business.version += 1
        await session.flush()

        after = BusinessSettingsService.serialize_profile(business, profile)
        await BusinessSettingsService._publish(
            session,
            event_type="business.profile.updated",
            audit_action="update_profile",
            business=business,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state=after,
        )
        return after

    @staticmethod
    async def get_branding(session: AsyncSession, business_id: uuid.UUID) -> dict[str, Any]:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        profile = await BusinessSettingsService._ensure_profile(session, business_id)
        return BusinessSettingsService.serialize_branding(business, profile)

    @staticmethod
    async def patch_branding(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        raw: dict[str, Any],
        actor_id: uuid.UUID,
        correlation_id: str,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        business = await BusinessSettingsService._load_business_for_update(session, business_id)
        profile = await BusinessSettingsService._ensure_profile(session, business_id)
        assert_business_mutable(business.state, action="update_branding")
        BusinessSettingsService._check_version(business, expected_version)

        before = BusinessSettingsService.serialize_branding(business, profile)
        validated = validate_branding_fields(raw)
        if not validated:
            raise ValidationError("No branding fields to update")

        changed = False
        for asset_field in ("logo_asset_id", "cover_asset_id"):
            if asset_field in validated:
                asset_id = validated[asset_field]
                if asset_id is not None:
                    await validate_media_asset_reference(
                        session,
                        business_id=business_id,
                        asset_id=asset_id,
                        field=asset_field,
                    )
                current = getattr(profile, asset_field)
                if current != asset_id:
                    setattr(profile, asset_field, asset_id)
                    changed = True

        if "display_name" in validated and business.display_name != validated["display_name"]:
            business.display_name = validated["display_name"]
            changed = True
        if "tagline" in validated and profile.tagline != validated["tagline"]:
            profile.tagline = validated["tagline"]
            changed = True

        if "branding" in validated:
            current_settings = dict(business.settings or {})
            branding = dict(current_settings.get("branding") or {})
            new_branding = _merge_dict(branding, validated["branding"])
            if new_branding != branding:
                current_settings["branding"] = new_branding
                business.settings = current_settings
                changed = True

        if not changed:
            return before

        business.version += 1
        await session.flush()

        after = BusinessSettingsService.serialize_branding(business, profile)
        await BusinessSettingsService._publish(
            session,
            event_type="business.branding.updated",
            audit_action="update_branding",
            business=business,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state=after,
        )
        return after

    @staticmethod
    async def get_preferences(session: AsyncSession, business_id: uuid.UUID) -> dict[str, Any]:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        return BusinessSettingsService.serialize_preferences(business)

    @staticmethod
    async def patch_preferences(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        raw: dict[str, Any],
        actor_id: uuid.UUID,
        correlation_id: str,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        business = await BusinessSettingsService._load_business_for_update(session, business_id)
        assert_business_mutable(business.state, action="update_preferences")
        BusinessSettingsService._check_version(business, expected_version)

        before = BusinessSettingsService.serialize_preferences(business)
        validated = validate_preferences_fields(raw)
        if not validated:
            raise ValidationError("No preference fields to update")

        changed = False
        visibility_changed_to: str | None = None
        if "visibility" in validated and business.visibility != validated["visibility"]:
            # Discoverable requires explicit Marketplace opt-in consent (Doc 11 §13.3).
            if validated["visibility"] == "discoverable":
                raise ValidationError(
                    "Use Marketplace opt-in consent to become discoverable",
                    details={"use": "POST /v1/b/{business_id}/marketplace/opt-in"},
                )
            visibility_changed_to = validated["visibility"]
            business.visibility = validated["visibility"]
            changed = True

        if "preferences" in validated:
            current_settings = dict(business.settings or {})
            prefs = dict(current_settings.get("preferences") or {})
            new_prefs = _merge_dict(prefs, validated["preferences"])
            if new_prefs != prefs:
                current_settings["preferences"] = new_prefs
                business.settings = current_settings
                changed = True

        if "onboarding_completed" in validated:
            metadata = dict(business.metadata_ or {})
            onboarding = dict(metadata.get("onboarding") or {})
            if onboarding.get("completed") != validated["onboarding_completed"]:
                onboarding["completed"] = validated["onboarding_completed"]
                metadata["onboarding"] = onboarding
                business.metadata_ = metadata
                changed = True

        if not changed:
            return before

        business.version += 1
        await session.flush()

        after = BusinessSettingsService.serialize_preferences(business)
        await BusinessSettingsService._publish(
            session,
            event_type="business.preferences.updated",
            audit_action="update_preferences",
            business=business,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state=after,
        )
        if visibility_changed_to is not None:
            await OutboxService.publish(
                session,
                event_type="business.visibility.changed",
                payload={
                    "business_id": str(business.id),
                    "before": before.get("visibility"),
                    "after": visibility_changed_to,
                    "consented": False,
                },
                business_id=business.id,
                correlation_id=correlation_id,
            )
            await AuditService.record(
                session,
                event_type="business.visibility.changed",
                actor_identity_id=actor_id,
                actor_context="business",
                business_id=business.id,
                resource_type="business",
                resource_id=business.id,
                action="visibility_changed",
                before_state={"visibility": before.get("visibility")},
                after_state={"visibility": visibility_changed_to},
            )
        return after
