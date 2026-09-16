"""Business entitlement service and override management (Stage 2G)."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.entitlements import (
    BusinessEntitlementResolver,
    FeatureRegistry,
    ModuleRegistry,
    PlanRegistry,
    PlatformCapabilityResolver,
)
from platform_core.entitlements.models import BusinessOverrideLayer
from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.gates import assert_business_mutable
from platform_core.models import Business
from platform_core.services.audit import AuditService
from platform_core.services.outbox import OutboxService
from platform_core.validation.business_entitlements import (
    validate_dependency_graph,
    validate_override_payload,
    validate_plan_id,
)


class BusinessEntitlementService:
    @staticmethod
    async def list_plans() -> list[dict[str, str]]:
        return list(PlanRegistry.list_plans())

    @staticmethod
    async def list_modules(*, module_class: str | None = None) -> list[dict[str, str]]:
        return list(ModuleRegistry.list_modules(module_class=module_class))

    @staticmethod
    async def get_module(module_id: str) -> dict[str, Any]:
        module = ModuleRegistry.get_or_raise(module_id)
        features = FeatureRegistry.list_features(module_id=module.module_id)
        return {
            "module_id": module.module_id,
            "display_name": module.display_name,
            "module_class": module.module_class,
            "description": module.description,
            "dependencies": list(module.dependencies),
            "default_state": module.default_state,
            "features": features,
        }

    @staticmethod
    async def list_features(*, module_id: str | None = None) -> list[dict[str, str]]:
        return list(FeatureRegistry.list_features(module_id=module_id))

    @staticmethod
    async def get_feature(feature_id: str) -> dict[str, Any]:
        feature = FeatureRegistry.get_or_raise(feature_id)
        return {
            "feature_id": feature.feature_id,
            "module_id": feature.module_id,
            "display_name": feature.display_name,
            "description": feature.description,
            "default_enabled": feature.default_enabled,
            "entitlement_required": feature.entitlement_required,
        }

    @staticmethod
    async def get_business_entitlements(
        session: AsyncSession, business_id: uuid.UUID
    ) -> dict[str, Any]:
        resolved = await BusinessEntitlementResolver.resolve(session, business_id)
        serialized: dict[str, Any] = resolved.serialize()
        return serialized

    @staticmethod
    async def get_business_capabilities(
        session: AsyncSession, business_id: uuid.UUID
    ) -> dict[str, Any]:
        snapshot = await PlatformCapabilityResolver.resolve(session, business_id)
        cap_serialized: dict[str, Any] = snapshot.serialize()
        return cap_serialized

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
    def _merge_overrides(
        current: BusinessOverrideLayer, patch: dict[str, Any]
    ) -> BusinessOverrideLayer:
        merged = BusinessOverrideLayer(
            modules=copy.deepcopy(current.modules),
            features=copy.deepcopy(current.features),
            limits=copy.deepcopy(current.limits),
        )
        if "modules" in patch and isinstance(patch["modules"], dict):
            merged.modules.update(patch["modules"])
        if "features" in patch and isinstance(patch["features"], dict):
            merged.features.update(patch["features"])
        if "limits" in patch and isinstance(patch["limits"], dict):
            merged.limits.update(patch["limits"])
        return merged

    @staticmethod
    async def patch_business_overrides(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        payload: dict[str, Any],
        actor_id: uuid.UUID,
        correlation_id: str,
    ) -> dict[str, Any]:
        business = await BusinessEntitlementService._load_business_for_update(session, business_id)
        assert_business_mutable(business.state, action="update_entitlements")

        expected_version = payload.get("version")
        if expected_version is not None:
            if not isinstance(expected_version, int):
                raise ValidationError("version must be an integer", details={"field": "version"})
            if business.version != expected_version:
                raise ConflictError(
                    "Stale business version",
                    details={
                        "expected_version": expected_version,
                        "current_version": business.version,
                    },
                )

        override_patch: dict[str, Any] = {
            key: payload[key]
            for key in ("modules", "features", "limits")
            if key in payload
        }
        if not override_patch:
            raise ValidationError(
                "At least one of modules, features, or limits is required",
                details={"field": "overrides"},
            )
        validate_override_payload(override_patch)

        before = BusinessEntitlementResolver.overrides_for_business(business)
        merged = BusinessEntitlementService._merge_overrides(before, override_patch)

        preview = await BusinessEntitlementResolver.resolve(session, business_id)
        simulated_modules = set(preview.entitled_modules)
        for module_id, override in merged.modules.items():
            if not isinstance(override, dict):
                continue
            entitled_flag = override.get("entitled")
            if entitled_flag is True:
                simulated_modules.add(module_id)
            elif entitled_flag is False and module_id not in ModuleRegistry.platform_core_ids():
                simulated_modules.discard(module_id)

        for module_id in simulated_modules:
            validate_dependency_graph(frozenset(simulated_modules), module_id)

        metadata = dict(business.metadata_ or {})
        commercial = dict(metadata.get("commercial") or {})
        commercial["overrides"] = merged.serialize()
        if "plan_id" not in commercial:
            commercial["plan_id"] = BusinessEntitlementResolver.plan_id_for_business(business)
        metadata["commercial"] = commercial
        business.metadata_ = metadata
        business.version += 1
        await session.flush()

        for module_id, override in merged.modules.items():
            if not isinstance(override, dict):
                continue
            entitled_flag = override.get("entitled")
            if entitled_flag is True:
                await OutboxService.publish(
                    session,
                    event_type="module.enabled",
                    payload={"business_id": str(business.id), "module_id": module_id, "source": "override"},
                    business_id=business.id,
                    correlation_id=correlation_id,
                )
            elif entitled_flag is False and module_id not in ModuleRegistry.platform_core_ids():
                await OutboxService.publish(
                    session,
                    event_type="module.disabled",
                    payload={"business_id": str(business.id), "module_id": module_id, "source": "override"},
                    business_id=business.id,
                    correlation_id=correlation_id,
                )

        for feature_id, override in merged.features.items():
            if not isinstance(override, dict):
                continue
            if override.get("enabled") is True:
                await OutboxService.publish(
                    session,
                    event_type="feature.enabled",
                    payload={"business_id": str(business.id), "feature_id": feature_id},
                    business_id=business.id,
                    correlation_id=correlation_id,
                )
            elif override.get("enabled") is False:
                await OutboxService.publish(
                    session,
                    event_type="feature.disabled",
                    payload={"business_id": str(business.id), "feature_id": feature_id},
                    business_id=business.id,
                    correlation_id=correlation_id,
                )

        resolved = await BusinessEntitlementResolver.resolve(session, business_id)
        after_state = resolved.serialize()

        await OutboxService.publish(
            session,
            event_type="business.override.updated",
            payload={
                "business_id": str(business.id),
                "version": business.version,
            },
            business_id=business.id,
            correlation_id=correlation_id,
        )
        await OutboxService.publish(
            session,
            event_type="entitlement.updated",
            payload={
                "business_id": str(business.id),
                "plan_id": resolved.plan_id,
                "version": business.version,
            },
            business_id=business.id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="business.override.updated",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business.id,
            resource_type="business_entitlement",
            resource_id=business.id,
            action="update_overrides",
            before_state=before.serialize(),
            after_state=merged.serialize(),
        )
        await AuditService.record(
            session,
            event_type="entitlement.updated",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business.id,
            resource_type="business_entitlement",
            resource_id=business.id,
            action="resolve_entitlements",
            before_state=None,
            after_state=after_state,
        )

        return after_state  # type: ignore[no-any-return]

    @staticmethod
    async def patch_business_plan(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        payload: dict[str, Any],
        actor_id: uuid.UUID,
        correlation_id: str,
    ) -> dict[str, Any]:
        business = await BusinessEntitlementService._load_business_for_update(session, business_id)
        assert_business_mutable(business.state, action="update_plan")

        expected_version = payload.get("version")
        if expected_version is not None:
            if not isinstance(expected_version, int):
                raise ValidationError("version must be an integer", details={"field": "version"})
            if business.version != expected_version:
                raise ConflictError(
                    "Stale business version",
                    details={
                        "expected_version": expected_version,
                        "current_version": business.version,
                    },
                )

        plan_id_raw = payload.get("plan_id")
        if not isinstance(plan_id_raw, str):
            raise ValidationError("plan_id is required", details={"field": "plan_id"})
        plan_id = validate_plan_id(plan_id_raw)
        previous_plan = BusinessEntitlementResolver.plan_id_for_business(business)
        if plan_id == previous_plan:
            raise ConflictError("Plan is unchanged", details={"plan_id": plan_id})

        metadata = dict(business.metadata_ or {})
        commercial = dict(metadata.get("commercial") or {})
        commercial["plan_id"] = plan_id
        metadata["commercial"] = commercial
        business.metadata_ = metadata
        business.version += 1
        await session.flush()

        resolved = await BusinessEntitlementResolver.resolve(session, business_id)
        after_state = resolved.serialize()

        await OutboxService.publish(
            session,
            event_type="entitlement.updated",
            payload={
                "business_id": str(business.id),
                "previous_plan_id": previous_plan,
                "plan_id": plan_id,
                "version": business.version,
            },
            business_id=business.id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="entitlement.updated",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business.id,
            resource_type="business_entitlement",
            resource_id=business.id,
            action="change_plan",
            before_state={"plan_id": previous_plan},
            after_state={"plan_id": plan_id},
        )

        return after_state  # type: ignore[no-any-return]
