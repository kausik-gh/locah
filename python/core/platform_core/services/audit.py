import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import PlatformAuditEvent


class AuditService:
    @staticmethod
    async def record(
        session: AsyncSession,
        *,
        event_type: str,
        actor_identity_id: uuid.UUID,
        actor_context: str,
        action: str,
        business_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> PlatformAuditEvent:
        audit = PlatformAuditEvent(
            event_type=event_type,
            actor_identity_id=actor_identity_id,
            actor_context=actor_context,
            business_id=business_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            before_state=before_state,
            after_state=after_state,
            reason=reason,
        )
        session.add(audit)
        await session.flush()
        return audit
