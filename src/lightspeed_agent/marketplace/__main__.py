"""Entry point for running the Marketplace Handler service."""

import logging
import os
import sys

import uvicorn


def main() -> None:
    """Run the Marketplace Handler service."""
    # Configure logging
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "text")

    handler = logging.StreamHandler(sys.stdout)  # stdout for container log collectors

    if log_format == "json":
        from pythonjsonlogger.json import JsonFormatter

        handler.setFormatter(
            JsonFormatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
                rename_fields={
                    "asctime": "time",
                    "levelname": "level",
                    "name": "logger",
                },
            )
        )
        logging.basicConfig(level=log_level, handlers=[handler])
    else:
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[handler],
        )

    # Get host and port from environment
    host = os.getenv("HANDLER_HOST", "0.0.0.0")
    port = int(os.getenv("HANDLER_PORT", "8001"))
    probe_port = int(os.getenv("HANDLER_PROBE_PORT", "8003"))

    logging.info(f"Starting Marketplace Handler on {host}:{port}")
    logging.info(f"Probe server will start on port {probe_port}")

    uvicorn.run(
        "lightspeed_agent.marketplace.app:create_app",
        host=host,
        port=port,
        factory=True,
        log_level=log_level.lower(),
        proxy_headers=os.getenv("PROXY_HEADERS", "true").lower() == "true",
        forwarded_allow_ips=os.getenv("FORWARDED_ALLOW_IPS", "*"),
    )


if __name__ == "__main__":
    main()
