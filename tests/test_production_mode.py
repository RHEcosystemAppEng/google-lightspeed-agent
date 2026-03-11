"""Tests for production mode security guards.

Validates that all 10 production guards are enforced when PRODUCTION=true
and that they are bypassed when PRODUCTION=false. Also tests runtime guards
for CORS middleware and MCP header forwarding.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from lightspeed_agent.config import Settings


def _production_settings_kwargs() -> dict:
    """Return a valid production-mode configuration dict.

    All 10 guards are satisfied so ``Settings(**_production_settings_kwargs())``
    succeeds.
    """
    return dict(
        production=True,
        google_genai_use_vertexai=True,
        google_api_key=None,
        google_cloud_project="my-project",
        skip_jwt_validation=False,
        debug=False,
        agent_provider_url="https://agent.example.com",
        mcp_server_url="https://mcp.example.com",
        database_url="postgresql+asyncpg://user:pass@db:5432/lightspeed",
        mcp_transport_mode="http",
        lightspeed_client_id="",
        lightspeed_client_secret="",
        red_hat_sso_client_id="my-sso-client",
        red_hat_sso_client_secret="my-sso-secret",
        dcr_enabled=True,
        dcr_initial_access_token="my-token",
        dcr_encryption_key="my-key",
    )


class TestProductionHappyPath:
    """Verify that a fully valid production config passes all guards."""

    def test_valid_production_config(self):
        """Settings construction succeeds when all guards are satisfied."""
        settings = Settings(**_production_settings_kwargs())
        assert settings.production is True

    def test_production_vertex_ai_enabled(self):
        """Vertex AI is correctly enabled in production config."""
        settings = Settings(**_production_settings_kwargs())
        assert settings.google_genai_use_vertexai is True
        assert settings.google_api_key is None

    def test_production_jwt_validation_enabled(self):
        """JWT validation is enforced in production config."""
        settings = Settings(**_production_settings_kwargs())
        assert settings.skip_jwt_validation is False

    def test_production_debug_disabled(self):
        """Debug mode is disabled in production config."""
        settings = Settings(**_production_settings_kwargs())
        assert settings.debug is False


class TestProductionGuard1VertexAI:
    """Guard 1: Force Vertex AI — no API key, use Vertex AI, require project."""

    def test_google_api_key_must_not_be_set(self):
        """GOOGLE_API_KEY must not be set in production."""
        kwargs = _production_settings_kwargs()
        kwargs["google_api_key"] = "some-key"
        with pytest.raises(ValidationError, match="GOOGLE_API_KEY must not be set"):
            Settings(**kwargs)

    def test_vertex_ai_must_be_true(self):
        """GOOGLE_GENAI_USE_VERTEXAI must be true in production."""
        kwargs = _production_settings_kwargs()
        kwargs["google_genai_use_vertexai"] = False
        with pytest.raises(
            ValidationError, match="GOOGLE_GENAI_USE_VERTEXAI must be true"
        ):
            Settings(**kwargs)

    def test_google_cloud_project_must_be_set(self):
        """GOOGLE_CLOUD_PROJECT must be set in production."""
        kwargs = _production_settings_kwargs()
        kwargs["google_cloud_project"] = None
        with pytest.raises(
            ValidationError, match="GOOGLE_CLOUD_PROJECT must be set"
        ):
            Settings(**kwargs)


class TestProductionGuard2JWT:
    """Guard 2: Force JWT validation."""

    def test_skip_jwt_must_not_be_true(self):
        """SKIP_JWT_VALIDATION must not be true in production."""
        kwargs = _production_settings_kwargs()
        kwargs["skip_jwt_validation"] = True
        with pytest.raises(
            ValidationError, match="SKIP_JWT_VALIDATION must not be true"
        ):
            Settings(**kwargs)


class TestProductionGuard3Debug:
    """Guard 3: Disable debug mode."""

    def test_debug_must_not_be_true(self):
        """DEBUG must not be true in production."""
        kwargs = _production_settings_kwargs()
        kwargs["debug"] = True
        with pytest.raises(ValidationError, match="DEBUG must not be true"):
            Settings(**kwargs)


class TestProductionGuard4HTTPS:
    """Guard 4: Force HTTPS on all URLs."""

    def test_agent_provider_url_must_be_https(self):
        """AGENT_PROVIDER_URL must start with https in production."""
        kwargs = _production_settings_kwargs()
        kwargs["agent_provider_url"] = "http://agent.example.com"
        with pytest.raises(
            ValidationError, match="AGENT_PROVIDER_URL must start with https"
        ):
            Settings(**kwargs)

    def test_mcp_server_url_must_be_https(self):
        """MCP_SERVER_URL must start with https in production."""
        kwargs = _production_settings_kwargs()
        kwargs["mcp_server_url"] = "http://mcp.example.com"
        with pytest.raises(
            ValidationError, match="MCP_SERVER_URL must start with https"
        ):
            Settings(**kwargs)


class TestProductionGuard5PostgreSQL:
    """Guard 5: Force PostgreSQL (no SQLite)."""

    def test_database_url_must_not_use_sqlite(self):
        """DATABASE_URL must not use SQLite in production."""
        kwargs = _production_settings_kwargs()
        kwargs["database_url"] = "sqlite+aiosqlite:///./test.db"
        with pytest.raises(
            ValidationError, match="DATABASE_URL must not use SQLite"
        ):
            Settings(**kwargs)


class TestProductionGuard6MCPTransport:
    """Guard 6: Force MCP http transport."""

    def test_mcp_transport_mode_must_be_http(self):
        """MCP_TRANSPORT_MODE must be 'http' in production."""
        kwargs = _production_settings_kwargs()
        kwargs["mcp_transport_mode"] = "stdio"
        with pytest.raises(
            ValidationError, match="MCP_TRANSPORT_MODE must be 'http'"
        ):
            Settings(**kwargs)


class TestProductionGuard7JWTForwarding:
    """Guard 7: Force JWT forwarding (no service-account credentials)."""

    def test_lightspeed_client_id_must_not_be_set(self):
        """LIGHTSPEED_CLIENT_ID must not be set in production."""
        kwargs = _production_settings_kwargs()
        kwargs["lightspeed_client_id"] = "some-id"
        with pytest.raises(
            ValidationError, match="LIGHTSPEED_CLIENT_ID must not be set"
        ):
            Settings(**kwargs)

    def test_lightspeed_client_secret_must_not_be_set(self):
        """LIGHTSPEED_CLIENT_SECRET must not be set in production."""
        kwargs = _production_settings_kwargs()
        kwargs["lightspeed_client_secret"] = "some-secret"
        with pytest.raises(
            ValidationError, match="LIGHTSPEED_CLIENT_SECRET must not be set"
        ):
            Settings(**kwargs)


class TestProductionGuard9SSO:
    """Guard 9: Require SSO credentials."""

    def test_sso_client_id_must_be_set(self):
        """RED_HAT_SSO_CLIENT_ID must be set in production."""
        kwargs = _production_settings_kwargs()
        kwargs["red_hat_sso_client_id"] = ""
        with pytest.raises(
            ValidationError, match="RED_HAT_SSO_CLIENT_ID must be set"
        ):
            Settings(**kwargs)

    def test_sso_client_secret_must_be_set(self):
        """RED_HAT_SSO_CLIENT_SECRET must be set in production."""
        kwargs = _production_settings_kwargs()
        kwargs["red_hat_sso_client_secret"] = ""
        with pytest.raises(
            ValidationError, match="RED_HAT_SSO_CLIENT_SECRET must be set"
        ):
            Settings(**kwargs)


class TestProductionGuard10DCR:
    """Guard 10: Require DCR configuration."""

    def test_dcr_enabled_must_be_true(self):
        """DCR_ENABLED must be true in production."""
        kwargs = _production_settings_kwargs()
        kwargs["dcr_enabled"] = False
        with pytest.raises(
            ValidationError, match="DCR_ENABLED must be true"
        ):
            Settings(**kwargs)

    def test_dcr_initial_access_token_must_be_set(self):
        """DCR_INITIAL_ACCESS_TOKEN must be set in production."""
        kwargs = _production_settings_kwargs()
        kwargs["dcr_initial_access_token"] = ""
        with pytest.raises(
            ValidationError, match="DCR_INITIAL_ACCESS_TOKEN must be set"
        ):
            Settings(**kwargs)

    def test_dcr_encryption_key_must_be_set(self):
        """DCR_ENCRYPTION_KEY must be set in production."""
        kwargs = _production_settings_kwargs()
        kwargs["dcr_encryption_key"] = ""
        with pytest.raises(
            ValidationError, match="DCR_ENCRYPTION_KEY must be set"
        ):
            Settings(**kwargs)


class TestProductionMultipleViolations:
    """Verify that multiple guard violations are reported together."""

    def test_multiple_violations_reported(self):
        """All violations appear in a single error when multiple guards fail."""
        kwargs = _production_settings_kwargs()
        # Violate guard 1, 3, and 5 simultaneously
        kwargs["google_api_key"] = "some-key"
        kwargs["debug"] = True
        kwargs["database_url"] = "sqlite+aiosqlite:///./test.db"

        with pytest.raises(ValidationError) as exc_info:
            Settings(**kwargs)

        error_text = str(exc_info.value)
        assert "GOOGLE_API_KEY must not be set" in error_text
        assert "DEBUG must not be true" in error_text
        assert "DATABASE_URL must not use SQLite" in error_text

    def test_violation_count_in_header(self):
        """The error header reports the correct number of violations."""
        kwargs = _production_settings_kwargs()
        kwargs["google_api_key"] = "some-key"
        kwargs["debug"] = True
        kwargs["database_url"] = "sqlite+aiosqlite:///./test.db"

        with pytest.raises(ValidationError, match="3 violation"):
            Settings(**kwargs)


class TestProductionFalseBypassesGuards:
    """Verify that guards are only enforced when production=true."""

    def test_non_production_allows_insecure_config(self):
        """Settings construction succeeds with insecure values when production=false."""
        settings = Settings(
            production=False,
            google_api_key="key",
            google_genai_use_vertexai=False,
            skip_jwt_validation=True,
            debug=True,
            agent_provider_url="http://localhost:8000",
            mcp_server_url="http://localhost:8080",
            database_url="sqlite+aiosqlite:///./test.db",
            mcp_transport_mode="stdio",
            lightspeed_client_id="some-id",
            lightspeed_client_secret="some-secret",
            red_hat_sso_client_id="",
            red_hat_sso_client_secret="",
            dcr_enabled=False,
            dcr_initial_access_token="",
            dcr_encryption_key="",
        )
        assert settings.production is False
        assert settings.debug is True
        assert settings.skip_jwt_validation is True


class TestProductionGuard8CORSAgent:
    """Guard 8: CORS middleware disabled in production (agent app)."""

    def test_cors_disabled_in_production(self):
        """CORS middleware is not added when production=true."""
        from fastapi.middleware.cors import CORSMiddleware

        prod_settings = Settings(**_production_settings_kwargs())
        with patch(
            "lightspeed_agent.api.app.get_settings", return_value=prod_settings
        ):
            with patch("lightspeed_agent.api.app.get_redis_rate_limiter"):
                from lightspeed_agent.api.app import create_app

                app = create_app()
                cors_middlewares = [
                    m for m in app.user_middleware if m.cls is CORSMiddleware
                ]
                assert len(cors_middlewares) == 0

    def test_cors_enabled_in_non_production(self):
        """CORS middleware is added when production=false."""
        from fastapi.middleware.cors import CORSMiddleware

        kwargs = _production_settings_kwargs()
        kwargs["production"] = False
        non_prod_settings = Settings(**kwargs)
        with patch(
            "lightspeed_agent.api.app.get_settings",
            return_value=non_prod_settings,
        ):
            with patch("lightspeed_agent.api.app.get_redis_rate_limiter"):
                from lightspeed_agent.api.app import create_app

                app = create_app()
                cors_middlewares = [
                    m for m in app.user_middleware if m.cls is CORSMiddleware
                ]
                assert len(cors_middlewares) == 1


class TestProductionGuard8CORSMarketplace:
    """Guard 8: CORS middleware disabled in production (marketplace app)."""

    def test_cors_disabled_in_production(self):
        """CORS middleware is not added to marketplace app in production."""
        from fastapi.middleware.cors import CORSMiddleware

        prod_settings = Settings(**_production_settings_kwargs())
        with patch(
            "lightspeed_agent.marketplace.app.get_settings",
            return_value=prod_settings,
        ):
            from lightspeed_agent.marketplace.app import create_app

            app = create_app()
            cors_middlewares = [
                m for m in app.user_middleware if m.cls is CORSMiddleware
            ]
            assert len(cors_middlewares) == 0

    def test_cors_enabled_in_non_production(self):
        """CORS middleware is added to marketplace app when production=false."""
        from fastapi.middleware.cors import CORSMiddleware

        kwargs = _production_settings_kwargs()
        kwargs["production"] = False
        non_prod_settings = Settings(**kwargs)
        with patch(
            "lightspeed_agent.marketplace.app.get_settings",
            return_value=non_prod_settings,
        ):
            from lightspeed_agent.marketplace.app import create_app

            app = create_app()
            cors_middlewares = [
                m for m in app.user_middleware if m.cls is CORSMiddleware
            ]
            assert len(cors_middlewares) == 1


class TestProductionGuard7MCPHeaders:
    """Guard 7 runtime: MCP header provider forwards JWT in production."""

    def test_mcp_headers_production_forwards_jwt(self):
        """In production, the MCP header provider forwards the user JWT."""
        from lightspeed_agent.auth.middleware import _request_access_token
        from lightspeed_agent.tools.mcp_headers import create_mcp_header_provider

        prod_settings = Settings(**_production_settings_kwargs())
        with patch(
            "lightspeed_agent.tools.mcp_headers.get_settings",
            return_value=prod_settings,
        ):
            provider = create_mcp_header_provider()
            token_exp = datetime.now(UTC) + timedelta(hours=1)
            _request_access_token.set(("user-jwt-token", token_exp))
            try:
                headers = provider(MagicMock())
                assert headers == {"Authorization": "Bearer user-jwt-token"}
            finally:
                _request_access_token.set(None)

    def test_mcp_headers_production_no_jwt_returns_empty(self):
        """In production with no JWT available, returns empty dict."""
        from lightspeed_agent.auth.middleware import _request_access_token
        from lightspeed_agent.tools.mcp_headers import create_mcp_header_provider

        prod_settings = Settings(**_production_settings_kwargs())
        with patch(
            "lightspeed_agent.tools.mcp_headers.get_settings",
            return_value=prod_settings,
        ):
            provider = create_mcp_header_provider()
            _request_access_token.set(None)
            headers = provider(MagicMock())
            assert headers == {}

    def test_mcp_headers_non_production_uses_service_account(self):
        """In non-production, service-account credentials are used if set."""
        from lightspeed_agent.tools.mcp_headers import create_mcp_header_provider

        kwargs = _production_settings_kwargs()
        kwargs["production"] = False
        kwargs["lightspeed_client_id"] = "svc-id"
        kwargs["lightspeed_client_secret"] = "svc-secret"
        non_prod_settings = Settings(**kwargs)
        with patch(
            "lightspeed_agent.tools.mcp_headers.get_settings",
            return_value=non_prod_settings,
        ):
            provider = create_mcp_header_provider()
            headers = provider(MagicMock())
            assert headers == {
                "lightspeed-client-id": "svc-id",
                "lightspeed-client-secret": "svc-secret",
            }
