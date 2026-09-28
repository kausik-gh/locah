"""Shared primitives (Capability Universe §24 #3–#9, #12; packet P1-02).

Each primitive has an isolation test and an idempotency test (§26.3 P1-02
"done when"). Zero model calls.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from platform_core.documents import DocSpec, render_pdf
from platform_core.money import CurrencyMismatch, Money
from platform_core.services.number_series import NumberSeriesService, financial_year, format_number
from platform_testing.phase_b import (
    assert_tenant_isolated,
    create_business,
    db_url,
    drain_events,
    new_identity,
    primary_location,
    run_automation,
    sql,
)

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)
IST = ZoneInfo("Asia/Kolkata")


# ======================================================================== money (#6)
def test_money_is_integer_paise_and_exact() -> None:
    assert Money.from_decimal("199.99").minor == 19999
    assert Money.from_decimal(Decimal("0.005")).minor == 1  # half-up
    assert Money.from_decimal("12").to_decimal() == Decimal("12.00")
    with pytest.raises(TypeError):
        Money(1.5)  # type: ignore[arg-type, unused-ignore]
    with pytest.raises(TypeError):
        Money.from_decimal(1.1)  # type: ignore[arg-type, unused-ignore]
    with pytest.raises(CurrencyMismatch):
        Money(100, "INR") + Money(100, "USD")
    assert Money(12345650).format() == "₹1,23,456.50"
    assert Money(-5000).format() == "-₹50.00"
    assert Money(123456789, "USD").format() == "$1,234,567.89"
    assert Money(24000).times("0.75").minor == 18000  # 0.75 kg at ₹240/kg
    assert Money(10001).percent(9).minor == 900  # 90.009 → 90.01? no: 900.09 paise → 900
    assert Money.from_decimal("100.00").stamped() == {"amount_minor": 10000, "currency": "INR"}


def test_allocate_never_loses_a_paisa() -> None:
    for amount in (1, 7, 100, 10001, 99999):
        parts = Money(amount).allocate([1, 1, 1])
        assert sum(p.minor for p in parts) == amount
        assert max(p.minor for p in parts) - min(p.minor for p in parts) <= 1
    cgst, sgst = Money(1801).allocate([1, 1])
    assert (cgst.minor, sgst.minor) == (901, 900)


# ======================================================================== number series (#5)
def test_financial_year_and_format() -> None:
    assert financial_year(date(2026, 3, 31)) == "25-26"
    assert financial_year(date(2026, 4, 1)) == "26-27"
    assert format_number("CHN1", "26-27", 123, 6) == "CHN1/26-27/000123"
    assert format_number("", "", 7, 4) == "0007"


def _biz_row() -> uuid.UUID:
    bid = uuid.uuid4()
    owner = uuid.uuid4()
    sql("insert into auth.users (id, email) values (:id, :e)", id=owner, e=f"{owner}@example.com")
    sql("insert into businesses (id, slug, display_name, state, primary_owner_identity_id) "
        "values (:id, :s, 'NS', 'draft', :o)", id=bid, s=f"ns-{bid.hex[:10]}", o=owner)
    return bid


@DB
def test_concurrent_allocations_are_gapless_and_unique() -> None:
    bid = _biz_row()

    async def one(factory: Any) -> int:
        async with factory() as session:
            got = await NumberSeriesService.next(session, bid, series_key="invoice:TEST:R1", period="26-27",
                                                 prefix="R1")
            await asyncio.sleep(0.01)
            await session.commit()
            return int(got.value)

    async def rolled_back(factory: Any) -> None:
        async with factory() as session:
            await NumberSeriesService.next(session, bid, series_key="invoice:TEST:R1", period="26-27", prefix="R1")
            await session.rollback()  # a bill that failed must not burn a number

    async def run() -> list[int]:
        engine = create_async_engine(db_url(), poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            await rolled_back(factory)
            values = await asyncio.gather(*[one(factory) for _ in range(20)])
            await rolled_back(factory)
            return list(values)
        finally:
            await engine.dispose()

    values = asyncio.run(run())
    assert sorted(values) == list(range(1, 21))


@DB
def test_register_blocks_do_not_overlap_and_continue_the_series() -> None:
    bid = _biz_row()

    async def run() -> tuple[Any, Any, Any]:
        engine = create_async_engine(db_url(), poolclass=NullPool)
        try:
            async with AsyncSession(engine) as session:
                a = await NumberSeriesService.reserve_block(session, bid, series_key="pos:R", holder="reg-a",
                                                            period="26-27", prefix="A", size=50)
                b = await NumberSeriesService.reserve_block(session, bid, series_key="pos:R", holder="reg-b",
                                                            period="26-27", prefix="A", size=50)
                nxt = await NumberSeriesService.next(session, bid, series_key="pos:R", period="26-27", prefix="A")
                await session.commit()
                return a, b, nxt
        finally:
            await engine.dispose()

    a, b, nxt = asyncio.run(run())
    assert (a.start, a.end, b.start, b.end, nxt.value) == (1, 50, 51, 100, 101)
    assert a.number(7) == "A/26-27/000007"
    with pytest.raises(Exception):
        a.number(51)


# ======================================================================== documents (#7)
def _spec(**over: Any) -> DocSpec:
    base = dict(title="Tax invoice", issuer=["Anna Meat Stall", "GSTIN 33ABCDE1234F1Z5"], number="R1/26-27/000001",
                date="27 Sep 2026", party=["Priya"], meta=[("Place of supply", "Tamil Nadu (33)")],
                columns=["Item", "Qty", "Rate", "Amount"], rows=[["Chicken curry cut", "0.750 kg", "₹240.00", "₹180.00"]],
                totals=[("Taxable value", "₹180.00"), ("Total", "₹180.00")])
    base.update(over)
    return DocSpec(**base)  # type: ignore[arg-type, unused-ignore]


def test_rendering_is_deterministic_and_has_every_layout() -> None:
    a4 = render_pdf(_spec())
    assert a4.startswith(b"%PDF-") and a4 == render_pdf(_spec())
    for layout in ("thermal_80", "thermal_58"):
        assert render_pdf(_spec(), layout).startswith(b"%PDF-")
    assert render_pdf(_spec(status_banner="CANCELLED")) != a4


@DB
def test_document_store_dedupes_and_serves_with_its_hash(monkeypatch: Any) -> None:
    import hashlib

    from platform_core.services.documents_store import DocumentStore

    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner)
    source = uuid.uuid4()

    async def run() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        engine = create_async_engine(db_url(), poolclass=NullPool)
        try:
            async with AsyncSession(engine) as session:
                first = await DocumentStore.store(session, uuid.UUID(bid), doc_type="receipt", source_type="test",
                                                  source_id=source, spec=_spec())
                again = await DocumentStore.store(session, uuid.UUID(bid), doc_type="receipt", source_type="test",
                                                  source_id=source, spec=_spec())
                changed = await DocumentStore.store(session, uuid.UUID(bid), doc_type="receipt", source_type="test",
                                                    source_id=source, spec=_spec(status_banner="CANCELLED"))
                await session.commit()
                return first, again, changed
        finally:
            await engine.dispose()

    first, again, changed = asyncio.run(run())
    assert first["created"] and not again["created"] and again["id"] == first["id"]
    assert changed["version"] == 2
    resp = client.get(f"/v1/platform/businesses/{bid}/documents/{first['id']}", headers=owner)
    assert resp.status_code == 200 and resp.headers["content-type"] == "application/pdf"
    assert hashlib.sha256(resp.content).hexdigest() == first["sha256"] == resp.headers["x-content-sha256"]
    _, stranger = new_identity(monkeypatch)
    assert client.get(f"/v1/platform/businesses/{bid}/documents/{first['id']}", headers=stranger).status_code in (403, 404)


# ======================================================================== consent (#8)
@DB
def test_consent_grant_withdraw_regrant_keeps_history(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("customer-relationships",))
    cust = client.post(f"/v1/platform/businesses/{bid}/customers", json={"display_name": "Priya", "phone": "+919876543210"},
                       headers=owner)
    assert cust.status_code == 200, cust.text
    cid = cust.json()["data"]["id"]
    url = f"/v1/platform/businesses/{bid}/customers/{cid}/consents"
    grant = client.post(url, json={"purpose": "marketing", "channel": "whatsapp", "granted": True}, headers=owner)
    assert grant.status_code == 200, grant.text and grant.json()["data"]["changed"]
    dup = client.post(url, json={"purpose": "marketing", "channel": "whatsapp", "granted": True}, headers=owner)
    assert dup.json()["data"]["changed"] is False  # idempotent: one open grant
    client.post(url, json={"purpose": "marketing", "channel": "whatsapp", "granted": False}, headers=owner)
    client.post(url, json={"purpose": "marketing", "channel": "whatsapp", "granted": True, "source": "my_activity"},
                headers=owner)
    history = client.get(url, headers=owner).json()["data"]["history"]
    assert [h["open"] for h in history] == [True, False]
    bad = client.post(url, json={"purpose": "spam", "channel": "whatsapp", "granted": True}, headers=owner)
    assert bad.status_code == 422


# ======================================================================== usage meters (#9)
@DB
def test_meters_count_once_enforce_caps_and_alert(monkeypatch: Any) -> None:
    from platform_core.services.usage_meter import CapReached, UsageMeterService

    _, owner = new_identity(monkeypatch)
    bid = uuid.UUID(create_business(client, owner))
    cap = client.put(f"/v1/platform/businesses/{bid}/usage/whatsapp_message/cap", json={"cap": 10}, headers=owner)
    assert cap.status_code == 200, cap.text

    async def run() -> list[Any]:
        engine = create_async_engine(db_url(), poolclass=NullPool)
        out: list[Any] = []
        try:
            async with AsyncSession(engine) as session:
                out.append(await UsageMeterService.record(session, bid, "whatsapp_message", 8, idempotency_key="m1"))
                out.append(await UsageMeterService.record(session, bid, "whatsapp_message", 8, idempotency_key="m1"))
                with pytest.raises(CapReached):
                    await UsageMeterService.check(session, bid, "whatsapp_message", 3)
                out.append(await UsageMeterService.record(session, bid, "whatsapp_message", 2, idempotency_key="m2"))
                await session.commit()
        finally:
            await engine.dispose()
        return out

    first, replay, full = asyncio.run(run())
    assert first["counted"] and first["used"] == 8 and first["alerts"] == [80]
    assert replay["counted"] is False and replay["used"] == 8
    assert full["used"] == 10 and full["alerts"] == [100]
    summary = {m["resource"]: m for m in client.get(f"/v1/platform/businesses/{bid}/usage", headers=owner).json()["data"]}
    assert summary["whatsapp_message"]["used"] == 10 and summary["whatsapp_message"]["cap"] == 10
    alerts = sql("select title from platform_notifications where business_id = :b and notification_type = "
                 "'usage.cap_alert' order by created_at", b=bid)
    assert [a[0] for a in alerts] == ["WhatsApp messages: 80% of this month’s limit used",
                                      "WhatsApp messages: this month’s limit is reached"]


# ======================================================================== automation ladders (#4)
@DB
def test_low_stock_ladder_runs_once_and_is_visible(monkeypatch: Any) -> None:
    owner_id, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("offerings-catalog", "inventory"))
    loc = primary_location(client, owner, bid)
    product = client.post(f"/v1/platform/businesses/{bid}/products", json={
        "title": "Mutton curry cut", "sku": f"M-{uuid.uuid4().hex[:6]}", "track_inventory": True,
        "low_stock_threshold": 5, "status": "active", "price_amount": 750}, headers=owner).json()["data"]["id"]
    client.post(f"/v1/platform/businesses/{bid}/inventory/opening-stock",
                json={"offering_id": product, "location_id": loc, "quantity": 10}, headers=owner)
    for _ in range(2):  # twice below threshold on the same day → one alert
        r = client.post(f"/v1/platform/businesses/{bid}/inventory/adjust", json={
            "offering_id": product, "location_id": loc, "quantity_delta": -3, "reason": "Sold at counter"},
            headers=owner)
        assert r.status_code == 200, r.text
    drain_events(bid)
    steps = sql("select status from automation_steps where business_id = :b and ladder_key = 'stock.low'", b=bid)
    assert [s[0] for s in steps] == ["pending"]
    noon = datetime.now(IST).replace(hour=12, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    assert run_automation(bid, now=noon + timedelta(days=1)) == 1
    assert run_automation(bid, now=noon + timedelta(days=1)) == 0  # nothing runs twice
    notes = sql("select title from platform_notifications where business_id = :b and notification_type = "
                "'inventory.low_stock' and recipient_identity_id = :o", b=bid, o=owner_id)
    assert [n[0] for n in notes] == ["Mutton curry cut is running low"]
    feed = client.get(f"/v1/platform/businesses/{bid}/automations", headers=owner).json()["data"]
    assert [a["key"] for a in feed["automations"]] == ["stock.low", "review.request", "chat.waiting", "compliance.due",
                                                              "inventory.expiry"]
    assert feed["activity"][0]["status"] == "done" and "low" in feed["activity"][0]["outcome"]


@DB
def test_only_wired_ladders_are_offered(monkeypatch: Any) -> None:
    """Memberships are built but their renewal ladder has no step code yet (P2)
    — the owner is never shown a switch that does nothing. Booking reminders,
    order tracking, bill and khata reminders and waiting chats have steps since
    WhatsApp (P1-07); reviews have a wired request step in P1-09, but their
    unfinished module is not shown to owners yet. Compliance reminders are
    wired too, while that module is still hidden. Each shows only while its
    module is on."""
    from platform_core.automation import LADDERS, is_wired

    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("offerings-catalog", "inventory", "leads", "memberships",
                                                   "bookings", "fulfilment"))
    shown = [a["key"] for a in client.get(f"/v1/platform/businesses/{bid}/automations",
                                          headers=owner).json()["data"]["automations"]]
    assert shown == ["booking.reminder", "stock.low", "order.tracking", "review.request",
                     "lead.followup", "chat.waiting", "compliance.due", "inventory.expiry"]
    assert "membership.renewal" not in shown
    assert {k for k in LADDERS if is_wired(k)} == {"stock.low", "lead.followup", "booking.reminder", "order.tracking",
                                                   "invoice.overdue", "ledger.statement", "chat.waiting",
                                                   "review.request", "compliance.due", "inventory.expiry"}


@DB
def test_ladder_schedule_is_idempotent_quiet_hours_wait_and_off_switch_cancels(monkeypatch: Any) -> None:
    from platform_core.automation import AutomationEngine

    owner_id, owner = new_identity(monkeypatch)
    bid = uuid.UUID(create_business(client, owner, modules=("leads",)))
    lead = uuid.uuid4()
    anchor = datetime(2031, 1, 10, 3, 0, tzinfo=timezone.utc)  # 08:30 IST

    async def run() -> tuple[int, int]:
        engine = create_async_engine(db_url(), poolclass=NullPool)
        try:
            async with AsyncSession(engine) as session:
                await session.execute(text("select 1"))
                a = await AutomationEngine.schedule(session, bid, ladder_key="booking.reminder", entity_id=lead,
                                                    anchor=anchor, period_key="1")
                b = await AutomationEngine.schedule(session, bid, ladder_key="booking.reminder", entity_id=lead,
                                                    anchor=anchor, period_key="1")
                await session.commit()
                return a, b
        finally:
            await engine.dispose()

    created, again = asyncio.run(run())
    assert (created, again) == (2, 0)
    # The 2-hours-before step is due at 06:30 IST — inside quiet hours — so it waits for 8 am.
    due_two_hours = anchor - timedelta(hours=2)
    run_automation(bid, now=due_two_hours)
    rows = dict(sql("select step_key, due_at from automation_steps where business_id = :b", b=bid))
    assert rows["two_hours"].astimezone(IST).hour == 8
    off = client.patch(f"/v1/platform/businesses/{bid}/automations/booking.reminder", json={"enabled": False},
                       headers=owner)
    assert off.status_code == 200, off.text
    statuses = sql("select status, outcome from automation_steps where business_id = :b", b=bid)
    assert {s[0] for s in statuses} == {"cancelled"} and statuses[0][1] == "Switched off by the owner"


@DB
def test_lead_followup_nudges_the_team_on_the_date(monkeypatch: Any) -> None:
    owner_id, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("leads",))
    when = datetime(2031, 2, 3, 6, 0, tzinfo=timezone.utc)  # 11:30 IST
    lead = client.post(f"/v1/platform/businesses/{bid}/leads", json={
        "display_name": "Ravi (2 BHK)", "phone": "+919000000001", "next_follow_up_at": when.isoformat()},
        headers=owner)
    assert lead.status_code == 200, lead.text
    drain_events(bid)
    assert run_automation(bid, now=when + timedelta(minutes=1)) == 1
    notes = sql("select title from platform_notifications where business_id = :b and notification_type = "
                "'lead.follow_up_due'", b=bid)
    assert notes and notes[0][0] == "Follow up: Ravi (2 BHK)"


@DB
def test_lead_followup_stops_when_the_lead_moves(monkeypatch: Any) -> None:
    """Guide §6: the follow-up stops when the lead moves stage or closes."""
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, modules=("leads",))
    when = datetime(2031, 3, 3, 6, 0, tzinfo=timezone.utc)
    lead = client.post(f"/v1/platform/businesses/{bid}/leads", json={
        "display_name": "Kavya", "phone": "+919000000002", "next_follow_up_at": when.isoformat()},
        headers=owner).json()["data"]
    drain_events(bid)
    moved = client.post(f"/v1/platform/businesses/{bid}/leads/{lead['id']}/move-stage",
                        json={"status": "contacted"}, headers=owner)
    assert moved.status_code == 200, moved.text
    drain_events(bid)
    assert run_automation(bid, now=when + timedelta(minutes=1)) == 0
    steps = sql("select status, outcome from automation_steps where business_id = :b", b=bid)
    assert steps == [("cancelled", "Lead moved to contacted")]


# ======================================================================== offline sync (#12)
@DB
def test_offline_replay_is_idempotent_and_permission_checked(monkeypatch: Any) -> None:
    from platform_core.services import offline_sync

    calls: list[dict[str, Any]] = []

    @offline_sync.mutation("test.echo", permission="settings.read")
    async def echo(session: AsyncSession, ctx: Any, payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload)
        return {"echo": payload.get("n")}

    @offline_sync.mutation("test.admin", permission="business.close")
    async def admin(session: AsyncSession, ctx: Any, payload: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("must not run without permission")

    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner)
    m1 = str(uuid.uuid4())
    body = {"device_id": "pos-1", "mutations": [
        {"client_mutation_id": m1, "kind": "test.echo", "payload": {"n": 1}},
        {"client_mutation_id": str(uuid.uuid4()), "kind": "nope", "payload": {}},
    ]}
    first = client.post(f"/v1/platform/businesses/{bid}/sync", json=body, headers=owner).json()["data"]["results"]
    again = client.post(f"/v1/platform/businesses/{bid}/sync", json=body, headers=owner).json()["data"]["results"]
    assert first[0]["status"] == "applied" and first[0]["echo"] == 1
    assert first[1]["status"] == "rejected"
    assert again[0]["replayed"] is True and len(calls) == 1
    offline_sync._HANDLERS.pop("test.echo", None)
    offline_sync._HANDLERS.pop("test.admin", None)


# ======================================================================== isolation (every new table)
TABLES = {
    "automation_rules": "insert into automation_rules (business_id, ladder_key) values (:b, 'stock.low')",
    "automation_steps": ("insert into automation_steps (business_id, ladder_key, step_key, entity_type, entity_id, "
                         "idempotency_key, due_at) values (:b, 'stock.low', 'now', 'x', gen_random_uuid(), "
                         "gen_random_uuid()::text, now())"),
    "number_series": "insert into number_series (business_id, series_key) values (:b, gen_random_uuid()::text)",
    "number_series_blocks": ("insert into number_series_blocks (business_id, series_key, holder, start_value, end_value)"
                             " values (:b, 's', 'h', 1, 2)"),
    "rendered_documents": ("insert into rendered_documents (business_id, doc_type, source_type, source_id, sha256, "
                           "size_bytes, content) values (:b, 'x', 'x', gen_random_uuid(), repeat('a', 64), 1, 'x')"),
    "usage_meters": "insert into usage_meters (business_id, resource, period) values (:b, 'maps_call', '2031-01')",
    "usage_events": ("insert into usage_events (business_id, resource, period, quantity, idempotency_key) "
                     "values (:b, 'maps_call', '2031-01', 1, gen_random_uuid()::text)"),
    "offline_mutations": ("insert into offline_mutations (business_id, client_mutation_id, device_id, kind, payload, "
                          "status) values (:b, gen_random_uuid(), 'd', 'k', '{}', 'applied')"),
}


@DB
@pytest.mark.parametrize("table", sorted(TABLES))
@pytest.mark.asyncio
async def test_new_tables_are_tenant_isolated(table: str) -> None:
    async def insert(session: AsyncSession, business_id: uuid.UUID) -> None:
        await session.execute(text(TABLES[table]), {"b": business_id})

    await assert_tenant_isolated(table, insert)


@DB
@pytest.mark.asyncio
async def test_consents_table_is_tenant_isolated() -> None:
    async def insert(session: AsyncSession, business_id: uuid.UUID) -> None:
        cid = (await session.execute(text(
            "insert into customer_relationships_contacts (business_id, display_name) values (:b, 'x') returning id"),
            {"b": business_id})).scalar()
        await session.execute(text(
            "insert into customer_consents (business_id, contact_id, purpose, channel, source) "
            "values (:b, :c, 'marketing', 'whatsapp', 'test')"), {"b": business_id, "c": cid})

    await assert_tenant_isolated("customer_consents", insert)
