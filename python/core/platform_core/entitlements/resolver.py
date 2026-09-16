"""Central entitlement and capability resolvers (Stage 2G)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.business_types import DEFAULT_BUSINESS_TYPE
from platform_core.context import EntitlementSet
from platform_core.entitlements.capability_registry import CAPABILITIES
from platform_core.entitlements.feature_registry import FeatureRegistry
from platform_core.entitlements.models import (
    REGISTRY_VERSION,
    BusinessOverrideLayer,
    CapabilitySnapshot,
    FeatureState,
    ModuleState,
    ResolvedEntitlement,
)
from platform_core.entitlements.module_registry import ModuleRegistry
from platform_core.entitlements.plan_registry import DEFAULT_PLAN_ID, PlanRegistry
from platform_core.exceptions import ResourceNotFound
from platform_core.models import Business, BusinessModuleState, CommercialEntitlement


class BusinessEntitlementResolver:
    """Single authority for Business-scoped entitlement resolution."""

    @staticmethod
    def _commercial_metadata(business: Business) -> dict[str, Any]:
        metadata = dict(business.metadata_ or {})
        commercial = metadata.get("commercial")
        return dict(commercial) if isinstance(commercial, dict) else {}

    @staticmethod
    def plan_id_for_business(business: Business) -> str:
        commercial = BusinessEntitlementResolver._commercial_metadata(business)
        plan_id = commercial.get("plan_id")
        if isinstance(plan_id, str) and plan_id.strip():
            normalized = plan_id.strip().lower()
            return normalized
        return cast(str, DEFAULT_PLAN_ID)

    @staticmethod
    def overrides_for_business(business: Business) -> BusinessOverrideLayer:
        commercial = BusinessEntitlementResolver._commercial_metadata(business)
        overrides = commercial.get("overrides")
        if isinstance(overrides, dict):
            return BusinessOverrideLayer.from_metadata(overrides)
        return BusinessOverrideLayer()

    @staticmethod
    async def _load_db_grants(
        session: AsyncSession, business_id: uuid.UUID
    ) -> list[CommercialEntitlement]:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(CommercialEntitlement).where(
                CommercialEntitlement.business_id == business_id,
                CommercialEntitlement.status == "active",
            )
        )
        grants: list[CommercialEntitlement] = []
        for grant in result.scalars().all():
            if grant.expires_at and grant.expires_at < now:
                continue
            grants.append(grant)
        return grants

    @staticmethod
    async def _load_module_states(
        session: AsyncSession, business_id: uuid.UUID
    ) -> dict[str, BusinessModuleState]:
        result = await session.execute(
            select(BusinessModuleState).where(BusinessModuleState.business_id == business_id)
        )
        return {row.module_id: row for row in result.scalars().all()}

    @staticmethod
    def _merge_limits(
        plan_limits: dict[str, int | None], overrides: BusinessOverrideLayer
    ) -> dict[str, int | None]:
        merged = dict(plan_limits)
        for key, override in overrides.limits.items():
            if not isinstance(override, dict):
                continue
            if "max" in override:
                max_value = override["max"]
                merged[key] = max_value if isinstance(max_value, int) or max_value is None else merged.get(key)
        return merged

    @staticmethod
    def resolve_from_parts(
        *,
        business: Business,
        db_grants: list[CommercialEntitlement],
        activation_rows: dict[str, BusinessModuleState],
    ) -> ResolvedEntitlement:
        from platform_core.services.business_configuration import BusinessConfigurationResolver

        configuration = BusinessConfigurationResolver.resolve_from_business(business)
        business_type = business.business_type or DEFAULT_BUSINESS_TYPE
        plan = PlanRegistry.get_or_default(BusinessEntitlementResolver.plan_id_for_business(business))
        overrides = BusinessEntitlementResolver.overrides_for_business(business)

        entitled_modules: set[str] = set(ModuleRegistry.platform_core_ids())
        entitled_features: set[str] = set(plan.feature_ids)
        module_sources: dict[str, str] = {
            mid: "platform_core" for mid in ModuleRegistry.platform_core_ids()
        }
        feature_sources: dict[str, str] = {fid: f"plan:{plan.plan_id}" for fid in plan.feature_ids}

        for mid in plan.module_ids:
            entitled_modules.add(mid)
            module_sources[mid] = f"plan:{plan.plan_id}"

        for grant in db_grants:
            if grant.subject_type == "module":
                entitled_modules.add(grant.subject_id)
                module_sources[grant.subject_id] = grant.source
            elif grant.subject_type in {"feature", "capability"}:
                entitled_features.add(grant.subject_id)
                feature_sources[grant.subject_id] = grant.source

        for module_id, override in overrides.modules.items():
            if not isinstance(override, dict):
                continue
            entitled_flag = override.get("entitled")
            if entitled_flag is True:
                entitled_modules.add(module_id)
                module_sources[module_id] = "business_override"
            elif entitled_flag is False:
                if module_id not in ModuleRegistry.platform_core_ids():
                    entitled_modules.discard(module_id)
                    module_sources[module_id] = "business_override"

        for feature_id, override in overrides.features.items():
            if not isinstance(override, dict):
                continue
            enabled_flag = override.get("entitled")
            if enabled_flag is True:
                entitled_features.add(feature_id)
                feature_sources[feature_id] = "business_override"
            elif enabled_flag is False:
                entitled_features.discard(feature_id)
                feature_sources[feature_id] = "business_override"

        plan_limits = {limit.limit_key: limit.max_value for limit in plan.usage_limits}
        usage_limits = BusinessEntitlementResolver._merge_limits(plan_limits, overrides)

        module_states: dict[str, ModuleState] = {}
        for module_id in sorted(entitled_modules | set(activation_rows.keys())):
            module_def = ModuleRegistry.get(module_id)
            if module_def is None:
                continue
            entitled = module_id in entitled_modules
            dep_ok, _missing = ModuleRegistry.dependencies_satisfied(
                module_id, frozenset(entitled_modules)
            )
            activation = activation_rows.get(module_id)
            activation_state = activation.activation_state if activation else module_def.default_state
            module_states[module_id] = ModuleState(
                module_id=module_id,
                entitled=entitled,
                activation_state=activation_state,
                configuration_ready=bool(
                    activation and activation.configuration and activation.activation_state in {"ready", "active"}
                ),
                dependency_satisfied=dep_ok,
                source=module_sources.get(module_id, "unknown"),
            )

        feature_states: dict[str, FeatureState] = {}
        for feature in FeatureRegistry.list_features():
            feature_id = feature["feature_id"]
            feature_def = FeatureRegistry.get(feature_id)
            if feature_def is None:
                continue
            module_entitled = feature_def.module_id in entitled_modules
            feature_entitled = feature_id in entitled_features
            override = overrides.features.get(feature_id, {})
            enabled_override = override.get("enabled") if isinstance(override, dict) else None
            default_enabled = feature_def.default_enabled
            if isinstance(enabled_override, bool):
                enabled = enabled_override
            else:
                enabled = default_enabled
            feature_states[feature_id] = FeatureState(
                feature_id=feature_id,
                module_id=feature_def.module_id,
                entitled=module_entitled and feature_entitled,
                enabled=enabled and module_entitled and feature_entitled,
                source=feature_sources.get(feature_id, f"plan:{plan.plan_id}"),
            )

        layers = {
            "business_type_configuration": {
                "business_type": business_type,
                "recommended_modules": [
                    seed["module_id"] for seed in configuration.resolved.get("module_seeds", [])
                ],
            },
            "plan": {
                "plan_id": plan.plan_id,
                "version": plan.version,
                "module_ids": sorted(plan.module_ids),
            },
            "module_registry": {"version": REGISTRY_VERSION},
            "business_overrides": overrides.serialize(),
            "usage_enforcement": {"status": "placeholder", "active": False},
            "db_grants": [
                {
                    "subject_type": grant.subject_type,
                    "subject_id": grant.subject_id,
                    "source": grant.source,
                }
                for grant in db_grants
            ],
        }

        return ResolvedEntitlement(
            business_id=str(business.id),
            plan_id=plan.plan_id,
            plan_version=plan.version,
            registry_version=REGISTRY_VERSION,
            business_type=business_type,
            entitled_modules=frozenset(entitled_modules),
            entitled_features=frozenset(
                fid for fid, state in feature_states.items() if state.entitled
            ),
            module_states=module_states,
            feature_states=feature_states,
            usage_limits=usage_limits,
            layers=layers,
            version=business.version,
        )

    @staticmethod
    async def resolve(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        business: Business | None = None,
        module_states: dict[str, BusinessModuleState] | None = None,
    ) -> ResolvedEntitlement:
        # Lazy import: BusinessService → entitlement → this module.
        from platform_core.services.business import BusinessService

        if business is None:
            business = await BusinessService.get_by_id(session, business_id)
            if business is None:
                raise ResourceNotFound("Business")
        db_grants = await BusinessEntitlementResolver._load_db_grants(session, business_id)
        activation_rows = (
            module_states
            if module_states is not None
            else await BusinessEntitlementResolver._load_module_states(session, business_id)
        )
        return BusinessEntitlementResolver.resolve_from_parts(
            business=business,
            db_grants=db_grants,
            activation_rows=activation_rows,
        )

    @staticmethod
    def to_entitlement_set(resolved: ResolvedEntitlement) -> EntitlementSet:
        return EntitlementSet(
            modules=resolved.entitled_modules,
            capabilities=frozenset(
                fid for fid, state in resolved.feature_states.items() if state.enabled
            ),
        )


class PlatformCapabilityResolver:
    """Answers platform capability questions without exposing plan logic."""

    @staticmethod
    def resolve_from_entitlement(resolved: ResolvedEntitlement) -> CapabilitySnapshot:
        capabilities: dict[str, bool] = {}
        details: dict[str, dict[str, Any]] = {}

        for capability_id, definition in CAPABILITIES.items():
            available = True
            reasons: list[str] = []

            if definition.required_module_id:
                module_state = resolved.module_states.get(definition.required_module_id)
                if module_state is None or not module_state.entitled:
                    available = False
                    reasons.append("module_not_entitled")
                elif not module_state.dependency_satisfied:
                    available = False
                    reasons.append("dependency_unsatisfied")

            if available and definition.required_feature_id:
                feature_state = resolved.feature_states.get(definition.required_feature_id)
                if feature_state is None or not feature_state.enabled:
                    available = False
                    reasons.append("feature_not_enabled")

            if available and definition.limit_key:
                limit = resolved.usage_limits.get(definition.limit_key)
                if limit is not None and limit <= 0:
                    available = False
                    reasons.append("limit_exhausted")

            capabilities[capability_id] = available
            details[capability_id] = {
                "display_name": definition.display_name,
                "available": available,
                "reasons": reasons,
            }

        return CapabilitySnapshot(
            business_id=resolved.business_id,
            capabilities=capabilities,
            details=details,
            version=resolved.version,
        )

    @staticmethod
    async def resolve(session: AsyncSession, business_id: uuid.UUID) -> CapabilitySnapshot:
        resolved = await BusinessEntitlementResolver.resolve(session, business_id)
        return PlatformCapabilityResolver.resolve_from_entitlement(resolved)
