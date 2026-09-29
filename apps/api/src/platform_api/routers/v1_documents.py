"""Business Documents API and single-resource public request links."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.permissions import DOCUMENTS_MANAGE, DOCUMENTS_READ, DOCUMENTS_REQUEST
from platform_core.services.document_workflows import DocumentWorkflows, MAX_FILE_BYTES

router = APIRouter(prefix="/v1/b/{business_id}/documents", tags=["documents"])
public_router = APIRouter(prefix="/v1/public/documents", tags=["documents-public"])
download_router = APIRouter(prefix="/v1/public/document-files", tags=["documents-public"])


class TemplateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["agreement", "consent", "intake", "certificate", "report", "generic"]
    title: str = Field(min_length=1, max_length=160)
    description: str = ""
    traits: dict[str, Any] = Field(default_factory=dict)
    content: dict[str, Any]


class FormInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=160)
    kind: Literal["agreement", "consent", "intake", "report", "generic"]
    fields: list[dict[str, Any]]
    consent_text: str | None = None
    guardian_required: bool = False


class FormVersionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fields: list[dict[str, Any]]
    consent_text: str | None = None
    guardian_required: bool = False


class RequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_type: Literal["form", "upload"]
    title: str = Field(min_length=1, max_length=160)
    form_id: UUID | None = None
    related_type: Literal["customer", "quote", "project", "job", "booking", "membership",
                          "academic_student", "order", "supplier", "general"] = "general"
    related_id: UUID | None = None
    customer_contact_id: UUID | None = None
    days_valid: int = Field(default=7, ge=1, le=30)


class SubmissionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: dict[str, Any]
    signer_name: str = Field(min_length=1, max_length=160)
    signature: dict[str, Any] | None = None
    age_confirmed: bool = False
    guardian_relationship: str | None = None


@router.get("/templates")
async def templates(business_id: UUID,
                    actor: BusinessActorContext = Depends(require_business_actor(DOCUMENTS_READ, "documents")),
                    session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    return {"data": await DocumentWorkflows.list_templates(session, business_id)}


@router.post("/templates")
async def create_template(business_id: UUID, body: TemplateInput,
                          actor: BusinessActorContext = Depends(require_business_actor(DOCUMENTS_MANAGE, "documents")),
                          session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    result = await DocumentWorkflows.create_template(session, business_id=business_id,
        kind=body.kind, title=body.title, description=body.description,
        traits=body.traits, content=body.content, actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id)
    await session.commit()
    return {"data": result}


@router.get("/forms")
async def forms(business_id: UUID,
                actor: BusinessActorContext = Depends(require_business_actor(DOCUMENTS_READ, "documents")),
                session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    return {"data": await DocumentWorkflows.list_forms(session, business_id)}


@router.post("/forms")
async def create_form(business_id: UUID, body: FormInput,
                      actor: BusinessActorContext = Depends(require_business_actor(DOCUMENTS_MANAGE, "documents")),
                      session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    result = await DocumentWorkflows.create_form(session, business_id=business_id,
        title=body.title, kind=body.kind, fields=body.fields,
        consent_text=body.consent_text, guardian_required=body.guardian_required,
        actor_id=actor.request.identity_id, correlation_id=actor.request.correlation_id)
    await session.commit()
    return {"data": result}


@router.post("/forms/{form_id}/versions")
async def version_form(business_id: UUID, form_id: UUID, body: FormVersionInput,
                       actor: BusinessActorContext = Depends(require_business_actor(DOCUMENTS_MANAGE, "documents")),
                       session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    result = await DocumentWorkflows.version_form(session, business_id=business_id,
        form_id=form_id, fields=body.fields, consent_text=body.consent_text,
        guardian_required=body.guardian_required, actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id)
    await session.commit()
    return {"data": result}


@router.get("/requests")
async def requests(business_id: UUID,
                   actor: BusinessActorContext = Depends(require_business_actor(DOCUMENTS_READ, "documents")),
                   session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    return {"data": await DocumentWorkflows.list_requests(session, business_id)}


@router.post("/requests")
async def create_request(business_id: UUID, body: RequestInput,
                         actor: BusinessActorContext = Depends(require_business_actor(DOCUMENTS_REQUEST, "documents")),
                         session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    result = await DocumentWorkflows.create_request(session, business_id=business_id,
        request_type=body.request_type, title=body.title, form_id=body.form_id,
        related_type=body.related_type, related_id=body.related_id,
        customer_contact_id=body.customer_contact_id, days_valid=body.days_valid,
        actor_id=actor.request.identity_id, correlation_id=actor.request.correlation_id)
    await session.commit()
    return {"data": result}


@router.get("/submissions/{submission_id}")
async def submission(business_id: UUID, submission_id: UUID,
                     actor: BusinessActorContext = Depends(require_business_actor(DOCUMENTS_READ, "documents")),
                     session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    return {"data": await DocumentWorkflows.submission(session, business_id, submission_id)}


@router.post("/files/{file_id}/access")
async def file_access(business_id: UUID, file_id: UUID,
                      actor: BusinessActorContext = Depends(require_business_actor(DOCUMENTS_READ, "documents")),
                      session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    result = await DocumentWorkflows.create_access_link(session, business_id=business_id,
        file_id=file_id, actor_id=actor.request.identity_id)
    await session.commit()
    return {"data": {**result, "download_path": f"/v1/public/document-files/{result['token']}"}}


@public_router.get("/{slug}/{token}")
async def public_request(slug: str, token: str,
                         session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    return {"data": await DocumentWorkflows.public_view(session, slug, token)}


@public_router.post("/{slug}/{token}/submit")
async def public_submit(slug: str, token: str, body: SubmissionInput, request: Request,
                        session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    result = await DocumentWorkflows.submit(session, slug=slug, token=token,
        answers=body.answers, signer_name=body.signer_name,
        signature=body.signature, age_confirmed=body.age_confirmed,
        guardian_relationship=body.guardian_relationship,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"))
    await session.commit()
    return {"data": result}


@public_router.post("/{slug}/{token}/upload")
async def public_upload(slug: str, token: str, request: Request,
                        field_key: str = Form(default="requested_file"),
                        file: UploadFile = File(...),
                        session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    content = await file.read(MAX_FILE_BYTES + 1)
    result = await DocumentWorkflows.upload(session, slug=slug, token=token,
        field_key=field_key, filename=file.filename or "upload",
        content_type=file.content_type or "", content=content,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"))
    await session.commit()
    return {"data": result}


@download_router.get("/{token}")
async def public_download(token: str,
                          session: AsyncSession = Depends(get_db_session)) -> Response:
    content, meta = await DocumentWorkflows.download(session, token)
    return Response(content=content, media_type=meta["content_type"], headers={
        "Content-Disposition": f'attachment; filename="{meta["filename"]}"',
        "X-Content-SHA256": meta["sha256"],
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    })
