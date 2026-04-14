"""Lightweight probe server for health and readiness checks."""

import asyncio
import logging

import uvicorn
from fastapi import FastAPI

logger = logging.getLogger(__name__)

_server: uvicorn.Server | None = None
_task: asyncio.Task | None = None  # type: ignore[type-arg]


def create_probe_app(service_name: str) -> FastAPI:
    """Create a minimal FastAPI app with health and readiness endpoints."""
    app = FastAPI(title=f"{service_name} probes", docs_url=None, redoc_url=None)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy", "service": service_name}

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        return {"status": "ready", "service": service_name}

    return app


async def start_probe_server(port: int, service_name: str) -> None:
    """Start the probe server as a background asyncio task."""
    global _server, _task  # noqa: PLW0603

    if _server is not None or _task is not None:
        await stop_probe_server()

    app = create_probe_app(service_name)
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="warning",
    )
    _server = uvicorn.Server(config)
    _task = asyncio.create_task(_server.serve())
    logger.info("Probe server started on port %d for service %s", port, service_name)


async def stop_probe_server() -> None:
    """Signal the probe server to shut down gracefully."""
    global _server, _task  # noqa: PLW0603

    if _server is not None:
        _server.should_exit = True
    if _task is not None:
        await _task
        _task = None
    _server = None
    logger.info("Probe server stopped")
