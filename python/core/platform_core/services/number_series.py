"""Gapless document numbering (Capability Universe §24 #5, §14.2, §14.4).

One series per key × period (for invoices: GSTIN × financial year ×
register). A number is taken inside the transaction that creates the
document, under a row lock, so two concurrent bills never share a number and a
rolled-back bill never burns one. Cancelled documents keep their number.

Offline registers reserve a block while online (default 50) and number bills
from it without a connection; the block's range is theirs alone.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ValidationError

DEFAULT_BLOCK = 50


def financial_year(day: date) -> str:
    """India's April–March financial year as '26-27'."""
    start = day.year if day.month >= 4 else day.year - 1
    return f"{start % 100:02d}-{(start + 1) % 100:02d}"


def format_number(prefix: str, period: str, value: int, pad: int) -> str:
    """CHN1/26-27/000123 — the §14.4 example shape; prefix/period optional."""
    parts = [p for p in (prefix, period) if p]
    return "/".join(parts + [str(value).zfill(pad)])


@dataclass(frozen=True)
class Allocated:
    value: int
    number: str
    period: str


@dataclass(frozen=True)
class Block:
    id: uuid.UUID
    start: int
    end: int
    period: str
    prefix: str
    pad: int

    def number(self, value: int) -> str:
        if not self.start <= value <= self.end:
            raise ValidationError("Number outside the register's reserved block",
                                  details={"value": value, "start": self.start, "end": self.end})
        return format_number(self.prefix, self.period, value, self.pad)


class NumberSeriesService:
    @staticmethod
    async def _lock(
        session: AsyncSession, business_id: uuid.UUID, series_key: str, period: str, prefix: str, pad: int
    ) -> tuple[int, str, int]:
        await session.execute(
            text("""
                INSERT INTO number_series (business_id, series_key, period, prefix, pad)
                VALUES (:b, :k, :p, :prefix, :pad)
                ON CONFLICT (business_id, series_key, period) DO NOTHING
            """),
            {"b": str(business_id), "k": series_key, "p": period, "prefix": prefix, "pad": pad},
        )
        row = (await session.execute(
            text("""
                SELECT next_value, prefix, pad FROM number_series
                WHERE business_id = :b AND series_key = :k AND period = :p
                FOR UPDATE
            """),
            {"b": str(business_id), "k": series_key, "p": period},
        )).one()
        return int(row[0]), str(row[1]), int(row[2])

    @staticmethod
    async def next(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        series_key: str,
        period: str = "",
        prefix: str = "",
        pad: int = 6,
    ) -> Allocated:
        """Take the next number. Call inside the document's own transaction."""
        value, stored_prefix, stored_pad = await NumberSeriesService._lock(
            session, business_id, series_key, period, prefix, pad
        )
        await session.execute(
            text("""
                UPDATE number_series SET next_value = next_value + 1, updated_at = now()
                WHERE business_id = :b AND series_key = :k AND period = :p
            """),
            {"b": str(business_id), "k": series_key, "p": period},
        )
        return Allocated(value, format_number(stored_prefix, period, value, stored_pad), period)

    @staticmethod
    async def reserve_block(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        series_key: str,
        holder: str,
        period: str = "",
        prefix: str = "",
        pad: int = 6,
        size: int = DEFAULT_BLOCK,
    ) -> Block:
        """Hand a register a contiguous range for offline use (§14.2)."""
        if not 1 <= size <= 1000:
            raise ValidationError("Block size must be between 1 and 1000", details={"field": "size"})
        start, stored_prefix, stored_pad = await NumberSeriesService._lock(
            session, business_id, series_key, period, prefix, pad
        )
        end = start + size - 1
        await session.execute(
            text("""
                UPDATE number_series SET next_value = :n, updated_at = now()
                WHERE business_id = :b AND series_key = :k AND period = :p
            """),
            {"n": end + 1, "b": str(business_id), "k": series_key, "p": period},
        )
        block_id = uuid.uuid4()
        await session.execute(
            text("""
                INSERT INTO number_series_blocks (id, business_id, series_key, period, holder, start_value, end_value)
                VALUES (:id, :b, :k, :p, :h, :s, :e)
            """),
            {"id": str(block_id), "b": str(business_id), "k": series_key, "p": period, "h": holder,
             "s": start, "e": end},
        )
        return Block(block_id, start, end, period, stored_prefix, stored_pad)

    @staticmethod
    async def block(session: AsyncSession, business_id: uuid.UUID, block_id: uuid.UUID) -> Block:
        row = (await session.execute(
            text("""
                SELECT b.id, b.start_value, b.end_value, b.period, s.prefix, s.pad, b.status
                FROM number_series_blocks b
                JOIN number_series s ON s.business_id = b.business_id AND s.series_key = b.series_key
                                    AND s.period = b.period
                WHERE b.business_id = :b AND b.id = :id
            """),
            {"b": str(business_id), "id": str(block_id)},
        )).first()
        if row is None:
            raise ConflictError("Unknown number block", details={"block_id": str(block_id)})
        return Block(row[0], int(row[1]), int(row[2]), str(row[3]), str(row[4]), int(row[5]))

    @staticmethod
    async def release_block(session: AsyncSession, business_id: uuid.UUID, block_id: uuid.UUID) -> None:
        """Retire a block. Unused numbers in it stay unused — the gap is recorded,
        never silently reused, because a register may have printed them."""
        await session.execute(
            text("UPDATE number_series_blocks SET status = 'released' WHERE business_id = :b AND id = :id"),
            {"b": str(business_id), "id": str(block_id)},
        )

    @staticmethod
    async def active_block(
        session: AsyncSession, business_id: uuid.UUID, *, series_key: str, period: str, holder: str,
    ) -> Block | None:
        """The holder's newest active block in this series and period, if any."""
        row = (await session.execute(
            text("""
                SELECT id FROM number_series_blocks
                WHERE business_id = :b AND series_key = :k AND period = :p AND holder = :h AND status = 'active'
                ORDER BY start_value DESC LIMIT 1
            """),
            {"b": str(business_id), "k": series_key, "p": period, "h": holder},
        )).first()
        return await NumberSeriesService.block(session, business_id, row[0]) if row else None

    @staticmethod
    async def return_tail(
        session: AsyncSession, business_id: uuid.UUID, block_id: uuid.UUID, last_used: int | None,
    ) -> int:
        """Give back the unused end of a block when nothing was allocated after
        it, so the series stays gapless (§14.2). Returns how many numbers came
        back; a block that is not the series tail keeps its numbers for the
        register's next shift instead."""
        blk = (await session.execute(
            text("""
                SELECT b.series_key, b.period, b.start_value, b.end_value, s.next_value
                FROM number_series_blocks b
                JOIN number_series s ON s.business_id = b.business_id AND s.series_key = b.series_key
                                    AND s.period = b.period
                WHERE b.business_id = :b AND b.id = :id AND b.status = 'active'
                FOR UPDATE OF s
            """),
            {"b": str(business_id), "id": str(block_id)},
        )).first()
        if blk is None:
            return 0
        key, period, start, end, next_value = blk
        used_end = start - 1 if last_used is None else int(last_used)
        if int(next_value) != int(end) + 1 or used_end >= int(end):
            return 0
        await session.execute(
            text("UPDATE number_series SET next_value = :n, updated_at = now() "
                 "WHERE business_id = :b AND series_key = :k AND period = :p"),
            {"n": used_end + 1, "b": str(business_id), "k": key, "p": period},
        )
        if used_end < int(start):
            await session.execute(text("DELETE FROM number_series_blocks WHERE business_id = :b AND id = :id"),
                                  {"b": str(business_id), "id": str(block_id)})
        else:
            await session.execute(
                text("UPDATE number_series_blocks SET end_value = :e, status = 'exhausted' "
                     "WHERE business_id = :b AND id = :id"),
                {"e": used_end, "b": str(business_id), "id": str(block_id)},
            )
        return int(end) - used_end

