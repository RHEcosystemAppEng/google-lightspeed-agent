"""Persistence helpers for order usage metering."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from lightspeed_agent.db import UsageRecordModel, get_session

logger = logging.getLogger(__name__)


def _current_hour_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return current UTC hour window [start, end)."""
    current = now or datetime.now(UTC)
    period_start = current.replace(minute=0, second=0, microsecond=0)
    period_end = period_start + timedelta(hours=1)
    return period_start, period_end


def _normalize_utc(dt: datetime) -> datetime:
    """Normalize datetime to timezone-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class UsageRepository:
    """Repository for persisting usage increments per order and period."""

    async def increment_usage(
        self,
        *,
        order_id: str,
        request_count: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        tool_calls: int = 0,
        client_id: str | None = None,
    ) -> None:
        """Persist usage increments into the current hourly usage record.

        Uses atomic INSERT ... ON CONFLICT DO UPDATE (no read-before-write) for
        concurrent-safe increments. Safe for multiple instances/workers.
        """
        if request_count == 0 and input_tokens == 0 and output_tokens == 0 and tool_calls == 0:
            return

        period_start, period_end = _current_hour_window()

        async with get_session() as session:
            dialect_name = session.get_bind().dialect.name
            if dialect_name == "postgresql":
                await self._increment_usage_atomic(
                    session, order_id, period_start, period_end,
                    request_count, input_tokens, output_tokens, tool_calls, client_id,
                )
            else:
                # SQLite (tests): fallback to read-modify-write; not safe under concurrency
                await self._increment_usage_fallback(
                    session, order_id, period_start, period_end,
                    request_count, input_tokens, output_tokens, tool_calls, client_id,
                )

    async def _increment_usage_atomic(
        self,
        session,
        order_id: str,
        period_start: datetime,
        period_end: datetime,
        request_count: int,
        input_tokens: int,
        output_tokens: int,
        tool_calls: int,
        client_id: str | None,
    ) -> None:
        """Atomic upsert: single SQL statement, no read-before-write."""
        stmt = pg_insert(UsageRecordModel).values(
            order_id=order_id,
            client_id=client_id,
            request_count=request_count,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            tool_calls=tool_calls,
            period_start=period_start,
            period_end=period_end,
            reported=False,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["order_id", "period_start", "period_end"],
            index_where=UsageRecordModel.reported.is_(False),
            set_={
                UsageRecordModel.request_count: UsageRecordModel.request_count + stmt.excluded.request_count,
                UsageRecordModel.input_tokens: UsageRecordModel.input_tokens + stmt.excluded.input_tokens,
                UsageRecordModel.output_tokens: UsageRecordModel.output_tokens + stmt.excluded.output_tokens,
                UsageRecordModel.tool_calls: UsageRecordModel.tool_calls + stmt.excluded.tool_calls,
                UsageRecordModel.client_id: func.coalesce(
                    UsageRecordModel.client_id,
                    stmt.excluded.client_id,
                ),
            },
        )
        await session.execute(stmt)

    async def _increment_usage_fallback(
        self,
        session,
        order_id: str,
        period_start: datetime,
        period_end: datetime,
        request_count: int,
        input_tokens: int,
        output_tokens: int,
        tool_calls: int,
        client_id: str | None,
    ) -> None:
        """Fallback for SQLite (tests): read-modify-write. Not concurrency-safe."""
        result = await session.execute(
            select(UsageRecordModel).where(
                UsageRecordModel.order_id == order_id,
                UsageRecordModel.period_start == period_start,
                UsageRecordModel.period_end == period_end,
                UsageRecordModel.reported.is_(False),
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.request_count += request_count
            existing.input_tokens += input_tokens
            existing.output_tokens += output_tokens
            existing.tool_calls += tool_calls
            if client_id and not existing.client_id:
                existing.client_id = client_id
            return

        session.add(
            UsageRecordModel(
                order_id=order_id,
                client_id=client_id,
                request_count=request_count,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                tool_calls=tool_calls,
                period_start=period_start,
                period_end=period_end,
                reported=False,
            )
        )

    async def get_unreported_usage(
        self,
        *,
        order_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, int]:
        """Aggregate unreported usage for an order within a period."""
        start = _normalize_utc(start_time)
        end = _normalize_utc(end_time)

        async with get_session() as session:
            result = await session.execute(
                select(UsageRecordModel).where(
                    UsageRecordModel.order_id == order_id,
                    UsageRecordModel.reported.is_(False),
                    UsageRecordModel.period_start >= start,
                    UsageRecordModel.period_end <= end,
                )
            )
            rows = result.scalars().all()

        if not rows:
            return {}

        total_requests = sum(r.request_count for r in rows)
        total_input_tokens = sum(r.input_tokens for r in rows)
        total_output_tokens = sum(r.output_tokens for r in rows)
        total_tool_calls = sum(r.tool_calls for r in rows)

        metrics: dict[str, int] = {}
        if total_requests > 0:
            metrics["send_message_requests"] = total_requests
        if total_input_tokens > 0:
            metrics["input_tokens"] = total_input_tokens
        if total_output_tokens > 0:
            metrics["output_tokens"] = total_output_tokens
        if total_tool_calls > 0:
            metrics["mcp_tool_calls"] = total_tool_calls
        return metrics

    async def mark_reported_for_period(
        self,
        *,
        order_id: str,
        start_time: datetime,
        end_time: datetime,
        reported_at: datetime | None = None,
    ) -> int:
        """Mark unreported usage rows as reported for an order/time window."""
        start = _normalize_utc(start_time)
        end = _normalize_utc(end_time)
        marked_at = _normalize_utc(reported_at or datetime.now(UTC))

        async with get_session() as session:
            stmt = (
                update(UsageRecordModel)
                .where(
                    UsageRecordModel.order_id == order_id,
                    UsageRecordModel.reported.is_(False),
                    UsageRecordModel.period_start >= start,
                    UsageRecordModel.period_end <= end,
                )
                .values(reported=True, reported_at=marked_at, report_error=None)
            )
            result = await session.execute(stmt)
            return int(result.rowcount or 0)

    async def get_usage_by_order(self) -> dict[str, dict[str, int]]:
        """Return cumulative usage totals grouped by order_id."""
        async with get_session() as session:
            result = await session.execute(
                select(
                    UsageRecordModel.order_id,
                    func.sum(UsageRecordModel.request_count),
                    func.sum(UsageRecordModel.input_tokens),
                    func.sum(UsageRecordModel.output_tokens),
                    func.sum(UsageRecordModel.tool_calls),
                ).group_by(UsageRecordModel.order_id)
            )
            rows = result.all()

        usage_by_order: dict[str, dict[str, int]] = {}
        for order_id, total_requests, total_input, total_output, total_tools in rows:
            in_tokens = int(total_input or 0)
            out_tokens = int(total_output or 0)
            usage_by_order[order_id] = {
                "total_input_tokens": in_tokens,
                "total_output_tokens": out_tokens,
                "total_tokens": in_tokens + out_tokens,
                "total_requests": int(total_requests or 0),
                "total_tool_calls": int(total_tools or 0),
            }
        return usage_by_order


_usage_repo: UsageRepository | None = None


def get_usage_repository() -> UsageRepository:
    """Return process-wide usage repository singleton."""
    global _usage_repo
    if _usage_repo is None:
        _usage_repo = UsageRepository()
    return _usage_repo

