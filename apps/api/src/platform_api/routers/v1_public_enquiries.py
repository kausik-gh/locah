"""Enquiries from a business's website become leads (Capability Universe §6.3,
§19.2). Anonymous and rate-limited as a public write; a hidden honeypot field
drops bot posts."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_core.services.public_enquiry import PublicEnquiryService

router = APIRouter(prefix="/v1/public", tags=["enquiries"])


class EnquiryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=80)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=254)
    message: str | None = Field(default=None, max_length=1000)
    offering_id: uuid.UUID | None = None
    plan_id: uuid.UUID | None = None
    purpose: str = "enquiry"
    preferred_date: str | None = None
    website: str | None = None  # honeypot


@router.post("/websites/{slug}/enquiries")
async def submit_enquiry(
    slug: str, body: EnquiryRequest, session: AsyncSession = Depends(get_db_session)
) -> dict[str, Any]:
    data = await PublicEnquiryService.submit(
        session, slug=slug, payload=body.model_dump(mode="json"), correlation_id=str(uuid.uuid4()))
    await session.commit()
    return {"data": data}
