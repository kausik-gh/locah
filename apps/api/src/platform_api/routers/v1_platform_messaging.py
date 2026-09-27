"""WhatsApp & messages (Capability Universe §6.2 `messaging`, §9.1, §12.5).

The business's WhatsApp number and what is sent automatically, the one inbox,
and sending a bill or a khata statement from the business's number. Inbound
messages arrive through the webhook router (webhooks_whatsapp).
"""

from __future__ import annotations

import uuid
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, assert_module_operational, require_business_actor
from platform_core.exceptions import ConflictError, PermissionDenied, ValidationError
from platform_core.messaging.provider import sandbox_enabled
from platform_core.permissions import (
    INVOICES_ISSUE,
    LEDGER_RECORD,
    MESSAGING_CONFIGURE,
    MESSAGING_READ,
    MESSAGING_REPLY,
)
from platform_core.services.messaging import MessagingService, NotSent

router = APIRouter(prefix="/v1/platform/businesses", tags=["messaging"])
MODULE = "messaging"


def _meta(actor: BusinessActorContext, **extra: Any) -> dict[str, Any]:
    return {"correlation_id": actor.request.correlation_id, **extra}


def _perms(actor: BusinessActorContext) -> frozenset[str]:
    return frozenset(actor.request.effective_permissions)


class SandboxConnectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_phone: str = Field(min_length=10, max_length=20)
    display_name: str | None = Field(default=None, max_length=120)


class SignupBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=4, max_length=1000)
    waba_id: str = Field(min_length=3, max_length=64)
    phone_number_id: str = Field(min_length=3, max_length=64)
    coexistence: bool = False


class SettingsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Literal["en", "ta", "hi"] | None = None
    customer_updates: dict[str, bool] | None = None
    human_pause_hours: int | None = Field(default=None, ge=1, le=72)


class AlertsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    phone: str | None = Field(default=None, max_length=20)
    kinds: list[str] = Field(default_factory=list, max_length=10)


class ReplyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=4096)


class AssignBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assigned_to: UUID | None = None


class StateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Literal["open", "closed"] | None = None
    handler: Literal["bot"] | None = None
    topic: Literal["order", "booking", "lead", "payment", "support"] | None = None


class QuickReplyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=60)
    body: str = Field(min_length=1, max_length=1000)


class SandboxInboundBody(BaseModel):
    """A customer's message on a test stack, delivered exactly as WhatsApp would."""

    model_config = ConfigDict(extra="forbid")

    from_phone: str = Field(min_length=10, max_length=20)
    name: str | None = Field(default=None, max_length=120)
    text: str | None = Field(default=None, max_length=4096)
    button_id: str | None = Field(default=None, max_length=200)
    button_title: str | None = Field(default=None, max_length=60)
    list_reply: bool = False
    latitude: float | None = None
    longitude: float | None = None
    message_id: str | None = Field(default=None, max_length=128)
    echo: bool = False  # the owner's reply from the WhatsApp Business app (coexistence)


# ------------------------------------------------------------------ setup
@router.get("/{business_id}/messaging/setup")
async def setup(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(MESSAGING_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await MessagingService.setup(session, business_id, actor.request.identity_id, _perms(actor))
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/messaging/channel/sandbox")
async def connect_sandbox(
    business_id: UUID, body: SandboxConnectBody,
    actor: BusinessActorContext = Depends(require_business_actor(MESSAGING_CONFIGURE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    channel = await MessagingService.connect_sandbox(session, business_id, actor.request.identity_id,
                                                     body.display_phone, body.display_name)
    await session.commit()
    return {"data": MessagingService.serialize_channel(channel), "meta": _meta(actor)}


@router.post("/{business_id}/messaging/channel/embedded-signup")
async def embedded_signup(
    business_id: UUID, body: SignupBody,
    actor: BusinessActorContext = Depends(require_business_actor(MESSAGING_CONFIGURE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    channel = await MessagingService.complete_signup(
        session, business_id, actor.request.identity_id, code=body.code, waba_id=body.waba_id,
        phone_number_id=body.phone_number_id, coexistence=body.coexistence)
    await session.commit()
    return {"data": MessagingService.serialize_channel(channel), "meta": _meta(actor)}


@router.delete("/{business_id}/messaging/channel")
async def disconnect(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(MESSAGING_CONFIGURE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await MessagingService.disconnect(session, business_id, actor.request.identity_id)
    await session.commit()
    return {"data": {"disconnected": True}, "meta": _meta(actor)}


@router.post("/{business_id}/messaging/templates/submit")
async def submit_templates(
    business_id: UUID,
    keys: list[str] | None = Query(default=None, max_length=20),
    actor: BusinessActorContext = Depends(require_business_actor(MESSAGING_CONFIGURE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    out = await MessagingService.submit_templates(session, business_id, keys)
    await session.commit()
    return {"data": out, "meta": _meta(actor)}


@router.put("/{business_id}/messaging/settings")
async def save_settings(
    business_id: UUID, body: SettingsBody,
    actor: BusinessActorContext = Depends(require_business_actor(MESSAGING_CONFIGURE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await MessagingService.save_settings(session, business_id, actor.request.identity_id,
                                         body.model_dump(exclude_none=True))
    data = await MessagingService.setup(session, business_id, actor.request.identity_id, _perms(actor))
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.put("/{business_id}/messaging/alerts/me")
async def my_alerts(
    business_id: UUID, body: AlertsBody,
    actor: BusinessActorContext = Depends(require_business_actor(MESSAGING_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """A team member's own WhatsApp alerts — anyone who can see the inbox chooses theirs."""
    await MessagingService.save_my_alerts(session, business_id, actor.request.identity_id, _perms(actor),
                                          body.model_dump())
    data = await MessagingService.setup(session, business_id, actor.request.identity_id, _perms(actor))
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


# ------------------------------------------------------------------ inbox
@router.get("/{business_id}/messaging/conversations")
async def conversations(
    business_id: UUID,
    view: Literal["open", "waiting", "mine", "closed", "order", "booking", "lead", "payment"] = Query(default="open"),
    q: str | None = Query(default=None, max_length=100),
    actor: BusinessActorContext = Depends(require_business_actor(MESSAGING_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await MessagingService.list_conversations(session, business_id, actor.request.identity_id, view=view, q=q)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.get("/{business_id}/messaging/conversations/{conversation_id}")
async def thread(
    business_id: UUID, conversation_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(MESSAGING_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await MessagingService.thread(session, business_id, conversation_id, _perms(actor))
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/messaging/conversations/{conversation_id}/messages")
async def reply(
    business_id: UUID, conversation_id: UUID, body: ReplyBody,
    actor: BusinessActorContext = Depends(require_business_actor(MESSAGING_REPLY, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    msg = await MessagingService.reply(session, business_id, conversation_id, actor.request.identity_id, body.body)
    await session.commit()
    if msg.status != "sent":
        raise ConflictError(f"Not sent: {msg.error or msg.status}")
    return {"data": await MessagingService.thread(session, business_id, conversation_id, _perms(actor)),
            "meta": _meta(actor)}


@router.post("/{business_id}/messaging/conversations/{conversation_id}/assign")
async def assign(
    business_id: UUID, conversation_id: UUID, body: AssignBody,
    actor: BusinessActorContext = Depends(require_business_actor(MESSAGING_REPLY, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await MessagingService.assign(session, business_id, conversation_id, actor.request.identity_id, body.assigned_to)
    await session.commit()
    return {"data": await MessagingService.thread(session, business_id, conversation_id, _perms(actor)),
            "meta": _meta(actor)}


@router.post("/{business_id}/messaging/conversations/{conversation_id}/state")
async def set_state(
    business_id: UUID, conversation_id: UUID, body: StateBody,
    actor: BusinessActorContext = Depends(require_business_actor(MESSAGING_REPLY, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await MessagingService.set_state(session, business_id, conversation_id, body.model_dump(exclude_unset=True))
    await session.commit()
    return {"data": await MessagingService.thread(session, business_id, conversation_id, _perms(actor)),
            "meta": _meta(actor)}


@router.post("/{business_id}/messaging/conversations/{conversation_id}/read")
async def mark_read(
    business_id: UUID, conversation_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(MESSAGING_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await MessagingService.mark_read(session, business_id, conversation_id)
    await session.commit()
    return {"data": {"read": True}, "meta": _meta(actor)}


@router.get("/{business_id}/messaging/quick-replies")
async def quick_replies(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(MESSAGING_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return {"data": await MessagingService.quick_replies(session, business_id), "meta": _meta(actor)}


@router.post("/{business_id}/messaging/quick-replies")
async def add_quick_reply(
    business_id: UUID, body: QuickReplyBody,
    actor: BusinessActorContext = Depends(require_business_actor(MESSAGING_REPLY, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await MessagingService.add_quick_reply(session, business_id, actor.request.identity_id, body.title, body.body)
    await session.commit()
    return {"data": await MessagingService.quick_replies(session, business_id), "meta": _meta(actor)}


@router.delete("/{business_id}/messaging/quick-replies/{reply_id}")
async def remove_quick_reply(
    business_id: UUID, reply_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(MESSAGING_REPLY, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await MessagingService.remove_quick_reply(session, business_id, reply_id)
    await session.commit()
    return {"data": await MessagingService.quick_replies(session, business_id), "meta": _meta(actor)}


# ------------------------------------------------------------------ documents from the business number
def _may_message(actor: BusinessActorContext) -> None:
    if MESSAGING_REPLY not in actor.request.effective_permissions:
        raise PermissionDenied(MESSAGING_REPLY)
    assert_module_operational(actor.request, MODULE)


def _sent(msg: Any) -> dict[str, Any]:
    if msg.status != "sent":
        raise ConflictError(f"Not sent: {msg.error or msg.status}")
    return {"status": msg.status, "message_id": str(msg.id), "body": msg.body}


@router.post("/{business_id}/invoices/{document_id}/whatsapp")
async def send_bill(
    business_id: UUID, document_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_ISSUE, "invoicing")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """The bill's link to the customer from the business's WhatsApp number."""
    from platform_core.services.invoicing import KIND_LABEL, InvoiceService
    from platform_core.site_urls import business_site_url

    _may_message(actor)
    doc = await InvoiceService.get(session, business_id, document_id)
    share = await InvoiceService.share(session, business_id, document_id)
    phone = share.get("phone")
    if not phone and doc.customer_contact_id:
        from platform_core.models import CustomerContact

        contact = await session.get(CustomerContact, doc.customer_contact_id)
        phone = contact.phone if contact else None
    if not phone:
        raise ValidationError("This bill has no customer phone number", details={"field": "phone"})
    slug = share["path"].split("/")[1]
    try:
        msg = await MessagingService.send_template(
            session, business_id, to=phone, key="bill_ready", contact_id=doc.customer_contact_id,
            params=[share["business_name"], f"{KIND_LABEL[doc.doc_kind]} {doc.number}", f"₹{float(doc.amount_due):,.2f}",
                    business_site_url(slug, f"/bill/{share['token']}")],
            sent_via="workspace", sent_by=actor.request.identity_id, idempotency_key=f"bill:{doc.id}:{uuid.uuid4()}")
    except NotSent as exc:
        raise ConflictError(str(exc)) from exc
    await session.commit()
    return {"data": _sent(msg), "meta": _meta(actor)}


@router.post("/{business_id}/ledger/accounts/{account_id}/whatsapp")
async def send_statement(
    business_id: UUID, account_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(LEDGER_RECORD, "ledger")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """The customer's khata statement link from the business's WhatsApp number."""
    from platform_core.services.ledger import LedgerService
    from platform_core.site_urls import business_site_url

    _may_message(actor)
    acct = await LedgerService.get(session, business_id, account_id)
    share = await LedgerService.share(session, business_id, account_id)
    if not acct.phone:
        raise ValidationError("This account has no phone number", details={"field": "phone"})
    slug = share["path"].split("/")[1]
    try:
        msg = await MessagingService.send_template(
            session, business_id, to=acct.phone, key="payment_due", contact_id=acct.customer_contact_id,
            params=[share["business_name"], f"₹{max(0.0, float(acct.balance)):,.2f}",
                    business_site_url(slug, f"/khata/{share['token']}")],
            sent_via="workspace", sent_by=actor.request.identity_id,
            idempotency_key=f"statement:{acct.id}:{uuid.uuid4()}")
    except NotSent as exc:
        raise ConflictError(str(exc)) from exc
    await session.commit()
    return {"data": _sent(msg), "meta": _meta(actor)}


# ------------------------------------------------------------------ test stacks
@router.post("/{business_id}/messaging/sandbox/inbound")
async def sandbox_inbound(
    business_id: UUID, body: SandboxInboundBody,
    actor: BusinessActorContext = Depends(require_business_actor(MESSAGING_CONFIGURE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Deliver a customer message to the sandbox number in WhatsApp's own
    webhook format, through the same code path as a real delivery."""
    from platform_core.messaging.fixtures import webhook_payload

    if not sandbox_enabled():
        raise ConflictError("The WhatsApp sandbox is only available on test stacks")
    channel = await MessagingService.channel(session, business_id)
    if channel is None or channel.provider != "sandbox":
        raise ConflictError("Connect the sandbox number first")
    payload = webhook_payload(str(channel.phone_number_id), str(channel.display_phone), body.model_dump())
    counts = await MessagingService.process_webhook(session, payload)
    await session.commit()
    return {"data": counts, "meta": _meta(actor)}
