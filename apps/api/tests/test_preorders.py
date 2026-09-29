"""P1-10D2: dated pre-orders (MD §6.1, §21.1; Business OS Guide p.22; Founder
refinement — Orders & Customer Transactions, "Pre-orders / scheduled orders").

Pure tests pin the rules: validation, notice, next-day cutoff, festival window,
ready times, advance. Database tests take a custom cake through the website
checkout (day required, too soon refused, the advance link made on the same
order, terms kept even when the rules change later, the daily limit shared by
concurrent orders), a phone order through the same check, the WhatsApp day
step, and the owner's board and production list.
"""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal as D
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_core.exceptions import ValidationError
from platform_core.models import Offering
from platform_core.orders import preorder as po
from platform_testing.phase_b import create_business, new_identity, primary_location, sql

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)
IST = ZoneInfo("Asia/Kolkata")
CAKE_RULES = {"mode": "required", "lead_hours": 24, "ready_times": ["11:00", "17:00"], "max_days": 30,
              "advance": {"type": "percent", "value": 30}, "cancel_hours": 24}


# ---------------------------------------------------------------- pure
def test_rules_are_validated_and_only_cart_items_are_ordered_ahead() -> None:
    clean = po.clean_rules("cart", {"mode": "required", "lead_hours": "48", "cutoff": "18:00",
                                    "ready_times": ["17:00", "11:00", "17:00"], "daily_limit": 6,
                                    "advance": {"type": "fixed", "value": 500}})
    assert clean is not None
    assert clean["ready_times"] == ["11:00", "17:00"] and clean["lead_hours"] == 48 and clean["daily_limit"] == 6
    assert clean["advance"] == {"type": "fixed", "value": "500.00"}
    assert po.clean_rules("cart", {"mode": "none"}) is None
    for bad in ({"mode": "sometimes"}, {"mode": "required", "ready_times": ["5pm"]},
                {"mode": "required", "advance": {"type": "percent", "value": 120}},
                {"mode": "required", "window": {"ready_from": "2026-11-12", "ready_until": "2026-11-10"}},
                {"mode": "required", "lead_hours": 9999}):
        with pytest.raises(ValidationError):
            po.clean_rules("cart", bad)
    with pytest.raises(ValidationError):
        po.clean_rules("booking", {"mode": "required"})


def _line(rules: dict[str, Any], price: str = "1000", qty: int = 1) -> po.Line:
    o = Offering(title="Cake", preorder=rules)
    return po.Line(o, po.Rules.of(po.clean_rules("cart", rules)), qty, D(price) * qty)


def _plan(rules: dict[str, Any], now_local: datetime, **kw: Any) -> po.Plan:
    import asyncio

    return asyncio.run(po.plan(None, business_id=None, location=None, lines=[_line(rules)],
                               now=now_local.astimezone(timezone.utc), **kw))


def test_notice_cutoff_window_and_ready_times_decide_the_first_day() -> None:
    mon_10am = datetime(2026, 10, 5, 10, 0, tzinfo=IST)
    plan = _plan({"mode": "required", "lead_hours": 24, "ready_times": ["11:00", "17:00"]}, mon_10am, require=False)
    assert plan.earliest == datetime(2026, 10, 6, 11, 0, tzinfo=IST), "24 hours' notice"
    # "order by 6 pm for tomorrow": at 7 pm the first day is the day after tomorrow
    late = _plan({"mode": "required", "lead_hours": 0, "cutoff": "18:00", "ready_times": ["10:00"]},
                 datetime(2026, 10, 5, 19, 0, tzinfo=IST), require=False)
    assert late.earliest == datetime(2026, 10, 7, 10, 0, tzinfo=IST)
    early = _plan({"mode": "required", "lead_hours": 0, "cutoff": "18:00", "ready_times": ["10:00"]},
                  datetime(2026, 10, 5, 12, 0, tzinfo=IST), require=False)
    assert early.earliest == datetime(2026, 10, 6, 10, 0, tzinfo=IST)
    # a festival window: ready only 1–3 Nov
    diwali = _plan({"mode": "required", "lead_hours": 0, "ready_times": ["09:00"],
                    "window": {"ready_from": "2026-11-01", "ready_until": "2026-11-03"}, "max_days": 60},
                   mon_10am, require=False)
    assert [d["date"] for d in diwali.dates] == ["2026-11-01", "2026-11-02", "2026-11-03"]
    with pytest.raises(ValidationError, match="Choose the day"):
        _plan(CAKE_RULES, mon_10am)
    with pytest.raises(ValidationError, match="notice"):
        _plan(CAKE_RULES, mon_10am, requested=datetime(2026, 10, 5, 17, 0, tzinfo=IST))
    with pytest.raises(ValidationError, match="ready times"):
        _plan(CAKE_RULES, mon_10am, requested=datetime(2026, 10, 8, 15, 0, tzinfo=IST))
    ok = _plan(CAKE_RULES, mon_10am, requested=datetime(2026, 10, 8, 17, 0, tzinfo=IST))
    assert ok.due_at == datetime(2026, 10, 8, 17, 0, tzinfo=IST)
    assert ok.advance == D("300") and ok.terms["cancel_hours"] == 24


def test_advance_is_rounded_up_and_never_more_than_the_line() -> None:
    rules = po.Rules.of(po.clean_rules("cart", {"mode": "required", "advance": {"type": "percent", "value": 30}}))
    assert rules is not None
    assert po.advance_for(rules, 1, D("2345")) == D("704")
    fixed = po.Rules.of(po.clean_rules("cart", {"mode": "optional", "advance": {"type": "fixed", "value": 800}}))
    assert fixed is not None
    assert po.advance_for(fixed, 2, D("1000")) == D("1000")


def test_the_owner_sees_orders_by_when_they_are_wanted() -> None:
    now = datetime(2026, 10, 5, 10, 0, tzinfo=IST)
    at = lambda d, h: datetime(2026, 10, d, h, 0, tzinfo=IST)  # noqa: E731
    assert po.bucket(at(5, 9), "accepted", now, IST) == "overdue"
    assert po.bucket(at(5, 12), "accepted", now, IST) == "now"
    assert po.bucket(at(5, 12), "preparing", now, IST) == "today"
    assert po.bucket(at(5, 18), "pending", now, IST) == "today"
    assert po.bucket(at(6, 11), "pending", now, IST) == "tomorrow"
    assert po.bucket(at(9, 11), "pending", now, IST) == "later"


# ---------------------------------------------------------------- database
def _bakery(monkeypatch: Any, *modules: str) -> tuple[dict[str, str], str, str, str, dict[str, Any]]:
    monkeypatch.setenv("MESSAGING_SANDBOX", "1")
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, business_type="other", modules=(
        "offerings-catalog", "orders", "fulfilment", "payments", "customer-relationships", "messaging", "pos",
        *modules))
    base = f"/v1/platform/businesses/{bid}"
    client.put(f"{base}/pos/settings", json={"upi_vpa": "madhuram@okhdfc"}, headers=owner)
    cake = client.post(f"{base}/products", json={
        "status": "active", "offering_type": "menu_item", "title": "Custom cake", "price_amount": 1200,
        "visibility": "public", "option_groups": [
            {"name": "Flavour", "required": True, "max": 1,
             "choices": [{"label": "Chocolate", "price_delta": 0}, {"label": "Black forest", "price_delta": 200}]},
            {"name": "Weight", "required": True, "max": 1,
             "choices": [{"label": "1 kg", "price_delta": 0}, {"label": "2 kg", "price_delta": 1100}]},
            {"name": "Message on the cake", "text": True, "required": False, "max_length": 30}],
        "preorder": {**CAKE_RULES, "daily_limit": 2}}, headers=owner)
    assert cake.status_code == 200, cake.text
    assert client.post(f"/v1/b/{bid}/website/publish", headers=owner).status_code == 200
    client.post(f"/v1/b/{bid}/marketplace/visibility", json={"visibility": "unlisted"}, headers=owner)
    slug = client.get(f"/v1/b/{bid}", headers=owner).json()["data"]["slug"]
    return owner, bid, base, slug, cake.json()["data"]


CAKE_OPTS = {"choices": {"Flavour": ["Black forest"], "Weight": ["2 kg"]},
             "notes": {"Message on the cake": "Happy birthday Asha"}}


def _day(n: int) -> str:
    return (datetime.now(timezone.utc).astimezone(IST).date() + timedelta(days=n)).isoformat()


def _checkout(slug: str, cake: dict[str, Any], due: dict[str, str] | None, *, qty: int = 1, email: str = "kavya@example.com") -> Any:
    body: dict[str, Any] = {"items": [{"offering_id": cake["id"], "quantity": qty, "options": CAKE_OPTS}],
                            "fulfilment_mode": "pickup", "payment_method": "cod",
                            "guest": {"name": "Kavya", "email": email, "phone": "+919840012345"}}
    if due is not None:
        body["due"] = due
    return client.post(f"/v1/public/websites/{slug}/checkout", json=body)


@DB
def test_a_custom_cake_is_ordered_for_a_day_with_an_advance_on_the_same_order(monkeypatch: Any) -> None:
    owner, bid, base, slug, cake = _bakery(monkeypatch)
    assert cake["preorder"]["mode"] == "required"
    shown = client.get(f"/v1/public/websites/{slug}/offerings").json()["data"]["offerings"]
    [pub] = [o for o in shown if o["id"] == cake["id"]]
    assert pub["preorder"]["needed"] and pub["preorder"]["earliest_words"] and pub["preorder"]["advance"]["value"] == 30

    priced = client.post(f"/v1/public/websites/{slug}/checkout/price", json={
        "items": [{"offering_id": cake["id"], "quantity": 1, "options": CAKE_OPTS}], "fulfilment_mode": "pickup"})
    assert priced.status_code == 200, priced.text
    p = priced.json()["data"]
    assert p["lines"][0]["unit_price"] == 2500.0 and "“Happy birthday Asha”" in p["lines"][0]["title"]
    assert p["preorder"]["needed"] and p["preorder"]["advance"] == 750.0 and p["preorder"]["dates"]
    first = p["preorder"]["dates"][0]
    assert first["date"] > _day(0) or first["times"], "never earlier than the notice allows"

    missing = _checkout(slug, cake, None)
    assert missing.status_code == 422 and "Choose the day" in missing.text
    too_soon = _checkout(slug, cake, {"date": _day(0), "time": "17:00"})
    assert too_soon.status_code == 422
    assert sql("select count(*) from orders_orders where business_id = :b", b=bid) == [(0,)]
    too_long = client.post(f"/v1/public/websites/{slug}/checkout", json={
        "items": [{"offering_id": cake["id"], "quantity": 1, "options": {
            **CAKE_OPTS, "notes": {"Message on the cake": "x" * 31}}}], "fulfilment_mode": "pickup",
        "guest": {"name": "Kavya", "email": "k@example.com"}, "due": {"date": _day(3), "time": "17:00"}})
    assert too_long.status_code == 422 and "up to 30 letters" in too_long.text

    placed = _checkout(slug, cake, {"date": _day(3), "time": "17:00"})
    assert placed.status_code == 200, placed.text
    data = placed.json()["data"]
    assert data["advance"]["amount"] == 750.0 and "/pay/" in data["advance"]["path"]
    order = client.get(f"{base}/orders/{data['order']['id']}", headers=owner).json()["data"]
    assert order["preorder"] and order["advance_amount"] == 750.0
    assert datetime.fromisoformat(order["due_at"]).astimezone(IST) == datetime.combine(
        date.fromisoformat(_day(3)), time(17, 0), tzinfo=IST)
    assert order["preorder_terms"]["cancel_hours"] == 24
    due = client.get(f"{base}/collect/due", params={"source_type": "order", "source_id": order["id"]},
                     headers=owner).json()["data"]
    assert due["advance"] == 750.0 and due["total"] == 2500.0
    [link] = [r for r in sql("select purpose, amount, status from payments_requests where source_id = :o",
                              o=order["id"])]
    assert (link[0], float(link[1]), link[2]) == ("advance", 750.0, "open")

    # the owner changes the rules later: the order keeps what the customer confirmed
    client.patch(f"{base}/products/{cake['id']}", json={
        "preorder": {**CAKE_RULES, "advance": {"type": "percent", "value": 50}}, "version": cake["version"]},
        headers=owner)
    again = client.get(f"{base}/orders/{order['id']}", headers=owner).json()["data"]
    assert again["advance_amount"] == 750.0 and again["preorder_terms"]["advance"] == "750"


@DB
def test_the_daily_limit_holds_across_orders_and_channels(monkeypatch: Any) -> None:
    owner, bid, base, slug, cake = _bakery(monkeypatch)
    day = {"date": _day(4), "time": "11:00"}
    assert _checkout(slug, cake, day, qty=2, email="a@example.com").status_code == 200
    full = _checkout(slug, cake, day, email="b@example.com")
    assert full.status_code == 422 and "is full" in full.text
    priced = client.post(f"/v1/public/websites/{slug}/checkout/price", json={
        "items": [{"offering_id": cake["id"], "quantity": 1, "options": CAKE_OPTS}]}).json()["data"]
    assert [d["full"] for d in priced["preorder"]["dates"] if d["date"] == day["date"]] == [True]
    # a phone order goes through the same check
    loc = primary_location(client, owner, bid)
    phone = client.post(f"{base}/orders", json={
        "location_id": loc, "payment_method": "pay_at_business", "channel": "phone",
        "items": [{"offering_id": cake["id"], "quantity": 1, "options": CAKE_OPTS}],
        "due_at": datetime.combine(date.fromisoformat(day["date"]), time(11, 0), tzinfo=IST).isoformat()},
        headers=owner)
    assert phone.status_code == 422 and "is full" in phone.text
    soon = client.post(f"{base}/orders", json={
        "location_id": loc, "payment_method": "pay_at_business", "channel": "phone",
        "items": [{"offering_id": cake["id"], "quantity": 1, "options": CAKE_OPTS}]}, headers=owner)
    assert soon.status_code == 422 and "Choose the day" in soon.text
    ok = client.post(f"{base}/orders", json={
        "location_id": loc, "payment_method": "pay_at_business", "channel": "phone",
        "items": [{"offering_id": cake["id"], "quantity": 1, "options": CAKE_OPTS}],
        "due_at": datetime.combine(date.fromisoformat(_day(5)), time(17, 0), tzinfo=IST).isoformat()}, headers=owner)
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["advance_amount"] == 750.0


@DB
def test_the_board_and_the_production_list(monkeypatch: Any) -> None:
    owner, bid, base, slug, cake = _bakery(monkeypatch)
    a = _checkout(slug, cake, {"date": _day(1), "time": "17:00"}, email="a@example.com").json()["data"]
    b = _checkout(slug, cake, {"date": _day(1), "time": "17:00"}, email="b@example.com").json()["data"]
    later = _checkout(slug, cake, {"date": _day(6), "time": "11:00"}, email="c@example.com").json()["data"]
    # an order already wanted in the past (taken before the rules applied) shows as overdue
    sql("update orders_orders set due_at = now() - interval '2 hours' where id = :o", o=later["order"]["id"])
    board = client.get(f"{base}/orders/board", headers=owner).json()["data"]
    by = {bk["key"]: [o["order_number"] for o in bk["orders"]] for bk in board["buckets"]}
    tomorrow = [a["order"]["order_number"], b["order"]["order_number"]]
    if datetime.now(timezone.utc).astimezone(IST).hour >= 14:  # tomorrow 5 pm is within the day anyway
        assert sorted(by["tomorrow"]) == sorted(tomorrow)
    assert by["overdue"] == [later["order"]["order_number"]]
    card = next(o for bk in board["buckets"] for o in bk["orders"] if o["order_number"] == tomorrow[0])
    assert card["advance"] == 750.0 and card["advance_state"] == "awaited"
    assert card["items"][0]["notes"] == {"Message on the cake": "Happy birthday Asha"}
    prod = client.get(f"{base}/orders/production", params={"date": _day(1)}, headers=owner).json()["data"]
    assert prod["orders"] == 2 and len(prod["items"]) == 1
    row = prod["items"][0]
    assert row["quantity"] == 2 and "Black forest" in row["item"] and "“" not in row["item"]
    assert [n["text"] for n in row["notes"]] == ["Happy birthday Asha", "Happy birthday Asha"]
    channel = client.get(f"{base}/orders", params={"channel": "web"}, headers=owner).json()["data"]
    assert len(channel) == 3 and client.get(f"{base}/orders", params={"channel": "whatsapp"},
                                            headers=owner).json()["data"] == []


@DB
def test_whatsapp_asks_the_day_and_sends_the_advance_link(monkeypatch: Any) -> None:
    from test_journeys import Phone  # the sandbox customer's phone

    owner, bid, base, slug, cake = _bakery(monkeypatch)
    client.post(f"{base}/messaging/channel/sandbox", json={"display_phone": "+919840011111"}, headers=owner)
    phone = Phone(owner, bid)
    phone.say("order")
    if f"o:item:{cake['id']}" not in phone.options():
        phone.tap(next(k for k in phone.options() if k.startswith("o:cat")))
    phone.tap(f"o:item:{cake['id']}")
    phone.tap(next(k for k, v in phone.options().items() if v.startswith("Black forest")))
    phone.tap(next(k for k, v in phone.options().items() if v.startswith("2 kg")))
    assert "type the message on the cake" in phone.last()[0]
    phone.say("Happy birthday Asha")
    phone.tap("o:qty:1")
    phone.tap("o:checkout")
    assert "When do you need it?" in phone.last()[0]
    days = [k for k in phone.options() if k.startswith("o:due:")]
    assert days and "o:due:-" not in days, "a made-to-order cake needs a day"
    phone.tap(days[0])
    times = [k for k in phone.options() if k.startswith("o:dtime:")]
    if times:
        phone.tap(times[-1])
    summary = phone.last()[0]
    assert "Ready:" in summary and "Advance ₹750" in summary and "Happy birthday Asha" in summary
    phone.tap("o:place")
    said = " ".join(phone.last(2))
    assert "placed for ₹2,500" in said and "advance here:" in said and "/pay/" in said
    order = sql("select channel, preorder, advance_amount from orders_orders where business_id = :b", b=bid)
    assert order == [("whatsapp", True, D("750.00"))]


def test_a_pre_order_can_be_cancelled_by_the_customer_until_its_notice() -> None:
    from platform_core.messaging.journeys import _why_not_cancel
    from platform_core.models import SalesOrder

    now = datetime.now(timezone.utc)
    far = SalesOrder(order_number="ORD-1", status="accepted", due_at=now + timedelta(days=3),
                     preorder_terms={"cancel_hours": 24})
    assert _why_not_cancel(far) is None, "an accepted pre-order three days out can still be cancelled"
    near = SalesOrder(order_number="ORD-2", status="accepted", due_at=now + timedelta(hours=10),
                      preorder_terms={"cancel_hours": 24})
    assert "too close to the day" in (_why_not_cancel(near) or "")
    baking = SalesOrder(order_number="ORD-3", status="preparing", due_at=now + timedelta(days=3),
                        preorder_terms={"cancel_hours": 24})
    assert "can't be cancelled here" in (_why_not_cancel(baking) or "")
    plain = SalesOrder(order_number="ORD-4", status="accepted", due_at=None, preorder_terms={})
    assert "can't be cancelled here" in (_why_not_cancel(plain) or ""), "an ordinary order: only while waiting"


@DB
def test_cancelling_a_paid_pre_order_shows_a_refund_due_until_refunded(monkeypatch: Any) -> None:
    owner, bid, base, slug, cake = _bakery(monkeypatch)
    data = _checkout(slug, cake, {"date": _day(3), "time": "17:00"}).json()["data"]
    token = data["advance"]["path"].rsplit("/", 1)[1]
    client.post(f"/v1/public/websites/{slug}/pay/{token}/paid", json={})
    [attempt] = [r[0] for r in sql("select id from payments_payment_attempts where request_id = :r",
                                   r=data["advance"]["request_id"])]
    client.post(f"{base}/collect/payments/{attempt}/confirm", json={"arrived": True}, headers=owner)
    r = client.post(f"{base}/orders/{data['order']['id']}/cancel", json={"reason": "Customer called to cancel"},
                    headers=owner)
    assert r.status_code == 200, r.text
    attention = client.get(f"{base}/collect/overview", headers=owner).json()["data"]["needs_attention"]
    assert [(a["id"], a["attention"], a["amount"]) for a in attention] == [(str(attempt), "refund_due", 750.0)]
    refund = client.post(f"{base}/payments/{attempt}/refunds", json={"amount": 750, "reason": "Order cancelled"},
                         headers=owner)
    assert refund.status_code == 200, refund.text
    assert client.get(f"{base}/collect/overview", headers=owner).json()["data"]["needs_attention"] == []
    assert sql("select payment_status from orders_orders where id = :o", o=data["order"]["id"]) == [("refunded",)]
