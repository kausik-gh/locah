"""WhatsApp & messages (Capability Universe §6.2 `messaging`, §9.1, §12.1,
§12.4, §12.5; §26.3 P1-07).

One WhatsApp number per business, one conversation per customer number, one
inbox. What this service guarantees:

* **Metered.** Every message LOCAH sends counts in the business's
  `whatsapp_message` meter (§8.4, §9.3) and stops at the owner's cap.
* **Consent.** A marketing template never goes to a customer without an open
  marketing opt-in for WhatsApp (§12.4, §12.6); STOP withdraws it.
* **Templates outside the window.** Free text goes only within 24 hours of
  the customer's last message; anything else is an approved template (§9.1).
* **People first.** A person's reply — in the inbox or from the WhatsApp
  Business app on the same number (coexistence) — keeps LOCAH's automatic
  replies out of that chat for the owner's pause (12 hours by default, §12.1).
* **Idempotent.** A webhook delivered twice records one message; a send with
  the same key sends once.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.crypto import decrypt_secret, encrypt_secret
from platform_core.exceptions import ConflictError, PlatformError, ResourceNotFound, ValidationError
from platform_core.messaging.provider import (
    MetaCloudProvider,
    meta_configured,
    meta_public_config,
    provider_for,
    sandbox_enabled,
)
from platform_core.messaging.templates import LANGUAGES, LIBRARY, library_view, render
from platform_core.models import (
    Business,
    CustomerContact,
    MessagingChannel,
    MessagingConversation,
    MessagingMessage,
    MessagingQuickReply,
    MessagingSettings,
    MessagingStaffAlert,
    MessagingTemplate,
    PlatformIdentity,
)
from platform_core.services.audit import AuditService

WINDOW = timedelta(hours=24)
WAITING_ALERT = timedelta(minutes=10)
# What LOCAH sends customers the moment something happens (owner switches each).
CUSTOMER_UPDATES: dict[str, str] = {
    "order_received": "When a customer places an order",
    "order_confirmed": "When you accept an order",
    "order_delivered": "When an order is delivered",
    "booking_confirmed": "When a booking is confirmed",
    "queue_turn_soon": "When a customer's queue turn is near",
}
# Timed messages are ladders the owner switches in Automations.
LADDER_UPDATES: dict[str, str] = {
    "order.tracking": "Out for delivery, with the tracking link",
    "booking.reminder": "Booking reminders",
    "invoice.overdue": "Payment reminders for bills",
    "ledger.statement": "Khata reminders",
}
# A team member's own WhatsApp alerts, and what they must be allowed to see.
STAFF_ALERTS: dict[str, tuple[str, str]] = {
    "order.new": ("New orders", "orders.read"),
    "booking.new": ("New bookings", "bookings.read"),
    "lead.new": ("New enquiries", "leads.read"),
    "chat.waiting": ("Customers waiting for a person on WhatsApp", "messaging.read"),
    "khata.over_limit": ("Khata allowed over a customer's limit", "ledger.manage"),
    "call.missed": ("WhatsApp calls LOCAH could not answer", "messaging.read"),
}
# "Talk to a person" in English, Tamil and Hindi (a button id, or words typed).
PERSON_WORDS = ("talk to person", "talk to a person", "human", "agent", "person", "call me", "speak to someone",
                "நபர்", "ஆளிடம் பேச", "इंसान", "व्यक्ति से बात")
STOP_WORDS = ("stop", "unsubscribe", "நிறுத்து", "बंद")


def _err(field: str, message: str) -> ValidationError:
    return ValidationError(message, details={"errors": [{"field": field, "message": message}], "field": field})


def normalise_phone(raw: Any) -> str | None:
    """Digits WhatsApp understands (country code, no +). Ten-digit Indian
    mobiles get 91 in front."""
    digits = re.sub(r"\D", "", str(raw or ""))
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in "6789":
        digits = "91" + digits
    return digits if 10 <= len(digits) <= 15 else None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _preview(text_: str | None) -> str | None:
    return (text_ or "").strip().replace("\n", " ")[:200] or None


class NotSent(Exception):
    """A message LOCAH decided not to send, with the reason in owner words."""


class MessagingService:
    # ------------------------------------------------------------------ channel
    @staticmethod
    async def channel(session: AsyncSession, business_id: uuid.UUID) -> MessagingChannel | None:
        return (await session.execute(select(MessagingChannel).where(
            MessagingChannel.business_id == business_id, MessagingChannel.status != "disconnected",
        ))).scalars().first()

    @staticmethod
    async def reachable(session: AsyncSession, business_id: uuid.UUID, contact_id: uuid.UUID | None) -> bool:
        """Can this business message this customer on WhatsApp right now (module on,
        a number connected, the customer has a phone)? Other modules ask before
        promising a customer that something "was sent"."""
        from platform_core.events.subscribers.automation_triggers import _module_on

        channel = await MessagingService.channel(session, business_id)
        if channel is None or channel.status != "connected" or not await _module_on(session, business_id, "messaging"):
            return False
        if contact_id is None:
            return False
        phone = (await session.execute(select(CustomerContact.phone).where(
            CustomerContact.id == contact_id, CustomerContact.business_id == business_id))).scalar()
        return normalise_phone(phone or "") is not None

    @staticmethod
    def serialize_channel(c: MessagingChannel | None) -> dict[str, Any] | None:
        if c is None:
            return None
        return {"id": str(c.id), "provider": c.provider, "status": c.status, "display_phone": c.display_phone,
                "display_name": c.display_name, "coexistence": c.coexistence, "quality_rating": c.quality_rating,
                "messaging_limit": c.messaging_limit, "last_error": c.last_error,
                "last_webhook_at": c.last_webhook_at.isoformat() if c.last_webhook_at else None,
                "connected_at": c.connected_at.isoformat() if c.connected_at else None,
                "waba_id": c.waba_id,
                "phone_registered_at": c.phone_registered_at.isoformat() if c.phone_registered_at else None,
                "registration_error": c.registration_error, "calling_status": c.calling_status,
                "calling_error": c.calling_error,
                "sandbox": c.provider == "sandbox"}

    @staticmethod
    async def settings(session: AsyncSession, business_id: uuid.UUID) -> MessagingSettings:
        row = await session.get(MessagingSettings, business_id)
        if row is None:
            row = MessagingSettings(business_id=business_id, language="en", customer_updates={}, human_pause_hours=12)
            session.add(row)
            await session.flush()
        return row

    @staticmethod
    def update_on(s: MessagingSettings, key: str) -> bool:
        return bool((s.customer_updates or {}).get(key, True))

    @staticmethod
    async def setup(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
                    permissions: frozenset[str]) -> dict[str, Any]:
        from platform_core.services.usage_meter import UsageMeterService

        from platform_core.services.fulfilment import FulfilmentService

        channel = await MessagingService.channel(session, business_id)
        s = await MessagingService.settings(session, business_id)
        cod = await FulfilmentService.payment_rules(session, business_id)
        states = {(t.template_key, t.language): t for t in (await session.execute(select(MessagingTemplate).where(
            MessagingTemplate.business_id == business_id))).scalars()}
        templates = []
        for t in library_view():
            templates.append({**t, "status": {lang: (states[(str(t["key"]), lang)].status
                                                     if (str(t["key"]), lang) in states else None)
                                              for lang in LANGUAGES}})
        mine = await session.get(MessagingStaffAlert, (business_id, actor_id))
        meters = {m["resource"]: m for m in await UsageMeterService.summary(session, business_id)}
        return {
            "channel": MessagingService.serialize_channel(channel),
            "connection": await MessagingService.connection(session, business_id),
            "meta": meta_public_config(), "meta_ready": meta_configured(), "sandbox_available": sandbox_enabled(),
            "settings": {"language": s.language, "human_pause_hours": s.human_pause_hours,
                         "customer_updates": {k: MessagingService.update_on(s, k) for k in CUSTOMER_UPDATES},
                         "cod_allowed": cod["on_delivery"], "first_order_cod_cap": cod["first_order_cap"]},
            "entry": await MessagingService.entry(session, business_id),
            "customer_updates": CUSTOMER_UPDATES, "ladder_updates": LADDER_UPDATES, "languages": LANGUAGES,
            "templates": templates,
            "alerts": {"mine": {"phone": mine.phone, "kinds": list(mine.kinds), "enabled": mine.enabled}
                       if mine else None,
                       "kinds": {k: label for k, (label, perm) in STAFF_ALERTS.items() if perm in permissions}},
            "meter": meters.get("whatsapp_message"),
        }

    @staticmethod
    async def connection(session: AsyncSession, business_id: uuid.UUID) -> dict[str, Any]:
        """The honest state of WhatsApp messaging and calling for this business
        (platform_core.messaging.connection), with what the owner must see."""
        from platform_core.calling.voice import telephony_state
        from platform_core.messaging.connection import calling_state, messaging_state

        channel = await MessagingService.channel(session, business_id)
        was_disconnected = channel is None and (await session.execute(select(MessagingChannel.id).where(
            MessagingChannel.business_id == business_id, MessagingChannel.status == "disconnected").limit(1))
        ).first() is not None
        rows = list((await session.execute(select(MessagingTemplate).where(
            MessagingTemplate.business_id == business_id))).scalars())
        approved_utility = sum(1 for r in rows if r.status == "approved"
                               and (r.category or (LIBRARY[r.template_key].category
                                                   if r.template_key in LIBRARY else "")) == "utility")
        awaiting = sum(1 for r in rows if r.status == "submitted")
        messaging = messaging_state(channel=channel, was_disconnected=was_disconnected, meta_ready=meta_configured(),
                                    sandbox_available=sandbox_enabled(), approved_utility=approved_utility,
                                    awaiting_review=awaiting)
        return {
            "messaging": messaging,
            "calling": calling_state(channel, messaging),
            "telephony": telephony_state(),
            "templates": {"approved": sum(1 for r in rows if r.status == "approved"), "approved_utility":
                          approved_utility, "awaiting_review": awaiting,
                          "rejected": sum(1 for r in rows if r.status == "rejected")},
            "last_webhook_at": channel.last_webhook_at.isoformat() if channel and channel.last_webhook_at else None,
        }

    @staticmethod
    async def entry(session: AsyncSession, business_id: uuid.UUID) -> dict[str, Any] | None:
        """§12.2 entry points for the owner to share: the link with "menu" typed,
        its QR for the counter and packaging, and what customers can do there."""
        from platform_core.messaging.entry import whatsapp_entry
        from platform_core.services.pos import PosService

        entry = await whatsapp_entry(session, business_id)
        if entry is None:
            return None
        return {**entry, "qr_svg": PosService.qr_svg(str(entry["href"]))}

    @staticmethod
    async def _connected(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
                         channel: MessagingChannel) -> MessagingChannel:
        channel.status, channel.connected_at, channel.connected_by = "connected", _now(), actor_id
        channel.last_error = None
        await session.flush()
        await AuditService.record(session, event_type="messaging.channel.connected", actor_identity_id=actor_id,
                                  actor_context="business", action="connect", business_id=business_id,
                                  resource_type="messaging_channel", resource_id=channel.id,
                                  after_state=MessagingService.serialize_channel(channel))
        await MessagingService.submit_templates(session, business_id)
        return channel

    @staticmethod
    async def connect_sandbox(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
                              display_phone: str, display_name: str | None) -> MessagingChannel:
        """A test stack's stand-in number: messages are recorded, never delivered."""
        if not sandbox_enabled():
            raise ConflictError("The WhatsApp sandbox is only available on test stacks")
        if await MessagingService.channel(session, business_id):
            raise ConflictError("A WhatsApp number is already connected; disconnect it first")
        phone = normalise_phone(display_phone)
        if phone is None:
            raise _err("display_phone", "Enter the WhatsApp number with its country code")
        business = await session.get(Business, business_id)
        channel = MessagingChannel(business_id=business_id, kind="whatsapp", provider="sandbox", status="pending",
                                   display_phone=f"+{phone}", display_name=(display_name or (business.display_name
                                   if business else ""))[:120], phone_number_id=f"sandbox-{business_id.hex[:16]}",
                                   waba_id=f"sandbox-{business_id.hex[:12]}", phone_registered_at=_now())
        session.add(channel)
        await session.flush()
        return await MessagingService._connected(session, business_id, actor_id, channel)

    @staticmethod
    async def complete_signup(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, *, code: str,
                              waba_id: str, phone_number_id: str, coexistence: bool,
                              pin: str | None = None) -> MessagingChannel:
        """Embedded Signup finished in the owner's browser; finish it with Meta:
        exchange the code, subscribe to the WABA's webhooks, then register the
        number (Meta requires it before a Cloud API number can send). A number
        kept on the WhatsApp Business app (coexistence) is already registered."""
        if await MessagingService.channel(session, business_id):
            raise ConflictError("A WhatsApp number is already connected; disconnect it first")
        provider = MetaCloudProvider()
        result = await provider.complete_signup(code, waba_id, phone_number_id)
        channel = MessagingChannel(
            business_id=business_id, kind="whatsapp", provider="meta_cloud", status="pending",
            display_phone=result.display_phone, display_name=result.display_name, phone_number_id=phone_number_id,
            waba_id=waba_id, coexistence=coexistence, quality_rating=result.quality_rating,
            messaging_limit=result.messaging_limit, encrypted_token=encrypt_secret(result.token))
        session.add(channel)
        await session.flush()
        if coexistence:
            channel.phone_registered_at = _now()
        elif pin:
            await MessagingService._register(session, channel, pin)
        if channel.phone_registered_at is None:
            await AuditService.record(session, event_type="messaging.channel.registration_required",
                                      actor_identity_id=actor_id, actor_context="business", action="signup",
                                      business_id=business_id, resource_type="messaging_channel",
                                      resource_id=channel.id, after_state=MessagingService.serialize_channel(channel))
            return channel
        return await MessagingService._connected(session, business_id, actor_id, channel)

    @staticmethod
    async def _register(session: AsyncSession, channel: MessagingChannel, pin: str) -> bool:
        if not re.fullmatch(r"\d{6}", pin or ""):
            raise _err("pin", "The two-step verification PIN is 6 digits")
        token = decrypt_secret(channel.encrypted_token) if channel.encrypted_token else None
        try:
            await provider_for(channel.provider).register_number(token, channel.phone_number_id, pin)
        except PlatformError as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            channel.registration_error = str(detail.get("message") or exc.code)[:500]
            await session.flush()
            return False
        channel.phone_registered_at, channel.registration_error = _now(), None
        await session.flush()
        return True

    @staticmethod
    async def register_number(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
                              pin: str) -> MessagingChannel:
        """Finish a sign-up whose number is not registered yet. The PIN goes to
        Meta only; it is never stored or logged."""
        channel = await MessagingService.channel(session, business_id)
        if channel is None or channel.status != "pending":
            raise ConflictError("There is no WhatsApp number waiting to be registered")
        if not await MessagingService._register(session, channel, pin):
            return channel
        return await MessagingService._connected(session, business_id, actor_id, channel)

    @staticmethod
    async def send_test(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
                        to: str) -> MessagingMessage:
        """A test message from the business's number to one the owner names
        (the staff-alert template, so it works outside any 24-hour window)."""
        business = await session.get(Business, business_id)
        return await MessagingService.send_template(
            session, business_id, to=to, key="staff_alert", audience="staff", sent_via="workspace", sent_by=actor_id,
            params=[business.display_name if business else "", "This is a test from LOCAH. WhatsApp messages "
                                                               "from your number are working."],
            idempotency_key=f"test:{business_id}:{_now().isoformat(timespec='seconds')}")

    @staticmethod
    async def disconnect(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        channel = await MessagingService.channel(session, business_id)
        if channel is None:
            raise ResourceNotFound("WhatsApp number")
        channel.status, channel.encrypted_token = "disconnected", None
        channel.updated_at, channel.version = _now(), channel.version + 1
        await session.flush()
        await AuditService.record(session, event_type="messaging.channel.disconnected", actor_identity_id=actor_id,
                                  actor_context="business", action="disconnect", business_id=business_id,
                                  resource_type="messaging_channel", resource_id=channel.id)

    @staticmethod
    async def submit_templates(session: AsyncSession, business_id: uuid.UUID,
                               keys: list[str] | None = None) -> list[dict[str, Any]]:
        """Submit library templates for approval (this phase's by default)."""
        channel = await MessagingService.channel(session, business_id)
        if channel is None or channel.status != "connected":
            raise ConflictError("Connect a WhatsApp number first")
        provider = provider_for(channel.provider)
        token = decrypt_secret(channel.encrypted_token) if channel.encrypted_token else None
        wanted = keys or [k for k, t in LIBRARY.items() if t.phase in ("P1", "P2")]
        out = []
        for key in wanted:
            if key not in LIBRARY:
                raise _err("keys", f"Unknown template {key}")
            for lang in LANGUAGES:
                row = await session.get(MessagingTemplate, (business_id, key, lang))
                if row is not None and row.status in ("approved", "submitted"):
                    continue
                status, provider_id, category = await provider.submit_template(token, channel.waba_id, key, lang)
                if row is None:
                    row = MessagingTemplate(business_id=business_id, template_key=key, language=lang)
                    session.add(row)
                row.status, row.provider_template_id, row.submitted_at = status, provider_id, _now()
                row.category = category
                row.decided_at = _now() if status in ("approved", "rejected") else None
                out.append({"key": key, "language": lang, "status": status})
        await session.flush()
        return out

    @staticmethod
    async def save_settings(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
                            payload: dict[str, Any]) -> MessagingSettings:
        s = await MessagingService.settings(session, business_id)
        if "language" in payload:
            if payload["language"] not in LANGUAGES:
                raise _err("language", "English, Tamil or Hindi")
            s.language = payload["language"]
        if "customer_updates" in payload:
            updates = dict(payload["customer_updates"] or {})
            unknown = set(updates) - set(CUSTOMER_UPDATES)
            if unknown:
                raise _err("customer_updates", f"Unknown update {sorted(unknown)[0]}")
            s.customer_updates = {**(s.customer_updates or {}), **{k: bool(v) for k, v in updates.items()}}
        if "human_pause_hours" in payload:
            hours = int(payload["human_pause_hours"])
            if not 1 <= hours <= 72:
                raise _err("human_pause_hours", "Between 1 and 72 hours")
            s.human_pause_hours = hours
        rules = {k: payload[k] for k in ("cod_allowed", "first_order_cod_cap") if k in payload}
        if rules:
            # Paying on delivery is an order rule for every channel; it lives with
            # pickup and delivery (fulfilment), this page only edits it there.
            from platform_core.services.fulfilment import FulfilmentService

            await FulfilmentService.set_payment_rules(session, business_id=business_id, actor_id=actor_id,
                                                      payload=rules)
        s.updated_by, s.updated_at, s.version = actor_id, _now(), s.version + 1
        await session.flush()
        return s

    @staticmethod
    async def save_my_alerts(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
                             permissions: frozenset[str], payload: dict[str, Any]) -> MessagingStaffAlert | None:
        """A team member turns their own WhatsApp alerts on or off."""
        row = await session.get(MessagingStaffAlert, (business_id, actor_id))
        if not payload.get("enabled"):
            if row is not None:
                row.enabled, row.updated_at = False, _now()
                await session.flush()
            return row
        phone = normalise_phone(payload.get("phone"))
        if phone is None:
            raise _err("phone", "Enter your WhatsApp number with its country code")
        kinds = [k for k in payload.get("kinds") or [] if k in STAFF_ALERTS]
        refused = [k for k in kinds if STAFF_ALERTS[k][1] not in permissions]
        if refused:
            raise _err("kinds", f"You cannot receive “{STAFF_ALERTS[refused[0]][0]}” in your role")
        if not kinds:
            raise _err("kinds", "Choose at least one alert")
        if row is None:
            row = MessagingStaffAlert(business_id=business_id, identity_id=actor_id, phone=phone, kinds=kinds)
            session.add(row)
        row.phone, row.kinds, row.enabled, row.updated_at = phone, kinds, True, _now()
        await session.flush()
        return row

    # ------------------------------------------------------------------ conversations
    @staticmethod
    async def find_contact(session: AsyncSession, business_id: uuid.UUID, wa_id: str) -> CustomerContact | None:
        """The customer with this WhatsApp number, however the phone was typed."""
        return (await session.execute(select(CustomerContact).where(
            CustomerContact.business_id == business_id, CustomerContact.deleted_at.is_(None),
            func.right(func.regexp_replace(CustomerContact.phone, r"\D", "", "g"), 10) == wa_id[-10:],
        ).order_by(CustomerContact.created_at))).scalars().first()

    @staticmethod
    async def conversation_for(session: AsyncSession, channel: MessagingChannel, wa_id: str, *,
                               contact: CustomerContact | None = None, name: str | None = None,
                               kind: str = "customer") -> MessagingConversation:
        stmt = pg_insert(MessagingConversation).values(
            id=uuid.uuid4(), business_id=channel.business_id, channel_id=channel.id, wa_id=wa_id, kind=kind,
            contact_id=contact.id if contact else None, profile_name=(name or None) and str(name)[:120],
        ).on_conflict_do_nothing(constraint="messaging_conversations_one_per_number")
        await session.execute(stmt)
        conv = (await session.execute(select(MessagingConversation).where(
            MessagingConversation.channel_id == channel.id, MessagingConversation.wa_id == wa_id,
        ).execution_options(populate_existing=True))).scalars().one()
        if contact is not None and conv.contact_id is None:
            conv.contact_id = contact.id
        if name and not conv.profile_name:
            conv.profile_name = str(name)[:120]
        return conv

    @staticmethod
    def window_open(conv: MessagingConversation, now: datetime | None = None) -> bool:
        return conv.last_inbound_at is not None and (now or _now()) - conv.last_inbound_at < WINDOW

    @staticmethod
    async def bot_may_reply(session: AsyncSession, conv: MessagingConversation, now: datetime | None = None) -> bool:
        """LOCAH's own automatic replies stay out of a chat a person answered
        within the owner's pause (§12.1, §12.6)."""
        if conv.last_human_at is None:
            return True
        s = await MessagingService.settings(session, conv.business_id)
        return bool((now or _now()) - conv.last_human_at >= timedelta(hours=s.human_pause_hours))

    # ------------------------------------------------------------------ sending
    @staticmethod
    async def _meter(session: AsyncSession, business_id: uuid.UUID, key: str, category: str | None) -> None:
        from platform_core.services.usage_meter import UsageMeterService

        await UsageMeterService.record(session, business_id, "whatsapp_message", 1, idempotency_key=f"wa:{key}",
                                       context={"category": category or "service"})

    @staticmethod
    async def _deliver(session: AsyncSession, channel: MessagingChannel, conv: MessagingConversation,
                       msg: MessagingMessage, send: Any) -> MessagingMessage:
        """Check the meter, hand the message to the provider, record what happened."""
        from platform_core.services.usage_meter import CapReached, UsageMeterService

        try:
            await UsageMeterService.check(session, channel.business_id, "whatsapp_message", 1)
        except CapReached as exc:
            msg.status, msg.error = "blocked", str(exc)
            await session.flush()
            return msg
        try:
            sent = await send(provider_for(channel.provider),
                              decrypt_secret(channel.encrypted_token) if channel.encrypted_token else None)
        except PlatformError as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            msg.status, msg.error = "failed", str(detail.get("message") or exc.code)[:500]
            channel.last_error = msg.error
            await session.flush()
            return msg
        msg.status, msg.provider_message_id, msg.status_at = "sent", sent.provider_message_id, _now()
        if channel.last_error:
            channel.last_error = None  # a send went through: the number is working again
        conv.last_outbound_at = _now()
        conv.last_preview = _preview(msg.body)
        conv.updated_at = _now()
        await session.flush()
        await MessagingService._meter(session, channel.business_id, str(msg.id), msg.category)
        return msg

    @staticmethod
    async def send_template(
        session: AsyncSession, business_id: uuid.UUID, *, to: str, key: str, params: list[str],
        contact_id: uuid.UUID | None = None, idempotency_key: str | None = None, sent_via: str = "automation",
        sent_by: uuid.UUID | None = None, audience: str = "customer",
    ) -> MessagingMessage:
        """Send one library template. Raises NotSent (owner words) when LOCAH may not."""
        from platform_core.services.consent import ConsentService

        template = LIBRARY[key]
        channel = await MessagingService.channel(session, business_id)
        if channel is None or channel.status != "connected":
            raise NotSent("WhatsApp is not connected")
        wa_id = normalise_phone(to)
        if wa_id is None:
            raise NotSent("No WhatsApp number for this person")
        if idempotency_key:
            prior = (await session.execute(select(MessagingMessage).where(
                MessagingMessage.business_id == business_id, MessagingMessage.idempotency_key == idempotency_key,
            ))).scalars().first()
            if prior is not None:
                return prior
        s = await MessagingService.settings(session, business_id)
        approved = {r.language: r.category for r in (await session.execute(select(MessagingTemplate).where(
            MessagingTemplate.business_id == business_id, MessagingTemplate.template_key == key,
            MessagingTemplate.status == "approved"))).scalars()}
        contact = await session.get(CustomerContact, contact_id) if contact_id else None
        if contact is None and audience == "customer":
            contact = await MessagingService.find_contact(session, business_id, wa_id)
        # The customer's own language when that version is approved (P1-10E6), else the business's, else English.
        wanted = contact.language if contact is not None and audience == "customer" else None
        language = next((x for x in (wanted, s.language, "en") if x and x in approved), None)
        if language is None:
            raise NotSent(f"The “{template.label}” message is not approved by WhatsApp yet")
        # What Meta decided at approval wins over what LOCAH asked for.
        category = approved.get(language) or template.category
        conv = await MessagingService.conversation_for(session, channel, wa_id, contact=contact,
                                                       kind="staff" if audience == "staff" else "customer")
        msg = MessagingMessage(
            business_id=business_id, conversation_id=conv.id, direction="out", kind="template",
            body=render(key, language, params), payload={"params": params}, template_key=key, language=language,
            category=category, status="queued", idempotency_key=idempotency_key, sent_via=sent_via,
            sent_by=sent_by)
        session.add(msg)
        # §12.4: marketing needs an explicit, open opt-in on WhatsApp.
        if category == "marketing" and (contact is None or not await ConsentService.has(
                session, business_id, contact.id, purpose="marketing", channel="whatsapp")):
            msg.status, msg.error = "blocked", "No marketing opt-in on WhatsApp"
            await session.flush()
            return msg
        await session.flush()
        return await MessagingService._deliver(
            session, channel, conv, msg,
            lambda p, token: p.send_template(token, channel.phone_number_id, wa_id, key, language, params))

    @staticmethod
    async def reply(session: AsyncSession, business_id: uuid.UUID, conversation_id: uuid.UUID, actor_id: uuid.UUID,
                    body: str) -> MessagingMessage:
        """A person replies from the inbox (inside the 24-hour window only)."""
        body = (body or "").strip()
        if not body:
            raise _err("body", "Write a reply")
        if len(body) > 4096:
            raise _err("body", "Keep it under 4,096 characters")
        conv = await MessagingService.get(session, business_id, conversation_id, lock=True)
        if not MessagingService.window_open(conv):
            raise ConflictError("WhatsApp lets a business write freely only within 24 hours of the customer's last "
                                "message. Send a bill or statement from its page, or wait for them to write.")
        channel = await session.get(MessagingChannel, conv.channel_id)
        if channel is None or channel.status != "connected":
            raise ConflictError("WhatsApp is not connected")
        now = _now()
        conv.last_human_at, conv.handler, conv.needs_person, conv.waiting_since, conv.unread = \
            now, "person", False, None, 0
        if conv.assigned_to is None:
            conv.assigned_to = actor_id
        msg = MessagingMessage(business_id=business_id, conversation_id=conv.id, direction="out", kind="text",
                               body=body, category="service", status="queued", sent_via="workspace", sent_by=actor_id)
        session.add(msg)
        await session.flush()
        wa_id = conv.wa_id
        return await MessagingService._deliver(
            session, channel, conv, msg, lambda p, token: p.send_text(token, channel.phone_number_id, wa_id, body))

    @staticmethod
    async def bot_text(session: AsyncSession, conv: MessagingConversation, body: str, *,
                       via: str = "journey") -> MessagingMessage | None:
        """LOCAH's own reply in a chat — only inside the window and never while a person is handling it."""
        if not MessagingService.window_open(conv) or not await MessagingService.bot_may_reply(session, conv):
            return None
        channel = await session.get(MessagingChannel, conv.channel_id)
        if channel is None or channel.status != "connected":
            return None
        msg = MessagingMessage(business_id=conv.business_id, conversation_id=conv.id, direction="out", kind="text",
                               body=body, category="service", status="queued", sent_via=via)
        session.add(msg)
        await session.flush()
        wa_id = conv.wa_id
        return await MessagingService._deliver(
            session, channel, conv, msg, lambda p, token: p.send_text(token, channel.phone_number_id, wa_id, body))

    @staticmethod
    async def bot_interactive(session: AsyncSession, conv: MessagingConversation, interactive: dict[str, Any], *,
                              via: str = "journey") -> MessagingMessage | None:
        """Buttons or a list from LOCAH (§12.3 structured journeys) — the same
        rules as bot_text: inside the window, never over a person."""
        if not MessagingService.window_open(conv) or not await MessagingService.bot_may_reply(session, conv):
            return None
        channel = await session.get(MessagingChannel, conv.channel_id)
        if channel is None or channel.status != "connected":
            return None
        body = str((interactive.get("body") or {}).get("text") or "")
        action = interactive.get("action") or {}
        # What the customer can tap, kept with the reply ids for the inbox.
        options = [{"id": b["reply"]["id"], "title": b["reply"]["title"]} for b in action.get("buttons") or []] or \
            [{"id": r["id"], "title": r["title"], **({"description": r["description"]} if r.get("description") else {})}
             for sec in action.get("sections") or [] for r in sec.get("rows") or []]
        msg = MessagingMessage(business_id=conv.business_id, conversation_id=conv.id, direction="out",
                               kind="interactive", body=body[:4096], payload={"interactive": interactive,
                                                                              "options": options,
                                                                              "reply_kind": interactive.get("type")},
                               category="service", status="queued", sent_via=via)
        session.add(msg)
        await session.flush()
        wa_id = conv.wa_id
        return await MessagingService._deliver(
            session, channel, conv, msg,
            lambda p, token: p.send_interactive(token, channel.phone_number_id, wa_id, interactive))

    # ------------------------------------------------------------------ webhooks
    @staticmethod
    async def process_webhook(session: AsyncSession, payload: dict[str, Any]) -> dict[str, int]:
        """A delivery from WhatsApp (Cloud API webhook format): messages,
        status updates, and coexistence echoes of the owner's app replies."""
        counts = {"messages": 0, "duplicates": 0, "statuses": 0, "echoes": 0, "unknown_number": 0, "calls": 0,
                  "templates": 0, "account": 0}
        for entry in payload.get("entry") or []:
            for change in entry.get("changes") or []:
                value = change.get("value") or {}
                field = str(change.get("field") or "")
                if field in ("message_template_status_update", "phone_number_quality_update"):
                    counts["templates" if field.startswith("message") else "account"] += \
                        await MessagingService._account_event(session, str(entry.get("id") or ""), field, value)
                    continue
                phone_number_id = str((value.get("metadata") or {}).get("phone_number_id") or "")
                channel = await MessagingService._bind(session, phone_number_id)
                if channel is None:
                    counts["unknown_number"] += 1
                    continue
                channel.last_webhook_at = _now()
                names = {str(c.get("wa_id")): (c.get("profile") or {}).get("name") for c in value.get("contacts") or []}
                for m in value.get("messages") or []:
                    added = await MessagingService._inbound(session, channel, m, names.get(str(m.get("from"))))
                    counts["messages" if added else "duplicates"] += 1
                for st in value.get("statuses") or []:
                    counts["statuses"] += await MessagingService._status(session, channel, st)
                for echo in value.get("message_echoes") or []:
                    counts["echoes"] += await MessagingService._echo(session, channel, echo)
                if value.get("calls"):
                    from platform_core.calling.service import CallService

                    for call in value.get("calls") or []:
                        counts["calls"] += await CallService.ingest_whatsapp(session, channel, call, names)
                await session.execute(text("SELECT set_config('app.current_business_id', '', true)"))
        return counts

    @staticmethod
    async def _bind(session: AsyncSession, phone_number_id: str) -> MessagingChannel | None:
        if not phone_number_id:
            return None
        await session.execute(text("SELECT set_config('app.current_wa_phone_number_id', :p, true)"),
                              {"p": phone_number_id})
        channel = (await session.execute(select(MessagingChannel).where(
            MessagingChannel.phone_number_id == phone_number_id, MessagingChannel.status == "connected",
        ))).scalars().first()
        await session.execute(text("SELECT set_config('app.current_wa_phone_number_id', '', true)"))
        if channel is None:
            return None
        await session.execute(text("SELECT set_config('app.current_business_id', :b, true)"),
                              {"b": str(channel.business_id)})
        return channel

    # Meta's template events -> LOCAH's template states (the column allows these four).
    _TEMPLATE_EVENTS = {"APPROVED": "approved", "REINSTATED": "approved", "UNARCHIVED": "approved",
                        "REJECTED": "rejected", "PAUSED": "paused", "DISABLED": "paused", "ARCHIVED": "paused",
                        "DELETED": "paused", "PENDING_DELETION": "paused", "PENDING": "submitted",
                        "IN_APPEAL": "submitted"}

    @staticmethod
    async def _account_event(session: AsyncSession, waba_id: str, field: str, value: dict[str, Any]) -> int:
        """WABA-level webhooks: a template's review result, a number's quality or limit."""
        if not waba_id:
            return 0
        await session.execute(text("SELECT set_config('app.current_waba_id', :w, true)"), {"w": waba_id})
        channels = list((await session.execute(select(MessagingChannel).where(
            MessagingChannel.waba_id == waba_id, MessagingChannel.status == "connected"))).scalars())
        await session.execute(text("SELECT set_config('app.current_waba_id', '', true)"))
        done = 0
        for channel in channels:
            await session.execute(text("SELECT set_config('app.current_business_id', :b, true)"),
                                  {"b": str(channel.business_id)})
            channel.last_webhook_at = _now()
            if field == "message_template_status_update":
                key = str(value.get("message_template_name") or "")
                lang = str(value.get("message_template_language") or "").split("_")[0].split("-")[0]
                status = MessagingService._TEMPLATE_EVENTS.get(str(value.get("event") or "").upper())
                row = await session.get(MessagingTemplate, (channel.business_id, key, lang)) if status else None
                if row is not None:
                    row.status, row.decided_at = status, _now()
                    category = str(value.get("message_template_category") or "").lower()
                    if category in ("utility", "marketing", "authentication"):
                        row.category = category
                    reason = str(value.get("reason") or "")
                    row.rejected_reason = reason[:300] if status == "rejected" and reason not in ("", "NONE") else None
                    done += 1
            else:  # phone_number_quality_update
                if value.get("display_phone_number") and normalise_phone(value["display_phone_number"]) != \
                        normalise_phone(channel.display_phone or ""):
                    continue
                event = str(value.get("event") or "").upper()
                if event in ("FLAGGED", "UNFLAGGED"):
                    channel.quality_rating = "FLAGGED" if event == "FLAGGED" else "GREEN"
                if value.get("current_limit"):
                    channel.messaging_limit = str(value["current_limit"])[:40]
                done += 1
            await session.flush()
            await session.execute(text("SELECT set_config('app.current_business_id', '', true)"))
        return done

    @staticmethod
    def _content(m: dict[str, Any]) -> tuple[str, str | None, dict[str, Any]]:
        kind = str(m.get("type") or "unsupported")
        if kind == "text":
            return "text", str((m.get("text") or {}).get("body") or ""), {}
        if kind == "interactive":
            inter = m.get("interactive") or {}
            reply = inter.get("button_reply") or inter.get("list_reply") or {}
            k = "button" if "button_reply" in inter else "list"
            return k, str(reply.get("title") or ""), {"id": reply.get("id"), "title": reply.get("title")}
        if kind == "button":  # a template's quick-reply button
            b = m.get("button") or {}
            return "button", str(b.get("text") or ""), {"id": b.get("payload"), "title": b.get("text")}
        if kind == "location":
            loc = m.get("location") or {}
            label = ", ".join(str(x) for x in (loc.get("name"), loc.get("address")) if x) or "Shared a location"
            return "location", label, {k: loc.get(k) for k in ("latitude", "longitude", "name", "address")}
        if kind in ("image", "audio", "video", "document", "sticker"):
            media = m.get(kind) or {}
            return "media", str(media.get("caption") or f"Sent a {kind}"), {"media_type": kind, "id": media.get("id")}
        if kind == "reaction":
            return "reaction", str((m.get("reaction") or {}).get("emoji") or ""), {}
        return "unsupported", "Sent something LOCAH cannot show yet", {"type": kind}

    @staticmethod
    async def _inbound(session: AsyncSession, channel: MessagingChannel, m: dict[str, Any],
                       profile_name: str | None) -> bool:
        wa_id = normalise_phone(m.get("from"))
        message_id = str(m.get("id") or "")
        if wa_id is None or not message_id:
            return False
        contact = await MessagingService.find_contact(session, channel.business_id, wa_id)
        if contact is None:
            contact = CustomerContact(business_id=channel.business_id,
                                      display_name=(profile_name or f"+{wa_id}")[:120], phone=f"+{wa_id}")
            session.add(contact)
            await session.flush()
        conv = await MessagingService.conversation_for(session, channel, wa_id, contact=contact, name=profile_name)
        kind, body, extra = MessagingService._content(m)
        when = datetime.fromtimestamp(int(m.get("timestamp") or 0), timezone.utc) if m.get("timestamp") else _now()
        recent = _now() - when < timedelta(seconds=2)
        inserted = (await session.execute(pg_insert(MessagingMessage).values(
            id=uuid.uuid4(), business_id=channel.business_id, conversation_id=conv.id, direction="in", kind=kind,
            body=body[:4096] if body else None, payload={"raw_type": m.get("type"), **extra}, status="received",
            # WhatsApp stamps to the second: a reply sent just now takes the
            # clock time, so it stays after the message of LOCAH's it answers.
            provider_message_id=message_id, created_at=func.clock_timestamp() if recent else when,
        ).on_conflict_do_nothing(index_elements=["business_id", "provider_message_id"],
                                 index_where=text("provider_message_id IS NOT NULL")).returning(
            MessagingMessage.id))).first()
        if inserted is None:
            return False  # the same delivery again (§12.6: duplicates create nothing)
        conv.last_inbound_at = max(conv.last_inbound_at or when, when)
        conv.unread += 1
        conv.state = "open"
        conv.last_preview = _preview(body)
        conv.updated_at = _now()
        contact.last_interaction_at = _now()
        await session.flush()
        inter = m.get("interactive") or {}
        if m.get("type") == "interactive" and inter.get("type") == "call_permission_reply":
            from platform_core.calling.service import CallService

            # The customer's answer to "may we call you?" - recorded, not routed to a journey.
            await CallService.permission_reply(session, channel.business_id, wa_id, contact.id,
                                               inter.get("call_permission_reply") or {})
            return True
        await MessagingService.route(session, conv, kind, body or "", extra)
        return True

    @staticmethod
    async def route(session: AsyncSession, conv: MessagingConversation, kind: str, body: str,
                    extra: dict[str, Any]) -> str:
        """§12.1 router, cheapest branch first: STOP → opt-out; 'talk to a person' →
        the inbox; a button or menu word → the structured journey (P1-08); free
        text → the AI WhatsApp Manager (P3, not built) — so, for now, a person."""
        from platform_core.messaging.journeys import language_for
        from platform_core.messaging.words import detect, tr
        from platform_core.services.consent import ConsentService

        async def lang() -> str:
            """The language they wrote in, else the one they chose or the business's (P1-10E6)."""
            contact = await session.get(CustomerContact, conv.contact_id) if conv.contact_id else None
            if contact is not None and contact.language_source == "chosen":
                return str(contact.language)
            found: str = detect(body) or await language_for(session, conv.business_id, contact)
            return found

        said = body.strip().lower()
        if said in STOP_WORDS and conv.contact_id:
            await ConsentService.withdraw(session, conv.business_id, conv.contact_id, purpose="marketing",
                                          channel="whatsapp", source="whatsapp_stop")
            await MessagingService.bot_text(session, conv, tr(await lang(), "You will not get offers from us on "
                                                              "WhatsApp any more. Order and booking updates still "
                                                              "come here."), via="journey")
            return "opted_out"
        wants_person = extra.get("id") == "talk_to_person" or any(w in said for w in PERSON_WORDS)
        if not wants_person:
            from platform_core.messaging import journeys

            if await journeys.handle(session, conv, kind, body, extra):
                return "journey"
        first_wait = conv.waiting_since is None
        conv.needs_person, conv.handler = True, "person"
        conv.waiting_since = conv.waiting_since or _now()
        await session.flush()
        if first_wait:
            from platform_core.messaging.entry import whatsapp_entry

            business = await session.get(Business, conv.business_id)
            words = await lang()
            menu = " " + tr(words, "Or send menu to see what you can do here.") if not wants_person and \
                await whatsapp_entry(session, conv.business_id) else ""
            await MessagingService.bot_text(
                session, conv, tr(words, "Thanks — someone from {business} will reply here soon.",
                                  business=business.display_name if business else "us") + menu, via="journey")
            await MessagingService._schedule_waiting(session, conv)
        return "person"

    @staticmethod
    async def _schedule_waiting(session: AsyncSession, conv: MessagingConversation) -> None:
        from platform_core.automation import AutomationEngine

        now = _now()
        await AutomationEngine.schedule(session, conv.business_id, ladder_key="chat.waiting", entity_id=conv.id,
                                        anchor=now, period_key=now.isoformat(timespec="seconds"), context={}, now=now)

    @staticmethod
    async def _status(session: AsyncSession, channel: MessagingChannel, st: dict[str, Any]) -> int:
        order = {"queued": 0, "sent": 1, "delivered": 2, "read": 3, "failed": 4}
        msg = (await session.execute(select(MessagingMessage).where(
            MessagingMessage.business_id == channel.business_id,
            MessagingMessage.provider_message_id == str(st.get("id") or "")))).scalars().first()
        new = str(st.get("status") or "")
        if msg is None or new not in order:
            return 0
        if new == "failed":
            errors = st.get("errors") or [{}]
            msg.status, msg.error = "failed", str(errors[0].get("title") or errors[0].get("message") or "Failed")[:500]
        elif order.get(msg.status, 0) < order[new]:
            msg.status = new
        msg.status_at = _now()
        await session.flush()
        return 1

    @staticmethod
    async def _echo(session: AsyncSession, channel: MessagingChannel, echo: dict[str, Any]) -> int:
        """Coexistence: the owner replied from the WhatsApp Business app."""
        wa_id = normalise_phone(echo.get("to"))
        message_id = str(echo.get("id") or "")
        if wa_id is None or not message_id:
            return 0
        conv = await MessagingService.conversation_for(session, channel, wa_id)
        kind, body, extra = MessagingService._content(echo)
        inserted = (await session.execute(pg_insert(MessagingMessage).values(
            id=uuid.uuid4(), business_id=channel.business_id, conversation_id=conv.id, direction="out", kind=kind,
            body=body[:4096] if body else None, payload=extra, status="sent", category="service",
            provider_message_id=message_id, sent_via="business_app",
        ).on_conflict_do_nothing(index_elements=["business_id", "provider_message_id"],
                                 index_where=text("provider_message_id IS NOT NULL")).returning(
            MessagingMessage.id))).first()
        if inserted is None:
            return 0
        now = _now()
        conv.last_human_at, conv.last_outbound_at, conv.handler = now, now, "person"
        conv.needs_person, conv.waiting_since, conv.last_preview = False, None, _preview(body)
        await session.flush()
        return 1

    # ------------------------------------------------------------------ inbox
    @staticmethod
    async def get(session: AsyncSession, business_id: uuid.UUID, conversation_id: uuid.UUID, *,
                  lock: bool = False) -> MessagingConversation:
        q = select(MessagingConversation).where(MessagingConversation.business_id == business_id,
                                                MessagingConversation.id == conversation_id,
                                                MessagingConversation.kind == "customer")
        if lock:
            q = q.with_for_update().execution_options(populate_existing=True)
        conv = (await session.execute(q)).scalars().first()
        if conv is None:
            raise ResourceNotFound("Conversation")
        return conv

    @staticmethod
    async def serialize_conversation(session: AsyncSession, c: MessagingConversation,
                                     names: dict[uuid.UUID, str] | None = None) -> dict[str, Any]:
        now = _now()
        paused_until = None
        if c.last_human_at is not None:
            s = await MessagingService.settings(session, c.business_id)
            until = c.last_human_at + timedelta(hours=s.human_pause_hours)
            paused_until = until.isoformat() if until > now else None
        return {
            "id": str(c.id), "wa_id": c.wa_id, "phone": f"+{c.wa_id}", "name": c.profile_name or f"+{c.wa_id}",
            "contact_id": str(c.contact_id) if c.contact_id else None, "state": c.state, "handler": c.handler,
            "needs_person": c.needs_person, "topic": c.topic,
            "assigned_to": str(c.assigned_to) if c.assigned_to else None,
            "assigned_name": (names or {}).get(c.assigned_to) if c.assigned_to else None,
            "unread": c.unread, "last_preview": c.last_preview,
            "waiting_since": c.waiting_since.isoformat() if c.waiting_since else None,
            "waiting_minutes": int((now - c.waiting_since).total_seconds() // 60) if c.waiting_since else None,
            "window_open": MessagingService.window_open(c, now),
            "window_closes_at": (c.last_inbound_at + WINDOW).isoformat() if c.last_inbound_at else None,
            "bot_paused_until": paused_until,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }

    @staticmethod
    async def _names(session: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not ids:
            return {}
        return {r[0]: r[1] or r[2] or "Team member" for r in (await session.execute(select(
            PlatformIdentity.id, PlatformIdentity.display_name, PlatformIdentity.email).where(
            PlatformIdentity.id.in_(ids)))).all()}

    @staticmethod
    async def list_conversations(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, *,
                                 view: str = "open", q: str | None = None) -> dict[str, Any]:
        base = select(MessagingConversation).where(MessagingConversation.business_id == business_id,
                                                   MessagingConversation.kind == "customer")
        if view == "waiting":
            base = base.where(MessagingConversation.needs_person.is_(True), MessagingConversation.state == "open")
        elif view == "mine":
            base = base.where(MessagingConversation.assigned_to == actor_id, MessagingConversation.state == "open")
        elif view == "closed":
            base = base.where(MessagingConversation.state == "closed")
        elif view in ("order", "booking", "lead", "payment"):
            base = base.where(MessagingConversation.topic == view)
        else:
            base = base.where(MessagingConversation.state == "open")
        if q:
            like = f"%{q.strip()}%"
            base = base.where(MessagingConversation.profile_name.ilike(like)
                              | MessagingConversation.wa_id.ilike(f"%{re.sub(r'[^0-9]', '', q) or q}%"))
        rows = list((await session.execute(base.order_by(MessagingConversation.needs_person.desc(),
                                                         MessagingConversation.updated_at.desc()).limit(200))).scalars())
        names = await MessagingService._names(session, {r.assigned_to for r in rows if r.assigned_to})
        row = (await session.execute(select(
            func.count().filter(MessagingConversation.needs_person.is_(True) & (MessagingConversation.state == "open")),
            func.count().filter((MessagingConversation.assigned_to == actor_id) & (MessagingConversation.state == "open")),
            func.count().filter(MessagingConversation.state == "open"),
        ).where(MessagingConversation.business_id == business_id, MessagingConversation.kind == "customer"))).one()
        return {"conversations": [await MessagingService.serialize_conversation(session, r, names) for r in rows],
                "counts": {"waiting": int(row[0]), "mine": int(row[1]), "open": int(row[2])}}

    @staticmethod
    async def thread(session: AsyncSession, business_id: uuid.UUID, conversation_id: uuid.UUID,
                     permissions: frozenset[str]) -> dict[str, Any]:
        """The chat and, beside it, what the business knows about this customer (§12.5)."""
        conv = await MessagingService.get(session, business_id, conversation_id)
        msgs = list((await session.execute(select(MessagingMessage).where(
            MessagingMessage.conversation_id == conv.id).order_by(MessagingMessage.created_at.desc()).limit(200)
        )).scalars())
        names = await MessagingService._names(session, {m.sent_by for m in msgs if m.sent_by}
                                              | ({conv.assigned_to} if conv.assigned_to else set()))
        side: dict[str, Any] = {}
        if conv.contact_id:
            side = await MessagingService._side_panel(session, business_id, conv.contact_id, permissions)
        return {
            **await MessagingService.serialize_conversation(session, conv, names),
            "messages": [{"id": str(m.id), "direction": m.direction, "kind": m.kind, "body": m.body,
                          "status": m.status, "error": m.error, "template_key": m.template_key,
                          "category": m.category, "sent_via": m.sent_via,
                          "sent_by_name": names.get(m.sent_by) if m.sent_by else None,
                          "payload": {k: v for k, v in (m.payload or {}).items() if k in ("latitude", "longitude",
                                                                                          "media_type", "title",
                                                                                          "options", "reply_kind")},
                          "at": m.created_at.isoformat() if m.created_at else None} for m in reversed(msgs)],
            "customer": side,
        }

    @staticmethod
    async def _side_panel(session: AsyncSession, business_id: uuid.UUID, contact_id: uuid.UUID,
                          permissions: frozenset[str]) -> dict[str, Any]:
        contact = await session.get(CustomerContact, contact_id)
        out: dict[str, Any] = {"contact_id": str(contact_id),
                               "name": contact.display_name if contact else None,
                               "phone": contact.phone if contact else None}
        if "orders.read" in permissions:
            rows = (await session.execute(text(
                "SELECT id, order_number, status, total_amount, created_at FROM orders_orders "
                "WHERE business_id = :b AND customer_contact_id = :c AND deleted_at IS NULL "
                "ORDER BY created_at DESC LIMIT 5"), {"b": str(business_id), "c": str(contact_id)})).all()
            out["orders"] = [{"id": str(r[0]), "number": r[1], "status": r[2], "total": float(r[3]),
                              "at": r[4].isoformat()} for r in rows]
        if "bookings.read" in permissions:
            rows = (await session.execute(text(
                "SELECT id, booking_number, status, title, starts_at FROM bookings_bookings "
                "WHERE business_id = :b AND customer_contact_id = :c AND deleted_at IS NULL "
                "ORDER BY starts_at DESC LIMIT 5"), {"b": str(business_id), "c": str(contact_id)})).all()
            out["bookings"] = [{"id": str(r[0]), "number": r[1], "status": r[2], "title": r[3],
                                "at": r[4].isoformat()} for r in rows]
        if "ledger.read" in permissions:
            row = (await session.execute(text(
                "SELECT id, balance, credit_limit FROM ledger_accounts WHERE business_id = :b "
                "AND customer_contact_id = :c"), {"b": str(business_id), "c": str(contact_id)})).first()
            out["khata"] = {"account_id": str(row[0]), "balance": float(row[1]),
                            "credit_limit": float(row[2]) if row[2] is not None else None} if row else None
        if "memberships.read" in permissions:
            rows = (await session.execute(text(
                "SELECT e.status, p.name, e.ends_at FROM memberships_enrolments e "
                "JOIN memberships_plans p ON p.id = e.plan_id WHERE e.business_id = :b AND e.customer_contact_id = :c "
                "AND e.deleted_at IS NULL ORDER BY e.ends_at DESC NULLS LAST LIMIT 1"),
                {"b": str(business_id), "c": str(contact_id)})).all() if await _table(session, "memberships_enrolments") \
                else []
            out["membership"] = {"status": rows[0][0], "plan": rows[0][1],
                                 "ends_at": rows[0][2].isoformat() if rows[0][2] else None} if rows else None
        return out

    @staticmethod
    async def assign(session: AsyncSession, business_id: uuid.UUID, conversation_id: uuid.UUID,
                     actor_id: uuid.UUID, assignee: uuid.UUID | None) -> MessagingConversation:
        from platform_core.authorization.resolver import AuthorizationService

        conv = await MessagingService.get(session, business_id, conversation_id, lock=True)
        if assignee is not None:
            try:
                perms = await AuthorizationService.effective_permissions(session, business_id=business_id,
                                                                         identity_id=assignee)
            except PlatformError:
                perms = frozenset()  # not a member of this business
            if "messaging.reply" not in perms:
                raise _err("assigned_to", "Hand chats only to someone who can reply on WhatsApp")
        conv.assigned_to, conv.updated_at, conv.version = assignee, _now(), conv.version + 1
        await session.flush()
        await AuditService.record(session, event_type="messaging.conversation.assigned", actor_identity_id=actor_id,
                                  actor_context="business", action="assign", business_id=business_id,
                                  resource_type="messaging_conversation", resource_id=conv.id,
                                  after_state={"assigned_to": str(assignee) if assignee else None})
        return conv

    @staticmethod
    async def set_state(session: AsyncSession, business_id: uuid.UUID, conversation_id: uuid.UUID,
                        payload: dict[str, Any]) -> MessagingConversation:
        conv = await MessagingService.get(session, business_id, conversation_id, lock=True)
        if payload.get("state") in ("open", "closed"):
            conv.state = payload["state"]
            if conv.state == "closed":
                conv.needs_person, conv.waiting_since = False, None
        if payload.get("handler") == "bot":
            # Hand back to LOCAH's structured replies straight away.
            conv.handler, conv.needs_person, conv.waiting_since, conv.last_human_at = "bot", False, None, None
        if payload.get("topic") in ("order", "booking", "lead", "payment", "support", None) and "topic" in payload:
            conv.topic = payload["topic"]
        conv.updated_at, conv.version = _now(), conv.version + 1
        await session.flush()
        return conv

    @staticmethod
    async def mark_read(session: AsyncSession, business_id: uuid.UUID, conversation_id: uuid.UUID) -> None:
        conv = await MessagingService.get(session, business_id, conversation_id, lock=True)
        conv.unread = 0
        await session.flush()

    @staticmethod
    async def waiting_long(session: AsyncSession, business_id: uuid.UUID) -> int:
        """Chats waiting for a person more than 10 minutes (§12.5 → Needs you now)."""
        return int((await session.execute(select(func.count()).select_from(MessagingConversation).where(
            MessagingConversation.business_id == business_id, MessagingConversation.kind == "customer",
            MessagingConversation.state == "open", MessagingConversation.needs_person.is_(True),
            MessagingConversation.waiting_since < _now() - WAITING_ALERT))).scalar_one())

    # ------------------------------------------------------------------ quick replies
    @staticmethod
    async def quick_replies(session: AsyncSession, business_id: uuid.UUID) -> list[dict[str, Any]]:
        return [{"id": str(r.id), "title": r.title, "body": r.body} for r in (await session.execute(
            select(MessagingQuickReply).where(MessagingQuickReply.business_id == business_id)
            .order_by(MessagingQuickReply.title))).scalars()]

    @staticmethod
    async def add_quick_reply(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, title: str,
                              body: str) -> MessagingQuickReply:
        title, body = (title or "").strip(), (body or "").strip()
        if not title or not body:
            raise _err("title", "Give the quick reply a name and its text")
        row = MessagingQuickReply(business_id=business_id, title=title[:60], body=body[:1000], created_by=actor_id)
        session.add(row)
        await session.flush()
        return row

    @staticmethod
    async def remove_quick_reply(session: AsyncSession, business_id: uuid.UUID, reply_id: uuid.UUID) -> None:
        row = await session.get(MessagingQuickReply, reply_id)
        if row is None or row.business_id != business_id:
            raise ResourceNotFound("Quick reply")
        await session.delete(row)
        await session.flush()

    # ------------------------------------------------------------------ staff alerts
    @staticmethod
    async def automated_messages(session: AsyncSession, business_id: uuid.UUID,
                                 limit: int = 30) -> list[dict[str, Any]]:
        """What LOCAH sent on its own, with WhatsApp's real delivery state
        (queued → sent → delivered → read, or failed / held back) and whether it
        went from a test number. The number is shown only by its last digits."""
        rows = (await session.execute(
            select(MessagingMessage, MessagingConversation.wa_id, MessagingChannel.provider)
            .join(MessagingConversation, MessagingConversation.id == MessagingMessage.conversation_id)
            .join(MessagingChannel, MessagingChannel.id == MessagingConversation.channel_id)
            .where(MessagingMessage.business_id == business_id, MessagingMessage.direction == "out",
                   MessagingMessage.sent_via == "automation")
            .order_by(MessagingMessage.created_at.desc()).limit(limit))).all()
        words = {"queued": "Queued", "sent": "Sent", "delivered": "Delivered", "read": "Read",
                 "failed": "Failed", "blocked": "Held back"}
        return [{
            "id": str(m.id), "what": LIBRARY[m.template_key].label if m.template_key in LIBRARY else (m.template_key or
                                                                                                      "Message"),
            "to": f"…{str(wa_id)[-4:]}", "status": m.status, "status_label": words.get(m.status, m.status),
            "error": m.error, "category": m.category, "test_number": provider == "sandbox",
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "status_at": m.status_at.isoformat() if m.status_at else None,
        } for m, wa_id, provider in rows]

    @staticmethod
    async def alert_staff(session: AsyncSession, business_id: uuid.UUID, kind: str, what: str, *,
                          key: str) -> int:
        """WhatsApp alerts to team members who asked for this kind (§26.3 P1-07:
        the owner receives order notifications)."""
        from platform_core.authorization.resolver import AuthorizationService

        if kind not in STAFF_ALERTS:
            return 0
        rows = list((await session.execute(select(MessagingStaffAlert).where(
            MessagingStaffAlert.business_id == business_id, MessagingStaffAlert.enabled.is_(True),
            MessagingStaffAlert.kinds.any(kind)))).scalars())
        if not rows:
            return 0
        business = await session.get(Business, business_id)
        sent = 0
        for row in rows:
            perms = await AuthorizationService.effective_permissions(session, business_id=business_id,
                                                                     identity_id=row.identity_id)
            if STAFF_ALERTS[kind][1] not in perms:
                continue  # their role changed since they switched it on
            try:
                msg = await MessagingService.send_template(
                    session, business_id, to=row.phone, key="staff_alert", audience="staff",
                    params=[business.display_name if business else "", what[:200]],
                    idempotency_key=f"alert:{kind}:{key}:{row.identity_id}")
            except NotSent:
                continue
            sent += int(msg.status == "sent")
        return sent


async def _table(session: AsyncSession, name: str) -> bool:
    return bool((await session.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": name})).scalar())
