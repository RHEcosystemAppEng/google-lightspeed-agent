"""Tests for application settings guards."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from lightspeed_agent.config import Settings


class TestSkipJwtProductionGuard:
    """Verify SKIP_JWT_VALIDATION cannot be enabled in Cloud Run."""

    def _env_without_k_service(self) -> dict[str, str]:
        """Return a copy of os.environ without K_SERVICE."""
        return {k: v for k, v in os.environ.items() if k != "K_SERVICE"}

    def test_skip_jwt_allowed_without_k_service(self):
        """SKIP_JWT_VALIDATION=true is fine when K_SERVICE is unset."""
        with patch.dict(os.environ, self._env_without_k_service(), clear=True):
            settings = Settings(skip_jwt_validation=True)
            assert settings.skip_jwt_validation is True

    def test_skip_jwt_blocked_in_cloud_run(self):
        """SKIP_JWT_VALIDATION=true must fail when K_SERVICE is set."""
        with (
            patch.dict(os.environ, {"K_SERVICE": "lightspeed-agent"}, clear=False),
            pytest.raises(ValidationError, match="not allowed in Cloud Run"),
        ):
            Settings(skip_jwt_validation=True)

    def test_no_skip_jwt_allowed_in_cloud_run(self):
        """SKIP_JWT_VALIDATION=false (default) is fine in Cloud Run."""
        with patch.dict(
            os.environ, {"K_SERVICE": "lightspeed-agent"}, clear=False
        ):
            settings = Settings(skip_jwt_validation=False)
            assert settings.skip_jwt_validation is False

    def test_skip_jwt_defaults_to_false(self):
        """Default value of skip_jwt_validation is False."""
        with patch.dict(
            os.environ,
            self._env_without_k_service()
            | {"SKIP_JWT_VALIDATION": "false"},
            clear=True,
        ):
            settings = Settings(skip_jwt_validation=False)
            assert settings.skip_jwt_validation is False


class TestMcpServerUrlHttpsGuard:
    """Verify MCP_SERVER_URL requires HTTPS (except localhost)."""

    def test_https_url_allowed(self):
        """HTTPS URLs are accepted for http/sse transport modes."""
        settings = Settings(
            mcp_transport_mode="http",
            mcp_server_url="https://rh-lightspeed-mcp-abc123.run.app",
        )
        assert settings.mcp_server_url == "https://rh-lightspeed-mcp-abc123.run.app"

    def test_http_localhost_allowed(self):
        """http://localhost is allowed for local development."""
        settings = Settings(
            mcp_transport_mode="http",
            mcp_server_url="http://localhost:8080",
        )
        assert settings.mcp_server_url == "http://localhost:8080"

    def test_http_localhost_no_port_allowed(self):
        """http://localhost without port is allowed."""
        settings = Settings(
            mcp_transport_mode="http",
            mcp_server_url="http://localhost",
        )
        assert settings.mcp_server_url == "http://localhost"

    def test_plain_http_rejected(self):
        """Plain HTTP to a non-localhost host must be rejected."""
        with pytest.raises(ValidationError, match="must use HTTPS"):
            Settings(
                mcp_transport_mode="http",
                mcp_server_url="http://mcp-server:8080",
            )

    def test_plain_http_remote_rejected(self):
        """HTTP to a remote host must be rejected."""
        with pytest.raises(ValidationError, match="must use HTTPS"):
            Settings(
                mcp_transport_mode="http",
                mcp_server_url="http://10.0.0.5:8080",
            )

    def test_sse_mode_also_validates(self):
        """SSE transport mode also enforces HTTPS."""
        with pytest.raises(ValidationError, match="must use HTTPS"):
            Settings(
                mcp_transport_mode="sse",
                mcp_server_url="http://mcp-server:8080",
            )

    def test_stdio_mode_skips_validation(self):
        """stdio mode does not use MCP_SERVER_URL, so no URL validation."""
        settings = Settings(
            mcp_transport_mode="stdio",
            mcp_server_url="http://anything:9999",
        )
        assert settings.mcp_server_url == "http://anything:9999"
