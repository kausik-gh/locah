"""Core Notifications service (Stage 7 — Doc 09 CORE-015, Doc 11 §17.7).

Platform Core group `core-notifications`: always entitled, so callers apply the
identity/context/membership/permission gates but never the [6] Entitlement or
[7] module-state gates (AUD-01 rule for Platform Core routes).

Recipient rule (approved for Stage 7):
  * fan out to every ACTIVE member of the Business holding the read permission
    relevant to the notification's resource;
  * filtered by Location scope when the notification carries a location_id;
  * ALWAYS include the Business's primary_owner_identity_id regardless of
    explicit grants — Primary Owner resolves to ALL_PERMISSIONS in
    EffectivePermissionResolver, and this guarantees every Business has a real
    recipient from day one while AUD-07 (roles carry no default permissions)
    is still open.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, cast

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.authorization.resolver import EffectivePermissionResolver
from platform_core.exceptions import ResourceNotFound, ValidationError
from platform_core.models import (
    BusinessMembership,
    PlatformNotification,
    PlatformNotificationPreference,
)
from platform_core.services.business import BusinessService

CATEGORIES: frozenset[str] = frozenset({"operational", "commercial", "access", "platform"})
SEVERITIES: frozenset[str] = frozenset({"info", "warning", "critical"})


class NotificationService:
    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    @staticmethod
    def serialize(notification: PlatformNotification) -> dict[str, Any]:
        return {
            "id": str(notification.id),
            "business_id": str(notification.business_id),
            "recipient_identity_id": str(notification.recipient_identity_id),
            "notification_type": notification.notification_type,
            "category": notification.category,
            "severity": notification.severity,
            "title": notification.title,
            "body": notification.body,
            "resource_type": notification.resource_type,
            "resource_id": str(notification.resource_id) if notification.resource_id else None,
            "location_id": str(notification.location_id) if notification.location_id else None,
            "payload": notification.payload,
            "read_at": notification.read_at.isoformat() if notification.read_at else None,
            "created_at": notification.created_at.isoformat() if notification.created_at else None,
            "version": notification.version,
        }

    @staticmethod
    def serialize_preference(pref: PlatformNotificationPreference) -> dict[str, Any]:
        return {
            "id": str(pref.id),
            "business_id": str(pref.business_id),
            "identity_id": str(pref.identity_id),
            "category": pref.category,
            "in_app_enabled": pref.in_app_enabled,
            "version": pref.version,
        }

    # ------------------------------------------------------------------
    # Recipient resolution
    # ------------------------------------------------------------------
    @staticmethod
    async def resolve_recipients(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        required_permission: str | None,
        location_id: uuid.UUID | None = None,
    ) -> list[uuid.UUID]:
        """Members who should receive a notification about this resource.

        Primary Owner is always included (see module docstring).
        """
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")

        recipients: list[uuid.UUID] = []
        seen: set[uuid.UUID] = set()

        owner_id = business.primary_owner_identity_id
        if owner_id is not None:
            recipients.append(owner_id)
            seen.add(owner_id)

        result = await session.execute(
            select(BusinessMembership).where(
                BusinessMembership.business_id == business_id,
                BusinessMembership.status == "active",
                BusinessMembership.deleted_at.is_(None),
            )
        )
        for membership in result.scalars().all():
            if membership.identity_id in seen:
                continue
            # Location scope: a scoped member only hears about their Locations.
            if location_id is not None and membership.location_scope:
                if location_id not in membership.location_scope:
                    continue
            if required_permission is not None:
                resolved = await EffectivePermissionResolver.resolve(
                    session, business_id, membership.identity_id
                )
                if required_permission not in resolved.effective_permissions:
                    continue
            recipients.append(membership.identity_id)
            seen.add(membership.identity_id)
        return recipients

    @staticmethod
    async def _muted_identities(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        category: str,
        identity_ids: list[uuid.UUID],
    ) -> set[uuid.UUID]:
        """Which of `identity_ids` muted `category` for this business.

        Deliberately NOT a plain SELECT on PlatformNotificationPreference:
        notification_prefs_api_write is `identity_id = current_identity_id()
        AND business_id = current_business_id()` (correctly keeping one
        member's preferences private from every other member for the
        general case), so a direct query here could only ever see the
        CURRENT ACTOR's own row — never the row of the recipient being
        checked, who is essentially always someone else. Fan-out would look
        like it worked (no error, no empty-policy failure) while silently
        never suppressing anything. resolve_muted_identities is a narrow
        SECURITY DEFINER resolver for exactly this internal check; it does
        not widen notification_prefs_api_write or expose preference rows on
        any route (see its migration comment,
        20260915010000_stage7_notification_mute_resolver.sql).
        """
        if not identity_ids:
            return set()
        result = await session.execute(
            text(
                "SELECT identity_id FROM resolve_muted_identities("
                ":business_id, :category, :identity_ids)"
            ),
            {
                "business_id": business_id,
                "category": category,
                "identity_ids": identity_ids,
            },
        )
        return {row[0] for row in result.all()}

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------
    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        recipient_identity_id: uuid.UUID,
        notification_type: str,
        title: str,
        category: str = "operational",
        severity: str = "info",
        body: str | None = None,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> PlatformNotification:
        if category not in CATEGORIES:
            raise ValidationError(f"Unsupported notification category '{category}'")
        if severity not in SEVERITIES:
            raise ValidationError(f"Unsupported notification severity '{severity}'")

        # Deliberately NOT session.add()+flush(): Postgres filters an
        # INSERT ... RETURNING through the table's SELECT policy, not just
        # WITH CHECK, and the ORM's implicit flush always issues RETURNING to
        # populate server-generated columns. notifications_api_select requires
        # recipient_identity_id = current_identity_id() — true for a
        # self-notification, false for every fan-out recipient other than the
        # acting identity, which is the normal case (inviting someone else,
        # notifying an assignee, etc.). That RETURNING then comes back empty
        # and SQLAlchemy raises, even though the row was written correctly
        # (WITH CHECK only constrains business_id, not recipient). Setting
        # every server-generated column in Python and inserting via Core with
        # no .returning() sidesteps the RETURNING-vs-SELECT-policy conflict
        # entirely, without touching notifications_api_select or any other
        # RLS policy. Do not "simplify" this back to session.add()+flush().
        now = datetime.now(timezone.utc)
        notification = PlatformNotification(
            id=uuid.uuid4(),
            business_id=business_id,
            recipient_identity_id=recipient_identity_id,
            notification_type=notification_type,
            category=category,
            severity=severity,
            title=title,
            body=body,
            resource_type=resource_type,
            resource_id=resource_id,
            location_id=location_id,
            payload=payload or {},
            correlation_id=correlation_id,
            created_at=now,
            updated_at=now,
            version=1,
        )
        await session.execute(
            insert(PlatformNotification.__table__).values(
                id=notification.id,
                business_id=notification.business_id,
                recipient_identity_id=notification.recipient_identity_id,
                notification_type=notification.notification_type,
                category=notification.category,
                severity=notification.severity,
                title=notification.title,
                body=notification.body,
                resource_type=notification.resource_type,
                resource_id=notification.resource_id,
                location_id=notification.location_id,
                payload=notification.payload,
                correlation_id=notification.correlation_id,
                created_at=notification.created_at,
                updated_at=notification.updated_at,
                version=notification.version,
            )
        )
        return notification

    @staticmethod
    async def fan_out(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        notification_type: str,
        title: str,
        required_permission: str | None,
        category: str = "operational",
        severity: str = "info",
        body: str | None = None,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        exclude_identity_id: uuid.UUID | None = None,
    ) -> list[PlatformNotification]:
        """Create one notification per eligible recipient.

        `exclude_identity_id` suppresses notifying the actor who caused the event.
        """
        recipients = await NotificationService.resolve_recipients(
            session,
            business_id=business_id,
            required_permission=required_permission,
            location_id=location_id,
        )
        if exclude_identity_id is not None:
            recipients = [r for r in recipients if r != exclude_identity_id]
        muted = await NotificationService._muted_identities(
            session, business_id=business_id, category=category, identity_ids=recipients
        )
        created: list[PlatformNotification] = []
        for identity_id in recipients:
            if identity_id in muted:
                continue
            created.append(
                await NotificationService.create(
                    session,
                    business_id=business_id,
                    recipient_identity_id=identity_id,
                    notification_type=notification_type,
                    title=title,
                    category=category,
                    severity=severity,
                    body=body,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    location_id=location_id,
                    payload=payload,
                    correlation_id=correlation_id,
                )
            )
        return created

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    @staticmethod
    async def list_for_recipient(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        identity_id: uuid.UUID,
        unread_only: bool = False,
        category: str | None = None,
        limit: int = 50,
    ) -> list[PlatformNotification]:
        stmt = select(PlatformNotification).where(
            PlatformNotification.business_id == business_id,
            PlatformNotification.recipient_identity_id == identity_id,
            PlatformNotification.deleted_at.is_(None),
        )
        if unread_only:
            stmt = stmt.where(PlatformNotification.read_at.is_(None))
        if category is not None:
            stmt = stmt.where(PlatformNotification.category == category)
        stmt = stmt.order_by(PlatformNotification.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def unread_count(
        session: AsyncSession, *, business_id: uuid.UUID, identity_id: uuid.UUID
    ) -> int:
        result = await session.execute(
            select(func.count())
            .select_from(PlatformNotification)
            .where(
                PlatformNotification.business_id == business_id,
                PlatformNotification.recipient_identity_id == identity_id,
                PlatformNotification.deleted_at.is_(None),
                PlatformNotification.read_at.is_(None),
            )
        )
        return int(result.scalar_one())

    @staticmethod
    async def _resolve_own(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        identity_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> PlatformNotification:
        result = await session.execute(
            select(PlatformNotification).where(
                PlatformNotification.id == notification_id,
                PlatformNotification.business_id == business_id,
                PlatformNotification.deleted_at.is_(None),
            )
        )
        notification = result.scalar_one_or_none()
        # A notification belonging to another recipient is Not Found, never
        # Forbidden — its existence must not leak across identities (Doc 09 ACC-011).
        if notification is None or notification.recipient_identity_id != identity_id:
            raise ResourceNotFound("Notification")
        return notification

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------
    @staticmethod
    async def mark_read(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        identity_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> PlatformNotification:
        notification = await NotificationService._resolve_own(
            session,
            business_id=business_id,
            identity_id=identity_id,
            notification_id=notification_id,
        )
        if notification.read_at is None:
            notification.read_at = datetime.now(timezone.utc)
            notification.version += 1
            await session.flush()
        return notification

    @staticmethod
    async def mark_all_read(
        session: AsyncSession, *, business_id: uuid.UUID, identity_id: uuid.UUID
    ) -> int:
        result = await session.execute(
            update(PlatformNotification)
            .where(
                PlatformNotification.business_id == business_id,
                PlatformNotification.recipient_identity_id == identity_id,
                PlatformNotification.deleted_at.is_(None),
                PlatformNotification.read_at.is_(None),
            )
            .values(read_at=datetime.now(timezone.utc))
        )
        return int(cast(Any, result).rowcount or 0)

    # ------------------------------------------------------------------
    # Preferences
    # ------------------------------------------------------------------
    @staticmethod
    async def list_preferences(
        session: AsyncSession, *, business_id: uuid.UUID, identity_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            select(PlatformNotificationPreference).where(
                PlatformNotificationPreference.business_id == business_id,
                PlatformNotificationPreference.identity_id == identity_id,
                PlatformNotificationPreference.deleted_at.is_(None),
            )
        )
        stored = {p.category: p for p in result.scalars().all()}
        # Unset categories default to enabled rather than being invisible.
        out: list[dict[str, Any]] = []
        for category in sorted(CATEGORIES):
            pref = stored.get(category)
            if pref is not None:
                out.append(NotificationService.serialize_preference(pref))
            else:
                out.append(
                    {
                        "id": None,
                        "business_id": str(business_id),
                        "identity_id": str(identity_id),
                        "category": category,
                        "in_app_enabled": True,
                        "version": 0,
                    }
                )
        return out

    @staticmethod
    async def set_preference(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        identity_id: uuid.UUID,
        category: str,
        in_app_enabled: bool,
    ) -> PlatformNotificationPreference:
        if category not in CATEGORIES:
            raise ValidationError(f"Unsupported notification category '{category}'")
        result = await session.execute(
            select(PlatformNotificationPreference).where(
                PlatformNotificationPreference.business_id == business_id,
                PlatformNotificationPreference.identity_id == identity_id,
                PlatformNotificationPreference.category == category,
                PlatformNotificationPreference.deleted_at.is_(None),
            )
        )
        pref = result.scalar_one_or_none()
        if pref is None:
            pref = PlatformNotificationPreference(
                business_id=business_id,
                identity_id=identity_id,
                category=category,
                in_app_enabled=in_app_enabled,
            )
            session.add(pref)
        else:
            pref.in_app_enabled = in_app_enabled
            pref.version += 1
        await session.flush()
        return pref
