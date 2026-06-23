"""Main entry point for the Lightspeed Agent."""

import logging
import sys

import uvicorn
from dotenv import load_dotenv

from lightspeed_agent.config import get_settings


def setup_logging() -> None:
    """Configure application logging."""
    from lightspeed_agent.logging.filters import AuditContextFilter

    settings = get_settings()

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(AuditContextFilter())

    level = getattr(logging, settings.log_level.upper())
    if settings.log_format == "json":
        from pythonjsonlogger.json import JsonFormatter

        handler.setFormatter(
            JsonFormatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s "
                "%(user_id)s %(org_id)s %(order_id)s %(request_id)s",
                rename_fields={
                    "asctime": "time",
                    "levelname": "level",
                    "name": "logger",
                },
            )
        )
        logging.basicConfig(level=level, handlers=[handler])
    else:
        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[handler],
        )


def main() -> None:
    """Run the Lightspeed Agent server."""
    # Load environment variables from .env file
    load_dotenv()

    # Set up logging
    setup_logging()

    settings = get_settings()
    logger = logging.getLogger(__name__)

    # Initialize OpenTelemetry tracing (must be done before creating app)
    from lightspeed_agent.telemetry import setup_telemetry, shutdown_telemetry

    setup_telemetry()

    logger.info(
        "Starting Lightspeed Agent",
        extra={
            "agent_name": settings.agent_name,
            "model": settings.gemini_model,
            "host": settings.agent_host,
            "port": settings.agent_port,
            "probe_port": settings.agent_probe_port,
            "otel_enabled": settings.otel_enabled,
        },
    )
    logger.info("Probe server will start on port %d", settings.agent_probe_port)

    # Import app here to ensure environment is configured
    from lightspeed_agent.api.app import create_app

    app = create_app()

    try:
        uvicorn.run(
            app,
            host=settings.agent_host,
            port=settings.agent_port,
            log_level=settings.log_level.lower(),
            proxy_headers=settings.proxy_headers,
            forwarded_allow_ips=settings.forwarded_allow_ips,
        )
    finally:
        # Ensure telemetry is properly shut down
        shutdown_telemetry()


if __name__ == "__main__":
    main()
