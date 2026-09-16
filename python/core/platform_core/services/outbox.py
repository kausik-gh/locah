import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import PlatformOutboxEvent


class OutboxService:
    @staticmethod
    async def publish(
        session: AsyncSession,
        *,
        event_type: str,
        payload: dict[str, Any],
        business_id: uuid.UUID | None = None,
        correlation_id: str | None = None,
        causation_id: uuid.UUID | None = None,
        skip_notifications: bool = False,
    ) -> PlatformOutboxEvent:
        event = PlatformOutboxEvent(
            business_id=business_id,
            event_type=event_type,
            payload=payload,
            correlation_id=uuid.UUID(correlation_id) if correlation_id else None,
            causation_id=causation_id,
            status="pending",
        )
        session.add(event)
        await session.flush()

        # Core Notifications fan-out (Stage 7). Every notification-worthy event
        # already passes through here, so dispatch hooks in once instead of being
        # duplicated across every emitting service. Imported lazily: the
        # dispatcher imports NotificationService, which imports BusinessService,
        # which would otherwise cycle back through this module.
        if not skip_notifications:
            from platform_core.services.notification_dispatch import NotificationDispatcher

            await NotificationDispatcher.dispatch(
                session,
                event_type=event_type,
                payload=payload,
                business_id=business_id,
                correlation_id=correlation_id,
            )
        return event
