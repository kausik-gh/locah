import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.context import EntitlementSet
from platform_core.entitlements.resolver import BusinessEntitlementResolver
from platform_core.models import Business, BusinessModuleState
from platform_core.services.audit import AuditService


class EntitlementService:
    @staticmethod
    async def get_effective(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        business: Business | None = None,
        module_states: dict[str, BusinessModuleState] | None = None,
    ) -> EntitlementSet:
        resolved = await BusinessEntitlementResolver.resolve(
            session, business_id, business=business, module_states=module_states
        )
        return BusinessEntitlementResolver.to_entitlement_set(resolved)


class ModuleService:
    @staticmethod
    async def get_states(
        session: AsyncSession, business_id: uuid.UUID
    ) -> dict[str, BusinessModuleState]:
        result = await session.execute(
            select(BusinessModuleState).where(BusinessModuleState.business_id == business_id)
        )
        return {row.module_id: row for row in result.scalars().all()}

    @staticmethod
    async def enable_module(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        module_id: str,
        actor_id: uuid.UUID,
        entitlements: EntitlementSet,
    ) -> BusinessModuleState:
        if not entitlements.is_entitled(module_id):
            from platform_core.exceptions import EntitlementRequired

            raise EntitlementRequired(module_id)

        result = await session.execute(
            select(BusinessModuleState).where(
                BusinessModuleState.business_id == business_id,
                BusinessModuleState.module_id == module_id,
            )
        )
        state = result.scalars().first()
        now = datetime.now(timezone.utc)
        # Doc 12 SS9.1: enabled -> (configuring -> ready, only "if configuration
        # required") -> active. No First Launch module declares a configuration
        # schema, so enabling completes the transition to `active`; leaving the
        # module in `enabled` would strand it permanently short of
        # ModuleStateInfo.is_operational() and deny gate [7] forever.
        if state is None:
            state = BusinessModuleState(
                business_id=business_id,
                module_id=module_id,
                activation_state="active",
                enabled_at=now,
                activated_at=now,
            )
            session.add(state)
        else:
            state.activation_state = "active"
            state.enabled_at = now
            state.activated_at = now
            state.deactivated_at = None
        await session.flush()
        await AuditService.record(
            session,
            event_type="module.enabled",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="module",
            resource_id=state.id,
            action="enable",
            after_state={"module_id": module_id},
        )
        return state

    @staticmethod
    async def deactivate_module(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        module_id: str,
        actor_id: uuid.UUID,
        reason: str | None = None,
    ) -> BusinessModuleState:
        result = await session.execute(
            select(BusinessModuleState).where(
                BusinessModuleState.business_id == business_id,
                BusinessModuleState.module_id == module_id,
            )
        )
        state = result.scalars().first()
        if state is None:
            from platform_core.exceptions import ResourceNotFound

            raise ResourceNotFound("Module state")
        state.activation_state = "deactivated"
        state.deactivated_at = datetime.now(timezone.utc)
        state.deactivated_reason = reason
        await session.flush()
        await AuditService.record(
            session,
            event_type="module.deactivated",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="module",
            resource_id=state.id,
            action="deactivate",
            after_state={"module_id": module_id, "reason": reason},
        )
        return state
