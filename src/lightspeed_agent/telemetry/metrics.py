"""OTel metrics: cache, collector, gauge callbacks, and tool call counter."""

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select

from lightspeed_agent.db import (
    DCRClientModel,
    MarketplaceEntitlementModel,
    UsageRecordModel,
    get_session,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cache dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SubscriptionSnapshot:
    account_id: str
    state: str
    count: int


@dataclass
class DCRClientSnapshot:
    account_id: str
    order_id: str
    client_id: str


@dataclass
class UsageSnapshot:
    order_id: str
    client_id: str | None
    input_tokens: int
    output_tokens: int
    request_count: int


@dataclass
class MetricsCache:
    subscriptions: list[SubscriptionSnapshot] = field(default_factory=list)
    dcr_clients: list[DCRClientSnapshot] = field(default_factory=list)
    usage_by_order: list[UsageSnapshot] = field(default_factory=list)
    last_updated: datetime | None = None


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------


class MetricsCollector:
    """Background task that polls the DB and updates the metrics cache."""

    def __init__(self, collection_interval: int = 60) -> None:
        self._interval = collection_interval
        self._cache = MetricsCache()
        self._task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def cache(self) -> MetricsCache:
        return self._cache

    async def _collect_once(self) -> None:
        """Run one collection cycle."""
        try:
            subscriptions = await self._query_subscriptions()
            dcr_clients = await self._query_dcr_clients()
            usage = await self._query_usage()

            self._cache = MetricsCache(
                subscriptions=subscriptions,
                dcr_clients=dcr_clients,
                usage_by_order=usage,
                last_updated=datetime.now(UTC),
            )
            logger.debug("Metrics cache updated")
        except Exception:
            logger.warning(
                "Failed to collect metrics from DB, serving stale cache", exc_info=True
            )

    async def _query_subscriptions(self) -> list[SubscriptionSnapshot]:
        async with get_session() as session:
            stmt = select(
                MarketplaceEntitlementModel.account_id,
                MarketplaceEntitlementModel.state,
                func.count().label("entitlement_count"),
            ).group_by(
                MarketplaceEntitlementModel.account_id,
                MarketplaceEntitlementModel.state,
            )
            result = await session.execute(stmt)
            return [
                SubscriptionSnapshot(
                    account_id=r.account_id,
                    state=r.state,
                    count=int(r.entitlement_count),
                )
                for r in result.all()
            ]

    async def _query_dcr_clients(self) -> list[DCRClientSnapshot]:
        async with get_session() as session:
            stmt = select(
                DCRClientModel.account_id,
                DCRClientModel.order_id,
                DCRClientModel.client_id,
            )
            result = await session.execute(stmt)
            return [
                DCRClientSnapshot(
                    account_id=r.account_id,
                    order_id=r.order_id,
                    client_id=r.client_id,
                )
                for r in result.all()
            ]

    async def _query_usage(self) -> list[UsageSnapshot]:
        async with get_session() as session:
            stmt = (
                select(
                    UsageRecordModel.order_id,
                    UsageRecordModel.client_id,
                    func.sum(UsageRecordModel.input_tokens).label("input_tokens"),
                    func.sum(UsageRecordModel.output_tokens).label("output_tokens"),
                    func.sum(UsageRecordModel.request_count).label("request_count"),
                )
                .group_by(
                    UsageRecordModel.order_id,
                    UsageRecordModel.client_id,
                )
            )
            result = await session.execute(stmt)
            return [
                UsageSnapshot(
                    order_id=r.order_id,
                    client_id=r.client_id,
                    input_tokens=int(r.input_tokens or 0),
                    output_tokens=int(r.output_tokens or 0),
                    request_count=int(r.request_count or 0),
                )
                for r in result.all()
            ]

    async def _collect_loop(self) -> None:
        while self._running:
            await self._collect_once()
            await asyncio.sleep(self._interval)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(
            self._collect_loop(),
            name="metrics_collector",
        )
        logger.info("Metrics collector started (interval=%ds)", self._interval)

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("Metrics collector stopped")


# ---------------------------------------------------------------------------
# Observation dataclass (for gauge callbacks)
# ---------------------------------------------------------------------------


@dataclass
class Observation:
    value: int | float
    attributes: dict[str, str]


# ---------------------------------------------------------------------------
# Gauge callback functions
# ---------------------------------------------------------------------------


def _observe_subscriptions(collector: MetricsCollector) -> list[Observation]:
    cache = collector.cache
    return [
        Observation(
            value=s.count,
            attributes={"account_id": s.account_id, "state": s.state},
        )
        for s in cache.subscriptions
    ]


def _observe_dcr_clients(collector: MetricsCollector) -> list[Observation]:
    cache = collector.cache
    return [
        Observation(
            value=1,
            attributes={
                "account_id": c.account_id,
                "order_id": c.order_id,
                "client_id": c.client_id,
            },
        )
        for c in cache.dcr_clients
    ]


def _observe_tokens_input(collector: MetricsCollector) -> list[Observation]:
    cache = collector.cache
    return [
        Observation(
            value=u.input_tokens,
            attributes={
                "order_id": u.order_id,
                "client_id": u.client_id or "",
            },
        )
        for u in cache.usage_by_order
    ]


def _observe_tokens_output(collector: MetricsCollector) -> list[Observation]:
    cache = collector.cache
    return [
        Observation(
            value=u.output_tokens,
            attributes={
                "order_id": u.order_id,
                "client_id": u.client_id or "",
            },
        )
        for u in cache.usage_by_order
    ]


def _observe_requests(collector: MetricsCollector) -> list[Observation]:
    cache = collector.cache
    return [
        Observation(
            value=u.request_count,
            attributes={
                "order_id": u.order_id,
                "client_id": u.client_id or "",
            },
        )
        for u in cache.usage_by_order
    ]


# ---------------------------------------------------------------------------
# Tool call counter
# ---------------------------------------------------------------------------

_tool_call_counter = None


def increment_tool_call(
    tool_name: str,
    order_id: str,
    client_id: str | None = None,
) -> None:
    """Increment the tool_calls_by_name counter. No-op if metrics are disabled."""
    if _tool_call_counter is None:
        return
    _tool_call_counter.add(
        1,
        attributes={
            "tool_name": tool_name,
            "order_id": order_id,
            "client_id": client_id or "",
        },
    )


# ---------------------------------------------------------------------------
# Instrument registration
# ---------------------------------------------------------------------------


def _register_instruments(collector: MetricsCollector) -> None:
    """Register OTel instruments on the global MeterProvider."""
    global _tool_call_counter
    from opentelemetry import metrics as otel_metrics

    meter = otel_metrics.get_meter("lightspeed_agent.metrics")

    meter.create_observable_gauge(
        name="subscriptions_total",
        description="Entitlement count by account and state",
        callbacks=[
            lambda _options: [
                otel_metrics.Observation(o.value, o.attributes)
                for o in _observe_subscriptions(collector)
            ]
        ],
    )
    meter.create_observable_gauge(
        name="dcr_clients_active",
        description="Active DCR clients",
        callbacks=[
            lambda _options: [
                otel_metrics.Observation(o.value, o.attributes)
                for o in _observe_dcr_clients(collector)
            ]
        ],
    )
    meter.create_observable_gauge(
        name="tokens_input_total",
        description="Total input tokens by order",
        callbacks=[
            lambda _options: [
                otel_metrics.Observation(o.value, o.attributes)
                for o in _observe_tokens_input(collector)
            ]
        ],
    )
    meter.create_observable_gauge(
        name="tokens_output_total",
        description="Total output tokens by order",
        callbacks=[
            lambda _options: [
                otel_metrics.Observation(o.value, o.attributes)
                for o in _observe_tokens_output(collector)
            ]
        ],
    )
    meter.create_observable_gauge(
        name="requests_total",
        description="Total requests by order",
        callbacks=[
            lambda _options: [
                otel_metrics.Observation(o.value, o.attributes)
                for o in _observe_requests(collector)
            ]
        ],
    )
    _tool_call_counter = meter.create_counter(
        name="tool_calls_by_name",
        description="Tool invocations by tool name and order",
    )
    logger.info("OTel metrics instruments registered")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector | None:
    return _collector


async def start_metrics_collector() -> None:
    """Start the global metrics collector. Call after DB init and setup_telemetry."""
    global _collector
    from lightspeed_agent.config import get_settings

    settings = get_settings()
    if not settings.otel_metrics_enabled:
        logger.debug("OTel metrics disabled, skipping collector")
        return

    _collector = MetricsCollector(
        collection_interval=settings.otel_metrics_collection_interval,
    )
    _register_instruments(_collector)
    await _collector.start()


async def stop_metrics_collector() -> None:
    """Stop the global metrics collector."""
    global _collector
    if _collector:
        await _collector.stop()
        _collector = None
