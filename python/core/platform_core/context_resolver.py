import os
import uuid
from uuid import uuid4

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.context import (
    EntitlementSet,
    ModuleStateInfo,
    OperatingContext,
    RequestContext,
)
from platform_core.exceptions import (
    LocationAccessDenied,
    MembershipRequired,
    ResourceNotFound,
    ValidationError,
)
from platform_core.logging import bind_request_context
from platform_core.models import PlatformIdentity
from platform_core.services.business import BusinessService
from platform_core.services.entitlement import EntitlementService, ModuleService
from platform_core.services.identity import IdentityService
from platform_core.services.team import TeamService


def _parse_optional_uuid(value: str | None, *, field: str) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ValidationError(
            f"Invalid UUID for {field}",
            details={"errors": [{"field": field, "message": f"Malformed UUID: {value}"}]},
        ) from exc


def _parse_business_context(
    request: Request,
) -> tuple[OperatingContext, uuid.UUID | None, uuid.UUID | None]:
    """Resolve operating context from path params and headers."""
    path = request.url.path
    if path.startswith("/v1/admin"):
        return OperatingContext.ADMIN, None, None

    business_id_str = request.path_params.get("business_id")
    if business_id_str:
        business_id = _parse_optional_uuid(str(business_id_str), field="business_id")
        location_id = _parse_optional_uuid(
            request.headers.get("X-Location-Id"), field="X-Location-Id"
        )
        return OperatingContext.BUSINESS, business_id, location_id

    ctx_header = request.headers.get("X-Operating-Context", "personal").lower()
    header_business_id = request.headers.get("X-Business-Id")
    header_location_id = request.headers.get("X-Location-Id")

    if ctx_header == "business":
        resolved_business_id = _parse_optional_uuid(header_business_id, field="X-Business-Id")
        resolved_location_id = _parse_optional_uuid(header_location_id, field="X-Location-Id")
        # business_id may be filled from default/last later
        return OperatingContext.BUSINESS, resolved_business_id, resolved_location_id
    if ctx_header == "admin":
        return OperatingContext.ADMIN, None, None
    return OperatingContext.PERSONAL, None, None


# RLS is only enforced when the API is on the platform_api connection
# (API_DATABASE_URL set). When it is not, the session GUCs are read by nobody —
# binding them is wasted round-trips, and at test parallelism the extra
# statements add connection pressure against the pooler. Gate every bind on it.
_RLS_ENFORCING = os.getenv("API_DATABASE_URL") is not None


async def bind_session_context(
    session: AsyncSession,
    identity_id: uuid.UUID,
    business_id: uuid.UUID | None,
) -> None:
    """Bind the RLS session GUCs for the request.

    Uses set_config(..., is_local=false) — SESSION scope, not transaction
    scope — because a transaction-local setting is wiped by the first commit()
    in a handler, which would strip the request's tenant scope mid-flight.

    Session scope means the value persists on the pooled connection after the
    request. That is safe here only because `get_db_session` RESETs both GUCs
    in its finally block before the connection returns to the pool, and every
    authenticated request re-binds through this function. A path that opens a
    session without binding context gets a connection with the GUCs cleared
    (RLS then returns nothing for tenant-scoped tables — fail closed).

    No-op when RLS is not being enforced (API_DATABASE_URL unset).
    """
    if not _RLS_ENFORCING:
        return
    await session.execute(
        text("SELECT set_config('app.current_identity_id', :iid, false)"),
        {"iid": str(identity_id)},
    )
    await session.execute(
        text("SELECT set_config('app.current_business_id', :bid, false)"),
        {"bid": str(business_id) if business_id else ""},
    )


async def bind_public_context(session: AsyncSession, business_id: uuid.UUID) -> None:
    """Bind only `app.current_business_id`, for guest/public routes.

    A guest has no identity. Public handlers resolve the business from the URL
    slug (the `businesses` policy has a public-visibility arm for exactly this)
    and then call here so subsequent reads of the tenant's offerings, website,
    availability, etc. pass their RLS policies.
    """
    if not _RLS_ENFORCING:
        return
    await session.execute(
        text("SELECT set_config('app.current_business_id', :bid, false)"),
        {"bid": str(business_id)},
    )
    await session.execute(text("SELECT set_config('app.current_identity_id', '', false)"))


async def bind_quote_share_token(session: AsyncSession, token: str) -> None:
    """Present a quote share token as this transaction's credential.

    Transaction-local (`set_config(..., true)`) rather than session-level: the
    connection goes back to a pool afterwards, and a token left bound on it
    would be offered on somebody else's next request.
    """
    await session.execute(
        text("SELECT set_config('app.current_quote_token', :token, true)"),
        {"token": token},
    )


def _empty_personal_context(
    *,
    identity: PlatformIdentity,
    supabase_user_id: uuid.UUID,
    email: str,
    is_super_admin: bool,
    correlation_id: str | None,
    request: Request,
) -> RequestContext:
    return RequestContext(
        identity_id=identity.id,
        supabase_user_id=supabase_user_id,
        email=email,
        display_name=identity.display_name,
        active_context=OperatingContext.PERSONAL,
        business_id=None,
        location_id=None,
        membership=None,
        effective_permissions=frozenset(),
        effective_entitlements=EntitlementSet(),
        module_states={},
        is_super_admin=is_super_admin,
        correlation_id=correlation_id or request.headers.get("X-Correlation-Id") or str(uuid4()),
    )


async def resolve_request_context(
    request: Request,
    session: AsyncSession,
    *,
    supabase_user_id: uuid.UUID,
    email: str,
    correlation_id: str | None = None,
    force_personal: bool = False,
) -> RequestContext:
    identity = await IdentityService.bootstrap_identity(session, supabase_user_id, email)
    await session.flush()

    # AUD-11: bind the identity to the log context as soon as it resolves, so
    # every subsequent log line in this request carries identity_id. business_id
    # is added below once a business context is confirmed.
    bind_request_context(identity_id=str(identity.id))

    # RLS (AUD-02): bind the identity GUC now, before any membership / business
    # / admin-grant lookup below. Those tables are row-level scoped, and the
    # `identity_id = current_identity_id()` policy arm is what lets this
    # function resolve the caller's own memberships to build the context.
    # `current_business_id` stays unset until a business context is confirmed.
    await bind_session_context(session, identity.id, None)

    active_context, business_id, location_id = _parse_business_context(request)
    membership_info = None
    effective_permissions: frozenset[str] = frozenset()
    effective_entitlements = EntitlementSet()
    module_states: dict[str, ModuleStateInfo] = {}
    business = None
    membership = None

    is_super_admin = await IdentityService.is_super_admin(session, identity.id)

    if force_personal:
        # Identity-only context for endpoints that must run before a membership
        # exists — invitation accept/decline. Doc 12 §8.9 gate [4] cannot apply
        # to the request that creates the membership it would check; those
        # handlers authorise on the invitation recipient match instead.
        await bind_session_context(session, identity.id, None)
        return _empty_personal_context(
            identity=identity,
            supabase_user_id=supabase_user_id,
            email=email,
            is_super_admin=is_super_admin,
            correlation_id=correlation_id,
            request=request,
        )
    explicit_business_header = request.headers.get("X-Business-Id") is not None
    path_business = request.path_params.get("business_id") is not None
    restored_preference = False

    if active_context == OperatingContext.BUSINESS and business_id is None:
        # Stage 2B restore: default → last → no business context (do not guess).
        remembered = await IdentityService.get_remembered_business_id(session, identity.id)
        if remembered is not None:
            business_id = remembered
            restored_preference = True
        else:
            await bind_session_context(session, identity.id, None)
            return _empty_personal_context(
                identity=identity,
                supabase_user_id=supabase_user_id,
                email=email,
                is_super_admin=is_super_admin,
                correlation_id=correlation_id,
                request=request,
            )

    if active_context == OperatingContext.BUSINESS:
        if business_id is None:
            raise MembershipRequired()

        # Gate [4] before gate [3]: business_memberships' RLS policy has an
        # `identity_id = current_identity_id()` arm that does not depend on
        # the Business being visible, so this membership check works
        # regardless of `businesses` RLS. Checking it first lets a non-member
        # (Category A scenarios 1/3: no relationship, or suspended/removed)
        # get the correct MembershipRequired decision instead of
        # businesses_api_select silently hiding the row and forcing a
        # not-found outcome before the app ever gets to decide.
        membership = await TeamService.get_membership(session, identity.id, business_id)
        if membership is None or membership.status != "active":
            if path_business or explicit_business_header:
                raise MembershipRequired()
            # Restored preference no longer valid → no business context.
            await bind_session_context(session, identity.id, None)
            return _empty_personal_context(
                identity=identity,
                supabase_user_id=supabase_user_id,
                email=email,
                is_super_admin=is_super_admin,
                correlation_id=correlation_id,
                request=request,
            )

        # RLS (AUD-02): bind the business GUC now that membership is confirmed
        # active, before reading the Business row (or module state /
        # permissions / entitlements) — those tables are business-scoped
        # policies keyed on current_business_id(), so binding after reading
        # them left those reads running under the still-unset (no business)
        # GUC. `businesses_api_select`'s active-membership EXISTS arm does not
        # itself require this bind, but the reads below do.
        await bind_session_context(session, identity.id, business_id)
        bind_request_context(business_id=str(business_id))

        # Gate [3]: now that membership is confirmed and the tenant scope is
        # bound, the Business row is visible. This ResourceNotFound branch is
        # a defensive fallback (e.g. a membership row surviving a deleted
        # Business), not the primary existence check anymore.
        business = await BusinessService.get_by_id(session, business_id)
        if not business:
            if path_business or explicit_business_header:
                raise ResourceNotFound("Business")
            await bind_session_context(session, identity.id, None)
            return _empty_personal_context(
                identity=identity,
                supabase_user_id=supabase_user_id,
                email=email,
                is_super_admin=is_super_admin,
                correlation_id=correlation_id,
                request=request,
            )

        # Restored closed default/last → no business context (do not guess another).
        if restored_preference and business.state == "closed":
            await bind_session_context(session, identity.id, None)
            return _empty_personal_context(
                identity=identity,
                supabase_user_id=supabase_user_id,
                email=email,
                is_super_admin=is_super_admin,
                correlation_id=correlation_id,
                request=request,
            )

        membership_info = TeamService.to_membership_info(membership)
        if location_id and not membership_info.allows_location(location_id):
            raise LocationAccessDenied()

        # `business`, `membership` and the module-state rows are already in hand.
        # Feed them through so the permission and entitlement resolvers don't
        # re-SELECT the same rows (was ~9 sequential queries here; now ~3).
        raw_states = await ModuleService.get_states(session, business_id)
        effective_permissions = await TeamService.resolve_permissions(
            session, membership, business=business
        )
        effective_entitlements = await EntitlementService.get_effective(
            session, business_id, business=business, module_states=raw_states
        )
        module_states = {
            mid: ModuleStateInfo(
                module_id=mid,
                activation_state=s.activation_state,
                configuration=s.configuration,
            )
            for mid, s in raw_states.items()
        }
    else:
        await bind_session_context(session, identity.id, None)

    return RequestContext(
        identity_id=identity.id,
        supabase_user_id=supabase_user_id,
        email=email,
        display_name=identity.display_name,
        active_context=active_context,
        business_id=business_id,
        location_id=location_id,
        membership=membership_info,
        effective_permissions=effective_permissions,
        effective_entitlements=effective_entitlements,
        module_states=module_states,
        is_super_admin=is_super_admin,
        correlation_id=correlation_id or request.headers.get("X-Correlation-Id") or str(uuid4()),
        orm_business=business,
        orm_membership=membership,
    )
