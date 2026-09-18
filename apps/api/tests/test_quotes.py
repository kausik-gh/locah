"""Quotations end to end.

The assertions that matter most are the ones about history: an issued quote is a
record of what a customer was sent, and neither a catalogue price change nor a
revision may alter it.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, cast

import jwt
import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_core.db import get_database_url
from platform_core.services.quote_calculation import calculate_quote
from platform_testing.db_helpers import ensure_auth_user
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"
pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")


def _headers(user_id: uuid.UUID, email: str) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(user_id),
            "email": email,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _seed(user_id: uuid.UUID, email: str) -> None:
    async def _run() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await ensure_auth_user(session, user_id, email)
            await session.commit()
        await engine.dispose()

    asyncio.run(_run())


@pytest.fixture
def owner(monkeypatch: Any) -> dict[str, str]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed(user_id, email)
    return _headers(user_id, email)


@pytest.fixture
def stranger(monkeypatch: Any) -> dict[str, str]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed(user_id, email)
    return _headers(user_id, email)


def _business(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/v1/platform/businesses",
        json={
            "display_name": f"QuoteCo {uuid.uuid4().hex[:8]}",
            "business_type": "professional_service",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    business_id = cast(str, resp.json()["data"]["business"]["id"])
    for mid in ("offerings-catalog", "quotes", "customer-relationships"):
        enabled = client.post(f"/v1/b/{business_id}/modules/{mid}/enable", headers=headers)
        assert enabled.status_code == 200, f"{mid}: {enabled.text}"
    return business_id


def _quote(
    client: TestClient, headers: dict[str, str], business_id: str, **over: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": "Website build",
        "items": [
            {"title": "Design", "quantity": 1, "unit_price": 40000, "tax_rate": 18},
            {"title": "Build", "quantity": 2, "unit_price": 25000, "tax_rate": 18},
        ],
    }
    body.update(over)
    resp = client.post(f"/v1/platform/businesses/{business_id}/quotes", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return cast(dict[str, Any], resp.json()["data"])


# ---------------------------------------------------------------- arithmetic


def test_line_and_quote_discounts_apportion_before_tax() -> None:
    """Tax follows the price actually charged, per line.

    Applying a quote-level discount to the final total instead would tax money
    the customer never pays, and would give a different answer depending on the
    mix of tax rates across lines.
    """
    result = calculate_quote(
        lines=[
            {"quantity": 2, "unit_price": 1000, "tax_rate": 18},
            {
                "quantity": 1,
                "unit_price": 500,
                "tax_rate": 5,
                "discount_type": "percent",
                "discount_value": 10,
            },
        ],
        charges=[{"amount": 200, "taxable": True, "tax_rate": 18}],
        discount_type="percent",
        discount_value=10,
        deposit_type="percent",
        deposit_value=25,
    )
    # gross 2500, line discount 50, net 2450, quote discount 245
    # apportioned 200 / 45, so taxed on 1800 @18% and 405 @5%
    assert result["subtotal"] == Decimal("2500.00")
    assert result["discount_amount"] == Decimal("295.00")
    assert result["lines"][0]["line_tax"] == Decimal("324.00")
    assert result["lines"][1]["line_tax"] == Decimal("20.25")
    assert result["tax_amount"] == Decimal("380.25")
    assert result["total"] == Decimal("2785.25")
    assert result["deposit_amount"] == Decimal("696.31")


def test_apportioned_discount_sums_to_the_whole() -> None:
    """Rounding must not lose or invent money across lines."""
    result = calculate_quote(
        lines=[{"quantity": 1, "unit_price": 33.33, "tax_rate": 0} for _ in range(3)],
        discount_type="percent",
        discount_value=10,
    )
    assert result["total"] == Decimal("89.99")


def test_discounts_cannot_exceed_the_base() -> None:
    """A 500% discount is a typo, not free money plus change."""
    result = calculate_quote(
        lines=[{"quantity": 1, "unit_price": 100, "tax_rate": 0}],
        discount_type="percent",
        discount_value=500,
    )
    assert result["total"] == Decimal("0.00")

    flat = calculate_quote(
        lines=[{"quantity": 1, "unit_price": 100, "tax_rate": 0}],
        discount_type="amount",
        discount_value=9999,
    )
    assert flat["total"] == Decimal("0.00")


# ----------------------------------------------------------------- lifecycle


def test_create_issue_and_share(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    quote = _quote(client, owner, business_id)

    assert quote["status"] == "draft"
    assert quote["is_editable"] is True
    assert quote["quote_number"].startswith("Q-")
    assert quote["total"] == "106200.00"  # 90000 + 18%

    issued = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/issue",
        json={"valid_days": 30},
        headers=owner,
    )
    assert issued.status_code == 200, issued.text
    body = issued.json()["data"]
    assert body["status"] == "issued"
    assert body["is_editable"] is False
    token = body["share_token"]
    assert token and len(token) > 20

    page = client.get(f"/v1/public/quotes/{token}")
    assert page.status_code == 200
    assert "Website build" in page.text
    assert page.headers["x-robots-tag"].startswith("noindex")
    assert "no-store" in page.headers["cache-control"]


def test_issued_quote_cannot_be_edited(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    quote = _quote(client, owner, business_id)
    client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/issue",
        json={},
        headers=owner,
    )
    resp = client.patch(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}",
        json={"title": "Sneaky change"},
        headers=owner,
    )
    assert resp.status_code == 409, resp.text


def test_empty_quote_cannot_be_issued(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    quote = _quote(client, owner, business_id, items=[])
    resp = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/issue",
        json={},
        headers=owner,
    )
    assert resp.status_code == 422, resp.text


def test_customer_accepts_from_the_share_link(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    quote = _quote(client, owner, business_id)
    token = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/issue",
        json={},
        headers=owner,
    ).json()["data"]["share_token"]

    resp = client.post(f"/v1/public/quotes/{token}", data={"decision": "accepted"})
    assert resp.status_code == 200, resp.text

    detail = client.get(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}", headers=owner
    ).json()["data"]
    assert detail["status"] == "accepted"
    assert detail["accepted_at"] is not None


def test_a_decided_quote_cannot_be_decided_again(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    quote = _quote(client, owner, business_id)
    token = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/issue",
        json={},
        headers=owner,
    ).json()["data"]["share_token"]

    client.post(f"/v1/public/quotes/{token}", data={"decision": "accepted"})
    again = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/decision",
        json={"decision": "rejected"},
        headers=owner,
    )
    assert again.status_code == 409, again.text


def test_cancelling_kills_the_share_link(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    quote = _quote(client, owner, business_id)
    token = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/issue",
        json={},
        headers=owner,
    ).json()["data"]["share_token"]
    assert client.get(f"/v1/public/quotes/{token}").status_code == 200

    client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/cancel",
        json={"reason": "Withdrawn"},
        headers=owner,
    )
    assert client.get(f"/v1/public/quotes/{token}").status_code == 404


# ------------------------------------------------------------ history holds


def test_issued_quote_survives_a_catalogue_price_change(owner: dict[str, str]) -> None:
    """The point of snapshots. A price rise must not rewrite a sent quote."""
    client = TestClient(app)
    business_id = _business(client, owner)

    offering = client.post(
        f"/v1/platform/businesses/{business_id}/products",
        json={
            "title": f"Consulting {uuid.uuid4().hex[:6]}",
            "offering_type": "service",
            "price_amount": 10000,
        },
        headers=owner,
    )
    assert offering.status_code == 200, offering.text
    offering_id = offering.json()["data"]["id"]

    quote = _quote(
        client,
        owner,
        business_id,
        items=[{"offering_id": offering_id, "quantity": 1, "tax_rate": 0}],
    )
    assert quote["items"][0]["unit_price"] == "10000.00"
    client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/issue",
        json={},
        headers=owner,
    )

    bumped = client.patch(
        f"/v1/platform/businesses/{business_id}/products/{offering_id}",
        json={"price_amount": 99999},
        headers=owner,
    )
    assert bumped.status_code == 200, bumped.text

    after = client.get(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}", headers=owner
    ).json()["data"]
    assert after["items"][0]["unit_price"] == "10000.00", "catalogue change rewrote a sent quote"
    assert after["total"] == "10000.00"


def test_revision_supersedes_without_altering_the_original(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    quote = _quote(client, owner, business_id)
    client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/issue",
        json={},
        headers=owner,
    )
    original_total = quote["total"]

    revised = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/revise", headers=owner
    )
    assert revised.status_code == 200, revised.text
    rev = revised.json()["data"]
    assert rev["revision"] == 2
    assert rev["quote_number"] == quote["quote_number"]
    assert rev["status"] == "draft"
    assert rev["supersedes_quote_id"] == quote["id"]

    client.patch(
        f"/v1/platform/businesses/{business_id}/quotes/{rev['id']}",
        json={"items": [{"title": "Reduced scope", "quantity": 1, "unit_price": 1000}]},
        headers=owner,
    )

    original = client.get(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}", headers=owner
    ).json()["data"]
    assert original["status"] == "superseded"
    assert original["total"] == original_total, "revising rewrote the original's figures"
    assert len(original["items"]) == 2


def test_a_draft_is_edited_not_revised(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    quote = _quote(client, owner, business_id)
    resp = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/revise", headers=owner
    )
    assert resp.status_code == 409, resp.text


# --------------------------------------------------------------- expiry


def test_a_lapsed_quote_reads_as_expired_before_any_sweep(owner: dict[str, str]) -> None:
    """Readers must not be shown an offer the business is no longer bound by."""
    client = TestClient(app)
    business_id = _business(client, owner)
    quote = _quote(client, owner, business_id)
    issued = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/issue",
        json={"valid_days": 1},
        headers=owner,
    )
    token = issued.json()["data"]["share_token"]

    async def _backdate() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await session.execute(
                text("UPDATE quotes_quotes SET valid_until = now() - interval '1 day' WHERE id=:i"),
                {"i": quote["id"]},
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(_backdate())

    detail = client.get(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}", headers=owner
    ).json()["data"]
    assert detail["status"] == "expired"
    assert detail["stored_status"] == "issued", "expiry should be computed, not yet swept"

    # And the customer cannot accept it.
    resp = client.post(f"/v1/public/quotes/{token}", data={"decision": "accepted"})
    assert resp.status_code == 409, resp.text


# --------------------------------------------------------------- idempotency


def test_repeat_create_with_the_same_key_returns_one_quote(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    key = f"idem-{uuid.uuid4().hex[:10]}"
    first = _quote(client, owner, business_id, idempotency_key=key)
    second = _quote(client, owner, business_id, idempotency_key=key)
    assert first["id"] == second["id"]


def test_numbers_are_sequential_per_business(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    numbers = [_quote(client, owner, business_id)["quote_number"] for _ in range(3)]
    assert len(set(numbers)) == 3
    tails = [int(n.rsplit("-", 1)[-1]) for n in numbers]
    assert tails == sorted(tails)


# ------------------------------------------------------------------ security


def test_quotes_are_tenant_isolated(owner: dict[str, str], stranger: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    quote = _quote(client, owner, business_id)

    for resp in (
        client.get(f"/v1/platform/businesses/{business_id}/quotes", headers=stranger),
        client.get(f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}", headers=stranger),
        client.patch(
            f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}",
            json={"title": "Hijacked"},
            headers=stranger,
        ),
    ):
        assert resp.status_code in (403, 404), resp.text


def test_quote_endpoints_require_authentication(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    assert client.get(f"/v1/platform/businesses/{business_id}/quotes").status_code == 401


def test_a_bogus_share_token_is_not_found() -> None:
    client = TestClient(app)
    assert client.get("/v1/public/quotes/short").status_code == 404
    assert client.get(f"/v1/public/quotes/{'x' * 43}").status_code == 404


def test_share_page_hides_internal_notes(owner: dict[str, str]) -> None:
    """The business's private annotation must not travel with the offer."""
    client = TestClient(app)
    business_id = _business(client, owner)
    secret = f"MARGIN-NOTE-{uuid.uuid4().hex[:8]}"
    quote = _quote(client, owner, business_id, internal_notes=secret)
    token = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/issue",
        json={},
        headers=owner,
    ).json()["data"]["share_token"]

    page = client.get(f"/v1/public/quotes/{token}")
    assert secret not in page.text
    data = client.get(f"/v1/public/quotes/{token}/data").json()["data"]
    assert secret not in str(data)
    assert "internal_notes" not in data
