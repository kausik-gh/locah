"""Employee ↔ location assignment service (Stage 3)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.gates import assert_business_mutable
from platform_core.models import BusinessEmployee, BusinessEmployeeLocationAssignment
from platform_core.resolvers.employee_resolver import EmployeeResolver
from platform_core.resolvers.location_resolver import LocationResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService


class EmployeeLocationAssignmentService:
    @staticmethod
    async def _clear_primary_assignment(
        session: AsyncSession, employee_id: uuid.UUID
    ) -> None:
        await session.execute(
            update(BusinessEmployeeLocationAssignment)
            .where(
                BusinessEmployeeLocationAssignment.employee_id == employee_id,
                BusinessEmployeeLocationAssignment.is_primary.is_(True),
            )
            .values(is_primary=False)
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
        extra_payload: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "business_id": str(business_id),
            "employee_id": str(employee.id),
            "version": employee.version,
            "after": after_state,
        }
        if extra_payload:
            payload.update(extra_payload)
        await OutboxService.publish(
            session,
            event_type=event_type,
            payload=payload,
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
    async def assign(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        employee_id: uuid.UUID,
        location_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        is_primary: bool = False,
        skip_operable_check: bool = False,
        skip_publish: bool = False,
    ) -> BusinessEmployeeLocationAssignment:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="assign_employee")

        if skip_operable_check:
            employee = await EmployeeResolver.resolve(
                session, business_id=business_id, employee_id=employee_id
            )
        else:
            employee = await EmployeeResolver.resolve_operable(
                session, business_id=business_id, employee_id=employee_id, action="assign"
            )
        await LocationResolver.resolve_active(
            session,
            business_id=business_id,
            location_id=location_id,
            action="assign_employee",
        )

        existing = await session.execute(
            select(BusinessEmployeeLocationAssignment).where(
                BusinessEmployeeLocationAssignment.employee_id == employee_id,
                BusinessEmployeeLocationAssignment.location_id == location_id,
            )
        )
        if existing.scalars().first():
            raise ConflictError(
                "Employee already assigned to location",
                details={"employee_id": str(employee_id), "location_id": str(location_id)},
            )

        if is_primary:
            await EmployeeLocationAssignmentService._clear_primary_assignment(
                session, employee_id
            )

        assignment = BusinessEmployeeLocationAssignment(
            business_id=business_id,
            employee_id=employee_id,
            location_id=location_id,
            is_primary=is_primary,
            assigned_by=actor_id,
        )
        session.add(assignment)
        await session.flush()

        if skip_publish:
            return assignment

        after = EmployeeResolver.serialize_employee(
            employee,
            assignments=await EmployeeResolver.list_assignments(
                session, business_id=business_id, employee_id=employee_id
            ),
        )
        await EmployeeLocationAssignmentService._publish(
            session,
            event_type="employee.assigned",
            audit_action="assign",
            business_id=business_id,
            employee=employee,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=None,
            after_state=after,
            extra_payload={"location_id": str(location_id), "is_primary": is_primary},
        )
        return assignment

    @staticmethod
    async def remove(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        employee_id: uuid.UUID,
        location_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
    ) -> None:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="remove_assignment")

        employee = await EmployeeResolver.resolve_operable(
            session, business_id=business_id, employee_id=employee_id, action="unassign"
        )

        result = await session.execute(
            select(BusinessEmployeeLocationAssignment).where(
                BusinessEmployeeLocationAssignment.business_id == business_id,
                BusinessEmployeeLocationAssignment.employee_id == employee_id,
                BusinessEmployeeLocationAssignment.location_id == location_id,
            )
        )
        assignment = result.scalars().first()
        if assignment is None:
            raise ResourceNotFound("Assignment")

        before = EmployeeResolver.serialize_employee(
            employee,
            assignments=await EmployeeResolver.list_assignments(
                session, business_id=business_id, employee_id=employee_id
            ),
        )
        await session.execute(
            delete(BusinessEmployeeLocationAssignment).where(
                BusinessEmployeeLocationAssignment.id == assignment.id
            )
        )
        await session.flush()

        after = EmployeeResolver.serialize_employee(
            employee,
            assignments=await EmployeeResolver.list_assignments(
                session, business_id=business_id, employee_id=employee_id
            ),
        )
        await EmployeeLocationAssignmentService._publish(
            session,
            event_type="employee.unassigned",
            audit_action="unassign",
            business_id=business_id,
            employee=employee,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state=after,
            extra_payload={"location_id": str(location_id)},
        )

    @staticmethod
    async def transfer(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        employee_id: uuid.UUID,
        from_location_id: uuid.UUID,
        to_location_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        set_primary: bool = False,
    ) -> BusinessEmployee:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="transfer_employee")

        if from_location_id == to_location_id:
            raise ValidationError(
                "Transfer source and destination must differ",
                details={
                    "errors": [
                        {
                            "field": "to_location_id",
                            "message": "Must differ from from_location_id",
                        }
                    ]
                },
            )

        employee = await EmployeeResolver.resolve_operable(
            session, business_id=business_id, employee_id=employee_id, action="transfer"
        )
        await LocationResolver.resolve_active(
            session,
            business_id=business_id,
            location_id=to_location_id,
            action="transfer_employee",
        )

        result = await session.execute(
            select(BusinessEmployeeLocationAssignment).where(
                BusinessEmployeeLocationAssignment.business_id == business_id,
                BusinessEmployeeLocationAssignment.employee_id == employee_id,
                BusinessEmployeeLocationAssignment.location_id == from_location_id,
            )
        )
        source = result.scalars().first()
        if source is None:
            raise ResourceNotFound("Assignment")

        before = EmployeeResolver.serialize_employee(
            employee,
            assignments=await EmployeeResolver.list_assignments(
                session, business_id=business_id, employee_id=employee_id
            ),
        )

        was_primary = source.is_primary or set_primary
        await session.execute(
            delete(BusinessEmployeeLocationAssignment).where(
                BusinessEmployeeLocationAssignment.id == source.id
            )
        )
        await session.flush()

        existing_dest = (
            await session.execute(
                select(BusinessEmployeeLocationAssignment).where(
                    BusinessEmployeeLocationAssignment.employee_id == employee_id,
                    BusinessEmployeeLocationAssignment.location_id == to_location_id,
                )
            )
        ).scalars().first()

        if was_primary:
            await EmployeeLocationAssignmentService._clear_primary_assignment(
                session, employee_id
            )

        if existing_dest is not None:
            # Idempotent transfer: the employee is already at the destination.
            # The source assignment has been removed; reconcile the primary flag
            # on the assignment that already exists rather than duplicating it.
            existing_dest.is_primary = was_primary
        else:
            session.add(
                BusinessEmployeeLocationAssignment(
                    business_id=business_id,
                    employee_id=employee_id,
                    location_id=to_location_id,
                    is_primary=was_primary,
                    assigned_by=actor_id,
                )
            )
        employee.version += 1
        await session.flush()

        after = EmployeeResolver.serialize_employee(
            employee,
            assignments=await EmployeeResolver.list_assignments(
                session, business_id=business_id, employee_id=employee_id
            ),
        )
        await EmployeeLocationAssignmentService._publish(
            session,
            event_type="employee.transferred",
            audit_action="transfer",
            business_id=business_id,
            employee=employee,
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state=after,
            extra_payload={
                "from_location_id": str(from_location_id),
                "to_location_id": str(to_location_id),
                "is_primary": was_primary,
            },
        )
        return employee
