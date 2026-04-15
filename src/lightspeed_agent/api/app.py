"""FastAPI application for the Lightspeed Agent.

This is the A2A agent service that handles:
- A2A protocol requests (message/send, message/stream)
- AgentCard discovery (/.well-known/agent.json)

Note: DCR and Marketplace provisioning are handled by the separate
marketplace-handler service. See lightspeed_agent.marketplace.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from a2a.server.apps.jsonrpc.fastapi_app import A2AFastAPI
from fastapi.middleware.cors import CORSMiddleware

from lightspeed_agent.api.a2a.a2a_setup import setup_a2a_routes
from lightspeed_agent.api.a2a.agent_card import get_agent_card_dict
from lightspeed_agent.auth import AuthenticationMiddleware
from lightspeed_agent.config import get_settings
from lightspeed_agent.probes import start_probe_server, stop_probe_server
from lightspeed_agent.ratelimit import RateLimitMiddleware, get_redis_rate_limiter
from lightspeed_agent.security import SecurityHeadersMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: A2AFastAPI) -> AsyncIterator[None]:
    """Application lifespan manager for startup/shutdown events."""
    settings = get_settings()

    # Startup: Verify Redis connectivity for rate limiting
    try:
        await get_redis_rate_limiter().verify_connection()
        logger.info("Rate limiter Redis backend is reachable")
    except Exception as e:
        logger.error("Rate limiter Redis backend is unavailable: %s", e)
        raise

    # Startup: Initialize database
    try:
        from lightspeed_agent.db import init_database

        logger.info("Initializing database: %s",
                    settings.database_url.split("@")[-1])
        await init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database: %s", e)
        raise

    # Startup: Start the usage reporting scheduler
    if (settings.service_control_enabled and
            settings.service_control_service_name):
        try:
            from lightspeed_agent.service_control import start_reporting_scheduler

            logger.info("Starting usage reporting scheduler")
            await start_reporting_scheduler()
        except ImportError:
            logger.warning(
                "google-cloud-service-control not installed, "
                "skipping usage reporting scheduler"
            )
        except Exception as e:
            logger.error("Failed to start reporting scheduler: %s", e)

    # Startup: Start the probe server on a separate port
    async def _check_database() -> None:
        from lightspeed_agent.db import get_engine

        engine = get_engine()
        async with engine.begin() as conn:
            await conn.exec_driver_sql("SELECT 1")

    async def _check_redis() -> None:
        await get_redis_rate_limiter().verify_connection()

    logger.info("Starting probe server on port %d", settings.agent_probe_port)
    await start_probe_server(
        settings.agent_probe_port,
        settings.agent_name,
        readiness_checks={"database": _check_database, "redis": _check_redis},
    )

    yield

    # Shutdown: Stop the probe server
    await stop_probe_server()

    # Shutdown: Stop the usage reporting scheduler
    if settings.service_control_enabled and settings.service_control_service_name:
        try:
            from lightspeed_agent.service_control import stop_reporting_scheduler

            logger.info("Stopping usage reporting scheduler")
            await stop_reporting_scheduler()
        except Exception as e:
            logger.error("Failed to stop reporting scheduler: %s", e)

    # Shutdown: Close database connection
    try:
        from lightspeed_agent.db import close_database

        logger.info("Closing database connection")
        await close_database()
    except Exception as e:
        logger.error("Failed to close database: %s", e)

    # Shutdown: Close Redis connection used by rate limiter
    try:
        await get_redis_rate_limiter().close()
    except Exception as e:
        logger.error("Failed to close rate limiter Redis connection: %s", e)


def create_app() -> A2AFastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    app = A2AFastAPI(
        title=settings.agent_name,
        description=settings.agent_description,
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # Set up A2A protocol routes using ADK's built-in integration
    # This provides:
    # - GET /.well-known/agent.json - AgentCard
    # - POST / - JSON-RPC 2.0 endpoint for message/send, message/stream, etc.
    # The ADK integration handles SSE streaming, task management, and
    # event conversion automatically.
    setup_a2a_routes(app)

    # Alias for agent card (some clients use agent-card.json)
    @app.get("/.well-known/agent-card.json")
    async def agent_card_alias() -> dict[str, Any]:
        """AgentCard endpoint (alias for agent.json)."""
        return get_agent_card_dict()

    # Add rate limiting middleware
    app.add_middleware(RateLimitMiddleware)

    # Add authentication middleware for A2A endpoint
    # Validates Red Hat SSO JWT tokens on POST / requests
    # Can be disabled with SKIP_JWT_VALIDATION=true for development
    app.add_middleware(AuthenticationMiddleware)

    # Add security headers middleware (HSTS, X-Content-Type-Options, X-Frame-Options)
    app.add_middleware(SecurityHeadersMiddleware)

    # Add CORS middleware for A2A Inspector and other browser-based clients
    # This must be added after other middleware to be processed first
    # Middleware execution order: CORS -> SecurityHeaders -> Auth -> RateLimit -> Handler
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for development
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # Include Service Control router (admin endpoints for usage reporting)
    # Provides:
    # - GET /service-control/status - Get scheduler status
    # - POST /service-control/report - Trigger manual report for an order
    # - POST /service-control/report/all - Trigger reports for all orders
    # - POST /service-control/retry - Retry failed reports
    if settings.service_control_enabled:
        try:
            from lightspeed_agent.service_control import service_control_router

            app.include_router(service_control_router)
        except ImportError:
            logger.warning(
                "google-cloud-service-control not installed, "
                "skipping service control router"
            )

    return app
