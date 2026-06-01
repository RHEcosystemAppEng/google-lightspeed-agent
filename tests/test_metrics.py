"""Tests for OTel metrics cache and collector."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest

from lightspeed_agent.db import (
    DCRClientModel,
    MarketplaceEntitlementModel,
    UsageRecordModel,
    get_session,
)


@pytest.fixture
async def seeded_db(db_session):
    """Seed the database with test data for metrics queries."""
    now = datetime.now(UTC)
    period_start = now.replace(minute=0, second=0, microsecond=0)
    period_end = period_start + timedelta(hours=1)

    async with get_session() as session:
        session.add(
            MarketplaceEntitlementModel(
                id="order-001",
                account_id="account-A",
                provider_id="google",
                state="active",
            )
        )
        session.add(
            MarketplaceEntitlementModel(
                id="order-002",
                account_id="account-B",
                provider_id="google",
                state="cancelled",
            )
        )
        session.add(
            DCRClientModel(
                order_id="order-001",
                client_id="client-aaa",
                client_secret_encrypted="encrypted",
                account_id="account-A",
            )
        )
        session.add(
            UsageRecordModel(
                order_id="order-001",
                client_id="client-aaa",
                input_tokens=100,
                output_tokens=50,
                request_count=5,
                tool_calls=3,
                period_start=period_start,
                period_end=period_end,
                reported=False,
            )
        )
        await session.commit()


class TestMetricsCache:
    """Tests for MetricsCache dataclass."""

    def test_empty_cache_defaults(self):
        from lightspeed_agent.telemetry.metrics import MetricsCache

        cache = MetricsCache()
        assert cache.subscriptions == []
        assert cache.dcr_clients == []
        assert cache.usage_by_order == []
        assert cache.last_updated is None


class TestMetricsCollector:
    """Tests for the background DB polling collector."""

    @pytest.mark.asyncio
    async def test_collect_populates_cache(self, seeded_db):
        from lightspeed_agent.telemetry.metrics import MetricsCollector

        collector = MetricsCollector(collection_interval=60)
        await collector._collect_once()

        cache = collector.cache
        assert cache.last_updated is not None

        assert len(cache.subscriptions) == 2
        active = [s for s in cache.subscriptions if s.state == "active"]
        assert len(active) == 1
        assert active[0].account_id == "account-A"
        assert active[0].count == 1

        cancelled = [s for s in cache.subscriptions if s.state == "cancelled"]
        assert len(cancelled) == 1
        assert cancelled[0].account_id == "account-B"

        assert len(cache.dcr_clients) == 1
        assert cache.dcr_clients[0].account_id == "account-A"
        assert cache.dcr_clients[0].count == 1

        assert len(cache.usage_by_order) == 1
        u = cache.usage_by_order[0]
        assert u.account_id == "account-A"
        assert u.input_tokens == 100
        assert u.output_tokens == 50
        assert u.request_count == 5

    @pytest.mark.asyncio
    async def test_collect_handles_db_error(self, db_session, monkeypatch):
        """DB errors should log a warning and leave cache stale."""
        from lightspeed_agent.telemetry.metrics import MetricsCollector

        collector = MetricsCollector(collection_interval=60)
        await collector._collect_once()
        first_update = collector.cache.last_updated

        import lightspeed_agent.telemetry.metrics as metrics_mod

        @asynccontextmanager
        async def broken_context():
            raise RuntimeError("DB down")
            yield  # pragma: no cover

        monkeypatch.setattr(metrics_mod, "get_session", broken_context)

        await collector._collect_once()
        assert collector.cache.last_updated == first_update

    @pytest.mark.asyncio
    async def test_collector_start_stop(self, db_session):
        from lightspeed_agent.telemetry.metrics import MetricsCollector

        collector = MetricsCollector(collection_interval=60)
        await collector.start()
        assert collector._task is not None
        assert not collector._task.done()

        await collector.stop()
        assert collector._task.done()


class TestMeterProviderSetup:
    """Tests for MeterProvider creation in setup_telemetry."""

    def test_setup_telemetry_creates_meter_provider_when_metrics_enabled(
        self, monkeypatch
    ):
        """When otel_metrics_enabled=True, setup_telemetry creates a MeterProvider."""
        from opentelemetry import metrics as otel_metrics

        from lightspeed_agent.telemetry import setup as setup_mod

        setup_mod._tracer_provider = None
        setup_mod._meter_provider = None

        monkeypatch.setenv("OTEL_ENABLED", "false")
        monkeypatch.setenv("OTEL_METRICS_ENABLED", "true")
        monkeypatch.setenv("OTEL_EXPORTER_PROMETHEUS_PORT", "0")

        from lightspeed_agent.config import get_settings

        get_settings.cache_clear()

        try:
            from lightspeed_agent.telemetry.setup import setup_telemetry, shutdown_telemetry

            setup_telemetry()

            provider = otel_metrics.get_meter_provider()
            assert not isinstance(provider, otel_metrics.NoOpMeterProvider)

            shutdown_telemetry()
        finally:
            get_settings.cache_clear()


class TestGaugeCallbacks:
    """Tests for OTel gauge callback functions."""

    def test_subscription_gauge_reads_cache(self):
        from lightspeed_agent.telemetry.metrics import (
            MetricsCache,
            MetricsCollector,
            SubscriptionSnapshot,
            _observe_subscriptions,
        )

        collector = MetricsCollector(collection_interval=60)
        collector._cache = MetricsCache(
            subscriptions=[
                SubscriptionSnapshot(account_id="acct-A", state="active", count=2),
                SubscriptionSnapshot(account_id="acct-B", state="cancelled", count=1),
            ],
        )

        observations = list(_observe_subscriptions(collector))
        assert len(observations) == 2

        active_obs = [o for o in observations if o.attributes["state"] == "active"]
        assert len(active_obs) == 1
        assert active_obs[0].value == 2
        assert active_obs[0].attributes["account_id"] == "acct-A"

    def test_dcr_clients_gauge_reads_cache(self):
        from lightspeed_agent.telemetry.metrics import (
            DCRClientSnapshot,
            MetricsCache,
            MetricsCollector,
            _observe_dcr_clients,
        )

        collector = MetricsCollector(collection_interval=60)
        collector._cache = MetricsCache(
            dcr_clients=[
                DCRClientSnapshot(account_id="acct-A", count=1),
            ],
        )

        observations = list(_observe_dcr_clients(collector))
        assert len(observations) == 1
        assert observations[0].value == 1
        assert observations[0].attributes["account_id"] == "acct-A"

    def test_usage_gauge_reads_cache(self):
        from lightspeed_agent.telemetry.metrics import (
            MetricsCache,
            MetricsCollector,
            UsageSnapshot,
            _observe_tokens_input,
        )

        collector = MetricsCollector(collection_interval=60)
        collector._cache = MetricsCache(
            usage_by_order=[
                UsageSnapshot(
                    account_id="acct-A",
                    input_tokens=5000,
                    output_tokens=1000,
                    request_count=10,
                ),
            ],
        )

        observations = list(_observe_tokens_input(collector))
        assert len(observations) == 1
        assert observations[0].value == 5000

    def test_empty_cache_returns_no_observations(self):
        from lightspeed_agent.telemetry.metrics import (
            MetricsCollector,
            _observe_subscriptions,
        )

        collector = MetricsCollector(collection_interval=60)
        observations = list(_observe_subscriptions(collector))
        assert observations == []


class TestToolCallCounter:
    """Tests for the in-process tool call counter."""

    def test_increment_tool_call(self):
        from lightspeed_agent.telemetry.metrics import increment_tool_call

        increment_tool_call(tool_name="advisor_list_recommendations")


class TestEndToEnd:
    """End-to-end test: DB -> collector -> gauge callbacks -> InMemoryMetricReader."""

    @pytest.mark.asyncio
    async def test_full_pipeline(self, seeded_db, monkeypatch):
        from opentelemetry import metrics as otel_metrics
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import InMemoryMetricReader

        import lightspeed_agent.telemetry.metrics as metrics_mod

        reader = InMemoryMetricReader()
        provider = MeterProvider(metric_readers=[reader])

        collector = metrics_mod.MetricsCollector(collection_interval=60)

        meter = provider.get_meter("lightspeed_agent.metrics")

        meter.create_observable_gauge(
            name="subscriptions_total",
            description="Entitlement count by account and state",
            callbacks=[
                lambda _options: [
                    otel_metrics.Observation(o.value, o.attributes)
                    for o in metrics_mod._observe_subscriptions(collector)
                ]
            ],
        )
        meter.create_observable_gauge(
            name="dcr_clients_active",
            description="Active DCR clients",
            callbacks=[
                lambda _options: [
                    otel_metrics.Observation(o.value, o.attributes)
                    for o in metrics_mod._observe_dcr_clients(collector)
                ]
            ],
        )
        meter.create_observable_gauge(
            name="tokens_input_total",
            description="Total input tokens by order",
            callbacks=[
                lambda _options: [
                    otel_metrics.Observation(o.value, o.attributes)
                    for o in metrics_mod._observe_tokens_input(collector)
                ]
            ],
        )
        meter.create_observable_gauge(
            name="tokens_output_total",
            description="Total output tokens by order",
            callbacks=[
                lambda _options: [
                    otel_metrics.Observation(o.value, o.attributes)
                    for o in metrics_mod._observe_tokens_output(collector)
                ]
            ],
        )
        meter.create_observable_gauge(
            name="requests_total",
            description="Total requests by order",
            callbacks=[
                lambda _options: [
                    otel_metrics.Observation(o.value, o.attributes)
                    for o in metrics_mod._observe_requests(collector)
                ]
            ],
        )
        tool_counter = meter.create_counter(
            name="tool_calls_by_name",
            description="Tool invocations by tool name and order",
        )
        tool_counter.add(1, attributes={"tool_name": "test"})

        await collector._collect_once()

        metrics_data = reader.get_metrics_data()
        metric_names = set()
        for resource_metrics in metrics_data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    metric_names.add(metric.name)

        assert "subscriptions_total" in metric_names
        assert "dcr_clients_active" in metric_names
        assert "tokens_input_total" in metric_names
        assert "tokens_output_total" in metric_names
        assert "requests_total" in metric_names
        assert "tool_calls_by_name" in metric_names

        provider.shutdown()
