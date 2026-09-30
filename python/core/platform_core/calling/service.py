"""Calls: the record, the permission rule, and WhatsApp call signalling.

* Every call LOCAH hears about becomes one calls_sessions row - business,
  channel (whatsapp_call | pstn), direction, the provider's call id, caller and
  callee, start/answer/end, state, who handled it (nobody / a person / an AI
  employee), hand-offs, and what it led to. No SDP, media or tokens.
* A business never places a WhatsApp call to someone who has not granted
  permission (call_permission_reply, or a temporary one from calling in).
* Answering needs a media runtime (calling_runtime()); without one a call is
  recorded, the team is alerted, and nobody pretends it was answered.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.business_types import DEFAULT_TIMEZONE
from platform_core.calling.whatsapp import WhatsAppCalling, call_hours, permission_request_interactive
from platform_core.crypto import decrypt_secret
from platform_core.exceptions import ConflictError, PlatformError, ResourceNotFound
from platform_core.messaging.connection import calling_runtime
from platform_core.models import (
    Business,
    BusinessLocation,
    CallPermission,
    CallSession,
    MessagingChannel,
    MessagingConversation,
)
from platform_core.services.audit import AuditService

TEMPORARY_PERMISSION = timedelta(days=7)  # Meta: a temporary permission lasts 7 days (168 hours)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _from_ts(value: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value), timezone.utc)
    except (TypeError, ValueError):
        return None


class CallService:
    # ------------------------------------------------------------------ read
    @staticmethod
    def serialize(call: CallSession) -> dict[str, Any]:
        return {
            "id": str(call.id), "channel": call.channel, "provider": call.provider, "direction": call.direction,
            "from_number": call.from_number, "to_number": call.to_number,
            "customer_contact_id": str(call.customer_contact_id) if call.customer_contact_id else None,
            "state": call.state, "handled_by_type": call.handled_by_type,
            "handled_by_id": str(call.handled_by_id) if call.handled_by_id else None,
            "within_business_hours": call.within_business_hours,
            "started_at": call.started_at.isoformat() if call.started_at else None,
            "answered_at": call.answered_at.isoformat() if call.answered_at else None,
            "ended_at": call.ended_at.isoformat() if call.ended_at else None,
            "duration_seconds": call.duration_seconds, "end_status": call.end_status,
            "related_type": call.related_type, "related_id": str(call.related_id) if call.related_id else None,
            "handoffs": call.handoffs or [], "note": call.note,
        }

    @staticmethod
    async def recent(session: AsyncSession, business_id: uuid.UUID, limit: int = 30) -> list[CallSession]:
        return list((await session.execute(select(CallSession).where(CallSession.business_id == business_id)
                                           .order_by(CallSession.started_at.desc()).limit(limit))).scalars().all())

    @staticmethod
    async def _within_hours(session: AsyncSession, business_id: uuid.UUID, at: datetime) -> bool | None:
        location = (await session.execute(select(BusinessLocation).where(
            BusinessLocation.business_id == business_id, BusinessLocation.is_primary.is_(True)))).scalars().first()
        if location is None or not location.hours:
            return None
        from platform_core.services.availability import AvailabilityService

        return AvailabilityService.closed_reason(location, "appointment", at, at + timedelta(minutes=1)) is None

    # ------------------------------------------------------------------ WhatsApp webhooks
    @staticmethod
    async def ingest_whatsapp(session: AsyncSession, channel: MessagingChannel, call: dict[str, Any],
                              names: dict[str, Any]) -> int:
        """A `calls` webhook event: connect (a call is ringing) or terminate."""
        from platform_core.services.messaging import MessagingService, normalise_phone

        call_id = str(call.get("id") or "")
        event = str(call.get("event") or "")
        if not call_id or event not in ("connect", "terminate"):
            return 0
        direction = "outbound" if str(call.get("direction") or "").upper() == "BUSINESS_INITIATED" else "inbound"
        customer = normalise_phone(call.get("from") if direction == "inbound" else call.get("to"))
        contact = await MessagingService.find_contact(session, channel.business_id, customer) if customer else None
        at = _from_ts(call.get("timestamp")) or _now()
        await session.execute(pg_insert(CallSession).values(
            id=uuid.uuid4(), business_id=channel.business_id, channel="whatsapp_call", provider=channel.provider,
            direction=direction, external_call_id=call_id[:200],
            from_number=(str(call.get("from") or "") or None), to_number=(str(call.get("to") or "") or None),
            customer_contact_id=contact.id if contact else None, state="ringing", started_at=at,
            within_business_hours=await CallService._within_hours(session, channel.business_id, at),
        ).on_conflict_do_nothing(index_elements=["business_id", "channel", "external_call_id"]))
        row = (await session.execute(select(CallSession).where(
            CallSession.business_id == channel.business_id, CallSession.channel == "whatsapp_call",
            CallSession.external_call_id == call_id[:200]).with_for_update())).scalars().one()
        if event == "connect":
            if row.note is not None:
                return 0  # the same ring again
            if customer and direction == "inbound" and channel.calling_status == "enabled":
                # Meta: calling in grants a temporary call-back permission (callback enabled).
                await CallService._set_permission(session, channel.business_id, customer, contact.id if contact
                                                  else None, status="granted", permanent=False,
                                                  expires=at + TEMPORARY_PERMISSION, source="customer_called")
            if calling_runtime() is None:
                row.note = "Nobody on LOCAH can answer WhatsApp calls yet; call the customer back"
                name = names.get(customer or "") or (contact.display_name if contact else None) or f"+{customer}"
                await MessagingService.alert_staff(session, channel.business_id, "call.missed",
                                                   f"WhatsApp call from {name} - LOCAH cannot answer calls yet",
                                                   key=call_id[:80])
            else:
                row.note = "Offered to the call runtime"
            await session.flush()
            return 1
        # terminate
        if row.state in ("ended", "missed", "failed", "rejected"):
            return 0
        answered = row.answered_at is not None or row.state == "connected"
        status = str(call.get("status") or "").upper()
        row.state = "failed" if status == "FAILED" else ("ended" if answered else "missed")
        row.end_status = status[:40] or None
        row.ended_at = _from_ts(call.get("end_time")) or _from_ts(call.get("timestamp")) or _now()
        if call.get("duration") is not None:
            row.duration_seconds = max(int(call["duration"]), 0)
        row.version += 1
        await session.flush()
        business = await session.get(Business, channel.business_id)
        await AuditService.record(session, event_type="calls.call_ended",
                                  actor_identity_id=business.primary_owner_identity_id if business else None,
                                  actor_context="system", business_id=channel.business_id,
                                  resource_type="call_session", resource_id=row.id, action=row.state,
                                  after_state={"channel": row.channel, "direction": row.direction,
                                               "state": row.state, "duration_seconds": row.duration_seconds})
        return 1

    # ------------------------------------------------------------------ permission
    @staticmethod
    async def _set_permission(session: AsyncSession, business_id: uuid.UUID, wa_id: str,
                              contact_id: uuid.UUID | None, *, status: str, permanent: bool,
                              expires: datetime | None, source: str) -> CallPermission:
        row = await session.get(CallPermission, (business_id, wa_id))
        if row is None:
            row = CallPermission(business_id=business_id, wa_id=wa_id, customer_contact_id=contact_id,
                                 status=status, requests=[])
            session.add(row)
        # A permanent grant is not shortened by a later temporary one.
        if not (row.status == "granted" and row.is_permanent and status == "granted" and not permanent):
            row.status, row.is_permanent, row.expires_at = status, permanent, None if permanent else expires
        row.source, row.updated_at = source, _now()
        row.customer_contact_id = row.customer_contact_id or contact_id
        await session.flush()
        return row

    @staticmethod
    async def permission_reply(session: AsyncSession, business_id: uuid.UUID, wa_id: str,
                               contact_id: uuid.UUID | None, reply: dict[str, Any]) -> CallPermission:
        """call_permission_reply: the customer allowed (or refused) calls."""
        accepted = str(reply.get("response") or "").lower() == "accept"
        permanent = bool(reply.get("is_permanent"))
        return await CallService._set_permission(
            session, business_id, wa_id, contact_id, status="granted" if accepted else "rejected",
            permanent=accepted and permanent, expires=_from_ts(reply.get("expiration_timestamp")),
            source=str(reply.get("response_source") or "user_action")[:40])

    @staticmethod
    def permission_open(row: CallPermission | None, now: datetime | None = None) -> bool:
        if row is None or row.status != "granted":
            return False
        return row.is_permanent or (row.expires_at is not None and row.expires_at > (now or _now()))

    @staticmethod
    async def request_permission(session: AsyncSession, business_id: uuid.UUID, conversation_id: uuid.UUID,
                                 actor_id: uuid.UUID, reason: str) -> CallPermission:
        """Ask the customer, inside their 24-hour window, whether the business may
        call. Meta allows at most one request a day and two a week per customer."""
        from platform_core.services.messaging import MessagingService

        conv = await session.get(MessagingConversation, conversation_id)
        if conv is None or conv.business_id != business_id:
            raise ResourceNotFound("Conversation")
        if not MessagingService.window_open(conv):
            raise ConflictError("A call permission request can only go inside the customer's 24-hour window; "
                                "outside it WhatsApp needs an approved call-permission template, which LOCAH's "
                                "library does not have yet", details={"code": "outside_window"})
        row = await session.get(CallPermission, (business_id, conv.wa_id))
        if CallService.permission_open(row):
            raise ConflictError("This customer already allows calls", details={"code": "already_granted"})
        now = _now()
        sent = [datetime.fromisoformat(t) for t in (row.requests if row else [])]
        if any(now - t < timedelta(days=1) for t in sent) or sum(now - t < timedelta(days=7) for t in sent) >= 2:
            raise ConflictError("WhatsApp allows one call permission request a day and two a week",
                                details={"code": "request_limit"})
        channel = await session.get(MessagingChannel, conv.channel_id)
        if channel is None or channel.status != "connected":
            raise ConflictError("WhatsApp is not connected")
        from platform_core.models import MessagingMessage

        msg = MessagingMessage(business_id=business_id, conversation_id=conv.id, direction="out", kind="interactive",
                               body=reason[:1024], payload={"interactive": permission_request_interactive(reason)},
                               category="service", status="queued", sent_via="workspace", sent_by=actor_id)
        session.add(msg)
        await session.flush()
        interactive = permission_request_interactive(reason)
        wa_id = conv.wa_id
        msg = await MessagingService._deliver(
            session, channel, conv, msg,
            lambda p, token: p.send_interactive(token, channel.phone_number_id, wa_id, interactive))
        if msg.status != "sent":
            raise ConflictError(f"Not sent: {msg.error or msg.status}")
        if row is None:
            row = CallPermission(business_id=business_id, wa_id=conv.wa_id, customer_contact_id=conv.contact_id,
                                 status="requested", requests=[])
            session.add(row)
        elif row.status != "granted":
            row.status = "requested"
        row.requests = [t.isoformat() for t in sent if now - t < timedelta(days=7)] + [now.isoformat()]
        row.updated_at = now
        await session.flush()
        return row

    @staticmethod
    async def assert_may_call(session: AsyncSession, business_id: uuid.UUID, wa_id: str) -> None:
        """The gate every business-initiated WhatsApp call goes through."""
        from platform_core.services.messaging import MessagingService

        channel = await MessagingService.channel(session, business_id)
        state = (await MessagingService.connection(session, business_id))["calling"]
        if channel is None or state["state"] != "CALLING_ACTIVE":
            raise ConflictError("WhatsApp calling is not active for this business",
                                details={"code": "calling_not_active", "calling_state": state["state"]})
        if not CallService.permission_open(await session.get(CallPermission, (business_id, wa_id))):
            raise ConflictError("This customer has not allowed calls from this business",
                                details={"code": "call_permission_required"})

    # ------------------------------------------------------------------ settings
    @staticmethod
    async def set_enabled(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, *, enabled: bool,
                          transport: Any = None) -> dict[str, Any]:
        """Switch calling on (with the location's hours) or off on the number."""
        from platform_core.services.messaging import MessagingService

        channel = await MessagingService.channel(session, business_id)
        connection = await MessagingService.connection(session, business_id)
        allowed = ("CALLING_ELIGIBLE", "CALLING_SETUP_REQUIRED", "CALLING_ACTIVE", "CALLING_DEGRADED")
        if channel is None or (enabled and connection["calling"]["state"] not in allowed):
            raise ConflictError(connection["calling"]["reason"] or "WhatsApp calling is not available",
                                details={"code": "calling_unavailable", "calling_state": connection["calling"]["state"]})
        location = (await session.execute(select(BusinessLocation).where(
            BusinessLocation.business_id == business_id, BusinessLocation.is_primary.is_(True)))).scalars().first()
        hours = call_hours(location.hours if location else None,
                           (location.timezone if location else None) or DEFAULT_TIMEZONE)
        client = WhatsAppCalling(channel.provider, transport=transport)
        token = decrypt_secret(channel.encrypted_token) if channel.encrypted_token else None
        try:
            await client.set_calling(token, str(channel.phone_number_id), enabled=enabled, hours=hours)
        except PlatformError as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            channel.calling_error = str(detail.get("message") or exc.code)[:500]
            await session.flush()
            return dict(await MessagingService.connection(session, business_id))
        channel.calling_status = "enabled" if enabled else "off"
        channel.calling_checked_at, channel.calling_error = _now(), None
        channel.version += 1
        await session.flush()
        await AuditService.record(session, event_type="messaging.calling_changed", actor_identity_id=actor_id,
                                  actor_context="business", business_id=business_id,
                                  resource_type="messaging_channel", resource_id=channel.id,
                                  action="calling_on" if enabled else "calling_off",
                                  after_state={"calling_status": channel.calling_status, "call_hours": bool(hours)})
        return dict(await MessagingService.connection(session, business_id))
