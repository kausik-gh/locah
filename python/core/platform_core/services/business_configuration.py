"""Business-Type Configuration Engine (Stage 2F)."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.business_type_profiles import (
    BusinessTypeProfile,
    BusinessTypeProfileRegistry,
    ConfigurationProfile,
)
from platform_core.business_types import DEFAULT_BUSINESS_TYPE
from platform_core.entitlements.resolver import BusinessEntitlementResolver
from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.gates import assert_business_mutable
from platform_core.models import Business
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService
from platform_core.validation.business_configuration import (
    profile_version_status,
    validate_business_type_value,
    validate_type_change_payload,
)


class BusinessConfigurationResolver:
    """Central resolver — single source of truth for business-type configuration."""

    @staticmethod
    def _settings_configuration(settings: dict[str, Any]) -> dict[str, Any]:
        configuration = settings.get("configuration")
        return dict(configuration) if isinstance(configuration, dict) else {}

    @staticmethod
    def _merge_terminology(
        profile: BusinessTypeProfile, settings: dict[str, Any]
    ) -> dict[str, str]:
        configuration = BusinessConfigurationResolver._settings_configuration(settings)
        overrides = configuration.get("terminology")
        if not isinstance(overrides, dict):
            overrides = settings.get("terminology")
        if not isinstance(overrides, dict):
            overrides = {}
        merged = dict(profile.terminology)
        for key, value in overrides.items():
            if isinstance(key, str) and isinstance(value, str) and value.strip():
                merged[key] = value.strip()
        return merged

    @staticmethod
    def _merge_operational_defaults(
        profile: BusinessTypeProfile, settings: dict[str, Any]
    ) -> dict[str, Any]:
        base = profile.operational_defaults
        configuration = BusinessConfigurationResolver._settings_configuration(settings)
        overrides = configuration.get("operational_defaults")
        if not isinstance(overrides, dict):
            overrides = {}

        def _bool(key: str, default: bool) -> bool:
            value = overrides.get(key)
            return default if not isinstance(value, bool) else value

        def _int_or_none(key: str, default: int | None) -> int | None:
            value = overrides.get(key)
            if value is None:
                return default
            if isinstance(value, bool):
                return default
            if isinstance(value, int):
                return value
            return default

        def _str(key: str, default: str) -> str:
            value = overrides.get(key)
            return default if not isinstance(value, str) or not value.strip() else value.strip()

        return {
            "booking_enabled": _bool("booking_enabled", base.booking_enabled),
            "inventory_enabled": _bool("inventory_enabled", base.inventory_enabled),
            "delivery_enabled": _bool("delivery_enabled", base.delivery_enabled),
            "default_service_duration_minutes": _int_or_none(
                "default_service_duration_minutes",
                base.default_service_duration_minutes,
            ),
            "working_mode": _str("working_mode", base.working_mode),
            "location_behavior": _str("location_behavior", base.location_behavior),
        }

    @staticmethod
    def _merge_navigation(
        profile: BusinessTypeProfile, settings: dict[str, Any]
    ) -> dict[str, Any]:
        configuration = BusinessConfigurationResolver._settings_configuration(settings)
        navigation_overrides = configuration.get("navigation")
        if not isinstance(navigation_overrides, dict):
            navigation_overrides = {}
        preferences = settings.get("preferences")
        default_route = profile.navigation.default_route
        if isinstance(preferences, dict):
            dashboard_pref = preferences.get("default_dashboard")
            if isinstance(dashboard_pref, str) and dashboard_pref.strip():
                default_route = dashboard_pref.strip()
        override_route = navigation_overrides.get("default_route")
        if isinstance(override_route, str) and override_route.strip():
            default_route = override_route.strip()
        return {
            "groups": copy.deepcopy(list(profile.navigation.groups)),
            "default_route": default_route,
            "workspace_layout": profile.navigation.workspace_layout,
        }

    @staticmethod
    def _merge_dashboard(profile: BusinessTypeProfile, settings: dict[str, Any]) -> dict[str, Any]:
        configuration = BusinessConfigurationResolver._settings_configuration(settings)
        dashboard_overrides = configuration.get("dashboard")
        emphasis = list(profile.dashboard.emphasis)
        if isinstance(dashboard_overrides, dict):
            override_emphasis = dashboard_overrides.get("emphasis")
            if isinstance(override_emphasis, list):
                cleaned = [item for item in override_emphasis if isinstance(item, str) and item]
                if cleaned:
                    emphasis = cleaned
        navigation = BusinessConfigurationResolver._merge_navigation(profile, settings)
        return {
            "emphasis": emphasis,
            "default_route": navigation["default_route"],
        }

    @staticmethod
    def resolve_from_business(business: Business) -> ConfigurationProfile:
        type_id = (business.business_type or DEFAULT_BUSINESS_TYPE).strip().lower()
        profile = BusinessTypeProfileRegistry.get_or_default(type_id)
        settings = dict(business.settings or {})
        metadata = dict(business.metadata_ or {})
        configuration_meta = metadata.get("configuration")
        if not isinstance(configuration_meta, dict):
            configuration_meta = {}
        stored_profile_version = configuration_meta.get("profile_version")
        if isinstance(stored_profile_version, str):
            version_status = profile_version_status(stored_profile_version, profile.version)
        else:
            version_status = "current"

        resolved = {
            "terminology": BusinessConfigurationResolver._merge_terminology(profile, settings),
            "module_seeds": profile.serialize()["module_seeds"],
            "navigation": BusinessConfigurationResolver._merge_navigation(profile, settings),
            "dashboard": BusinessConfigurationResolver._merge_dashboard(profile, settings),
            "operational_defaults": BusinessConfigurationResolver._merge_operational_defaults(
                profile, settings
            ),
            "profile_version_status": version_status,
        }

        layers = {
            "profile": profile.serialize(),
            "business_settings": {
                "configuration": BusinessConfigurationResolver._settings_configuration(settings),
                "preferences": dict(settings.get("preferences") or {}),
            },
            "entitlements": {
                "status": "active",
                "plan_id": BusinessEntitlementResolver.plan_id_for_business(business),
            },
            "permissions": {"status": "placeholder", "active": False},
        }

        return ConfigurationProfile(
            business_id=str(business.id),
            business_type=profile.type_id,
            profile_version=profile.version,
            profile=profile.serialize(),
            resolved=resolved,
            layers=layers,
            version=business.version,
        )

    @staticmethod
    async def resolve(session: AsyncSession, business_id: uuid.UUID) -> ConfigurationProfile:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        return BusinessConfigurationResolver.resolve_from_business(business)


class BusinessConfigurationService:
    @staticmethod
    async def list_available_types() -> list[dict[str, str]]:
        return list(BusinessTypeProfileRegistry.list_types())

    @staticmethod
    async def get_type_profile(type_id: str) -> dict[str, Any]:
        normalized = validate_business_type_value(type_id)
        profile = BusinessTypeProfileRegistry.get(normalized)
        assert profile is not None
        serialized: dict[str, Any] = profile.serialize()
        return serialized

    @staticmethod
    async def get_business_profile(
        session: AsyncSession, business_id: uuid.UUID
    ) -> dict[str, Any]:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        type_id = business.business_type or DEFAULT_BUSINESS_TYPE
        profile = BusinessTypeProfileRegistry.get_or_default(type_id)
        payload: dict[str, Any] = profile.serialize()
        payload["assigned_to_business"] = True
        payload["business_id"] = str(business.id)
        return payload

    @staticmethod
    async def get_resolved_configuration(
        session: AsyncSession, business_id: uuid.UUID
    ) -> dict[str, Any]:
        resolved = await BusinessConfigurationResolver.resolve(session, business_id)
        serialized: dict[str, Any] = resolved.serialize()
        return serialized

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
    def _onboarding_completed(business: Business) -> bool:
        metadata = dict(business.metadata_ or {})
        onboarding = metadata.get("onboarding")
        if isinstance(onboarding, dict):
            return bool(onboarding.get("completed"))
        return False

    @staticmethod
    async def patch_business_type(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        payload: dict[str, Any],
        actor_id: uuid.UUID,
        correlation_id: str,
    ) -> dict[str, Any]:
        business = await BusinessConfigurationService._load_business_for_update(
            session, business_id
        )
        assert_business_mutable(business.state, action="update_business_type")

        expected_version = payload.get("version")
        if expected_version is not None:
            if not isinstance(expected_version, int):
                raise ValidationError(
                    "version must be an integer",
                    details={"field": "version"},
                )
            if business.version != expected_version:
                raise ConflictError(
                    "Stale business version",
                    details={
                        "expected_version": expected_version,
                        "current_version": business.version,
                    },
                )

        onboarding_completed = BusinessConfigurationService._onboarding_completed(business)
        new_type = validate_type_change_payload(payload, onboarding_completed=onboarding_completed)
        previous_type = (business.business_type or DEFAULT_BUSINESS_TYPE).strip().lower()
        if new_type == previous_type:
            raise ConflictError(
                "Business type is unchanged",
                details={"business_type": new_type},
            )

        profile = BusinessTypeProfileRegistry.get(new_type)
        if profile is None:
            raise ValidationError(
                "Invalid business type profile",
                details={"field": "business_type"},
            )

        before_state = {
            "business_type": business.business_type,
            "version": business.version,
        }

        business.business_type = new_type
        business.version += 1
        metadata = dict(business.metadata_ or {})
        configuration_meta = dict(metadata.get("configuration") or {})
        configuration_meta.update(
            {
                "profile_version": profile.version,
                "profile_type_id": profile.type_id,
            }
        )
        metadata["configuration"] = configuration_meta
        business.metadata_ = metadata

        await session.flush()

        resolved = BusinessConfigurationResolver.resolve_from_business(business)
        after_state = {
            "business_type": business.business_type,
            "profile_version": profile.version,
            "version": business.version,
        }

        await OutboxService.publish(
            session,
            event_type="business_type.changed",
            payload={
                "business_id": str(business.id),
                "previous_type": previous_type,
                "business_type": new_type,
                "profile_version": profile.version,
                "version": business.version,
            },
            business_id=business.id,
            correlation_id=correlation_id,
        )
        await OutboxService.publish(
            session,
            event_type="configuration.resolved",
            payload={
                "business_id": str(business.id),
                "business_type": new_type,
                "profile_version": profile.version,
                "version": business.version,
            },
            business_id=business.id,
            correlation_id=correlation_id,
        )
        await OutboxService.publish(
            session,
            event_type="configuration.profile.updated",
            payload={
                "business_id": str(business.id),
                "business_type": new_type,
                "profile_version": profile.version,
                "version": business.version,
            },
            business_id=business.id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="business_type.changed",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business.id,
            resource_type="business",
            resource_id=business.id,
            action="change_business_type",
            before_state=before_state,
            after_state=after_state,
        )
        await AuditService.record(
            session,
            event_type="configuration.resolved",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business.id,
            resource_type="business_configuration",
            resource_id=business.id,
            action="resolve_configuration",
            before_state=None,
            after_state=resolved.serialize(),
        )
        await AuditService.record(
            session,
            event_type="configuration.profile.updated",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business.id,
            resource_type="business_type_profile",
            resource_id=business.id,
            action="assign_profile",
            before_state={"business_type": previous_type},
            after_state={"business_type": new_type, "profile_version": profile.version},
        )

        return resolved.serialize()  # type: ignore[no-any-return]
