"""Fast P5 guard tests that do not need a deployed database or external providers."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.routers.v1_jobs import CreateJob, MoveJob
from platform_api.main import app
from platform_core.exceptions import ConflictError, ValidationError
from platform_core.jobs.service import JobService, TRANSITIONS
from platform_core.services.inventory_field import InventoryFieldService
from platform_core.services.academics import _safe_url, _word


def test_jobs_are_not_projects_or_reopenable_tasks() -> None:
    assert "completed" not in TRANSITIONS["new"]
    assert "approved" in TRANSITIONS["awaiting_approval"]
    assert "in_progress" not in TRANSITIONS["awaiting_approval"]
    assert TRANSITIONS["completed"] == frozenset()
    assert TRANSITIONS["cancelled"] == frozenset()


def test_job_payload_requires_a_real_customer_and_title() -> None:
    with pytest.raises(PydanticValidationError):
        CreateJob(title="Repair compressor", customer_contact_id="not-a-uuid")
    with pytest.raises(PydanticValidationError):
        CreateJob(title="", customer_contact_id=uuid.uuid4())
    with pytest.raises(PydanticValidationError):
        MoveJob(status="completed", version=0)


def _job(status: str = "quality_check", work: str | None = "Replaced compressor") -> Any:
    return SimpleNamespace(
        status=status, version=3, assigned_member_id=uuid.uuid4(),
        work_performed=work, completed_at=None, completion_note=None, updated_at=None,
        source_quote_id=None, approval_note=None, approval_recorded_at=None,
    )


async def _move(monkeypatch: pytest.MonkeyPatch, job: Any, *, status: str,
                version: int = 3, approval_note: str | None = None) -> Any:
    monkeypatch.setattr(JobService, "resolve", AsyncMock(return_value=job))
    monkeypatch.setattr(JobService, "_record", AsyncMock())
    return await JobService.transition(
        cast(AsyncSession, object()), uuid.uuid4(), uuid.uuid4(), status,
        None, "Handed back to customer", approval_note, version, uuid.uuid4(), str(uuid.uuid4()),
    )


@pytest.mark.asyncio
async def test_job_completion_requires_work_record(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError):
        await _move(monkeypatch, _job(work=None), status="completed")


@pytest.mark.asyncio
async def test_job_rejects_stale_and_illegal_moves(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ConflictError):
        await _move(monkeypatch, _job(), status="completed", version=2)
    with pytest.raises(ValidationError):
        await _move(monkeypatch, _job(status="new"), status="completed")


@pytest.mark.asyncio
async def test_job_finishes_once_and_becomes_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    job = _job()
    result = await _move(monkeypatch, job, status="completed")
    assert result is job
    assert job.status == "completed" and job.completed_at is not None
    assert job.version == 4
    with pytest.raises(ValidationError):
        await _move(monkeypatch, job, status="in_progress", version=4)


@pytest.mark.asyncio
async def test_customer_approval_needs_recorded_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    job = _job(status="awaiting_approval")
    with pytest.raises(ValidationError):
        await _move(monkeypatch, job, status="approved")
    await _move(monkeypatch, job, status="approved", approval_note="Customer confirmed by phone")
    assert job.approval_note == "Customer confirmed by phone"
    assert job.approval_recorded_at is not None


@pytest.mark.asyncio
async def test_retrying_a_job_part_does_not_consume_stock_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    business_id, job_id, record_id, offering_id = (uuid.uuid4() for _ in range(4))
    job = _job(status="in_progress")
    job.customer_contact_id = uuid.uuid4()
    monkeypatch.setattr(JobService, "resolve", AsyncMock(return_value=job))
    monkeypatch.setattr(JobService, "_record", AsyncMock())
    movement = SimpleNamespace(id=uuid.uuid4(), business_id=business_id,
                               inventory_record_id=record_id, offering_id=offering_id)
    stock = AsyncMock(return_value=movement)
    monkeypatch.setattr(InventoryFieldService, "consume_record_for_job", stock)

    class Result:
        def __init__(self, value: Any) -> None:
            self.value = value

        def scalar_one_or_none(self) -> Any:
            return self.value

    class Session:
        info: dict[str, Any] = {}

        def __init__(self) -> None:
            self.saved: Any = None
            self.execute = AsyncMock(side_effect=self._execute)
            self.flush = AsyncMock()

        async def _execute(self, query: Any) -> Result:
            if self.saved is None:
                return Result(None)
            self.reads += 1
            return Result(self.saved if self.reads == 1 else movement)

        def add(self, row: Any) -> None:
            self.saved = row
            self.reads = 0

    session = Session()
    args: tuple[Any, ...] = (cast(AsyncSession, session), business_id, job_id, record_id, 2, [],
            "retry-1", uuid.uuid4(), str(uuid.uuid4()))
    first = await JobService.consume_part(*args)
    second = await JobService.consume_part(*args)
    assert second is first
    stock.assert_awaited_once()


def test_academic_online_links_are_https_only() -> None:
    assert _safe_url("https://meet.example.org/class") == "https://meet.example.org/class"
    for url in ("javascript:alert(1)", "http://meet.example.org/class", "data:text/html,bad"):
        with pytest.raises(ValidationError):
            _safe_url(url)


def test_academic_names_cannot_be_empty_or_unbounded() -> None:
    assert _word("  Maths  ", "course") == "Maths"
    for value in ("   ", "x" * 201):
        with pytest.raises(ValidationError):
            _word(value, "course")


def test_new_job_academic_and_guardian_routes_require_authentication() -> None:
    client = TestClient(app)
    business_id = uuid.uuid4()
    for path in (
        f"/v1/b/{business_id}/jobs",
        f"/v1/b/{business_id}/academics/courses",
        f"/v1/me/academics/{business_id}",
    ):
        assert client.get(path).status_code == 401
