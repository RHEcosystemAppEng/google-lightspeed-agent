"""OpenTelemetry setup and configuration."""

import logging
from typing import TYPE_CHECKING, Any

from opentelemetry import metrics as otel_metrics
from opentelemetry import trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    ParentBased,
    TraceIdRatioBased,
)

if TYPE_CHECKING:
    from opentelemetry.sdk.trace.sampling import Sampler

logger = logging.getLogger(__name__)

_tracer_provider: TracerProvider | None = None
_meter_provider: MeterProvider | None = None


def _get_sampler(sampler_type: str, sampler_arg: float) -> "Sampler":
    """Get the appropriate sampler based on configuration."""
    if sampler_type == "always_on":
        return ALWAYS_ON
    elif sampler_type == "always_off":
        return ALWAYS_OFF
    elif sampler_type == "traceidratio":
        return TraceIdRatioBased(sampler_arg)
    elif sampler_type == "parentbased_always_on":
        return ParentBased(ALWAYS_ON)
    elif sampler_type == "parentbased_always_off":
        return ParentBased(ALWAYS_OFF)
    elif sampler_type == "parentbased_traceidratio":
        return ParentBased(TraceIdRatioBased(sampler_arg))
    else:
        logger.warning("Unknown sampler type '%s', using always_on", sampler_type)
        return ALWAYS_ON


def _create_exporter(exporter_type: str, otlp_endpoint: str, otlp_http_endpoint: str) -> Any:
    """Create the appropriate span exporter based on configuration."""
    if exporter_type == "console":
        return ConsoleSpanExporter()

    elif exporter_type == "otlp":
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        return OTLPSpanExporter(endpoint=otlp_endpoint)

    elif exporter_type == "otlp-http":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore[assignment]
            OTLPSpanExporter,
        )

        return OTLPSpanExporter(endpoint=f"{otlp_http_endpoint}/v1/traces")

    elif exporter_type == "jaeger":
        try:
            from opentelemetry.exporter.jaeger.thrift import JaegerExporter

            return JaegerExporter()
        except ImportError:
            logger.error(
                "Jaeger exporter not installed."
                " Install with: pip install opentelemetry-exporter-jaeger"
            )
            raise

    elif exporter_type == "zipkin":
        try:
            from opentelemetry.exporter.zipkin.json import ZipkinExporter

            return ZipkinExporter()
        except ImportError:
            logger.error(
                "Zipkin exporter not installed."
                " Install with: pip install opentelemetry-exporter-zipkin"
            )
            raise

    else:
        logger.warning("Unknown exporter type '%s', using console", exporter_type)
        return ConsoleSpanExporter()


def _create_meter_provider(resource: Resource, settings: Any) -> MeterProvider:
    """Create MeterProvider with OTLP and Prometheus MetricReaders."""
    from opentelemetry.sdk.metrics.export import MetricReader

    readers: list[MetricReader] = []

    if settings.otel_exporter_type in ("otlp", "otlp-http", "console"):
        metric_exporter: Any
        if settings.otel_exporter_type == "console":
            metric_exporter = ConsoleMetricExporter()
        elif settings.otel_exporter_type == "otlp":
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

            metric_exporter = OTLPMetricExporter(
                endpoint=settings.otel_exporter_otlp_endpoint
            )
        else:  # otlp-http
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import (  # type: ignore[assignment]
                OTLPMetricExporter,
            )

            metric_exporter = OTLPMetricExporter(
                endpoint=f"{settings.otel_exporter_otlp_http_endpoint}/v1/metrics"
            )

        readers.append(PeriodicExportingMetricReader(metric_exporter))
        logger.info("Metric reader created for exporter '%s'", settings.otel_exporter_type)
    else:
        logger.debug(
            "Exporter '%s' does not support metrics, skipping metric reader",
            settings.otel_exporter_type,
        )

    try:
        from opentelemetry.exporter.prometheus import PrometheusMetricReader
        from prometheus_client import start_http_server

        readers.append(PrometheusMetricReader())
        start_http_server(port=settings.otel_metrics_prometheus_port, addr="0.0.0.0")
        logger.info(
            "Prometheus scrape endpoint started on port %d",
            settings.otel_metrics_prometheus_port,
        )
    except ImportError:
        logger.warning(
            "opentelemetry-exporter-prometheus not installed, "
            "Prometheus scrape endpoint unavailable"
        )
    except OSError as e:
        logger.error(
            "Failed to start Prometheus scrape endpoint on port %d: %s",
            settings.otel_metrics_prometheus_port,
            e,
        )

    return MeterProvider(resource=resource, metric_readers=readers)


def setup_telemetry() -> None:
    """Initialize OpenTelemetry tracing, metrics, and/or MLflow span export.

    All three features are independently toggleable:
    - otel_enabled: standard OTel tracing (Jaeger/Zipkin/OTLP) + instrumentation
    - otel_metrics_enabled: OTel metrics with Prometheus + OTLP export
    - mlflow_enabled: span export to MLflow's OTLP endpoint (works with or without otel_enabled)
    """
    global _tracer_provider, _meter_provider

    from lightspeed_agent.config import get_settings

    settings = get_settings()

    if not settings.otel_enabled and not settings.otel_metrics_enabled and not settings.mlflow_enabled:
        logger.debug("OpenTelemetry tracing, metrics, and MLflow are disabled")
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": "0.1.0",
            "deployment.environment": "development" if settings.debug else "production",
        }
    )

    # Tracing setup (needed for both otel_enabled and mlflow_enabled)
    if settings.otel_enabled or settings.mlflow_enabled:
        sampler = _get_sampler(settings.otel_traces_sampler, settings.otel_traces_sampler_arg)
        _tracer_provider = TracerProvider(resource=resource, sampler=sampler)

        if settings.otel_enabled:
            logger.info(
                "Initializing OpenTelemetry tracing (service=%s, exporter=%s, sampler=%s)",
                settings.otel_service_name,
                settings.otel_exporter_type,
                settings.otel_traces_sampler,
            )
            exporter = _create_exporter(
                settings.otel_exporter_type,
                settings.otel_exporter_otlp_endpoint,
                settings.otel_exporter_otlp_http_endpoint,
            )
            _tracer_provider.add_span_processor(BatchSpanProcessor(exporter))

        if settings.mlflow_enabled:
            _add_mlflow_processor(settings, _tracer_provider)

        trace.set_tracer_provider(_tracer_provider)

        if settings.otel_enabled:
            _instrument_fastapi()
            _instrument_httpx()
            logger.info("OpenTelemetry tracing initialized successfully")

    # Metrics setup (independent of tracing)
    if settings.otel_metrics_enabled:
        logger.info("Initializing OpenTelemetry metrics")
        _meter_provider = _create_meter_provider(resource, settings)
        otel_metrics.set_meter_provider(_meter_provider)
        logger.info("OpenTelemetry metrics initialized")


def _instrument_fastapi() -> None:
    """Instrument FastAPI for automatic tracing."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor().instrument()
        logger.debug("FastAPI instrumentation enabled")
    except ImportError:
        logger.warning(
            "FastAPI instrumentation not available. "
            "Install with: pip install opentelemetry-instrumentation-fastapi"
        )
    except Exception as e:
        logger.warning("Failed to instrument FastAPI: %s", e)


def _instrument_httpx() -> None:
    """Instrument HTTPX for automatic tracing of outgoing requests."""
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
        logger.debug("HTTPX instrumentation enabled")
    except ImportError:
        logger.warning(
            "HTTPX instrumentation not available. "
            "Install with: pip install opentelemetry-instrumentation-httpx"
        )
    except Exception as e:
        logger.warning("Failed to instrument HTTPX: %s", e)


def _add_mlflow_processor(settings: Any, provider: TracerProvider) -> None:
    """Add an OTLP HTTP span processor that exports traces to MLflow."""
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter as OTLPHttpSpanExporter,
        )

        tracking_uri = settings.mlflow_tracking_uri.rstrip("/")

        mlflow_headers: dict[str, str] = {}
        if settings.mlflow_experiment_id:
            mlflow_headers["x-mlflow-experiment-id"] = settings.mlflow_experiment_id
        if settings.mlflow_experiment_name:
            mlflow_headers["x-mlflow-experiment-name"] = settings.mlflow_experiment_name
        if settings.mlflow_log_prompts:
            mlflow_headers["x-mlflow-log-prompts"] = "true"
        if settings.mlflow_run_tags:
            mlflow_headers["x-mlflow-run-tags"] = settings.mlflow_run_tags

        mlflow_exporter = OTLPHttpSpanExporter(
            endpoint=f"{tracking_uri}/v1/traces",
            headers=mlflow_headers,
        )
        provider.add_span_processor(BatchSpanProcessor(mlflow_exporter))

        logger.info(
            "MLflow tracing enabled (endpoint=%s/v1/traces)",
            tracking_uri,
        )
    except ImportError:
        logger.error(
            "MLflow tracing requires opentelemetry-exporter-otlp-proto-http. "
            "Install with: pip install 'lightspeed-agent[mlflow]'"
        )
        raise


def shutdown_telemetry() -> None:
    """Shutdown OpenTelemetry and flush any pending spans/metrics."""
    global _tracer_provider, _meter_provider

    if _meter_provider is not None:
        logger.info("Shutting down OpenTelemetry metrics")
        _meter_provider.shutdown()
        _meter_provider = None

    if _tracer_provider is not None:
        logger.info("Shutting down OpenTelemetry tracing")
        _tracer_provider.shutdown()
        _tracer_provider = None
