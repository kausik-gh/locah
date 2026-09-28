"""Structured WhatsApp journeys (Capability Universe §12.3, P1 column; §12.4).

Order, book, enquire, pay / dues, track, reorder, change / cancel — with
buttons and lists, zero model calls. The router (MessagingService.route)
offers every message here first; a journey that does not recognise it says
so, and a person takes over.

Rules kept here (§12.4):
* **The customer confirms every cart or booking with a button.** Nothing is
  placed silently; if a price changed since the summary they confirmed, they
  see the new total and confirm again.
* **Prices and stock come only from LOCAH.** The cart holds what was chosen,
  never a price: every summary and the order itself are priced from the
  catalogue at that moment, and stock and slots are re-checked at confirm
  with alternatives offered.
* **Every path ends in the same order, booking or lead the website creates**
  (CheckoutService.place_for_contact, BookingService, LeadService), marked
  with the channel `whatsapp`.
* **Addresses:** a location pin or a typed address with its PIN code; the
  customer's last delivery address is offered first. Turning a pin into a
  street address needs a maps provider (P2); the pin itself is kept.
* **Payment:** cash on delivery / at pickup where the owner allows it, with
  the owner's first-order COD cap. Online payment links need a payment
  provider (activation required).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import PlatformError
from platform_core.models import (
    Booking,
    Business,
    BusinessLocation,
    CustomerContact,
    FulfilmentJob,
    InventoryRecord,
    InvoicingDocument,
    LedgerAccount,
    MessagingConversation,
    Offering,
    OfferingCategory,
    OfferingVariant,
    OrderLineItem,
    SalesOrder,
)

IST = ZoneInfo("Asia/Kolkata")
MENU_WORDS = {"hi", "hii", "hello", "hey", "menu", "start", "help", "vanakkam", "வணக்கம்", "மெனு", "namaste", "namaskar",
              "नमस्ते", "मेनू", "0"}
# Checked in this order: "cancel my booking" is a cancellation, not a booking.
INTENTS: dict[str, tuple[str, ...]] = {
    "m:cancel": ("cancel", "change my"),
    "m:track": ("where is my order", "where's my order", "track", "status", "எங்கே", "कहाँ"),
    "m:pay": ("how much do i owe", "balance", "dues", "due", "pay", "khata", "bill", "பாக்கி", "बकाया"),
    "m:reorder": ("repeat", "reorder", "same as last", "same again"),
    "m:book": ("book", "appointment", "booking", "slot", "முன்பதிவு", "बुक"),
    "m:order": ("order", "buy", "ஆர்டர்", "ऑर्डर"),
    "m:enquire": ("enquire", "enquiry", "inquiry", "question", "price list", "details"),
}
OPEN_ORDER = ("pending", "accepted", "preparing", "ready")
STATUS_WORDS = {"pending": "waiting for the shop to accept", "accepted": "accepted", "preparing": "being prepared",
                "ready": "ready", "completed": "completed", "cancelled": "cancelled", "rejected": "declined"}
PAGE = 8  # a list holds ten rows: checkout, eight items, more


def _t(s: str, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _inr(v: Any) -> str:
    return f"₹{Decimal(str(v or 0)):,.2f}"


def buttons(body: str, items: list[tuple[str, str]]) -> dict[str, Any]:
    """Up to three reply buttons (WhatsApp's limit), titles up to 20 characters."""
    return {"type": "button", "body": {"text": _t(body, 1024)},
            "action": {"buttons": [{"type": "reply", "reply": {"id": i, "title": _t(title, 20)}}
                                   for i, title in items[:3]]}}


def listing(body: str, button: str, rows: list[tuple[str, str, str]]) -> dict[str, Any]:
    """A list of up to ten rows (titles 24, descriptions 72 characters)."""
    return {"type": "list", "body": {"text": _t(body, 1024)},
            "action": {"button": _t(button, 20), "sections": [{"title": _t("Choose", 24), "rows": [
                {"id": i, "title": _t(title, 24), **({"description": _t(desc, 72)} if desc else {})}
                for i, title, desc in rows[:10]]}]}}


@dataclass
class Ctx:
    session: AsyncSession
    conv: MessagingConversation
    business: Business
    contact: CustomerContact | None
    live: set[str]

    @property
    def j(self) -> dict[str, Any]:
        return dict(self.conv.journey or {})

    def save(self, **changes: Any) -> None:
        j = self.j
        for k, v in changes.items():
            if v is None:
                j.pop(k, None)
            else:
                j[k] = v
        self.conv.journey = j

    async def say(self, body: str) -> None:
        from platform_core.services.messaging import MessagingService

        await MessagingService.bot_text(self.session, self.conv, body)

    async def ask(self, interactive: dict[str, Any]) -> None:
        from platform_core.services.messaging import MessagingService

        await MessagingService.bot_interactive(self.session, self.conv, interactive)


async def _ctx(session: AsyncSession, conv: MessagingConversation) -> Ctx:
    business = await session.get(Business, conv.business_id)
    assert business is not None
    contact = await session.get(CustomerContact, conv.contact_id) if conv.contact_id else None
    live = {r[0] for r in (await session.execute(text(
        "SELECT module_id FROM business_module_states WHERE business_id = :b "
        "AND activation_state IN ('enabled', 'ready', 'active')"), {"b": str(conv.business_id)})).all()}
    # The same readiness answer the website and Marketplace use (Guide §4):
    # ordering, booking and enquiring are offered only once they are set up.
    from platform_core.services.module_readiness import readiness

    states = await readiness(session, conv.business_id, modules=("orders", "bookings", "leads"))
    live -= {m for m, st in states.items() if not st["ready"]}
    return Ctx(session, conv, business, contact, live)


# ---------------------------------------------------------------- entry
async def handle(session: AsyncSession, conv: MessagingConversation, kind: str, body: str,
                 extra: dict[str, Any]) -> bool:
    """True when a structured journey answered the message."""
    from platform_core.services.messaging import MessagingService

    if not await MessagingService.bot_may_reply(session, conv):
        return False  # a person is handling this chat (§12.1)
    ctx = await _ctx(session, conv)
    reply_id = str(extra.get("id") or "") if kind in ("button", "list") else ""
    if reply_id:
        return await _dispatch(ctx, reply_id)
    step = ctx.j.get("step")
    if kind == "location" and step == "address":
        return await _address_pin(ctx, extra)
    if kind != "text":
        return False
    said = body.strip().lower()
    if step in TEXT_STEPS:
        if said in MENU_WORDS:
            ctx.save(step=None)
        else:
            return bool(await TEXT_STEPS[step](ctx, body.strip()))
    if said in MENU_WORDS:
        return await menu(ctx)
    for key, words in INTENTS.items():
        if any(said == w or said.startswith(w + " ") or (len(w) > 5 and w in said) for w in words):
            return await _dispatch(ctx, key)
    return False


async def _dispatch(ctx: Ctx, rid: str) -> bool:
    if rid == "menu":
        return await menu(ctx)
    for prefix, fn in ROUTES:
        if rid == prefix or rid.startswith(prefix + ":"):
            return bool(await fn(ctx, rid[len(prefix) + 1:] if rid != prefix else ""))
    return False


# ---------------------------------------------------------------- menu
async def _orderable(session: AsyncSession, business_id: uuid.UUID) -> list[Offering]:
    from platform_core.catalog.offering_kinds import KINDS

    rows = (await session.execute(select(Offering).where(
        Offering.business_id == business_id, Offering.deleted_at.is_(None), Offering.status == "active",
        Offering.visibility == "public", Offering.title != "Delivery fee").order_by(Offering.title))).scalars()
    return [o for o in rows if (KINDS.get(o.offering_type) is None or KINDS[o.offering_type].flow == "cart")
            and (o.price_amount is not None or o.variant_options)]


async def _bookable(session: AsyncSession, business_id: uuid.UUID) -> list[Offering]:
    return list((await session.execute(select(Offering).where(
        Offering.business_id == business_id, Offering.deleted_at.is_(None), Offering.status == "active",
        Offering.visibility == "public", Offering.offering_type.in_(("service", "experience", "rental")),
    ).order_by(Offering.title))).scalars())


async def _open_orders(ctx: Ctx) -> list[SalesOrder]:
    if ctx.contact is None:
        return []
    return list((await ctx.session.execute(select(SalesOrder).where(
        SalesOrder.business_id == ctx.business.id, SalesOrder.customer_contact_id == ctx.contact.id,
        SalesOrder.deleted_at.is_(None), SalesOrder.status.in_(OPEN_ORDER)).order_by(SalesOrder.created_at.desc())
        .limit(5))).scalars())


async def _upcoming_bookings(ctx: Ctx) -> list[Booking]:
    if ctx.contact is None:
        return []
    return list((await ctx.session.execute(select(Booking).where(
        Booking.business_id == ctx.business.id, Booking.customer_contact_id == ctx.contact.id,
        Booking.deleted_at.is_(None), Booking.status.in_(("pending", "confirmed")),
        Booking.starts_at > datetime.now(timezone.utc)).order_by(Booking.starts_at).limit(5))).scalars())


async def menu(ctx: Ctx) -> bool:
    rows: list[tuple[str, str, str]] = []
    if "orders" in ctx.live and await _orderable(ctx.session, ctx.business.id):
        rows.append(("m:order", "Order", "See what we have and order here"))
    if "bookings" in ctx.live and await _bookable(ctx.session, ctx.business.id):
        rows.append(("m:book", "Book", "Pick a service and a time"))
    if "leads" in ctx.live:
        rows.append(("m:enquire", "Ask a question", "About a product, service or price"))
    open_orders = await _open_orders(ctx)
    if open_orders:
        rows.append(("m:track", "Track my order", "Where your order is now"))
    if ctx.contact and "orders" in ctx.live and (await ctx.session.execute(select(func.count()).select_from(SalesOrder)
            .where(SalesOrder.business_id == ctx.business.id, SalesOrder.customer_contact_id == ctx.contact.id,
                   SalesOrder.deleted_at.is_(None)))).scalar_one():
        rows.append(("m:reorder", "Repeat my last order", "Same items, today's prices"))
    if ctx.contact and ({"ledger", "invoicing"} & ctx.live):
        rows.append(("m:pay", "What do I owe", "Your balance and bills"))
    if any(o.status == "pending" for o in open_orders) or await _upcoming_bookings(ctx):
        rows.append(("m:cancel", "Change or cancel", "An order or a booking"))
    rows.append(("talk_to_person", "Talk to a person", "Someone from the team replies here"))
    ctx.save(step=None)
    name = (ctx.contact.display_name.split()[0] if ctx.contact and ctx.contact.display_name
            and not ctx.contact.display_name.startswith("+") else "there")
    await ctx.ask(listing(f"Hi {name}! This is {ctx.business.display_name}. What would you like to do?", "Menu", rows))
    return True


# ---------------------------------------------------------------- order
async def order_start(ctx: Ctx, arg: str) -> bool:
    items = await _orderable(ctx.session, ctx.business.id)
    if "orders" not in ctx.live or not items:
        await ctx.say("Ordering on WhatsApp is not available right now. Tap Talk to a person, or send menu.")
        return True
    cats = {o.category_id for o in items if o.category_id}
    if not ctx.j.get("cart_id"):
        ctx.save(cart_id=uuid.uuid4().hex, cart=[])
    ctx.conv.topic = "order"
    if len(cats) > 1 and not arg:
        names: dict[uuid.UUID, str] = {r[0]: r[1] for r in (await ctx.session.execute(select(
            OfferingCategory.id, OfferingCategory.name).where(OfferingCategory.id.in_(cats)))).all()}
        rows = [*await _checkout_row(ctx),
                *[(f"o:cat:{cid}", names.get(cid, "Other"), f"{sum(1 for o in items if o.category_id == cid)} items")
                  for cid in sorted(cats, key=lambda c: names.get(c, ""))][:8]]
        if any(o.category_id is None for o in items):
            rows.append(("o:cat:none", "Other items", ""))
        await ctx.ask(listing("What would you like to order?", "Categories", rows))
        return True
    ctx.save(cat=None)
    return await order_page(ctx, arg or "0")


async def order_category(ctx: Ctx, arg: str) -> bool:
    ctx.save(cat=arg)
    return await order_page(ctx, "0")


async def order_page(ctx: Ctx, arg: str) -> bool:
    items = await _orderable(ctx.session, ctx.business.id)
    cat = ctx.j.get("cat")
    if cat:
        items = [o for o in items if (str(o.category_id) if o.category_id else "none") == cat]
    page = int(arg or 0)
    chunk = items[page * PAGE:(page + 1) * PAGE]
    rows = [*await _checkout_row(ctx), *[(f"o:item:{o.id}", o.title, _price_words(o)) for o in chunk]]
    if len(items) > (page + 1) * PAGE:
        rows.append((f"o:page:{page + 1}", "More items…", f"{len(items) - (page + 1) * PAGE} more"))
    await ctx.ask(listing("Choose an item — prices are today's.", "Items", rows))
    return True


async def _checkout_row(ctx: Ctx) -> list[tuple[str, str, str]]:
    cart = list(ctx.j.get("cart") or [])
    if not cart:
        return []
    priced = await _price_cart(ctx, cart)
    n = sum(int(line["quantity"]) for line in cart)
    return [("o:checkout", f"Checkout ({n} item{'s' if n != 1 else ''})", f"{_inr(priced['subtotal'])} so far")]


def _price_words(o: Offering) -> str:
    if o.price_amount is None:
        return "Choose an option"
    per = (o.attributes or {}).get("price_per")
    return f"{_inr(o.price_amount)}{f' / {per}' if per else ''}"


async def order_item(ctx: Ctx, arg: str) -> bool:
    offering = await ctx.session.get(Offering, uuid.UUID(arg))
    if offering is None or offering.business_id != ctx.business.id or offering.status != "active":
        await ctx.say("That item is no longer available.")
        return await order_page(ctx, "0")
    ctx.save(pending={"offering_id": str(offering.id), "options": {}, "title": offering.title}, step=None)
    return await _next_choice(ctx, offering)


async def _next_choice(ctx: Ctx, offering: Offering) -> bool:
    """Ask for what still has to be chosen: option, pack, required choices, then quantity."""
    p = dict(ctx.j.get("pending") or {})
    variants = list((await ctx.session.execute(select(OfferingVariant).where(
        OfferingVariant.offering_id == offering.id, OfferingVariant.status == "active")
        .order_by(OfferingVariant.sort_order))).scalars())
    if variants and not p.get("variant_id"):
        await ctx.ask(listing(f"{offering.title}: which one?", "Options",
                              [(f"o:var:{v.id}", v.name, _inr(v.price_amount if v.price_amount is not None
                                                            else offering.price_amount)) for v in variants[:10]]))
        return True
    packs = list(offering.sell_units or [])
    opts = dict(p.get("options") or {})
    if packs and not opts.get("pack"):
        await ctx.ask(listing(f"{offering.title}: how much?", "Sizes",
                              [(f"o:pack:{i}", str(pk["label"]), "") for i, pk in enumerate(packs[:10])]))
        return True
    choices = dict(opts.get("choices") or {})
    for gi, g in enumerate(offering.option_groups or []):
        if g["name"] in choices or f"skip:{g['name']}" in (p.get("skipped") or []):
            continue
        rows = [(f"o:opt:{gi}:{ci}", str(c["label"]),
                 f"+{_inr(c['price_delta'])}" if Decimal(str(c["price_delta"])) else "")
                for ci, c in enumerate(g["choices"][:9])]
        if not g["required"]:
            rows.append((f"o:opt:{gi}:-", f"No {g['name'].lower()}", ""))
        await ctx.ask(listing(f"{offering.title}: {g['name'].lower()}?", _t(g["name"], 20), rows))
        return True
    ctx.save(step="qty")
    await ctx.ask(buttons(f"How many {offering.title}?", [("o:qty:1", "1"), ("o:qty:2", "2"), ("o:qty:3", "3")]))
    await ctx.say("Or type a number.")
    return True


async def order_variant(ctx: Ctx, arg: str) -> bool:
    p = dict(ctx.j.get("pending") or {})
    if not p:
        return await order_page(ctx, "0")
    p["variant_id"] = arg
    ctx.save(pending=p)
    return await _next_choice(ctx, await _pending_offering(ctx))


async def order_pack(ctx: Ctx, arg: str) -> bool:
    p = dict(ctx.j.get("pending") or {})
    offering = await _pending_offering(ctx)
    packs = list(offering.sell_units or [])
    p["options"] = {**(p.get("options") or {}), "pack": packs[int(arg)]["label"]}
    ctx.save(pending=p)
    return await _next_choice(ctx, offering)


async def order_option(ctx: Ctx, arg: str) -> bool:
    p = dict(ctx.j.get("pending") or {})
    offering = await _pending_offering(ctx)
    gi, ci = arg.split(":")
    g = (offering.option_groups or [])[int(gi)]
    if ci == "-":
        p["skipped"] = [*(p.get("skipped") or []), f"skip:{g['name']}"]
    else:
        opts = dict(p.get("options") or {})
        opts["choices"] = {**(opts.get("choices") or {}), g["name"]: [g["choices"][int(ci)]["label"]]}
        p["options"] = opts
    ctx.save(pending=p)
    return await _next_choice(ctx, offering)


async def _pending_offering(ctx: Ctx) -> Offering:
    p = ctx.j.get("pending") or {}
    o = await ctx.session.get(Offering, uuid.UUID(str(p.get("offering_id"))))
    assert o is not None
    return o


async def order_qty(ctx: Ctx, arg: str) -> bool:
    return await _add_to_cart(ctx, arg)


async def _qty_typed(ctx: Ctx, said: str) -> bool:
    m = re.fullmatch(r"\s*(\d{1,3})\s*", said)
    if not m or int(m.group(1)) < 1:
        await ctx.say("Type how many as a number, like 2.")
        return True
    return await _add_to_cart(ctx, m.group(1))


async def _add_to_cart(ctx: Ctx, qty: str) -> bool:
    p = dict(ctx.j.get("pending") or {})
    if not p:
        return await order_page(ctx, "0")
    line = {"offering_id": p["offering_id"], "variant_id": p.get("variant_id"), "options": p.get("options") or {},
            "quantity": max(1, min(999, int(qty)))}
    cart = [*(ctx.j.get("cart") or []), line]
    ctx.save(cart=cart, pending=None, step=None)
    priced = await _price_cart(ctx, cart)
    n = sum(int(ln["quantity"]) for ln in cart)
    await ctx.ask(buttons(f"Added. Your cart: {n} item{'s' if n != 1 else ''}, {_inr(priced['subtotal'])}.",
                          [("o:start", "Add more"), ("o:checkout", "Checkout"), ("talk_to_person", "Talk to a person")]))
    return True


async def _stock_location(ctx: Ctx) -> uuid.UUID | None:
    """Orders placed here reserve stock at the primary location (as the website's do)."""
    return (await ctx.session.execute(select(BusinessLocation.id).where(
        BusinessLocation.business_id == ctx.business.id, BusinessLocation.status == "active")
        .order_by(BusinessLocation.is_primary.desc(), BusinessLocation.created_at).limit(1))).scalar()


async def _price_cart(ctx: Ctx, cart: list[dict[str, Any]]) -> dict[str, Any]:
    """Every price from the catalogue now (§12.6: never the cart's)."""
    from platform_core.services.offering_pricing import price_selection

    lines: list[dict[str, Any]] = []
    problems: list[tuple[int, str, int]] = []
    subtotal = Decimal(0)
    demand: dict[tuple[str, str | None], int] = {}
    location_id = await _stock_location(ctx)
    for i, raw in enumerate(cart):
        o = await ctx.session.get(Offering, uuid.UUID(str(raw["offering_id"])))
        if o is None or o.status != "active" or o.deleted_at is not None or o.business_id != ctx.business.id:
            problems.append((i, "is no longer available", 0))
            continue
        v = await ctx.session.get(OfferingVariant, uuid.UUID(str(raw["variant_id"]))) if raw.get("variant_id") else None
        try:
            priced = price_selection(o, v, raw.get("options") or None)
        except PlatformError:
            problems.append((i, "needs choosing again", 0))
            continue
        qty = int(raw["quantity"])
        unit = Decimal(str(priced.unit_price))
        label = o.title + (f" — {v.name}" if v else "") + (f" ({priced.title_suffix})" if priced.title_suffix else "")
        if o.track_inventory:
            key = (str(o.id), str(v.id) if v else None)
            record = (await ctx.session.execute(select(InventoryRecord).where(
                InventoryRecord.business_id == ctx.business.id, InventoryRecord.offering_id == o.id,
                InventoryRecord.location_id == location_id,
                InventoryRecord.variant_id == v.id if v else InventoryRecord.variant_id.is_(None))
                .execution_options(populate_existing=True))).scalars().first()
            available = max(record.quantity_on_hand - record.quantity_reserved, 0) if record else 0
            per = max(int(priced.stock_per_unit or 1), 1)
            can = max((available - demand.get(key, 0)) // per, 0)
            if can < qty:
                problems.append((i, f"has only {can} left" if can else "is out of stock", can))
            demand[key] = demand.get(key, 0) + min(qty, can) * per
        total = unit * qty
        subtotal += total
        lines.append({"i": i, "label": label, "qty": qty, "unit": unit, "total": total})
    return {"lines": lines, "problems": problems, "subtotal": subtotal}


async def order_checkout(ctx: Ctx, arg: str) -> bool:
    from platform_core.services.fulfilment import FulfilmentService

    cart = list(ctx.j.get("cart") or [])
    if not cart:
        await ctx.say("Your cart is empty.")
        return await order_start(ctx, "")
    priced = await _price_cart(ctx, cart)
    if priced["problems"]:
        return await _fix_problems(ctx, priced)
    modes = [m for m in await FulfilmentService.active_modes(ctx.session, ctx.business.id)
             if m in ("delivery", "pickup")]
    if not modes:
        await ctx.ask(buttons("We can't take orders here right now.", [("talk_to_person", "Talk to a person")]))
        return True
    ctx.save(modes=modes)
    if len(modes) == 1:
        return await order_mode(ctx, modes[0])
    await ctx.ask(buttons(_cart_text(priced) + "\n\nDelivery or pickup?",
                          [("o:mode:delivery", "Delivery"), ("o:mode:pickup", "Pickup")]))
    return True


def _cart_text(priced: dict[str, Any], charge: Decimal = Decimal(0)) -> str:
    lines = [f"{ln['qty']} × {ln['label']} — {_inr(ln['total'])}" for ln in priced["lines"]]
    if charge:
        lines.append(f"Delivery — {_inr(charge)}")
    lines.append(f"Total {_inr(priced['subtotal'] + charge)}")
    return "\n".join(lines)


async def _fix_problems(ctx: Ctx, priced: dict[str, Any]) -> bool:
    cart = list(ctx.j.get("cart") or [])
    i, what, can = priced["problems"][0]
    o = await ctx.session.get(Offering, uuid.UUID(str(cart[i]["offering_id"])))
    name = o.title if o else "An item"
    opts = [("o:drop:" + str(i), "Remove it")]
    if can:
        opts.insert(0, (f"o:fix:{i}:{can}", f"Make it {can}"))
    opts.append(("talk_to_person", "Talk to a person"))
    await ctx.ask(buttons(f"{name} {what}.", opts))
    return True


async def order_fix(ctx: Ctx, arg: str) -> bool:
    i, n = (int(x) for x in arg.split(":"))
    cart = list(ctx.j.get("cart") or [])
    if 0 <= i < len(cart):
        cart[i] = {**cart[i], "quantity": n}
    ctx.save(cart=cart)
    return await order_checkout(ctx, "")


async def order_drop(ctx: Ctx, arg: str) -> bool:
    cart = list(ctx.j.get("cart") or [])
    i = int(arg)
    if 0 <= i < len(cart):
        cart.pop(i)
    ctx.save(cart=cart)
    return await order_checkout(ctx, "")


async def _last_address(ctx: Ctx) -> dict[str, Any] | None:
    if ctx.contact is None:
        return None
    row = (await ctx.session.execute(select(FulfilmentJob.delivery_address).join(
        SalesOrder, SalesOrder.id == FulfilmentJob.order_id).where(
        FulfilmentJob.business_id == ctx.business.id, SalesOrder.customer_contact_id == ctx.contact.id,
        FulfilmentJob.mode == "delivery", FulfilmentJob.delivery_address.is_not(None))
        .order_by(FulfilmentJob.created_at.desc()).limit(1))).scalar()
    return dict(row) if row else None


async def order_mode(ctx: Ctx, arg: str) -> bool:
    if arg not in (ctx.j.get("modes") or ["pickup"]):
        return await order_checkout(ctx, "")
    ctx.save(mode=arg)
    if arg == "pickup":
        ctx.save(address=None)
        return await _payment(ctx)
    last = await _last_address(ctx)
    if last:
        ctx.save(last_address=last)
        await ctx.ask(buttons(f"Deliver to {_t(_address_words(last), 180)}?",
                              [("o:addr:last", "Yes, same address"), ("o:addr:new", "New address")]))
        return True
    return await order_address(ctx, "new")


def _address_words(a: dict[str, Any]) -> str:
    line1 = str(a.get("line1") or "")
    parts = [line1, *(str(a[k]) for k in ("city", "postal_code") if a.get(k) and str(a[k]) not in line1)]
    words = ", ".join(p for p in parts if p)
    return words or ("Location pin" if a.get("lat") is not None else "your address")


async def order_address(ctx: Ctx, arg: str) -> bool:
    if arg == "last" and ctx.j.get("last_address"):
        return await _use_address(ctx, dict(ctx.j["last_address"]))
    ctx.save(step="address")
    await ctx.say("Send your location pin (tap + → Location), or type your address with its PIN code.")
    return True


async def _address_pin(ctx: Ctx, extra: dict[str, Any]) -> bool:
    lat, lng = extra.get("latitude"), extra.get("longitude")
    if lat is None or lng is None:
        return False
    return await _use_address(ctx, {"lat": float(lat), "lng": float(lng),
                                    "line1": " ".join(str(x) for x in (extra.get("name"), extra.get("address")) if x)
                                    or None})


async def _address_typed(ctx: Ctx, said: str) -> bool:
    pin = re.search(r"\b(\d{6})\b", said)
    if len(said) < 8:
        await ctx.say("Type the full address with its PIN code, or send your location pin.")
        return True
    city = None
    parts = [p.strip() for p in re.split(r"[,\n]", said) if p.strip()]
    if len(parts) > 1:
        city = re.sub(r"\d{6}", "", parts[-1]).strip(" -") or (parts[-2] if len(parts) > 2 else None)
    return await _use_address(ctx, {"line1": said[:300], "postal_code": pin.group(1) if pin else None, "city": city})


async def _use_address(ctx: Ctx, address: dict[str, Any]) -> bool:
    from platform_core.services.fulfilment import FulfilmentService

    zone, charge = await FulfilmentService.match_zone(ctx.session, business_id=ctx.business.id, address=address)
    if zone is None:
        ctx.save(step=None)
        opts = [("o:mode:pickup", "Pickup instead")] if "pickup" in (ctx.j.get("modes") or []) else []
        await ctx.ask(buttons("Sorry — we don't deliver there yet.",
                              [*opts, ("o:addr:new", "Another address"), ("talk_to_person", "Talk to a person")]))
        return True
    ctx.save(address=address, charge=str(charge), step=None)
    return await _payment(ctx)


async def _is_first_order(ctx: Ctx) -> bool:
    if ctx.contact is None:
        return True
    return not (await ctx.session.execute(select(func.count()).select_from(SalesOrder).where(
        SalesOrder.business_id == ctx.business.id, SalesOrder.customer_contact_id == ctx.contact.id,
        SalesOrder.deleted_at.is_(None), SalesOrder.status.notin_(("cancelled", "rejected"))))).scalar_one()


async def _payment(ctx: Ctx) -> bool:
    from platform_core.services.messaging import MessagingService

    s = await MessagingService.settings(ctx.session, ctx.business.id)
    priced = await _price_cart(ctx, list(ctx.j.get("cart") or []))
    charge = Decimal(str(ctx.j.get("charge") or 0)) if ctx.j.get("mode") == "delivery" else Decimal(0)
    total = priced["subtotal"] + charge
    if not s.cod_allowed:
        await ctx.ask(buttons("Paying online on WhatsApp is not available yet. A person will help you finish this order.",
                              [("talk_to_person", "Talk to a person"), ("menu", "Menu")]))
        return True
    if s.first_order_cod_cap is not None and await _is_first_order(ctx) and total > Decimal(str(s.first_order_cod_cap)):
        await ctx.ask(buttons(f"For a first order, cash on delivery is up to {_inr(s.first_order_cod_cap)}. "
                              "A person will help you pay for this one.",
                              [("talk_to_person", "Talk to a person"), ("o:start", "Change the cart")]))
        return True
    ctx.save(pay="cod", confirmed_total=str(total))
    where = f"Deliver to {_t(_address_words(ctx.j.get('address') or {}), 120)}" if ctx.j.get("mode") == "delivery" \
        else "Pickup"
    pay = "Pay on delivery" if ctx.j.get("mode") == "delivery" else "Pay at pickup"
    await ctx.ask(buttons(f"{_cart_text(priced, charge)}\n{where} · {pay}\n\nPlace this order?",
                          [("o:place", "Place order"), ("o:start", "Change"), ("o:clear", "Cancel")]))
    return True


async def order_place(ctx: Ctx, arg: str) -> bool:
    from platform_core.services.checkout import CheckoutService

    j = ctx.j
    if not j.get("cart") or not j.get("confirmed_total"):
        if j.get("last_order"):
            await ctx.say(f"Your order {j['last_order']} is already placed.")
            return True
        return await menu(ctx)
    priced = await _price_cart(ctx, list(j["cart"]))
    if priced["problems"]:
        return await _fix_problems(ctx, priced)
    charge = Decimal(str(j.get("charge") or 0)) if j.get("mode") == "delivery" else Decimal(0)
    total = priced["subtotal"] + charge
    if total != Decimal(str(j["confirmed_total"])):
        # §12.4: prices only from LOCAH, and the customer confirms what they pay.
        ctx.save(confirmed_total=str(total))
        await ctx.ask(buttons(f"A price changed since your summary.\n{_cart_text(priced, charge)}\n\nPlace it at this total?",
                              [("o:place", "Place order"), ("o:clear", "Cancel")]))
        return True
    contact = ctx.contact
    if contact is None:
        return False
    try:
        result = await CheckoutService.place_for_contact(
            ctx.session, business=ctx.business, contact=contact,
            correlation_id=str(uuid.uuid4()), actor_context="whatsapp",
            payload={"items": [{k: v for k, v in line.items() if k in ("offering_id", "variant_id", "options",
                                                                          "quantity")} for line in j["cart"]],
                     "fulfilment_mode": j.get("mode") or "pickup", "payment_method": "cod",
                     "delivery_address": j.get("address") if j.get("mode") == "delivery" else None,
                     "idempotency_key": f"wa-{ctx.conv.id}-{j.get('cart_id')}", "channel": "whatsapp"})
    except PlatformError as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        await ctx.ask(buttons(f"That did not go through: {detail.get('message') or exc.code}.",
                              [("o:checkout", "Try again"), ("talk_to_person", "Talk to a person")]))
        return True
    from platform_core.site_urls import business_site_url

    order = result["order"]
    track = business_site_url(ctx.business.slug, f"/track/{order['id']}?token={result['tracking']['token']}")
    ctx.save(cart=None, cart_id=None, pending=None, confirmed_total=None, charge=None, address=None, mode=None,
             modes=None, last_address=None, pay=None, cat=None, last_order=order["order_number"])
    await ctx.say(f"Order {order['order_number']} placed for {_inr(order['total_amount'])}. "
                  f"{ctx.business.display_name} will confirm it here. Follow it: {track}")
    return True


async def order_clear(ctx: Ctx, arg: str) -> bool:
    ctx.save(cart=None, cart_id=None, pending=None, confirmed_total=None, charge=None, address=None, mode=None,
             step=None)
    await ctx.say("Cart cleared. Send menu any time.")
    return True


# ---------------------------------------------------------------- book
async def book_start(ctx: Ctx, arg: str) -> bool:
    services = await _bookable(ctx.session, ctx.business.id)
    if "bookings" not in ctx.live or not services:
        await ctx.say("Booking on WhatsApp is not available right now. Tap Talk to a person, or send menu.")
        return True
    ctx.conv.topic = "booking"
    ctx.save(booking_key=uuid.uuid4().hex, step=None)
    await ctx.ask(listing("What would you like to book?", "Services",
                          [(f"b:svc:{o.id}", o.title, _svc_words(o)) for o in services[:10]]))
    return True


def _svc_words(o: Offering) -> str:
    mins = (o.attributes or {}).get("duration_minutes")
    return " · ".join(x for x in (_inr(o.price_amount) if o.price_amount is not None else "",
                                  f"{mins} min" if mins else "") if x)


async def book_service(ctx: Ctx, arg: str) -> bool:
    locations = list((await ctx.session.execute(select(BusinessLocation).where(
        BusinessLocation.business_id == ctx.business.id, BusinessLocation.status == "active")
        .order_by(BusinessLocation.is_primary.desc(), BusinessLocation.name))).scalars())
    ctx.save(service=arg)
    if len(locations) > 1 and not ctx.j.get("location"):
        await ctx.ask(listing("Where?", "Locations", [(f"b:loc:{loc.id}", loc.name, "") for loc in locations[:10]]))
        return True
    if locations:
        ctx.save(location=str(locations[0].id))
    return await _days(ctx)


async def book_location(ctx: Ctx, arg: str) -> bool:
    ctx.save(location=arg)
    return await _days(ctx)


async def _days(ctx: Ctx) -> bool:
    today = datetime.now(IST).date()
    rows = []
    for d in range(8):
        day = today + timedelta(days=d)
        rows.append((f"b:day:{day.isoformat()}", "Today" if d == 0 else "Tomorrow" if d == 1 else day.strftime("%a %d %b"),
                     ""))
    await ctx.ask(listing("Which day?", "Days", rows))
    return True


def _hours_for(location: BusinessLocation, day: date) -> list[tuple[time, time]]:
    """Opening hours saved as {"mon": [["09:00", "18:00"]], ...} (Locations › Opening hours)."""
    hours = location.hours or {}
    key = day.strftime("%a").lower()[:3]
    out = []
    for span in hours.get(key) or []:
        try:
            out.append((time.fromisoformat(span[0]), time.fromisoformat(span[1])))
        except (ValueError, TypeError, IndexError):
            continue
    return out


async def _free(ctx: Ctx, service: Offering, location_id: uuid.UUID, start: datetime) -> list[str] | None:
    """The same check the website's booking page makes: None when the time is
    taken; otherwise the resource to hold (a chair, a room), or [] when the
    business allocates none."""
    from platform_core.services.availability import AvailabilityService
    from platform_core.services.booking_allocation import BookingAllocationService
    from platform_core.validation.booking import validate_availability_query

    mins = int((service.attributes or {}).get("duration_minutes") or 30)
    try:
        params = validate_availability_query({"location_id": str(location_id), "offering_id": str(service.id),
                                              "reservation_mode": "appointment", "starts_at": start.isoformat(),
                                              "ends_at": (start + timedelta(minutes=mins)).isoformat(),
                                              "party_size": 1})
        result = await AvailabilityService.check_availability(ctx.session, business_id=ctx.business.id, params=params)
    except PlatformError:
        return None
    if not result.get("available"):
        return None
    free = await BookingAllocationService.free_resources(
        ctx.session, business_id=ctx.business.id, location_id=location_id, resource_type=None,
        starts_at=params["starts_at"], ends_at=params["ends_at"], party_size=1)
    if free:
        return [str(free[0]["resource_id"])]
    if await BookingAllocationService.has_resources(ctx.session, business_id=ctx.business.id, location_id=location_id):
        return None
    return []


async def book_day(ctx: Ctx, arg: str) -> bool:
    service = await ctx.session.get(Offering, uuid.UUID(str(ctx.j.get("service"))))
    location = await ctx.session.get(BusinessLocation, uuid.UUID(str(ctx.j.get("location"))))
    if service is None or location is None:
        return await book_start(ctx, "")
    day = date.fromisoformat(arg)
    ctx.save(day=arg)
    spans = _hours_for(location, day)
    if not spans:
        ctx.save(step="time")
        await ctx.say(f"What time on {day.strftime('%a %d %b')}? Type it like 5:30 pm.")
        return True
    mins = int((service.attributes or {}).get("duration_minutes") or 30)
    step = timedelta(minutes=30 if mins <= 60 else 60)  # times on the half hour, or the hour for long ones
    earliest = datetime.now(timezone.utc) + timedelta(minutes=30)
    rows: list[tuple[str, str, str]] = []
    for open_at, close_at in spans:
        at = datetime.combine(day, open_at, IST)
        end = datetime.combine(day, close_at, IST)
        while at + timedelta(minutes=mins) <= end and len(rows) < 10:
            if at >= earliest and await _free(ctx, service, location.id, at) is not None:
                rows.append((f"b:slot:{at.astimezone(timezone.utc).isoformat()}", at.strftime("%I:%M %p").lstrip("0"), ""))
            at += step
    if not rows:
        await ctx.ask(buttons(f"No free times on {day.strftime('%a %d %b')}.",
                              [("m:book", "Another day"), ("talk_to_person", "Talk to a person")]))
        return True
    await ctx.ask(listing(f"Free times on {day.strftime('%a %d %b')}:", "Times", rows))
    return True


async def _time_typed(ctx: Ctx, said: str) -> bool:
    m = re.fullmatch(r"\s*(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?\s*", said.lower())
    if not m or not ctx.j.get("day"):
        await ctx.say("Type the time like 5:30 pm.")
        return True
    hour, minute = int(m.group(1)), int(m.group(2) or 0)
    if m.group(3) == "pm" and hour < 12:
        hour += 12
    if m.group(3) == "am" and hour == 12:
        hour = 0
    if not (0 <= hour < 24 and 0 <= minute < 60):
        await ctx.say("Type the time like 5:30 pm.")
        return True
    at = datetime.combine(date.fromisoformat(ctx.j["day"]), time(hour, minute), IST)
    ctx.save(step=None)
    return await book_slot(ctx, at.astimezone(timezone.utc).isoformat())


async def book_slot(ctx: Ctx, arg: str) -> bool:
    service = await ctx.session.get(Offering, uuid.UUID(str(ctx.j.get("service"))))
    location_id = uuid.UUID(str(ctx.j.get("location")))
    at = datetime.fromisoformat(arg)
    if service is None:
        return await book_start(ctx, "")
    if at < datetime.now(timezone.utc) or await _free(ctx, service, location_id, at) is None:
        await ctx.ask(buttons("That time is not free.", [(f"b:day:{at.astimezone(IST).date().isoformat()}", "Other times"),
                                                         ("talk_to_person", "Talk to a person")]))
        return True
    ctx.save(slot=arg)
    local = at.astimezone(IST)
    await ctx.ask(buttons(f"{service.title} on {local.strftime('%a %d %b')} at {local.strftime('%I:%M %p').lstrip('0')}."
                          " Confirm?", [("b:confirm", "Confirm"), (f"b:day:{local.date().isoformat()}", "Other time"),
                                        ("talk_to_person", "Talk to a person")]))
    return True


async def book_confirm(ctx: Ctx, arg: str) -> bool:
    from platform_core.services.booking import BookingService

    j = ctx.j
    if not (j.get("service") and j.get("slot") and j.get("location")) or ctx.contact is None:
        return await book_start(ctx, "")
    service = await ctx.session.get(Offering, uuid.UUID(str(j["service"])))
    at = datetime.fromisoformat(j["slot"])
    assert service is not None
    hold = await _free(ctx, service, uuid.UUID(str(j["location"])), at)
    if hold is None:
        return await book_slot(ctx, j["slot"])  # §12.4: re-checked at confirm, alternatives offered
    mins = int((service.attributes or {}).get("duration_minutes") or 30)
    try:
        booking = await BookingService.create_booking(
            ctx.session, business_id=ctx.business.id, actor_id=ctx.business.primary_owner_identity_id,
            correlation_id=str(uuid.uuid4()),
            payload={"location_id": str(j["location"]), "customer_contact_id": str(ctx.contact.id),
                     "offering_id": str(service.id), "reservation_mode": "appointment",
                     "starts_at": at.isoformat(), "ends_at": (at + timedelta(minutes=mins)).isoformat(),
                     "party_size": 1, "payment_method": "pay_at_business", "channel": "whatsapp",
                     "resource_ids": hold or None,
                     "idempotency_key": f"wa-{ctx.conv.id}-{j.get('booking_key')}"},
            allow_capacity_override=False)
    except PlatformError as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        await ctx.ask(buttons(f"That did not go through: {detail.get('message') or exc.code}.",
                              [("m:book", "Try again"), ("talk_to_person", "Talk to a person")]))
        return True
    local = at.astimezone(IST)
    ctx.save(service=None, slot=None, day=None, location=None, booking_key=None, step=None)
    await ctx.say(f"Booking {booking.booking_number}: {service.title} on {local.strftime('%a %d %b')} at "
                  f"{local.strftime('%I:%M %p').lstrip('0')}. "
                  + ("It's confirmed." if booking.status == "confirmed"
                     else f"{ctx.business.display_name} will confirm it here."))
    return True


# ---------------------------------------------------------------- enquire
async def enquire_start(ctx: Ctx, arg: str) -> bool:
    if "leads" not in ctx.live:
        return False
    ctx.conv.topic = "lead"
    ctx.save(step="enquiry")
    await ctx.say("What would you like to know? Type your question and we'll get back to you here.")
    return True


async def _enquiry_typed(ctx: Ctx, said: str) -> bool:
    from platform_core.services.lead import LeadService

    if len(said) < 3:
        await ctx.say("Type your question in a few words.")
        return True
    contact = ctx.contact
    await LeadService.create_lead(
        ctx.session, business_id=ctx.business.id, actor_id=ctx.business.primary_owner_identity_id,
        correlation_id=str(uuid.uuid4()), actor_context="whatsapp",
        payload={"display_name": contact.display_name if contact else f"+{ctx.conv.wa_id}",
                 "phone": f"+{ctx.conv.wa_id}", "message": said[:1000], "source": "whatsapp",
                 "origin_context": {"channel": "whatsapp", "conversation_id": str(ctx.conv.id)}})
    from platform_core.services.messaging import MessagingService

    ctx.save(step=None)
    first_wait = ctx.conv.waiting_since is None
    ctx.conv.needs_person, ctx.conv.waiting_since = True, ctx.conv.waiting_since or datetime.now(timezone.utc)
    await ctx.say(f"Thanks — {ctx.business.display_name} has your question and will reply here.")
    if first_wait:
        await MessagingService._schedule_waiting(ctx.session, ctx.conv)
    return True


# ---------------------------------------------------------------- pay / dues, track
async def dues(ctx: Ctx, arg: str) -> bool:
    from platform_core.services.invoicing import InvoiceService, share_token
    from platform_core.services.ledger import LedgerService
    from platform_core.site_urls import business_site_url

    if ctx.contact is None:
        return False
    ctx.conv.topic = "payment"
    lines = []
    acct = (await ctx.session.execute(select(LedgerAccount).where(
        LedgerAccount.business_id == ctx.business.id, LedgerAccount.customer_contact_id == ctx.contact.id))).scalars().first()
    if acct is not None and Decimal(str(acct.balance)) > 0 and "ledger" in ctx.live:
        share = await LedgerService.share(ctx.session, ctx.business.id, acct.id)
        lines.append(f"Your account: {_inr(acct.balance)} due. Details and pay: "
                     f"{business_site_url(ctx.business.slug, '/khata/' + share['token'])}")
    if "invoicing" in ctx.live:
        bills = list((await ctx.session.execute(select(InvoicingDocument).where(
            InvoicingDocument.business_id == ctx.business.id, InvoicingDocument.customer_contact_id == ctx.contact.id,
            InvoicingDocument.status == "issued", InvoicingDocument.on_account.is_(False),
            InvoicingDocument.doc_kind.in_(("tax_invoice", "bill_of_supply", "bill")),
            InvoicingDocument.amount_due > InvoicingDocument.amount_paid)
            .order_by(InvoicingDocument.issue_date).execution_options(skip_location_scope=True))).scalars())
        for b in bills[:5]:
            view = await InvoiceService._money_view(ctx.session, b)
            if view["outstanding"] > 0:
                lines.append(f"Bill {b.number}: {_inr(view['outstanding'])} — "
                             f"{business_site_url(ctx.business.slug, '/bill/' + share_token(ctx.business.id, b.id))}")
    await ctx.say("\n".join(lines) if lines else "Nothing is due. Thank you!")
    return True


async def track(ctx: Ctx, arg: str) -> bool:
    from platform_core.site_urls import business_site_url

    orders = await _open_orders(ctx)
    if not orders:
        await ctx.say("You have no open orders with us. Send menu to order.")
        return True
    ctx.conv.topic = "order"
    out = []
    for o in orders[:3]:
        job = (await ctx.session.execute(select(FulfilmentJob).where(FulfilmentJob.order_id == o.id))).scalars().first()
        link = business_site_url(ctx.business.slug, f"/track/{o.id}?token={job.tracking_token}") if job else None
        out.append(f"{o.order_number}: {STATUS_WORDS.get(o.status, o.status)}" + (f" — {link}" if link else ""))
    await ctx.say("\n".join(out))
    return True


async def reorder(ctx: Ctx, arg: str) -> bool:
    if ctx.contact is None:
        return False
    last = (await ctx.session.execute(select(SalesOrder).where(
        SalesOrder.business_id == ctx.business.id, SalesOrder.customer_contact_id == ctx.contact.id,
        SalesOrder.deleted_at.is_(None)).order_by(SalesOrder.created_at.desc()).limit(1))).scalars().first()
    if last is None:
        return await order_start(ctx, "")
    items = list((await ctx.session.execute(select(OrderLineItem).where(OrderLineItem.order_id == last.id))).scalars())
    cart = []
    for it in items:
        o = await ctx.session.get(Offering, it.offering_id) if it.offering_id else None
        if o is None or o.title == "Delivery fee" or o.status != "active":
            continue
        cart.append({"offering_id": str(o.id), "variant_id": str(it.variant_id) if getattr(it, "variant_id", None) else None,
                     "options": dict(getattr(it, "options", None) or {}), "quantity": int(it.quantity)})
    if not cart:
        await ctx.say("The items from your last order are not available now.")
        return await order_start(ctx, "")
    ctx.save(cart_id=uuid.uuid4().hex, cart=cart, pending=None)
    ctx.conv.topic = "order"
    await ctx.say(f"Your last order ({last.order_number}) again, at today's prices:")
    return await order_checkout(ctx, "")


# ---------------------------------------------------------------- change / cancel
async def cancel_start(ctx: Ctx, arg: str) -> bool:
    if ctx.contact is None:
        return False
    rows: list[tuple[str, str, str]] = []
    for o in await _open_orders(ctx):
        rows.append((f"c:order:{o.id}", f"Order {o.order_number}", STATUS_WORDS.get(o.status, o.status)))
    for b in await _upcoming_bookings(ctx):
        rows.append((f"c:booking:{b.id}", _t(b.title, 24), b.starts_at.astimezone(IST).strftime("%a %d %b, %I:%M %p")))
    if not rows:
        await ctx.say("You have nothing open to change or cancel.")
        return True
    await ctx.ask(listing("Which one?", "Choose", [*rows[:9], ("talk_to_person", "Talk to a person", "To change it")]))
    return True


async def cancel_pick(ctx: Ctx, arg: str) -> bool:
    kind, rid = arg.split(":", 1)
    ctx.save(cancel={"kind": kind, "id": rid})
    if kind == "order":
        o = await ctx.session.get(SalesOrder, uuid.UUID(rid))
        if o is None or o.customer_contact_id != (ctx.contact.id if ctx.contact else None):
            return await cancel_start(ctx, "")
        if o.status != "pending":
            await ctx.ask(buttons(f"Order {o.order_number} is already {STATUS_WORDS.get(o.status, o.status)}, so it "
                                  "can't be cancelled here.", [("talk_to_person", "Talk to a person"), ("menu", "Menu")]))
            return True
        await ctx.ask(buttons(f"Cancel order {o.order_number}?", [("c:yes", "Yes, cancel it"), ("menu", "Keep it")]))
        return True
    b = await ctx.session.get(Booking, uuid.UUID(rid))
    if b is None or b.customer_contact_id != (ctx.contact.id if ctx.contact else None):
        return await cancel_start(ctx, "")
    local = b.starts_at.astimezone(IST).strftime("%a %d %b, %I:%M %p")
    await ctx.ask(buttons(f"{b.title} on {local}.", [("c:yes", "Cancel it"), ("m:book", "Book another time"),
                                                     ("talk_to_person", "Talk to a person")]))
    return True


async def cancel_yes(ctx: Ctx, arg: str) -> bool:
    from platform_core.services.booking import BookingService
    from platform_core.services.booking_lifecycle import BookingLifecycleService
    from platform_core.services.order_lifecycle import OrderLifecycleService

    what = dict(ctx.j.get("cancel") or {})
    ctx.save(cancel=None)
    if not what:
        return await menu(ctx)
    owner = ctx.business.primary_owner_identity_id
    try:
        if what["kind"] == "order":
            o = await ctx.session.get(SalesOrder, uuid.UUID(what["id"]))
            if o is None or o.status != "pending":
                return await cancel_start(ctx, "")
            await OrderLifecycleService.transition_status(
                ctx.session, business_id=ctx.business.id, order_id=o.id, actor_id=owner,
                correlation_id=str(uuid.uuid4()), payload={"status": "cancelled",
                                                             "reason": "Cancelled by the customer on WhatsApp"})
            await ctx.say(f"Order {o.order_number} is cancelled.")
            return True
        b = await ctx.session.get(Booking, uuid.UUID(what["id"]))
        if b is None:
            return await cancel_start(ctx, "")
        policy = await BookingService.get_or_create_policy(ctx.session, ctx.business.id)
        if datetime.now(timezone.utc) > b.starts_at - timedelta(hours=policy.cancel_window_hours):
            await ctx.ask(buttons(f"It's too close to the time to cancel here ({policy.cancel_window_hours} hours' "
                                  "notice).", [("talk_to_person", "Talk to a person"), ("menu", "Menu")]))
            return True
        await BookingLifecycleService.transition_status(
            ctx.session, business_id=ctx.business.id, booking_id=b.id, actor_id=owner,
            correlation_id=str(uuid.uuid4()), payload={"status": "cancelled",
                                                         "reason": "Cancelled by the customer on WhatsApp"})
        await ctx.say(f"Your booking {b.booking_number} is cancelled.")
        return True
    except PlatformError as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        await ctx.ask(buttons(f"That did not go through: {detail.get('message') or exc.code}.",
                              [("talk_to_person", "Talk to a person")]))
        return True


ROUTES: list[tuple[str, Any]] = [
    ("m:order", order_start), ("o:start", order_start), ("o:cat", order_category), ("o:page", order_page),
    ("o:item", order_item), ("o:var", order_variant), ("o:pack", order_pack), ("o:opt", order_option),
    ("o:qty", order_qty), ("o:checkout", order_checkout), ("o:fix", order_fix), ("o:drop", order_drop),
    ("o:mode", order_mode), ("o:addr", order_address), ("o:place", order_place), ("o:clear", order_clear),
    ("m:book", book_start), ("b:svc", book_service), ("b:loc", book_location), ("b:day", book_day),
    ("b:slot", book_slot), ("b:confirm", book_confirm),
    ("m:enquire", enquire_start), ("m:pay", dues), ("m:track", track), ("m:reorder", reorder),
    ("m:cancel", cancel_start), ("c:order", lambda c, a: cancel_pick(c, "order:" + a)),
    ("c:booking", lambda c, a: cancel_pick(c, "booking:" + a)), ("c:yes", cancel_yes),
]
TEXT_STEPS: dict[str, Any] = {"qty": _qty_typed, "address": _address_typed, "time": _time_typed,
                              "enquiry": _enquiry_typed}
