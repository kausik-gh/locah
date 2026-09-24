"""Keep the Marketplace projection in step with the business it projects.

Doc 12 §14.5. Previously a hardcoded `MARKETPLACE_INDEX_TRIGGERS` branch inside
the worker's outbox consumer; the trigger set is unchanged, it now just lives
next to the capability that owns it.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.events.registry import EventContext, subscribe

# What the Marketplace card actually renders: the business itself, its
# published website, its offerings, its locations — and which capability
# buttons it offers.
#
# The module events matter more than they look. Search reads capability_flags
# straight off the projection rather than re-deriving them per result, so
# without these a business that switched Bookings off keeps showing a "Book"
# button that leads nowhere until something unrelated happens to reindex it.
_TRIGGERS = (
    "website.published",
    "business.profile.updated",
    "business.visibility.changed",
    "business.suspended",
    "offering.created",
    "offering.updated",
    "offering.archived",
    "offering.restored",
    "location.created",
    "location.updated",
    "location.archived",
    "module.enabled",
    "module.disabled",
    "module.deactivated",
)


@subscribe(  # type: ignore[untyped-decorator]  # mypy loses the Callable[[EventHandler], EventHandler]
    # return type of this decorator factory once it wraps an `async def`; every
    # other @subscribe(...) site in the codebase hits the same false positive.
    "marketplace.index",
    *_TRIGGERS,
    description="Re-index the Marketplace projection for the affected business",
)
async def reindex(session: AsyncSession, event: EventContext) -> None:
    from platform_core.services.marketplace_indexing import MarketplaceIndexingService

    await MarketplaceIndexingService.reindex_business(
        session,
        business_id=event.require_business_id(),
        correlation_id=event.correlation_id or str(event.event_id),
        trigger=event.event_type,
    )
