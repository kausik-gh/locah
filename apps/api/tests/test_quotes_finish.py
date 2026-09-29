"""The rest of the quotes domain: RFQ, commercial lines, approval, views, lock, handoff.

These tests stay inside quotes. An accepted quote hands Orders, Projects,
Invoicing and Payments a contract. It does not insert their rows.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_core.db import get_database_url
from platform_testing.phase_b import new_identity
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from test_quotes import _accept_from_share, _business, _quote, _reachable_customer, _seed, _headers


@pytest.fixture
def owner(monkeypatch: Any) -> dict[str, str]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "super-secret-jwt-token-with-at-least-32-characters-long")
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed(user_id, email)
    return cast(dict[str, str], _headers(user_id, email))


@pytest.fixture
def stranger(monkeypatch: Any) -> dict[str, str]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "super-secret-jwt-token-with-at-least-32-characters-long")
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed(user_id, email)
    return cast(dict[str, str], _headers(user_id, email))

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")

QUOTE_TABLES = (
    "quotes_quotes",
    "quotes_quote_items",
    "quotes_quote_charges",
    "quotes_settings",
    "quotes_payment_plan_lines",
    "quotes_views",
    "quotes_rfq_intakes",
)


def _engine_url() -> str:
    url = get_database_url()
    assert url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return cast(str, url)


def _run(script: Any) -> Any:
    async def _go() -> Any:
        engine = create_async_engine(_engine_url(), echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as session:
                return await script(session)
        finally:
            await engine.dispose()

    return asyncio.run(_go())


def _count(table: str, business_id: str) -> int:
    async def _script(session: AsyncSession) -> int:
        return int(
            (
                await session.execute(
                    text(f"select count(*) from {table} where business_id = :b"),
                    {"b": business_id},
                )
            ).scalar_one()
        )

    return int(_run(_script))


def _join_sales(client: TestClient, owner: dict[str, str], business_id: str, monkeypatch: Any) -> dict[str, str]:
    person, headers = new_identity(monkeypatch)
    invited = client.post(
        f"/v1/b/{business_id}/team/invitations",
        json={"identity_id": str(person), "role": "member"},
        headers=owner,
    )
    assert invited.status_code == 200, invited.text
    membership_id = invited.json()["data"]["id"]
    activated = client.post(
        f"/v1/b/{business_id}/team/members/{membership_id}/activate",
        headers=owner,
    )
    assert activated.status_code == 200, activated.text
    given = client.put(
        f"/v1/platform/businesses/{business_id}/members/{membership_id}/role",
        json={"role": "sales_executive"},
        headers=owner,
    )
    assert given.status_code == 200, given.text
    return cast(dict[str, str], headers)


# ---------------------------------------------------------------- intake


def test_whatsapp_rfq_is_one_draft_and_a_replay_does_not_open_another(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    key = f"wa-{uuid.uuid4().hex}"
    body = {
        "channel": "whatsapp",
        "idempotency_key": key,
        "customer": {"name": "Meena", "phone": "9840011111"},
        "brief": "MS gate, 12 ft",
        "source_ref": "wamid.1",
        "lines": [{"title": "Main gate", "quantity": 1, "unit_price": 0}],
    }
    first = client.post(f"/v1/platform/businesses/{business_id}/quotes/intake", json=body, headers=owner)
    assert first.status_code == 200, first.text
    draft = first.json()["data"]
    assert draft["status"] == "draft"
    assert draft["source"] == "whatsapp"
    assert draft["items"][0]["unit_price"] == "0.00"

    again = client.post(f"/v1/platform/businesses/{business_id}/quotes/intake", json=body, headers=owner)
    assert again.status_code == 200, again.text
    assert again.json()["data"]["id"] == draft["id"]
    assert _count("quotes_rfq_intakes", business_id) == 1
    assert _count("quotes_quotes", business_id) == 1


def test_a_website_quote_request_opens_a_draft_and_keeps_the_lead(owner: dict[str, str]) -> None:
    client = TestClient(app)
    created = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"Steel {uuid.uuid4().hex[:6]}", "business_type": "other"},
        headers=owner,
    )
    assert created.status_code == 200, created.text
    business = created.json()["data"]["business"]
    business_id, slug = business["id"], business["slug"]
    for module in ("leads", "quotes", "customer-relationships"):
        enabled = client.post(f"/v1/b/{business_id}/modules/{module}/enable", headers=owner)
        assert enabled.status_code == 200, enabled.text
    # A fresh business is private (no public URL); its website form needs it reachable.
    assert client.post(f"/v1/b/{business_id}/marketplace/visibility", json={"visibility": "unlisted"},
                       headers=owner).status_code == 200

    sent = client.post(
        f"/v1/public/websites/{slug}/enquiries",
        json={"name": "Ravi", "phone": "9840012345", "message": "Main gate", "purpose": "quote_request"},
    )
    assert sent.status_code == 200, sent.text

    listed = client.get(f"/v1/platform/businesses/{business_id}/quotes", headers=owner)
    assert listed.status_code == 200, listed.text
    quotes = listed.json()["data"]["quotes"]
    assert len(quotes) == 1
    assert quotes[0]["source"] == "website"
    assert quotes[0]["status"] == "draft"
    leads = client.get(f"/v1/platform/businesses/{business_id}/leads", headers=owner)
    assert leads.status_code == 200, leads.text
    assert len(leads.json()["data"]) == 1


def test_a_quote_request_stays_a_lead_when_quotes_is_off(owner: dict[str, str]) -> None:
    client = TestClient(app)
    created = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"Leads only {uuid.uuid4().hex[:6]}", "business_type": "other"},
        headers=owner,
    )
    business = created.json()["data"]["business"]
    enabled = client.post(f"/v1/b/{business['id']}/modules/leads/enable", headers=owner)
    assert enabled.status_code == 200, enabled.text
    assert client.post(f"/v1/b/{business['id']}/marketplace/visibility", json={"visibility": "unlisted"},
                       headers=owner).status_code == 200
    sent = client.post(
        f"/v1/public/websites/{business['slug']}/enquiries",
        json={"name": "Ravi", "phone": "9840099999", "message": "A gate", "purpose": "quote_request"},
    )
    assert sent.status_code == 200, sent.text
    assert _count("quotes_quotes", business["id"]) == 0


# ---------------------------------------------------------------- commercial lines


def test_breaks_moq_lead_time_boq_and_size_matrix(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    quote = _quote(
        client,
        owner,
        business_id,
        items=[
            {
                "title": "Shirts",
                "quantity": 50,
                "unit_price": 500,
                "moq": 10,
                "lead_time_days": 12,
                "quantity_breaks": [
                    {"min_qty": 10, "unit_price": 450},
                    {"min_qty": 50, "unit_price": 400},
                ],
            },
            {
                "title": "Flooring",
                "line_kind": "boq",
                "boq_section": "Ground floor",
                "quantity": 20,
                "unit_price": 80,
            },
            {
                "title": "Uniforms",
                "line_kind": "size_matrix",
                "unit_price": 300,
                "size_matrix": [
                    {"size": "S", "quantity": 2},
                    {"size": "M", "quantity": 3},
                ],
            },
        ],
        payment_plan=[
            {"label": "Token", "amount_type": "percent", "amount_value": 20, "due_rule": "on_acceptance"},
            {"label": "Balance", "amount_type": "amount", "amount_value": 1000, "due_rule": "net_days", "due_days": 15},
        ],
        deposit_type="amount",
        deposit_value=2500,
    )
    by_title = {item["title"]: item for item in quote["items"]}
    assert by_title["Shirts"]["unit_price"] == "400.00"
    assert by_title["Shirts"]["lead_time_days"] == 12
    assert by_title["Shirts"]["moq"] == "10"
    assert by_title["Flooring"]["line_kind"] == "boq"
    assert by_title["Flooring"]["boq_section"] == "Ground floor"
    assert by_title["Uniforms"]["line_kind"] == "size_matrix"
    assert by_title["Uniforms"]["quantity"] == "5"
    assert len(quote["payment_plan"]) == 2

    below = client.post(
        f"/v1/platform/businesses/{business_id}/quotes",
        json={"items": [{"title": "Too few", "quantity": 2, "unit_price": 100, "moq": 5}]},
        headers=owner,
    )
    assert below.status_code == 422, below.text
    assert "below_moq" in below.text


# ---------------------------------------------------------------- discount approval and validity


def test_a_discount_over_the_executive_limit_needs_the_owner(
    owner: dict[str, str], monkeypatch: Any
) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    executive = _join_sales(client, owner, business_id, monkeypatch)
    quote = _quote(
        client,
        executive,
        business_id,
        discount_type="percent",
        discount_value=10,
        items=[{"title": "Fit-out", "quantity": 1, "unit_price": 100000}],
    )
    blocked = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/issue",
        json={},
        headers=executive,
    )
    assert blocked.status_code == 422, blocked.text
    assert "discount_approval_required" in blocked.text

    approved = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/discount-approval",
        json={"decision": "approved"},
        headers=owner,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["approval_status"] == "approved"

    issued = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/issue",
        json={},
        headers=executive,
    )
    assert issued.status_code == 200, issued.text
    assert issued.json()["data"]["status"] == "issued"

    # The owner can send their own over-limit quote without a second approval.
    own = _quote(
        client,
        owner,
        business_id,
        discount_type="percent",
        discount_value=12,
        items=[{"title": "Owner deal", "quantity": 1, "unit_price": 10000}],
    )
    owner_issue = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{own['id']}/issue",
        json={},
        headers=owner,
    )
    assert owner_issue.status_code == 200, owner_issue.text
    assert owner_issue.json()["data"]["approval_status"] == "approved"


def test_an_issued_quote_defaults_to_seven_days(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    quote = _quote(client, owner, business_id)
    issued = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/issue",
        json={},
        headers=owner,
    )
    assert issued.status_code == 200, issued.text
    until = datetime.fromisoformat(issued.json()["data"]["valid_until"])
    span = until - datetime.now(timezone.utc)
    assert timedelta(days=6, hours=20) < span < timedelta(days=7, hours=4)


# ---------------------------------------------------------------- view, accept, lock, handoff


def test_opening_a_share_link_is_counted_on_that_version(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    quote = _quote(client, owner, business_id)
    issued = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/issue",
        json={"valid_days": 14},
        headers=owner,
    )
    token = issued.json()["data"]["share_token"]
    assert client.get(f"/v1/public/quotes/{token}").status_code == 200
    assert client.get(f"/v1/public/quotes/{token}").status_code == 200
    detail = client.get(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}", headers=owner
    ).json()["data"]
    assert detail["open_count"] == 2
    assert detail["opened_at"] is not None
    assert _count("quotes_views", business_id) == 2

    revised = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/revise", headers=owner
    )
    assert revised.status_code == 200, revised.text
    revision = revised.json()["data"]
    second = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{revision['id']}/issue",
        json={"valid_days": 14},
        headers=owner,
    )
    second_token = second.json()["data"]["share_token"]
    assert client.get(f"/v1/public/quotes/{second_token}").status_code == 200
    original = client.get(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}", headers=owner
    ).json()["data"]
    opened_revision = client.get(
        f"/v1/platform/businesses/{business_id}/quotes/{revision['id']}", headers=owner
    ).json()["data"]
    assert original["open_count"] == 2
    assert original["status"] == "superseded"
    assert opened_revision["open_count"] == 1
    assert opened_revision["revision"] == 2


def test_accept_locks_prices_and_hands_a_contract_not_an_order(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    quote = _quote(
        client,
        owner,
        business_id,
        customer_contact_id=_reachable_customer(client, owner, business_id),
        deposit_type="amount",
        deposit_value=5000,
        payment_plan=[
            {"label": "Token", "amount_type": "percent", "amount_value": 20, "due_rule": "on_acceptance"},
        ],
    )
    issued = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/issue",
        json={"valid_days": 10},
        headers=owner,
    )
    token = issued.json()["data"]["share_token"]
    wrong = client.post(
        f"/v1/public/quotes/{token}",
        data={"decision": "accepted", "name": "Ravi", "code": "000000"},
    )
    assert wrong.status_code == 422, wrong.text

    accepted = _accept_from_share(client, token, quote["id"], name="Ravi")
    assert accepted.status_code == 200, accepted.text
    detail = client.get(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}", headers=owner
    ).json()["data"]
    assert detail["status"] == "accepted"
    assert detail["prices_locked"] is True
    assert detail["price_locked_at"] is not None
    assert detail["decided_by_name"] == "Ravi"
    locked_total = detail["total"]

    async def _locked(session: AsyncSession) -> None:
        with pytest.raises(DBAPIError, match="accepted quote prices are locked"):
            async with session.begin_nested():
                await session.execute(
                    text("update quotes_quotes set total = 1 where id = :id"),
                    {"id": quote["id"]},
                )
        with pytest.raises(DBAPIError, match="accepted quote prices are locked"):
            async with session.begin_nested():
                await session.execute(
                    text("update quotes_quote_items set unit_price = 1 where quote_id = :id"),
                    {"id": quote["id"]},
                )

    _run(_locked)

    revised = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/revise", headers=owner
    )
    assert revised.status_code == 409, revised.text

    orders_before = _count("orders_orders", business_id)
    projects_before = _count("projects_projects", business_id)
    invoices_before = _count("invoicing_documents", business_id)

    handed = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/conversion",
        json={"target": "order"},
        headers=owner,
    )
    assert handed.status_code == 200, handed.text
    contract = handed.json()["data"]
    assert contract["contract"] == "locah.quote.conversion.v1"
    assert contract["target"] == "order"
    assert contract["totals"]["total"] == locked_total
    assert contract["token_amount"] == "5000.00"

    again = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/conversion",
        json={"target": "order"},
        headers=owner,
    )
    assert again.status_code == 200, again.text
    assert again.json()["data"]["quote_id"] == contract["quote_id"]
    other = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/conversion",
        json={"target": "invoice"},
        headers=owner,
    )
    assert other.status_code == 409, other.text

    after = client.get(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}", headers=owner
    ).json()["data"]
    assert after["conversion_target"] == "order"
    assert after["converted_to_id"] is None
    assert after["total"] == locked_total
    assert _count("orders_orders", business_id) == orders_before
    assert _count("projects_projects", business_id) == projects_before
    assert _count("invoicing_documents", business_id) == invoices_before

    async def _events(session: AsyncSession) -> tuple[int, str | None]:
        handoffs = (
            await session.execute(
                text(
                    "select count(*) from platform_outbox_events "
                    "where event_type = 'quote.payment_handoff' and payload->>'quote_id' = :id"
                ),
                {"id": quote["id"]},
            )
        ).scalar_one()
        token_amount = (
            await session.execute(
                text(
                    "select payload->>'token_amount' from platform_outbox_events "
                    "where event_type = 'quote.payment_handoff' and payload->>'quote_id' = :id "
                    "order by created_at desc limit 1"
                ),
                {"id": quote["id"]},
            )
        ).scalar_one()
        conversions = (
            await session.execute(
                text(
                    "select count(*) from platform_outbox_events "
                    "where event_type = 'quote.conversion_requested' and payload->>'quote_id' = :id"
                ),
                {"id": quote["id"]},
            )
        ).scalar_one()
        assert int(conversions) == 1
        return int(handoffs), token_amount

    handoffs, token_amount = _run(_events)
    assert handoffs == 1
    assert token_amount == "5000.00"


# ---------------------------------------------------------------- RLS


def test_quote_rows_stay_inside_their_business(owner: dict[str, str], stranger: dict[str, str]) -> None:
    client = TestClient(app)
    business_a = _business(client, owner)
    business_b = _business(client, stranger)
    quote = _quote(
        client,
        owner,
        business_a,
        payment_plan=[{"label": "Token", "amount_type": "amount", "amount_value": 100, "due_rule": "on_acceptance"}],
    )
    settings = client.put(
        f"/v1/platform/businesses/{business_a}/quotes/settings",
        json={"executive_discount_limit_percent": 8},
        headers=owner,
    )
    assert settings.status_code == 200, settings.text
    intake = client.post(
        f"/v1/platform/businesses/{business_a}/quotes/intake",
        json={
            "channel": "whatsapp",
            "idempotency_key": f"iso-{uuid.uuid4().hex}",
            "customer": {"name": "Anita", "phone": "9840022222"},
            "brief": "Shelving",
        },
        headers=owner,
    )
    assert intake.status_code == 200, intake.text
    issued = client.post(
        f"/v1/platform/businesses/{business_a}/quotes/{quote['id']}/issue",
        json={"valid_days": 7},
        headers=owner,
    )
    assert client.get(f"/v1/public/quotes/{issued.json()['data']['share_token']}").status_code == 200
    other = _quote(client, stranger, business_b)

    async def _as_api(session: AsyncSession) -> None:
        await session.execute(text("set local role platform_api"))
        await session.execute(
            text("select set_config('app.current_business_id', :a, true)"),
            {"a": business_a},
        )
        for table in QUOTE_TABLES:
            seen = (
                await session.execute(text(f"select distinct business_id::text from {table}"))
            ).scalars().all()
            assert set(seen) <= {business_a}, table
        hidden = (
            await session.execute(
                text("select id from quotes_quotes where id = :id"),
                {"id": other["id"]},
            )
        ).all()
        assert hidden == []
        changed = await session.execute(
            text("update quotes_quotes set title = 'hijacked' where business_id = :b returning id"),
            {"b": business_b},
        )
        assert changed.all() == []
        with pytest.raises(DBAPIError, match="row-level security"):
            async with session.begin_nested():
                await session.execute(
                    text("insert into quotes_settings (business_id) values (:b)"),
                    {"b": business_b},
                )
        await session.rollback()

    async def _unbound(session: AsyncSession) -> None:
        await session.execute(text("set local role platform_api"))
        for table in QUOTE_TABLES:
            count = (await session.execute(text(f"select count(*) from {table}"))).scalar_one()
            assert int(count) == 0, table
        await session.rollback()

    _run(_as_api)
    _run(_unbound)
