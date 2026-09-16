"""Business invitation lifecycle (Stage 2D)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.context_resolver import bind_session_context
from platform_core.exceptions import (
    ConflictError,
    ResourceNotFound,
    ValidationError,
)
from platform_core.gates import assert_business_mutable
from platform_core.models import Business, BusinessInvitation, BusinessMembership
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.identity import IdentityService
from platform_core.services.outbox import OutboxService
from platform_core.services.team import TeamService

INVITATION_TTL_HOURS = 48
RESEND_COOLDOWN_SECONDS = 60
MAX_RESEND_COUNT = 5

INVITATION_STATUSES: frozenset[str] = frozenset(
    {"pending", "accepted", "declined", "revoked", "expired"}
)

ALLOWED_INVITATION_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"accepted", "declined", "revoked", "expired"}),
    "accepted": frozenset(),
    "declined": frozenset(),
    "revoked": frozenset(),
    "expired": frozenset(),
}

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class InvitationService:
    @staticmethod
    def normalize_email(email: str) -> str:
        normalized = email.strip().lower()
        if not EMAIL_PATTERN.match(normalized):
            raise ValidationError(
                "Invalid email address",
                details={"field": "invited_email", "value": email},
            )
        return normalized

    @staticmethod
    def serialize_invitation(inv: BusinessInvitation) -> dict[str, Any]:
        location_scope = (
            [str(lid) for lid in inv.location_scope] if inv.location_scope is not None else None
        )
        return {
            "id": str(inv.id),
            "business_id": str(inv.business_id),
            "invited_email": inv.invited_email,
            "invited_identity_id": (
                str(inv.invited_identity_id) if inv.invited_identity_id else None
            ),
            "invited_role": inv.invited_role,
            "location_scope": location_scope,
            "status": inv.status,
            "expires_at": inv.expires_at.isoformat(),
            "invited_by": str(inv.invited_by),
            "accepted_at": inv.accepted_at.isoformat() if inv.accepted_at else None,
            "declined_at": inv.declined_at.isoformat() if inv.declined_at else None,
            "revoked_at": inv.revoked_at.isoformat() if inv.revoked_at else None,
            "membership_id": str(inv.membership_id) if inv.membership_id else None,
            "resend_count": inv.resend_count,
            "last_resent_at": inv.last_resent_at.isoformat() if inv.last_resent_at else None,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
            "updated_at": inv.updated_at.isoformat() if inv.updated_at else None,
        }

    @staticmethod
    def validate_transition(current: str, target: str) -> None:
        allowed = ALLOWED_INVITATION_TRANSITIONS.get(current, frozenset())
        if target not in allowed:
            raise ValidationError(
                f"Invalid invitation status transition: {current} → {target}",
                details={"from_status": current, "to_status": target},
            )

    @staticmethod
    async def get_by_id(
        session: AsyncSession, business_id: uuid.UUID, invitation_id: uuid.UUID
    ) -> BusinessInvitation | None:
        result = await session.execute(
            select(BusinessInvitation).where(
                BusinessInvitation.id == invitation_id,
                BusinessInvitation.business_id == business_id,
            )
        )
        return result.scalars().first()

    @staticmethod
    async def get_by_id_for_update(
        session: AsyncSession, business_id: uuid.UUID, invitation_id: uuid.UUID
    ) -> BusinessInvitation | None:
        result = await session.execute(
            select(BusinessInvitation)
            .where(
                BusinessInvitation.id == invitation_id,
                BusinessInvitation.business_id == business_id,
            )
            .with_for_update()
        )
        return result.scalars().first()

    @staticmethod
    async def list_for_business(
        session: AsyncSession, business_id: uuid.UUID
    ) -> list[BusinessInvitation]:
        result = await session.execute(
            select(BusinessInvitation)
            .where(BusinessInvitation.business_id == business_id)
            .order_by(BusinessInvitation.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def _ensure_pending_usable(inv: BusinessInvitation) -> None:
        if inv.status != "pending":
            if inv.status == "accepted":
                raise ConflictError("Invitation has already been accepted")
            if inv.status == "declined":
                raise ConflictError("Invitation has already been declined")
            if inv.status == "revoked":
                raise ConflictError("Invitation has been revoked")
            if inv.status == "expired":
                raise ConflictError("Invitation has expired")
            raise ConflictError(f"Invitation is not pending (status={inv.status})")

        now = datetime.now(timezone.utc)
        expires = inv.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= now:
            inv.status = "expired"
            inv.version += 1
            raise ConflictError("Invitation has expired", details={"status": "expired"})

    @staticmethod
    async def _assert_no_active_membership(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        email: str,
        identity_id: uuid.UUID | None,
    ) -> None:
        if identity_id is not None:
            membership = await TeamService.get_membership(session, identity_id, business_id)
            if membership is not None and membership.status in {"pending", "active", "suspended"}:
                raise ConflictError(
                    "An active or pending membership already exists for this identity",
                    details={"identity_id": str(identity_id)},
                )

        if identity_id is None:
            identity = await IdentityService.get_by_email(session, email)
            if identity is not None:
                membership = await TeamService.get_membership(session, identity.id, business_id)
                if membership is not None and membership.status in {
                    "pending",
                    "active",
                    "suspended",
                }:
                    raise ConflictError(
                        "An active or pending membership already exists for this email",
                        details={"email": email},
                    )

    @staticmethod
    async def _assert_no_pending_duplicate(
        session: AsyncSession, *, business_id: uuid.UUID, email: str
    ) -> None:
        result = await session.execute(
            select(BusinessInvitation).where(
                BusinessInvitation.business_id == business_id,
                BusinessInvitation.status == "pending",
                func.lower(BusinessInvitation.invited_email) == email,
            )
        )
        if result.scalars().first() is not None:
            raise ConflictError(
                "A pending invitation already exists for this email",
                details={"email": email},
            )

    @staticmethod
    async def _publish_invitation_event(
        session: AsyncSession,
        *,
        event_type: str,
        audit_action: str,
        invitation: BusinessInvitation,
        actor_id: uuid.UUID,
        correlation_id: str,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "invitation_id": str(invitation.id),
            "business_id": str(invitation.business_id),
            "invited_email": invitation.invited_email,
            "invited_role": invitation.invited_role,
            "status": invitation.status,
        }
        await OutboxService.publish(
            session,
            event_type=event_type,
            payload=payload,
            business_id=invitation.business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type=event_type,
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=invitation.business_id,
            resource_type="invitation",
            resource_id=invitation.id,
            action=audit_action,
            before_state=before_state,
            after_state=after_state or InvitationService.serialize_invitation(invitation),
        )

    @staticmethod
    async def create_invitation(
        session: AsyncSession,
        *,
        business: Business,
        actor: BusinessMembership,
        invited_email: str,
        invited_role: str,
        correlation_id: str,
        location_scope: list[uuid.UUID] | None = None,
    ) -> BusinessInvitation:
        assert_business_mutable(business.state, action="create_invitation")
        email = InvitationService.normalize_email(invited_email)
        TeamService.assert_can_assign_role(actor.role, invited_role)

        existing_identity = await IdentityService.get_by_email(session, email)
        identity_id = existing_identity.id if existing_identity else None
        await InvitationService._assert_no_active_membership(
            session,
            business_id=business.id,
            email=email,
            identity_id=identity_id,
        )
        await InvitationService._assert_no_pending_duplicate(
            session, business_id=business.id, email=email
        )

        now = datetime.now(timezone.utc)
        invitation = BusinessInvitation(
            business_id=business.id,
            invited_email=email,
            invited_identity_id=identity_id,
            invited_role=invited_role,
            location_scope=location_scope,
            status="pending",
            expires_at=now + timedelta(hours=INVITATION_TTL_HOURS),
            invited_by=actor.identity_id,
        )
        session.add(invitation)
        await session.flush()

        await InvitationService._publish_invitation_event(
            session,
            event_type="invitation.created",
            audit_action="create",
            invitation=invitation,
            actor_id=actor.identity_id,
            correlation_id=correlation_id,
        )
        return invitation

    @staticmethod
    async def resend_invitation(
        session: AsyncSession,
        *,
        business: Business,
        invitation: BusinessInvitation,
        actor: BusinessMembership,
        correlation_id: str,
    ) -> BusinessInvitation:
        assert_business_mutable(business.state, action="resend_invitation")
        locked = await InvitationService.get_by_id_for_update(session, business.id, invitation.id)
        if locked is None:
            raise ResourceNotFound("Invitation")
        invitation = locked
        await InvitationService._ensure_pending_usable(invitation)

        now = datetime.now(timezone.utc)
        if invitation.last_resent_at is not None:
            last = invitation.last_resent_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            elapsed = (now - last).total_seconds()
            if elapsed < RESEND_COOLDOWN_SECONDS:
                raise ConflictError(
                    "Invitation was resent too recently",
                    details={"retry_after_seconds": int(RESEND_COOLDOWN_SECONDS - elapsed)},
                )
        if invitation.resend_count >= MAX_RESEND_COUNT:
            raise ConflictError("Maximum resend limit reached for this invitation")

        before = {"resend_count": invitation.resend_count}
        invitation.resend_count += 1
        invitation.last_resent_at = now
        invitation.expires_at = now + timedelta(hours=INVITATION_TTL_HOURS)
        invitation.version += 1
        await session.flush()

        await InvitationService._publish_invitation_event(
            session,
            event_type="invitation.resent",
            audit_action="resend",
            invitation=invitation,
            actor_id=actor.identity_id,
            correlation_id=correlation_id,
            before_state=before,
        )
        return invitation

    @staticmethod
    async def revoke_invitation(
        session: AsyncSession,
        *,
        business: Business,
        invitation: BusinessInvitation,
        actor: BusinessMembership,
        correlation_id: str,
    ) -> BusinessInvitation:
        assert_business_mutable(business.state, action="revoke_invitation")
        locked = await InvitationService.get_by_id_for_update(session, business.id, invitation.id)
        if locked is None:
            raise ResourceNotFound("Invitation")
        invitation = locked
        await InvitationService._ensure_pending_usable(invitation)

        before = {"status": invitation.status}
        InvitationService.validate_transition(invitation.status, "revoked")
        now = datetime.now(timezone.utc)
        invitation.status = "revoked"
        invitation.revoked_at = now
        invitation.version += 1
        await session.flush()

        await InvitationService._publish_invitation_event(
            session,
            event_type="invitation.revoked",
            audit_action="revoke",
            invitation=invitation,
            actor_id=actor.identity_id,
            correlation_id=correlation_id,
            before_state=before,
        )
        return invitation

    @staticmethod
    def _assert_recipient(
        invitation: BusinessInvitation, identity_id: uuid.UUID, email: str
    ) -> None:
        normalized = email.strip().lower()
        if invitation.invited_identity_id is not None:
            if invitation.invited_identity_id != identity_id:
                raise ValidationError("Invitation is not addressed to this identity")
        elif invitation.invited_email != normalized:
            raise ValidationError("Invitation is not addressed to this identity")

    @staticmethod
    async def accept_invitation(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        invitation_id: uuid.UUID,
        accepter_identity_id: uuid.UUID,
        accepter_email: str,
        correlation_id: str,
    ) -> tuple[BusinessInvitation, BusinessMembership]:
        # RLS (AUD-02): the request was resolved with force_personal=True (no
        # membership existed yet, so gate [4] legitimately doesn't apply), so
        # app.current_business_id is still unset at this point. Bind it from
        # the supplied (path) business_id BEFORE the Business lookup below —
        # otherwise businesses_api_select has no arm covering "identity with
        # a pending invitation, not yet a member" and the lookup 404s.
        #
        # This bind is tenant-scope plumbing only, not an authorization
        # decision — it does not grant this identity anything. The Business
        # lookup, assert_business_mutable, the invitation lookup, and
        # especially _assert_recipient below remain the actual authorization
        # checks: an identity that binds this business_id but turns out not
        # to be the invitation's recipient is still rejected by
        # _assert_recipient, same as before this change.
        await bind_session_context(session, accepter_identity_id, business_id)

        business = await BusinessService.get_by_id(session, business_id)
        if not business:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="accept_invitation")

        locked = await InvitationService.get_by_id_for_update(session, business_id, invitation_id)
        if locked is None:
            raise ResourceNotFound("Invitation")
        invitation = locked

        try:
            await InvitationService._ensure_pending_usable(invitation)
        except ConflictError:
            if invitation.status == "expired":
                await session.flush()
                await InvitationService._publish_invitation_event(
                    session,
                    event_type="invitation.expired",
                    audit_action="expire",
                    invitation=invitation,
                    actor_id=accepter_identity_id,
                    correlation_id=correlation_id,
                    before_state={"status": "pending"},
                )
            raise

        InvitationService._assert_recipient(invitation, accepter_identity_id, accepter_email)

        membership = await TeamService.create_membership_from_invitation(
            session,
            business_id=business_id,
            identity_id=accepter_identity_id,
            role=invitation.invited_role,
            location_scope=invitation.location_scope,
            invited_by=invitation.invited_by,
            correlation_id=correlation_id,
        )

        now = datetime.now(timezone.utc)
        invitation.status = "accepted"
        invitation.accepted_at = now
        invitation.invited_identity_id = accepter_identity_id
        invitation.membership_id = membership.id
        invitation.version += 1
        await session.flush()

        await InvitationService._publish_invitation_event(
            session,
            event_type="invitation.accepted",
            audit_action="accept",
            invitation=invitation,
            actor_id=accepter_identity_id,
            correlation_id=correlation_id,
            before_state={"status": "pending"},
        )
        return invitation, membership

    @staticmethod
    async def decline_invitation(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        invitation_id: uuid.UUID,
        decliner_identity_id: uuid.UUID,
        decliner_email: str,
        correlation_id: str,
    ) -> BusinessInvitation:
        # RLS (AUD-02): same reasoning as accept_invitation — the request was
        # resolved with force_personal=True (no membership yet), so
        # app.current_business_id is unset. Bind it from the verified path
        # business_id before any business-scoped read/write.
        await bind_session_context(session, decliner_identity_id, business_id)

        locked = await InvitationService.get_by_id_for_update(session, business_id, invitation_id)
        if locked is None:
            raise ResourceNotFound("Invitation")
        invitation = locked
        await InvitationService._ensure_pending_usable(invitation)
        InvitationService._assert_recipient(invitation, decliner_identity_id, decliner_email)

        before = {"status": invitation.status}
        InvitationService.validate_transition(invitation.status, "declined")
        now = datetime.now(timezone.utc)
        invitation.status = "declined"
        invitation.declined_at = now
        invitation.invited_identity_id = decliner_identity_id
        invitation.version += 1
        await session.flush()

        await InvitationService._publish_invitation_event(
            session,
            event_type="invitation.declined",
            audit_action="decline",
            invitation=invitation,
            actor_id=decliner_identity_id,
            correlation_id=correlation_id,
            before_state=before,
        )
        return invitation
