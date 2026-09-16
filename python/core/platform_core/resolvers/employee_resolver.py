"""Employee lookup resolver (Stage 3)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ResourceNotFound, ResourceStateDenied
from platform_core.models import BusinessEmployee, BusinessEmployeeLocationAssignment


class EmployeeResolver:
    @staticmethod
    async def resolve(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        employee_id: uuid.UUID,
    ) -> BusinessEmployee:
        result = await session.execute(
            select(BusinessEmployee).where(
                BusinessEmployee.id == employee_id,
                BusinessEmployee.business_id == business_id,
                BusinessEmployee.deleted_at.is_(None),
            )
        )
        employee = result.scalars().first()
        if employee is None:
            raise ResourceNotFound("Employee")
        return employee

    @staticmethod
    def require_operable(employee: BusinessEmployee, *, action: str = "update") -> None:
        if employee.status == "archived":
            raise ResourceStateDenied(
                "employee",
                employee.status,
                action=action,
                allowed_states=["active", "inactive"],
            )

    @staticmethod
    async def resolve_operable(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        employee_id: uuid.UUID,
        action: str = "update",
    ) -> BusinessEmployee:
        employee = await EmployeeResolver.resolve(
            session, business_id=business_id, employee_id=employee_id
        )
        EmployeeResolver.require_operable(employee, action=action)
        return employee

    @staticmethod
    async def list_assignments(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        employee_id: uuid.UUID,
    ) -> list[BusinessEmployeeLocationAssignment]:
        result = await session.execute(
            select(BusinessEmployeeLocationAssignment).where(
                BusinessEmployeeLocationAssignment.business_id == business_id,
                BusinessEmployeeLocationAssignment.employee_id == employee_id,
            )
        )
        return list(result.scalars().all())

    @staticmethod
    def serialize_employee(
        employee: BusinessEmployee,
        *,
        assignments: list[BusinessEmployeeLocationAssignment] | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": str(employee.id),
            "business_id": str(employee.business_id),
            "display_name": employee.display_name,
            "email": employee.email,
            "phone": employee.phone,
            "designation": employee.designation,
            "internal_code": employee.internal_code,
            "status": employee.status,
            "notes": employee.notes,
            "identity_id": str(employee.identity_id) if employee.identity_id else None,
            "membership_id": str(employee.membership_id) if employee.membership_id else None,
            "version": employee.version,
            "created_at": employee.created_at.isoformat(),
            "updated_at": employee.updated_at.isoformat(),
        }
        if assignments is not None:
            data["location_assignments"] = [
                EmployeeResolver.serialize_assignment(a) for a in assignments
            ]
        return data

    @staticmethod
    def serialize_assignment(
        assignment: BusinessEmployeeLocationAssignment,
    ) -> dict[str, Any]:
        return {
            "id": str(assignment.id),
            "location_id": str(assignment.location_id),
            "is_primary": assignment.is_primary,
            "assigned_at": assignment.assigned_at.isoformat(),
        }
