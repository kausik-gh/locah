"""Employee domain service (Stage 3)."""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.gates import assert_business_mutable
from platform_core.models import BusinessEmployee, BusinessEmployeeLocationAssignment, BusinessMembership
from platform_core.resolvers.employee_resolver import EmployeeResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.employee_location_assignment import EmployeeLocationAssignmentService
from platform_core.services.outbox import OutboxService
from platform_core.validation.employee import (
    validate_employee_create_payload,
    validate_employee_patch_payload,
)


class EmployeeService:
    @staticmethod
    def serialize_employee(
        employee: BusinessEmployee,
        *,
        assignments: list[BusinessEmployeeLocationAssignment] | None = None,
    ) -> dict[str, Any]:
        data = cast(dict[str, Any], EmployeeResolver.serialize_employee(employee, assignments=assignments))
        return data

    @staticmethod
    def _check_version(employee: BusinessEmployee, expected_version: int | None) -> None:
        if expected_version is None:
            return
        if employee.version != expected_version:
            raise ConflictError(
                "Stale employee version",
                details={
                    "expected_version": expected_version,
                    "current_version": employee.version,
                },
            )

    @staticmethod
    async def _publish(
        session: AsyncSession,
        *,
        event_type: str,
        audit_action: str,
        business_id: uuid.UUID,
        employee: BusinessEmployee,
        actor_id: uuid.UUID,
        correlation_id: str,
        before_state: dict[str, Any] | None,
        after_state: dict[str, Any],
    ) -> None:
        await OutboxService.publish(
            session,
            event_type=event_type,
            payload={
                "business_id": str(business_id),
                "employee_id": str(employee.id),
                "version": employee.version,
                "after": after_state,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type=event_type,
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="employee",
            resource_id=employee.id,
            action=audit_action,
            before_state=before_state,
            after_state=after_state,
        )

    @staticmethod
    async def _validate_membership_link(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        membership_id: uuid.UUID | None,
        identity_id: uuid.UUID | None,
    ) -> None:
        if membership_id is None:
            return
        result = await session.execute(
            select(BusinessMembership).where(
                BusinessMembership.id == membership_id,
                BusinessMembership.business_id == business_id,
                BusinessMembership.deleted_at.is_(None),
            )
        )
        membership = result.scalars().first()
        if membership is None:
            raise ValidationError(
                "Membership not found for business",
                details={"errors": [{"field": "membership_id", "message": "Invalid membership"}]},
            )
        if identity_id is not None and membership.identity_id != identity_id:
            raise ValidationError(
                "Identity does not match membership",
                details={
                    "errors": [
                        {
                            "field": "identity_id",
                            "message": "Must match the linked membership identity",
                        }
                    ]
                },
            )

    @staticmethod
    async def list_for_business(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        status: str | None = None,
        search: str | None = None,
    ) -> list[BusinessEmployee]:
        query = select(BusinessEmployee).where(
            BusinessEmployee.business_id == business_id,
            BusinessEmployee.deleted_at.is_(None),
        )
        if status is not None:
            query = query.where(BusinessEmployee.status == status)
        if search:
            term = f"%{search.strip()}%"
            query = query.where(BusinessEmployee.display_name.ilike(term))
        query = query.order_by(BusinessEmployee.display_name)
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(
        session: AsyncSession,
        business_id: uuid.UUID,
        employee_id: uuid.UUID,
        *,
        include_assignments: bool = False,
    ) -> dict[str, Any] | None:
        try:
            employee = await EmployeeResolver.resolve(
                session, business_id=business_id, employee_id=employee_id
            )
        except ResourceNotFound:
            return None
        assignments = None
        if include_assignments:
            assignments = await EmployeeResolver.list_assignments(
                session, business_id=business_id, employee_id=employee_id
            )
        data = cast(dict[str, Any], EmployeeResolver.serialize_employee(employee, assignments=assignments))
        return data

    @staticmethod
    async def create_employee(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> BusinessEmployee:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="create_employee")

        validated = validate_employee_create_payload(payload)
        await EmployeeService._validate_membership_link(
            session,
            business_id=business_id,
            membership_id=validated["membership_id"],
            identity_id=validated["identity_id"],
        )

        if validated["internal_code"]:
            dup = await session.execute(
                select(BusinessEmployee.id).where(
                    BusinessEmployee.business_id == business_id,
                    BusinessEmployee.internal_code == validated["internal_code"],
                    BusinessEmployee.deleted_at.is_(None),
                )
            )
            if dup.scalars().first():
                raise ConflictError(
                    "Employee internal code already exists",
                    details={"internal_code": validated["internal_code"]},
                )

        employee = BusinessEmployee(
            business_id=business_id,
            display_name=validated["display_name"],
            email=validated["email"],
            phone=validated["phone"],
            designation=validated["designation"],
            internal_code=validated["internal_code"],
            status=validated["status"],
            notes=validated["notes"],
            identity_id=validated["identity_id"],
            membership_id=validated["membership_id"],
        )
        session.add(employee)
        await session.flush()

        for loc_id in validated["location_ids"]:
            is_primary = validated["primary_location_id"] == loc_id
            await EmployeeLocationAssignmentService.assign(
                session,
                business_id=business_id,
                employee_id=employee.id,
                location_id=loc_id,
                actor_id=actor_id,
                correlation_id=correlation_id,
                is_primary=is_primary,
                skip_operable_check=True,
                skip_publish=True,
            )

        after = EmployeeResolver.serialize_employee(
            employee,
            assignments=await EmployeeResolver.list_assignments(
                session, business_id=business_id, employee_id=employee.id
            ),
        )
        await EmployeeService._publish(
            session,
            event_type="employee.created",
            audit_action="create",
            business_id=business_id,
            employee=employee,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=None,
            after_state=after,
        )
        return employee

    @staticmethod
    async def update_employee(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        employee_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
        expected_version: int | None = None,
    ) -> BusinessEmployee:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="update_employee")

        employee = await EmployeeResolver.resolve_operable(
            session, business_id=business_id, employee_id=employee_id
        )
        EmployeeService._check_version(employee, expected_version)

        patch = validate_employee_patch_payload(payload)
        if not patch:
            return employee

        if "membership_id" in patch or "identity_id" in patch:
            await EmployeeService._validate_membership_link(
                session,
                business_id=business_id,
                membership_id=patch.get("membership_id", employee.membership_id),
                identity_id=patch.get("identity_id", employee.identity_id),
            )

        if patch.get("internal_code"):
            dup = await session.execute(
                select(BusinessEmployee.id).where(
                    BusinessEmployee.business_id == business_id,
                    BusinessEmployee.internal_code == patch["internal_code"],
                    BusinessEmployee.id != employee.id,
                    BusinessEmployee.deleted_at.is_(None),
                )
            )
            if dup.scalars().first():
                raise ConflictError(
                    "Employee internal code already exists",
                    details={"internal_code": patch["internal_code"]},
                )

        before = EmployeeResolver.serialize_employee(employee)
        for key, value in patch.items():
            setattr(employee, key, value)
        employee.version += 1
        await session.flush()

        after = EmployeeResolver.serialize_employee(employee)
        await EmployeeService._publish(
            session,
            event_type="employee.updated",
            audit_action="update",
            business_id=business_id,
            employee=employee,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state=after,
        )
        return employee

    @staticmethod
    async def deactivate_employee(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        employee_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        expected_version: int | None = None,
    ) -> BusinessEmployee:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="deactivate_employee")

        employee = await EmployeeResolver.resolve_operable(
            session, business_id=business_id, employee_id=employee_id, action="deactivate"
        )
        EmployeeService._check_version(employee, expected_version)

        if employee.status == "inactive":
            return employee

        before = EmployeeResolver.serialize_employee(employee)
        employee.status = "inactive"
        employee.version += 1
        await session.flush()

        after = EmployeeResolver.serialize_employee(employee)
        await EmployeeService._publish(
            session,
            event_type="employee.deactivated",
            audit_action="deactivate",
            business_id=business_id,
            employee=employee,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state=after,
        )
        return employee
