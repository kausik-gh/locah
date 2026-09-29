"""Projects, job cards and academics on a real local database.

These checks use the API and the platform_api role. They are skipped only when
no database URL is configured at all. Point TEST_DATABASE_URL at disposable
local Postgres; do not point it at hosted Supabase.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from platform_testing.phase_b import create_business, db_url, new_identity, primary_location

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)


def _customer(owner: dict[str, str], bid: str, name: str, identity: uuid.UUID | None = None) -> str:
    body: dict[str, Any] = {"display_name": name, "phone": f"97{uuid.uuid4().int % 10**8:08d}"}
    if identity:
        body["identity_id"] = str(identity)
    response = client.post(f"/v1/platform/businesses/{bid}/customers", json=body, headers=owner)
    assert response.status_code == 200, response.text
    return str(response.json()["data"]["id"])


def _member(owner: dict[str, str], bid: str, loc: str, name: str, identity: uuid.UUID) -> str:
    response = client.post(
        f"/v1/platform/businesses/{bid}/workforce/members",
        json={"display_name": name, "location_ids": [loc], "primary_location_id": loc, "identity_id": str(identity)},
        headers=owner,
    )
    assert response.status_code == 200, response.text
    return str(response.json()["data"]["id"])


def _join(owner: dict[str, str], bid: str, monkeypatch: Any, role: str,
          locations: list[str] | None = None) -> tuple[uuid.UUID, dict[str, str]]:
    person, headers = new_identity(monkeypatch)
    invited = client.post(
        f"/v1/b/{bid}/team/invitations",
        json={"identity_id": str(person), "role": "member"},
        headers=owner,
    )
    assert invited.status_code == 200, invited.text
    membership = invited.json()["data"]["id"]
    assert client.post(f"/v1/b/{bid}/team/members/{membership}/activate", headers=owner).status_code == 200
    given = client.put(
        f"/v1/platform/businesses/{bid}/members/{membership}/role",
        json={"role": role, "location_ids": locations or []},
        headers=owner,
    )
    assert given.status_code == 200, given.text
    return person, headers


def _on_hand(bid: str, record_id: str) -> int:
    async def run() -> int:
        engine = create_async_engine(db_url(), poolclass=NullPool)
        try:
            async with AsyncSession(engine) as session:
                value = await session.scalar(text(
                    "SELECT quantity_on_hand FROM inventory_records WHERE business_id = :b AND id = :r"
                ), {"b": bid, "r": record_id})
                return int(value)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_projects_jobs_and_academics_hold_their_boundaries(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(
        client, owner, business_type="professional_service",
        modules=("projects", "jobs", "academics", "inventory", "offerings-catalog",
                 "customer-relationships", "workforce"),
    )
    loc = primary_location(client, owner, bid)
    customer = _customer(owner, bid, "Ravi site")
    project = client.post(
        f"/v1/platform/businesses/{bid}/projects",
        json={"title": "Shop refit", "customer_contact_id": customer, "location_id": loc},
        headers=owner,
    )
    assert project.status_code == 200, project.text
    project_id = project.json()["data"]["id"]
    phase = client.post(
        f"/v1/platform/businesses/{bid}/projects/{project_id}/phases",
        json={"name": "Payment milestone", "is_milestone": True},
        headers=owner,
    )
    assert phase.status_code == 200, phase.text
    milestone = next(row for row in phase.json()["data"]["phases"] if row["name"] == "Payment milestone")
    assert milestone["is_milestone"] is True

    tech_identity, tech_headers = _join(owner, bid, monkeypatch, "technician")
    other_identity, other_headers = _join(owner, bid, monkeypatch, "technician")
    _, manager_headers = _join(owner, bid, monkeypatch, "manager", [loc])
    tech = _member(owner, bid, loc, "Arun", tech_identity)
    _member(owner, bid, loc, "Bala", other_identity)
    assigned = client.post(
        f"/v1/platform/businesses/{bid}/projects/{project_id}/phases/{milestone['id']}/assign",
        json={"responsible_member_id": tech},
        headers=owner,
    )
    assert assigned.status_code == 200, assigned.text
    assert any(row["responsible_member_id"] == tech for row in assigned.json()["data"]["phases"])

    created = client.post(f"/v1/b/{bid}/jobs", json={
        "title": "Fit the shutter", "customer_contact_id": customer, "project_id": project_id,
        "location_id": loc, "problem": "Shutter will not lock", "assigned_member_id": tech,
    }, headers=owner)
    assert created.status_code == 200, created.text
    job = created.json()["data"]
    assert job["project_id"] == project_id and job["status"] == "assigned"
    linked = client.get(f"/v1/b/{bid}/jobs", params={"project_id": project_id}, headers=owner)
    assert [row["id"] for row in linked.json()["data"]] == [job["id"]]

    illegal = client.post(f"/v1/b/{bid}/jobs/{job['id']}/move", json={
        "status": "completed", "version": job["version"],
    }, headers=owner)
    assert illegal.status_code >= 400

    started = client.post(f"/v1/b/{bid}/jobs/{job['id']}/move", json={
        "status": "in_progress", "version": job["version"], "work_performed": "Removed the old lock",
    }, headers=tech_headers)
    assert started.status_code == 200, started.text
    assert started.json()["data"]["status"] == "in_progress"
    assert client.get(f"/v1/b/{bid}/jobs/{job['id']}", headers=tech_headers).status_code == 200
    # Another technician's job card does not exist for them (as bookings and
    # tasks, and as RLS answers on the API role).
    denied = client.get(f"/v1/b/{bid}/jobs/{job['id']}", headers=other_headers)
    assert denied.status_code == 404, denied.text
    assert job["id"] not in [row["id"] for row in client.get(f"/v1/b/{bid}/jobs", headers=other_headers).json()["data"]]
    assert client.post(f"/v1/b/{bid}/jobs/{job['id']}/assign", json={"member_id": tech}, headers=tech_headers).status_code == 403
    manager_view = client.get(f"/v1/b/{bid}/jobs", headers=manager_headers)
    assert manager_view.status_code == 200
    assert job["id"] in [row["id"] for row in manager_view.json()["data"]]

    product = client.post(f"/v1/platform/businesses/{bid}/products", json={
        "title": "Shutter bolt", "status": "active", "offering_type": "product",
        "track_inventory": True, "price_amount": 120,
    }, headers=owner)
    assert product.status_code == 200, product.text
    offering_id = product.json()["data"]["id"]
    opening = client.post(f"/v1/platform/businesses/{bid}/inventory/opening-stock", json={
        "offering_id": offering_id, "location_id": loc, "quantity": 20,
    }, headers=owner)
    assert opening.status_code == 200, opening.text
    record_id = opening.json()["data"]["id"]
    assert _on_hand(bid, record_id) == 20
    first = client.post(f"/v1/b/{bid}/jobs/{job['id']}/parts", json={
        "inventory_record_id": record_id, "quantity": 3, "idempotency_key": "bolt-1",
    }, headers=tech_headers)
    assert first.status_code == 200, first.text
    assert _on_hand(bid, record_id) == 17
    replay = client.post(f"/v1/b/{bid}/jobs/{job['id']}/parts", json={
        "inventory_record_id": record_id, "quantity": 3, "idempotency_key": "bolt-1",
    }, headers=tech_headers)
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["id"] == first.json()["data"]["id"]
    assert _on_hand(bid, record_id) == 17
    second = client.post(f"/v1/b/{bid}/jobs/{job['id']}/parts", json={
        "inventory_record_id": record_id, "quantity": 2, "idempotency_key": "bolt-2",
    }, headers=tech_headers)
    assert second.status_code == 200, second.text
    assert _on_hand(bid, record_id) == 15

    _, stranger = new_identity(monkeypatch)
    other_business = create_business(client, stranger, business_type="professional_service", modules=("jobs",))
    assert client.get(f"/v1/b/{bid}/jobs/{job['id']}", headers=stranger).status_code in (403, 404)
    assert client.get(f"/v1/b/{other_business}/jobs/{job['id']}", headers=stranger).status_code in (403, 404)

    course = client.post(f"/v1/b/{bid}/academics/courses", json={"title": "Foundation maths"}, headers=owner)
    assert course.status_code == 200, course.text
    teacher_identity, teacher_headers = _join(owner, bid, monkeypatch, "teacher")
    other_teacher, other_teacher_headers = _join(owner, bid, monkeypatch, "teacher")
    teacher = _member(owner, bid, loc, "Meera", teacher_identity)
    _member(owner, bid, loc, "Nila", other_teacher)
    batch = client.post(f"/v1/b/{bid}/academics/batches", json={
        "course_id": course.json()["data"]["id"], "name": "Morning 2026",
        "teacher_member_id": teacher, "location_id": loc, "capacity": 12,
    }, headers=owner)
    assert batch.status_code == 200, batch.text
    batch_id = batch.json()["data"]["id"]
    guardian_id, guardian_headers = new_identity(monkeypatch)
    _, stranger_headers = new_identity(monkeypatch)
    student_a = _customer(owner, bid, "Asha")
    guardian = _customer(owner, bid, "Asha's parent", guardian_id)
    student_b = _customer(owner, bid, "Bharat")
    enrolled_a = client.post(f"/v1/b/{bid}/academics/batches/{batch_id}/enrolments", json={
        "student_contact_id": student_a, "guardian_contact_id": guardian, "is_minor": True,
    }, headers=owner)
    assert enrolled_a.status_code == 200, enrolled_a.text
    enrolled_b = client.post(f"/v1/b/{bid}/academics/batches/{batch_id}/enrolments", json={
        "student_contact_id": student_b,
    }, headers=owner)
    assert enrolled_b.status_code == 200, enrolled_b.text
    assert client.post(f"/v1/b/{bid}/academics/batches/{batch_id}/enrolments", json={
        "student_contact_id": student_a,
    }, headers=teacher_headers).status_code == 403
    starts = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=1)
    session = client.post(f"/v1/b/{bid}/academics/batches/{batch_id}/sessions", json={
        "starts_at": starts.isoformat(), "ends_at": (starts + timedelta(hours=1)).isoformat(),
        "topic": "Fractions",
    }, headers=teacher_headers)
    assert session.status_code == 200, session.text
    # Another teacher's batch does not exist for them (as RLS answers on the API role).
    hidden = client.get(f"/v1/b/{bid}/academics/batches/{batch_id}/sessions", headers=other_teacher_headers)
    assert hidden.status_code == 404, hidden.text
    assessment = client.post(f"/v1/b/{bid}/academics/batches/{batch_id}/assessments", json={
        "title": "Weekly test", "maximum": 20,
    }, headers=teacher_headers)
    assert assessment.status_code == 200, assessment.text
    result = client.post(
        f"/v1/b/{bid}/academics/assessments/{assessment.json()['data']['id']}/results",
        json={"enrolment_id": enrolled_a.json()["data"]["id"], "marks": 16, "teacher_note": "Steady"},
        headers=teacher_headers,
    )
    assert result.status_code == 200, result.text
    portal = client.get(f"/v1/me/academics/{bid}", headers=guardian_headers)
    assert portal.status_code == 200, portal.text
    names = [row["student_name"] for row in portal.json()["data"]]
    assert names == ["Asha"]
    assert portal.json()["data"][0]["results"][0]["marks"] == 16
    assert client.get(f"/v1/me/academics/{bid}", headers=stranger_headers).json()["data"] == []
    assert client.get(f"/v1/me/academics/{other_business}", headers=guardian_headers).json()["data"] == []

    async def isolated() -> tuple[int, int, int]:
        engine = create_async_engine(db_url(), poolclass=NullPool)
        try:
            async with AsyncSession(engine) as session:
                await session.execute(text("set local role platform_api"))
                await session.execute(text("select set_config('app.current_business_id', :b, true)"), {"b": other_business})
                foreign_jobs = await session.scalar(text("select count(*) from jobs_job_cards"))
                foreign_courses = await session.scalar(text("select count(*) from academics_courses"))
                await session.execute(text("select set_config('app.current_business_id', :b, true)"), {"b": bid})
                await session.execute(text("select set_config('app.current_assignee', :a, true)"), {"a": str(tech_identity)})
                own_jobs = await session.scalar(text("select count(*) from jobs_job_cards"))
                return int(foreign_jobs), int(foreign_courses), int(own_jobs)
        finally:
            await engine.dispose()

    assert asyncio.run(isolated()) == (0, 0, 1)


def _place(owner: dict[str, str], bid: str, name: str, role: str) -> str:
    created = client.post(f"/v1/platform/businesses/{bid}/locations", json={"name": name, "stock_role": role},
                          headers=owner)
    assert created.status_code == 200, created.text
    return str(created.json()["data"]["id"])


def _opening(owner: dict[str, str], bid: str, offering_id: str, location: str, quantity: int) -> str:
    opened = client.post(f"/v1/platform/businesses/{bid}/inventory/opening-stock", json={
        "offering_id": offering_id, "location_id": location, "quantity": quantity,
    }, headers=owner)
    assert opened.status_code == 200, opened.text
    return str(opened.json()["data"]["id"])


def test_job_parts_come_from_the_job_and_the_technicians_van_and_go_back_once(monkeypatch: Any) -> None:
    """One Inventory contract for job parts: Jobs routes through Inventory Field."""
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, business_type="professional_service",
                          modules=("jobs", "inventory", "offerings-catalog", "customer-relationships", "workforce"))
    branch = primary_location(client, owner, bid)
    van = _place(owner, bid, "Service van 1", "van")
    far = _place(owner, bid, "Far store", "store")
    customer = _customer(owner, bid, "Kannan")
    tech_identity, tech_headers = _join(owner, bid, monkeypatch, "technician")
    other_identity, other_headers = _join(owner, bid, monkeypatch, "technician")
    made = client.post(f"/v1/platform/businesses/{bid}/workforce/members", json={
        "display_name": "Arun", "location_ids": [branch, van], "primary_location_id": branch,
        "identity_id": str(tech_identity)}, headers=owner)
    assert made.status_code == 200, made.text
    tech = str(made.json()["data"]["id"])
    _member(owner, bid, branch, "Bala", other_identity)
    product = client.post(f"/v1/platform/businesses/{bid}/products", json={
        "title": "AC capacitor", "status": "active", "offering_type": "product",
        "track_inventory": True, "price_amount": 300}, headers=owner)
    assert product.status_code == 200, product.text
    item = product.json()["data"]["id"]
    at_branch = _opening(owner, bid, item, branch, 20)
    in_van = _opening(owner, bid, item, van, 4)
    at_far = _opening(owner, bid, item, far, 10)

    job = client.post(f"/v1/b/{bid}/jobs", json={
        "title": "AC not cooling", "customer_contact_id": customer, "location_id": branch,
        "assigned_member_id": tech}, headers=owner).json()["data"]
    started = client.post(f"/v1/b/{bid}/jobs/{job['id']}/move", json={
        "status": "in_progress", "version": job["version"], "work_performed": "Opened the unit"}, headers=tech_headers)
    assert started.status_code == 200, started.text
    parts = f"/v1/b/{bid}/jobs/{job['id']}/parts"

    # The technician never holds the stock book; they see the job's place and their van.
    assert client.get(f"/v1/platform/businesses/{bid}/stock", headers=tech_headers).status_code == 403
    picker = client.get(f"{parts}/stock", headers=tech_headers)
    assert picker.status_code == 200, picker.text
    assert {row["inventory_record_id"] for row in picker.json()["data"]} == {at_branch, in_van}
    owner_picker = client.get(f"{parts}/stock", headers=owner).json()["data"]
    assert {row["inventory_record_id"] for row in owner_picker} == {at_branch, in_van, at_far}
    refused = client.post(parts, json={"inventory_record_id": at_far, "quantity": 1, "idempotency_key": "far-1"},
                          headers=tech_headers)
    assert refused.status_code == 403, refused.text
    assert _on_hand(bid, at_far) == 10

    # 20 → 3 used → 17; the same key again → 17; 2 more → 15.
    first = client.post(parts, json={"inventory_record_id": at_branch, "quantity": 3, "idempotency_key": "cap-1"},
                        headers=tech_headers)
    assert first.status_code == 200, first.text
    assert _on_hand(bid, at_branch) == 17
    replay = client.post(parts, json={"inventory_record_id": at_branch, "quantity": 3, "idempotency_key": "cap-1"},
                         headers=tech_headers)
    assert replay.json()["data"]["id"] == first.json()["data"]["id"] and _on_hand(bid, at_branch) == 17
    assert client.post(parts, json={"inventory_record_id": at_branch, "quantity": 2, "idempotency_key": "cap-2"},
                       headers=tech_headers).status_code == 200
    assert _on_hand(bid, at_branch) == 15
    from_van = client.post(parts, json={"inventory_record_id": in_van, "quantity": 1, "idempotency_key": "cap-3"},
                           headers=tech_headers)
    assert from_van.status_code == 200, from_van.text
    assert _on_hand(bid, in_van) == 3

    detail = client.get(f"/v1/b/{bid}/jobs/{job['id']}", headers=tech_headers).json()["data"]
    out = {row["location_id"]: (row["quantity_out"], row["open"]) for row in detail["parts_out"]}
    assert out == {branch: (5, 5), van: (1, 1)}
    assert {p["location_id"] for p in detail["parts"]} == {branch, van}

    # Unused parts go back where they came from, once, never more than is still out.
    part = first.json()["data"]["id"]
    back = client.post(f"{parts}/{part}/return", json={"quantity": 2, "idempotency_key": "back-1"},
                       headers=tech_headers)
    assert back.status_code == 200, back.text
    assert _on_hand(bid, at_branch) == 17
    again = client.post(f"{parts}/{part}/return", json={"quantity": 2, "idempotency_key": "back-1"},
                        headers=tech_headers)
    assert again.status_code == 200 and _on_hand(bid, at_branch) == 17
    too_many = client.post(f"{parts}/{part}/return", json={"quantity": 4, "idempotency_key": "back-2"},
                           headers=tech_headers)
    assert too_many.status_code == 422, too_many.text
    assert _on_hand(bid, at_branch) == 17
    van_part = from_van.json()["data"]["id"]
    assert client.post(f"{parts}/{van_part}/return", json={"quantity": 1, "idempotency_key": "back-3"},
                       headers=tech_headers).status_code == 200
    assert _on_hand(bid, in_van) == 4
    assert client.post(f"{parts}/{part}/return", json={"quantity": 1, "idempotency_key": "back-4"},
                       headers=other_headers).status_code in (403, 404)
    detail = client.get(f"/v1/b/{bid}/jobs/{job['id']}", headers=owner).json()["data"]
    settled = {row["location_id"]: (row["quantity_out"], row["quantity_back"], row["open"])
               for row in detail["parts_out"]}
    assert settled == {branch: (5, 2, 3), van: (1, 1, 0)}

    async def returned_events() -> int:
        engine = create_async_engine(db_url(), poolclass=NullPool)
        try:
            async with AsyncSession(engine) as session:
                return int(await session.scalar(text(
                    "SELECT count(*) FROM platform_outbox_events WHERE business_id = :b "
                    "AND event_type = 'job.part.returned'"), {"b": bid}) or 0)
        finally:
            await engine.dispose()

    assert asyncio.run(returned_events()) == 2, "two returns recorded; the replayed one published nothing"
