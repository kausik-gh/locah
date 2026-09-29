"""Google Business Profile neutral contract (MK-06; MD §18.2).

Status: ACTIVATION_REQUIRED. Zero live Google API calls.
Provides configuration contract for listing hours, holiday hours, review replies, and ordering links.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict


class GoogleBusinessProfileConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_id: uuid.UUID
    location_id: uuid.UUID | None = None
    account_id: str | None = None
    location_name: str | None = None
    status: str = "ACTIVATION_REQUIRED"
    sync_hours: bool = True
    sync_menu_links: bool = True
    auto_reply_reviews: bool = False


class GoogleBusinessProfileContractService:
    @staticmethod
    def get_status(business_id: uuid.UUID) -> dict[str, Any]:
        return {
            "business_id": str(business_id),
            "status": "ACTIVATION_REQUIRED",
            "message": "Google Business Profile integration requires Google OAuth activation and verification.",
        }
