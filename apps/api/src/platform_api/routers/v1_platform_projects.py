"""Projects and work orders for the business side.

Lifecycle is separated from editing at the permission level: scoping a project
and declaring it finished are different authorities, and a coordinator who
allocates work should not need the second to do the first.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.business_type_profiles.registry import BusinessTypeProfileRegistry
from platform_core.permissions import (
    PROJECTS_ASSIGN,
    PROJECTS_CREATE,
    PROJECTS_MANAGE_LIFECYCLE,
    PROJECTS_READ,
    PROJECTS_UPDATE,
)
from platform_core.services.business import BusinessService
from platform_core.services.project import ProjectService

router = APIRouter(prefix="/v1/platform/businesses", tags=["projects"])


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    summary: str | None = None
    internal_notes: str | None = None
    customer_contact_id: UUID | None = None
    location_id: UUID | None = None
    lead_member_id: UUID | None = None
    priority: str = "normal"
    starts_on: str | None = None
    due_on: str | None = None
    # Omitted entirely means "seed from the Business-Type Profile"; an explicit
    # empty list means "no stages", which is a real choice for a one-visit job.
    phases: list[str] | None = Field(default=None, max_length=40)


class UpdateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, max_length=200)
    summary: str | None = None
    internal_notes: str | None = None
    customer_contact_id: UUID | None = None
    lead_member_id: UUID | None = None
    priority: str | None = None
    starts_on: str | None = None
    due_on: str | None = None


class StatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    reason: str | None = None


class ConvertQuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)
    starts_on: str | None = None
    due_on: str | None = None
    lead_member_id: UUID | None = None


class PhaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=120)
    status: str | None = None
    is_milestone: bool | None = None
    due_on: str | None = None


class TaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, max_length=200)
    description: str | None = None
    status: str | None = None
    phase_id: UUID | None = None
    assignee_member_id: UUID | None = None
    due_on: str | None = None
    blocked_reason: str | None = None


def _meta(actor: BusinessActorContext, **extra: Any) -> dict[str, Any]:
    return {"correlation_id": actor.request.correlation_id, **extra}


@router.get("/{business_id}/projects")
async def list_projects(
    business_id: UUID,
    status: str | None = Query(default=None),
    customer_contact_id: UUID | None = Query(default=None),
    assignee_member_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    actor: BusinessActorContext = Depends(require_business_actor(PROJECTS_READ, "projects")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    projects = await ProjectService.list_projects(
        session,
        business_id=business_id,
        status=status,
        customer_contact_id=customer_contact_id,
        assignee_member_id=assignee_member_id,
        limit=limit,
        offset=offset,
    )
    # The Workspace needs to know what this business calls a project before it
    # can render a heading, so the vocabulary travels with the list rather than
    # costing a second request.
    business = await BusinessService.get_by_id(session, business_id)
    profile = BusinessTypeProfileRegistry.get_or_default(business.business_type)
    return {
        "data": {
            "projects": projects,
            "semantics": profile.project_semantics.serialize(),
        },
        "meta": _meta(actor, count=len(projects)),
    }


@router.post("/{business_id}/projects")
async def create_project(
    business_id: UUID,
    body: CreateProjectRequest,
    actor: BusinessActorContext = Depends(require_business_actor(PROJECTS_CREATE, "projects")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    project = await ProjectService.create(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(mode="json", exclude_unset=True),
    )
    await session.commit()
    detail = await ProjectService.get_detail(
        session, business_id=business_id, project_id=project.id
    )
    return {"data": detail, "meta": _meta(actor)}


@router.post("/{business_id}/quotes/{quote_id}/convert-to-project")
async def convert_quote(
    business_id: UUID,
    quote_id: UUID,
    body: ConvertQuoteRequest,
    actor: BusinessActorContext = Depends(require_business_actor(PROJECTS_CREATE, "projects")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Turn an accepted quote into the work it describes.

    Idempotent: converting the same quote twice returns the project that already
    exists rather than creating a second one.
    """
    project = await ProjectService.create_from_quote(
        session,
        business_id=business_id,
        quote_id=quote_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(mode="json", exclude_unset=True),
    )
    await session.commit()
    detail = await ProjectService.get_detail(
        session, business_id=business_id, project_id=project.id
    )
    return {"data": detail, "meta": _meta(actor)}


@router.get("/{business_id}/projects/{project_id}")
async def get_project(
    business_id: UUID,
    project_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(PROJECTS_READ, "projects")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    detail = await ProjectService.get_detail(
        session, business_id=business_id, project_id=project_id
    )
    return {"data": detail, "meta": _meta(actor)}


@router.patch("/{business_id}/projects/{project_id}")
async def update_project(
    business_id: UUID,
    project_id: UUID,
    body: UpdateProjectRequest,
    actor: BusinessActorContext = Depends(require_business_actor(PROJECTS_UPDATE, "projects")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    payload = body.model_dump(mode="json", exclude_unset=True)
    expected_version = payload.pop("version", None)
    await ProjectService.update(
        session,
        business_id=business_id,
        project_id=project_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=payload,
        expected_version=expected_version,
    )
    await session.commit()
    detail = await ProjectService.get_detail(
        session, business_id=business_id, project_id=project_id
    )
    return {"data": detail, "meta": _meta(actor)}


@router.post("/{business_id}/projects/{project_id}/status")
async def change_status(
    business_id: UUID,
    project_id: UUID,
    body: StatusRequest,
    actor: BusinessActorContext = Depends(
        require_business_actor(PROJECTS_MANAGE_LIFECYCLE, "projects")
    ),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await ProjectService.change_status(
        session,
        business_id=business_id,
        project_id=project_id,
        status=body.status,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        reason=body.reason,
    )
    await session.commit()
    detail = await ProjectService.get_detail(
        session, business_id=business_id, project_id=project_id
    )
    return {"data": detail, "meta": _meta(actor)}


@router.post("/{business_id}/projects/{project_id}/phases")
async def add_phase(
    business_id: UUID,
    project_id: UUID,
    body: PhaseRequest,
    actor: BusinessActorContext = Depends(require_business_actor(PROJECTS_UPDATE, "projects")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await ProjectService.add_phase(
        session,
        business_id=business_id,
        project_id=project_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(mode="json", exclude_unset=True),
    )
    await session.commit()
    detail = await ProjectService.get_detail(
        session, business_id=business_id, project_id=project_id
    )
    return {"data": detail, "meta": _meta(actor)}


@router.patch("/{business_id}/projects/{project_id}/phases/{phase_id}")
async def update_phase(
    business_id: UUID,
    project_id: UUID,
    phase_id: UUID,
    body: PhaseRequest,
    actor: BusinessActorContext = Depends(require_business_actor(PROJECTS_UPDATE, "projects")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await ProjectService.update_phase(
        session,
        business_id=business_id,
        project_id=project_id,
        phase_id=phase_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(mode="json", exclude_unset=True),
    )
    await session.commit()
    detail = await ProjectService.get_detail(
        session, business_id=business_id, project_id=project_id
    )
    return {"data": detail, "meta": _meta(actor)}


@router.post("/{business_id}/projects/{project_id}/tasks")
async def add_task(
    business_id: UUID,
    project_id: UUID,
    body: TaskRequest,
    actor: BusinessActorContext = Depends(require_business_actor(PROJECTS_UPDATE, "projects")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await ProjectService.add_task(
        session,
        business_id=business_id,
        project_id=project_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(mode="json", exclude_unset=True),
    )
    await session.commit()
    detail = await ProjectService.get_detail(
        session, business_id=business_id, project_id=project_id
    )
    return {"data": detail, "meta": _meta(actor)}


@router.patch("/{business_id}/projects/{project_id}/tasks/{task_id}")
async def update_task(
    business_id: UUID,
    project_id: UUID,
    task_id: UUID,
    body: TaskRequest,
    # Editing a task and allocating one are the same endpoint but not the same
    # authority: a coordinator holds `assign`, and `update` covers the rest.
    actor: BusinessActorContext = Depends(
        require_business_actor(PROJECTS_ASSIGN, "projects")
    ),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    payload = body.model_dump(mode="json", exclude_unset=True)
    expected_version = payload.pop("version", None)
    await ProjectService.update_task(
        session,
        business_id=business_id,
        project_id=project_id,
        task_id=task_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=payload,
        expected_version=expected_version,
    )
    await session.commit()
    detail = await ProjectService.get_detail(
        session, business_id=business_id, project_id=project_id
    )
    return {"data": detail, "meta": _meta(actor)}
