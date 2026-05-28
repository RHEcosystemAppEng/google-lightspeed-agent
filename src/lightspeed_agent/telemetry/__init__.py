"""OpenTelemetry integration for distributed tracing and metrics."""

from lightspeed_agent.telemetry.setup import setup_telemetry, shutdown_telemetry

__all__ = ["setup_telemetry", "shutdown_telemetry"]
