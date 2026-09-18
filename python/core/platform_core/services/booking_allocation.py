"""Allocating bookable subjects — resources and providers — to a time interval.

This is the half of booking that can collide. Everything about which business
type is being served lives elsewhere; here there are only subjects, intervals
and two allocation modes.

Why exclusive and pooled are enforced differently
-------------------------------------------------
An exclusive subject is guarded by a Postgres exclusion constraint, so two
requests that both read availability before either commits cannot both win —
the loser's INSERT is rejected by the database rather than by whichever process
happened to look second.

A pooled subject cannot be guarded that way. "Seats sold across overlapping
allocations must not exceed capacity" is a sum, and an exclusion constraint
compares pairs. Those go through an advisory lock keyed on the resource plus a
sum inside the same transaction, which is correct but is a genuinely weaker
mechanism: it holds because every writer takes the same lock, not because the
database would refuse a bad row on its own.
"""

from __future__ import annotations

import uuid
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, NoReturn

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.models import BookingAllocation, BookingResource

# The exclusion constraints, by name, so a violation can be reported as the
# domain conflict it is rather than as an opaque integrity error.
_RESOURCE_CONFLICT = "bookings_allocation_resource_no_overlap"
_PROVIDER_CONFLICT = "bookings_allocation_provider_no_overlap"


@dataclass(frozen=True)
class AllocationRequest:
    """A subject to claim. Exactly one of resource_id / provider_id is set."""

    resource_id: uuid.UUID | None = None
    provider_id: uuid.UUID | None = None
    quantity: int = 1


class BookingAllocationService:
    @staticmethod
    async def load_resource(
        session: AsyncSession, *, business_id: uuid.UUID, resource_id: uuid.UUID
    ) -> BookingResource:
        result = await session.execute(
            select(BookingResource).where(
                BookingResource.id == resource_id,
                BookingResource.business_id == business_id,
                BookingResource.deleted_at.is_(None),
            )
        )
        resource = result.scalars().first()
        if resource is None:
            raise ResourceNotFound("Bookable resource")
        return resource

    @staticmethod
    def occupancy_window(
        resource: BookingResource | None, starts_at: datetime, ends_at: datetime
    ) -> tuple[datetime, datetime]:
        """Widen the guest-facing window by the resource's turnaround.

        Putting buffers in the stored range is what lets the exclusion
        constraint enforce them: a chair with ten minutes of cleanup simply
        occupies ten more minutes, and nothing on the booking path has to know.
        """
        if resource is None:
            return starts_at, ends_at
        return (
            starts_at - timedelta(minutes=resource.buffer_before_minutes),
            ends_at + timedelta(minutes=resource.buffer_after_minutes),
        )

    @staticmethod
    def assert_party_fits(resource: BookingResource, party_size: int) -> None:
        """A four-top cannot seat six.

        Fit is separate from supply: it constrains which resource may be used,
        not how many are left.
        """
        if resource.max_party_size is not None and party_size > resource.max_party_size:
            raise ValidationError(
                f"{resource.name} seats at most {resource.max_party_size}",
                details={"resource_id": str(resource.id), "party_size": party_size},
            )
        if resource.min_party_size is not None and party_size < resource.min_party_size:
            raise ValidationError(
                f"{resource.name} requires at least {resource.min_party_size}",
                details={"resource_id": str(resource.id), "party_size": party_size},
            )

    @staticmethod
    async def _lock_subject(session: AsyncSession, subject_id: uuid.UUID) -> None:
        """Serialise writers to one subject for the rest of the transaction.

        Taken for exclusive subjects as well as pooled ones, even though an
        exclusion constraint already guards those. Without it the constraint is
        the primary mechanism, and losing to it costs the whole request: a
        failed flush puts the session into a pending-rollback state, so nothing
        afterwards can run on it, not even reporting the conflict, let alone
        trying the next table along.

        With the lock held the check below is authoritative and the flush
        succeeds, so a caller offering three tables in turn gets three clean
        answers. The constraint stays as the backstop that keeps the invariant
        true even if some future code path forgets to take the lock.
        """
        lock_id = zlib.crc32(f"subject:{subject_id}".encode()) & 0x7FFFFFFF
        await session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": lock_id})

    @staticmethod
    async def _exclusive_conflict(
        session: AsyncSession,
        *,
        subject_column: Any,
        subject_id: uuid.UUID,
        starts_at: datetime,
        ends_at: datetime,
        exclude_booking_id: uuid.UUID | None,
    ) -> bool:
        query = select(BookingAllocation.id).where(
            subject_column == subject_id,
            BookingAllocation.released_at.is_(None),
            BookingAllocation.is_exclusive.is_(True),
            func.upper(BookingAllocation.occupies) > starts_at,
            func.lower(BookingAllocation.occupies) < ends_at,
        )
        if exclude_booking_id is not None:
            query = query.where(
                (BookingAllocation.booking_id.is_(None))
                | (BookingAllocation.booking_id != exclude_booking_id)
            )
        return (await session.execute(query.limit(1))).scalars().first() is not None

    @staticmethod
    async def pooled_usage(
        session: AsyncSession,
        *,
        resource_id: uuid.UUID,
        starts_at: datetime,
        ends_at: datetime,
        exclude_booking_id: uuid.UUID | None = None,
    ) -> int:
        query = select(func.coalesce(func.sum(BookingAllocation.quantity), 0)).where(
            BookingAllocation.resource_id == resource_id,
            BookingAllocation.released_at.is_(None),
            func.upper(BookingAllocation.occupies) > starts_at,
            func.lower(BookingAllocation.occupies) < ends_at,
        )
        if exclude_booking_id is not None:
            query = query.where(
                (BookingAllocation.booking_id.is_(None))
                | (BookingAllocation.booking_id != exclude_booking_id)
            )
        return int((await session.execute(query)).scalar_one())

    @staticmethod
    async def allocate(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        booking_id: uuid.UUID | None,
        requests: list[AllocationRequest],
        starts_at: datetime,
        ends_at: datetime,
        party_size: int = 1,
        kind: str = "booking",
        exclude_booking_id: uuid.UUID | None = None,
    ) -> list[BookingAllocation]:
        """Claim every subject for the interval, or raise and claim none.

        Ordering matters: subjects are claimed in a stable order so two bookings
        wanting the same pair cannot deadlock by taking them in opposite orders.
        """
        if ends_at <= starts_at:
            raise ValidationError("Booking must end after it starts")

        created: list[BookingAllocation] = []
        ordered = sorted(
            requests,
            key=lambda r: (str(r.resource_id or ""), str(r.provider_id or "")),
        )

        for request in ordered:
            if (request.resource_id is None) == (request.provider_id is None):
                raise ValidationError("An allocation needs exactly one subject")

            resource: BookingResource | None = None
            is_exclusive = True

            if request.resource_id is not None:
                resource = await BookingAllocationService.load_resource(
                    session, business_id=business_id, resource_id=request.resource_id
                )
                if not resource.is_active:
                    raise ValidationError(
                        f"{resource.name} is not currently bookable",
                        details={"resource_id": str(resource.id)},
                    )
                BookingAllocationService.assert_party_fits(resource, party_size)
                is_exclusive = resource.allocation_mode == "exclusive"

            window_start, window_end = BookingAllocationService.occupancy_window(
                resource, starts_at, ends_at
            )

            subject_id = request.resource_id or request.provider_id
            assert subject_id is not None
            # Lock before reading. Checking first and locking afterwards leaves
            # exactly the race the lock exists to close.
            await BookingAllocationService._lock_subject(session, subject_id)

            if is_exclusive:
                subject_column = (
                    BookingAllocation.resource_id
                    if request.resource_id is not None
                    else BookingAllocation.provider_id
                )
                if await BookingAllocationService._exclusive_conflict(
                    session,
                    subject_column=subject_column,
                    subject_id=subject_id,
                    starts_at=window_start,
                    ends_at=window_end,
                    exclude_booking_id=exclude_booking_id,
                ):
                    label = resource.name if resource is not None else "That provider"
                    key = "resource_id" if request.resource_id else "provider_id"
                    raise ConflictError(
                        f"{label} is already booked for this time",
                        details={key: str(subject_id)},
                    )
            else:
                # Pooled: "seats sold must not exceed capacity" is a sum, which
                # an exclusion constraint cannot express, so the lock is the
                # only thing holding this invariant.
                assert resource is not None
                used = await BookingAllocationService.pooled_usage(
                    session,
                    resource_id=resource.id,
                    starts_at=window_start,
                    ends_at=window_end,
                    exclude_booking_id=exclude_booking_id,
                )
                if used + request.quantity > resource.capacity:
                    raise ConflictError(
                        f"{resource.name} has {max(resource.capacity - used, 0)} place(s) left",
                        details={
                            "resource_id": str(resource.id),
                            "capacity": resource.capacity,
                            "used": used,
                            "requested": request.quantity,
                        },
                    )

            allocation = BookingAllocation(
                business_id=business_id,
                kind=kind,
                booking_id=booking_id,
                resource_id=request.resource_id,
                provider_id=request.provider_id,
                quantity=request.quantity,
                is_exclusive=is_exclusive,
                occupies=func.tstzrange(window_start, window_end),
            )
            session.add(allocation)
            try:
                await session.flush()
            except IntegrityError as exc:
                # Reaching here means the constraint caught something the lock
                # and the check above did not, so the session is already
                # unusable and this request is finished either way. Translate it
                # so the caller still sees a conflict rather than an opaque
                # integrity error.
                BookingAllocationService._raise_conflict(exc, resource, request)
            created.append(allocation)

        return created

    @staticmethod
    def _raise_conflict(
        exc: IntegrityError, resource: BookingResource | None, request: AllocationRequest
    ) -> NoReturn:
        """Report an exclusion violation as the domain conflict it is.

        The constraint firing is the expected outcome of losing a race, not an
        internal error, so the caller should see "already booked" rather than a
        500 from an integrity error it cannot interpret.
        """
        message = str(getattr(exc, "orig", exc))
        if _RESOURCE_CONFLICT in message:
            label = resource.name if resource else "That resource"
            raise ConflictError(
                f"{label} is already booked for this time",
                details={"resource_id": str(request.resource_id)},
            ) from exc
        if _PROVIDER_CONFLICT in message:
            raise ConflictError(
                "That provider is already booked for this time",
                details={"provider_id": str(request.provider_id)},
            ) from exc
        raise exc

    @staticmethod
    async def release_for_booking(
        session: AsyncSession, *, business_id: uuid.UUID, booking_id: uuid.UUID
    ) -> int:
        """Free a booking's subjects without losing the record of who held them.

        Released rows fall out of the exclusion constraint's partial index, so
        the slot reopens immediately while the history stays queryable.
        """
        result = await session.execute(
            select(BookingAllocation).where(
                BookingAllocation.business_id == business_id,
                BookingAllocation.booking_id == booking_id,
                BookingAllocation.released_at.is_(None),
            )
        )
        allocations = list(result.scalars().all())
        for allocation in allocations:
            allocation.released_at = datetime.now(timezone.utc)
        await session.flush()
        return len(allocations)

    @staticmethod
    async def list_for_booking(
        session: AsyncSession, *, business_id: uuid.UUID, booking_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            select(BookingAllocation).where(
                BookingAllocation.business_id == business_id,
                BookingAllocation.booking_id == booking_id,
            )
        )
        return [
            {
                "id": str(a.id),
                "resource_id": str(a.resource_id) if a.resource_id else None,
                "provider_id": str(a.provider_id) if a.provider_id else None,
                "quantity": a.quantity,
                "released_at": a.released_at.isoformat() if a.released_at else None,
            }
            for a in result.scalars().all()
        ]
