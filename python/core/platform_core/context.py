from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class OperatingContext(str, Enum):
    PERSONAL = "personal"
    BUSINESS = "business"
    ADMIN = "admin"


class EntitlementSet(BaseModel):
    modules: frozenset[str] = Field(default_factory=frozenset)
    capabilities: frozenset[str] = Field(default_factory=frozenset)

    def is_entitled(self, module_id: str) -> bool:
        return module_id in self.modules


class ModuleStateInfo(BaseModel):
    module_id: str
    activation_state: str
    configuration: dict[str, Any] | None = None

    def is_operational(self) -> bool:
        return self.activation_state in ("ready", "active")


class MembershipInfo(BaseModel):
    id: UUID
    business_id: UUID
    identity_id: UUID
    role: str
    status: str
    location_scope: list[UUID] | None

    def allows_location(self, location_id: UUID | None) -> bool:
        if location_id is None:
            return True
        if self.location_scope is None:
            return True
        return location_id in self.location_scope


class RequestContext(BaseModel):
    identity_id: UUID
    supabase_user_id: UUID
    email: str
    display_name: str | None = None
    active_context: OperatingContext = OperatingContext.PERSONAL
    business_id: UUID | None = None
    location_id: UUID | None = None
    membership: MembershipInfo | None = None
    effective_permissions: frozenset[str] = Field(default_factory=frozenset)
    effective_entitlements: EntitlementSet = Field(default_factory=EntitlementSet)
    module_states: dict[str, ModuleStateInfo] = Field(default_factory=dict)
    is_super_admin: bool = False
    correlation_id: str

    # Perf: the ORM Business / BusinessMembership rows that resolve_request_context
    # already loaded for a path-based business route. resolve_business_actor /
    # resolve_business_member reuse these instead of re-SELECTing the same rows
    # (and re-resolving permissions) that the gate chain just produced. Excluded
    # from any serialization — RequestContext is never dumped, but be explicit.
    orm_business: Any = Field(default=None, exclude=True, repr=False)
    orm_membership: Any = Field(default=None, exclude=True, repr=False)

    model_config = {"arbitrary_types_allowed": True}

    def has_permission(self, permission: str) -> bool:
        return permission in self.effective_permissions

    def require_business_context(self) -> UUID:
        if self.business_id is None or self.membership is None:
            raise ValueError("Business context required")
        return self.business_id
