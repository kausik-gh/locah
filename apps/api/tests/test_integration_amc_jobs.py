"""Integration: a covered AMC visit falling due becomes one job card.

Memberships owns the service contract and asks once per visit
(membership.service_visit_due); Jobs owns the work and opens one job card
(source service_contract); Memberships then records which job is doing the
visit. Real API, membership sweep and worker on local PostgreSQL; replays and
a second sweep add nothing.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime, time, timedelta
from typing import Any

import pytest
from platform_testing.phase_b import drain_events, sql
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from test_p2_memberships import IST, _customer, _detail, _enrol, _gym, _pay, _plan, svc

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")


def test_a_covered_visit_is_one_job_card(monkeypatch: Any) -> None:
    owner, bid, base = _gym(monkeypatch, "jobs")
    amc = _plan(owner, base, plan_kind="service_contract", price_amount=4000, duration_days=365, visits_included=2)
    e = _enrol(owner, base, amc["id"], _customer(owner, base, "Kannan"))
    _pay(owner, base, e["id"], 4000)
    first = _detail(owner, base, e["id"])["visits"][0]
    first_due = date.fromisoformat(first["due_on"])

    async def sweep(session: AsyncSession, moment: datetime) -> dict[str, Any]:
        from platform_core.memberships.sweep import sweep_business

        await session.execute(text("select set_config('app.current_business_id', :b, true)"), {"b": bid})
        swept: dict[str, Any] = await sweep_business(session, uuid.UUID(bid), now=moment)
        return swept

    when = datetime.combine(first_due - timedelta(days=3), time(10, 0), IST)
    assert svc(lambda s: sweep(s, when))["visits_due"] == 1
    drain_events(bid)
    drain_events(bid)
    jobs = sql("select id::text, title, source_id::text, customer_contact_id::text from jobs_job_cards "
               "where business_id = :b and source_type = 'service_contract'", b=bid)
    assert len(jobs) == 1, "one covered visit, one job card"
    job_id, title, source_id, _customer_id = jobs[0]
    assert source_id == first["id"] and "covered visit 1" in title
    assert _detail(owner, base, e["id"])["visits"][0]["job_ref"] == job_id, "Memberships knows the job"

    assert svc(lambda s: sweep(s, when + timedelta(hours=1)))["visits_due"] == 0
    drain_events(bid)
    assert int(sql("select count(*) from jobs_job_cards where business_id = :b", b=bid)[0][0]) == 1
