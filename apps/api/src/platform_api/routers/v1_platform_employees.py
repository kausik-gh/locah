"""Platform employee APIs (Stage 3)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.exceptions import ResourceNotFound
from platform_core.permissions import (
    WORKFORCE_CREATE,
    WORKFORCE_DEACTIVATE,
    WORKFORCE_READ,
    WORKFORCE_UPDATE,
)
from platform_core.resolvers.employee_resolver import EmployeeResolver
from platform_core.services.employee import EmployeeService
from platform_core.services.employee_location_assignment import EmployeeLocationAssignmentService

router = APIRouter(prefix="/v1/platform/businesses", tags=["employees"])


class VersionedBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int | None = Field(default=None, ge=1)


class CreateEmployeeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str
    email: str | None = None
    phone: str | None = None
    designation: str | None = None
    internal_code: str | None = None
    status: str = "active"
    notes: str | None = None
    identity_id: UUID | None = None
    membership_id: UUID | None = None
    location_ids: list[UUID] = Field(default_factory=list)
    primary_location_id: UUID | None = None


class PatchEmployeeRequest(VersionedBody):
    display_name: str | None = None
    email: str | None = None
    phone: str | None = None
    designation: str | None = None
    internal_code: str | None = None
    status: str | None = None
    notes: str | None = None
    identity_id: UUID | None = None
    membership_id: UUID | None = None


class AssignLocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID
    is_primary: bool = False


class TransferEmployeeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_location_id: UUID
    to_location_id: UUID
    set_primary: bool = False


def _patch_payload(body: BaseModel) -> dict[str, Any]:
    return body.model_dump(exclude_unset=True)


@router.get("/{business_id}/employees")
async def list_employees(
    business_id: UUID,
    status: str | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=120),
    actor: BusinessActorContext = Depends(require_business_actor(WORKFORCE_READ, "workforce")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    employees = await EmployeeService.list_for_business(
        session, business_id, status=status, search=search
    )
    return {
        "data": [EmployeeService.serialize_employee(emp) for emp in employees],
        "meta": {"correlation_id": actor.request.correlation_id, "count": len(employees)},
    }


@router.post("/{business_id}/employees")
async def create_employee(
    business_id: UUID,
    body: CreateEmployeeRequest,
    actor: BusinessActorContext = Depends(require_business_actor(WORKFORCE_CREATE, "workforce")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    employee = await EmployeeService.create_employee(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(),
    )
    await session.commit()
    data = await EmployeeService.get_by_id(
        session, business_id, employee.id, include_assignments=True
    )
    return {
        "data": data,
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/employees/{employee_id}")
async def get_employee(
    business_id: UUID,
    employee_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(WORKFORCE_READ, "workforce")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await EmployeeService.get_by_id(
        session, business_id, employee_id, include_assignments=True
    )
    if data is None:
        raise ResourceNotFound("Employee")
    return {
        "data": data,
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.patch("/{business_id}/employees/{employee_id}")
async def patch_employee(
    business_id: UUID,
    employee_id: UUID,
    body: PatchEmployeeRequest,
    actor: BusinessActorContext = Depends(require_business_actor(WORKFORCE_UPDATE, "workforce")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    payload = _patch_payload(body)
    version = payload.pop("version", None)
    employee = await EmployeeService.update_employee(
        session,
        business_id=business_id,
        employee_id=employee_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=payload,
        expected_version=version,
    )
    await session.commit()
    return {
        "data": EmployeeService.serialize_employee(employee),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/employees/{employee_id}/deactivate")
async def deactivate_employee(
    business_id: UUID,
    employee_id: UUID,
    body: VersionedBody,
    actor: BusinessActorContext = Depends(require_business_actor(WORKFORCE_DEACTIVATE, "workforce")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    employee = await EmployeeService.deactivate_employee(
        session,
        business_id=business_id,
        employee_id=employee_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        expected_version=body.version,
    )
    await session.commit()
    return {
        "data": EmployeeService.serialize_employee(employee),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/employees/{employee_id}/locations")
async def list_employee_locations(
    business_id: UUID,
    employee_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(WORKFORCE_READ, "workforce")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await EmployeeResolver.resolve(session, business_id=business_id, employee_id=employee_id)
    assignments = await EmployeeResolver.list_assignments(
        session, business_id=business_id, employee_id=employee_id
    )
    return {
        "data": [EmployeeResolver.serialize_assignment(a) for a in assignments],
        "meta": {"correlation_id": actor.request.correlation_id, "count": len(assignments)},
    }


@router.post("/{business_id}/employees/{employee_id}/locations")
async def assign_employee_location(
    business_id: UUID,
    employee_id: UUID,
    body: AssignLocationRequest,
    actor: BusinessActorContext = Depends(require_business_actor(WORKFORCE_UPDATE, "workforce")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    assignment = await EmployeeLocationAssignmentService.assign(
        session,
        business_id=business_id,
        employee_id=employee_id,
        location_id=body.location_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        is_primary=body.is_primary,
    )
    await session.commit()
    return {
        "data": EmployeeResolver.serialize_assignment(assignment),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.delete("/{business_id}/employees/{employee_id}/locations/{location_id}")
async def remove_employee_location(
    business_id: UUID,
    employee_id: UUID,
    location_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(WORKFORCE_UPDATE, "workforce")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await EmployeeLocationAssignmentService.remove(
        session,
        business_id=business_id,
        employee_id=employee_id,
        location_id=location_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
    )
    await session.commit()
    return {"data": {"removed": True}, "meta": {"correlation_id": actor.request.correlation_id}}


@router.post("/{business_id}/employees/{employee_id}/transfer")
async def transfer_employee(
    business_id: UUID,
    employee_id: UUID,
    body: TransferEmployeeRequest,
    actor: BusinessActorContext = Depends(require_business_actor(WORKFORCE_UPDATE, "workforce")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    employee = await EmployeeLocationAssignmentService.transfer(
        session,
        business_id=business_id,
        employee_id=employee_id,
        from_location_id=body.from_location_id,
        to_location_id=body.to_location_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        set_primary=body.set_primary,
    )
    await session.commit()
    data = await EmployeeService.get_by_id(
        session, business_id, employee.id, include_assignments=True
    )
    return {
        "data": data,
        "meta": {"correlation_id": actor.request.correlation_id},
    }
