"""The customer's view of a quote, reached by share link.

The recipient has no LOCAH account and never will for this transaction, so the
token in the URL is the whole credential. That puts real weight on it: it is
opaque and random, it is cleared the moment the quote is cancelled or superseded,
and the page is marked noindex so a link forwarded into a crawlable place does
not end up in a search result.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_core.context_resolver import bind_public_context, bind_quote_share_token
from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.models import Business, Quote
from platform_core.services.quote import QuoteService
from platform_core.services.quote_document import render_quote_document

router = APIRouter(prefix="/v1/public", tags=["quotes"])


async def _resolve_by_token(session: AsyncSession, token: str) -> tuple[Quote, Business]:
    """Find the quote a share token refers to, then bind its tenant.

    The lookup runs before any business context exists, which is the same
    ordering the website preview path uses: the token is what tells us which
    tenant to bind, so it cannot be bound first.
    """
    if not token or len(token) < 20:
        raise ResourceNotFound("Quote")
    # The token is the credential, and RLS needs it bound before the row it
    # points at becomes visible — there is no business context yet to bind.
    await bind_quote_share_token(session, token)
    quote = (
        await session.execute(select(Quote).where(Quote.access_token == token))
    ).scalars().first()
    if quote is None or quote.deleted_at is not None:
        raise ResourceNotFound("Quote")
    await bind_public_context(session, quote.business_id)

    business = (
        await session.execute(select(Business).where(Business.id == quote.business_id))
    ).scalars().first()
    if business is None or business.deleted_at is not None:
        raise ResourceNotFound("Quote")
    return quote, business


def _expired_token(quote: Quote) -> bool:
    from datetime import datetime, timezone

    return (
        quote.access_token_expires_at is not None
        and quote.access_token_expires_at <= datetime.now(timezone.utc)
    )


@router.get("/quotes/{token}", response_class=HTMLResponse)
async def view_quote(
    token: str,
    session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    quote, business = await _resolve_by_token(session, token)
    if _expired_token(quote):
        raise ResourceNotFound("Quote")

    if QuoteService.effective_status(quote) == "issued":
        await QuoteService.record_view(session, quote)
        await session.commit()
    detail = await QuoteService.get_detail(
        session, business_id=quote.business_id, quote_id=quote.id
    )
    html = render_quote_document(
        quote=detail,
        business_name=business.display_name,
        can_decide=True,
    )
    return HTMLResponse(
        content=html,
        headers={
            # A priced offer addressed to one person should not be cached by an
            # intermediary or indexed anywhere.
            "Cache-Control": "no-store, private",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )


@router.post("/quotes/{token}", response_class=HTMLResponse)
async def decide_quote(
    token: str,
    request: Request,
    decision: str = Form(...),
    name: str = Form(""),
    code: str = Form(""),
    session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    """Accept or decline from the document itself.

    Posting back to the same URL keeps the customer on one page and means the
    decision needs no account, no app and no second link.
    """
    quote, business = await _resolve_by_token(session, token)
    if _expired_token(quote):
        raise ResourceNotFound("Quote")

    correlation = str(getattr(request.state, "correlation_id", "") or uuid.uuid4())
    notice = ""
    # Status first, so a lapsed quote is a conflict even when the form is empty.
    current = QuoteService.effective_status(quote)
    if decision == "request_code":
        if current != "issued":
            raise ConflictError(
                f"A {current} quote cannot be accepted",
                details={"status": current},
            )
        from platform_core.services.messaging import MessagingService

        # The code only ever travels by WhatsApp. Promise it only when it can
        # actually reach this customer; otherwise say who confirms instead.
        if await MessagingService.reachable(session, quote.business_id, quote.customer_contact_id):
            await QuoteService.issue_acceptance_code(
                session, quote=quote, name=name, correlation_id=correlation
            )
            await session.commit()
            notice = "We sent a 6-digit code to your WhatsApp. Enter it, then accept."
        else:
            notice = (f"{business.display_name} cannot send you a code on WhatsApp yet. "
                      f"Tell {business.display_name} you accept and they will record it on this quote.")
    elif decision in {"accepted", "rejected"}:
        if current != "issued":
            raise ConflictError(
                f"A {current} quote cannot be {decision}",
                details={"status": current},
            )
        cleaned = name.strip()
        if not cleaned:
            raise ValidationError("Tell us your name")
        if decision == "accepted":
            try:
                QuoteService.verify_acceptance_code(quote, code)
            except ValidationError:
                await session.commit()
                raise
        await QuoteService.decide(
            session,
            business_id=quote.business_id,
            quote_id=quote.id,
            decision=decision,
            # platform_audit_events requires a real identity, and a share-link
            # customer has none. Attribute it to the business owner the way
            # guest checkout and public bookings already do; actor_context on
            # the audit row is what records that a guest, not the owner, acted.
            actor_id=business.primary_owner_identity_id,
            correlation_id=correlation,
            decided_by_name=cleaned,
            actor_context="guest_checkout",
        )
        await session.commit()

    detail = await QuoteService.get_detail(
        session, business_id=quote.business_id, quote_id=quote.id
    )
    html = render_quote_document(
        quote=detail,
        business_name=business.display_name,
        can_decide=True,
        notice=notice,
        name=name.strip(),
    )
    return HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-store, private", "X-Robots-Tag": "noindex, nofollow"},
    )


@router.get("/quotes/{token}/data")
async def quote_data(
    token: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """The same quote as JSON, for a richer client-side view later.

    Deliberately omits internal_notes and the token itself — the customer sees
    the offer, not the business's private annotations about it.
    """
    quote, business = await _resolve_by_token(session, token)
    if _expired_token(quote):
        raise ResourceNotFound("Quote")
    if QuoteService.effective_status(quote) == "issued":
        await QuoteService.record_view(session, quote)
        await session.commit()
    detail = await QuoteService.get_detail(
        session, business_id=quote.business_id, quote_id=quote.id
    )
    detail["business_name"] = business.display_name
    return {"data": detail}
