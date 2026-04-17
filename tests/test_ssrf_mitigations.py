"""Tests for SSRF mitigation validators (CWE-918).

Covers URL scheme restrictions, metadata-IP blocking, and redirect URI
validation added to prevent Server-Side Request Forgery.
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from lightspeed_agent.config import Settings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_kwargs(**overrides: object) -> dict:
    """Return Settings kwargs with sensible test defaults, merged with overrides."""
    defaults: dict[str, object] = {
        "skip_jwt_validation": True,
        "dcr_enabled": False,
    }
    defaults.update(overrides)
    return defaults


def _env_without_k_service() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k != "K_SERVICE"}


# ---------------------------------------------------------------------------
# 1. MCP_SERVER_URL validation
# ---------------------------------------------------------------------------


class TestMcpServerUrlValidation:
    """Validate that MCP_SERVER_URL rejects dangerous schemes and IPs."""

    def test_http_scheme_allowed(self):
        s = Settings(**_base_kwargs(
            mcp_transport_mode="http",
            mcp_server_url="http://mcp-sidecar:8080",
        ))
        assert s.mcp_server_url == "http://mcp-sidecar:8080"

    def test_https_scheme_allowed(self):
        s = Settings(**_base_kwargs(
            mcp_transport_mode="http",
            mcp_server_url="https://mcp.internal:443",
        ))
        assert s.mcp_server_url == "https://mcp.internal:443"

    def test_file_scheme_rejected(self):
        with pytest.raises(ValidationError, match="http:// or https://"):
            Settings(**_base_kwargs(
                mcp_transport_mode="http",
                mcp_server_url="file:///etc/passwd",
            ))

    def test_ftp_scheme_rejected(self):
        with pytest.raises(ValidationError, match="http:// or https://"):
            Settings(**_base_kwargs(
                mcp_transport_mode="sse",
                mcp_server_url="ftp://internal-ftp:21",
            ))

    def test_gopher_scheme_rejected(self):
        with pytest.raises(ValidationError, match="http:// or https://"):
            Settings(**_base_kwargs(
                mcp_transport_mode="http",
                mcp_server_url="gopher://internal:70",
            ))

    def test_cloud_metadata_ip_rejected(self):
        with pytest.raises(ValidationError, match="cloud metadata"):
            Settings(**_base_kwargs(
                mcp_transport_mode="http",
                mcp_server_url="http://169.254.169.254/latest/meta-data",
            ))

    def test_stdio_mode_skips_url_validation(self):
        """stdio mode does not use server_url, so no validation needed."""
        s = Settings(**_base_kwargs(
            mcp_transport_mode="stdio",
            mcp_server_url="gopher://anything",
        ))
        assert s.mcp_server_url == "gopher://anything"

    def test_localhost_allowed(self):
        s = Settings(**_base_kwargs(
            mcp_transport_mode="http",
            mcp_server_url="http://localhost:8080",
        ))
        assert s.mcp_server_url == "http://localhost:8080"


# ---------------------------------------------------------------------------
# 2. RED_HAT_SSO_ISSUER scheme validation
# ---------------------------------------------------------------------------


class TestSsoIssuerSchemeValidation:
    """Ensure RED_HAT_SSO_ISSUER requires https:// when JWT validation is on."""

    def test_https_accepted(self):
        s = Settings(**_base_kwargs(
            skip_jwt_validation=False,
            red_hat_sso_issuer="https://sso.redhat.com/auth/realms/redhat-external",
        ))
        assert s.red_hat_sso_issuer.startswith("https://")

    def test_http_rejected_when_jwt_active(self):
        with pytest.raises(ValidationError, match="RED_HAT_SSO_ISSUER must use https://"):
            Settings(**_base_kwargs(
                skip_jwt_validation=False,
                red_hat_sso_issuer="http://sso.redhat.com/auth/realms/redhat-external",
            ))

    def test_http_allowed_when_jwt_skipped(self):
        """Dev mode (skip_jwt_validation=True) allows non-https for convenience."""
        s = Settings(**_base_kwargs(
            skip_jwt_validation=True,
            red_hat_sso_issuer="http://localhost:8080/auth/realms/test",
        ))
        assert s.red_hat_sso_issuer.startswith("http://")


# ---------------------------------------------------------------------------
# 3. GMA_API_BASE_URL scheme validation
# ---------------------------------------------------------------------------


class TestGmaApiUrlValidation:
    """Ensure GMA_API_BASE_URL requires https:// when DCR is enabled."""

    def test_https_accepted(self):
        s = Settings(**_base_kwargs(
            dcr_enabled=True,
            gma_api_base_url="https://sso.redhat.com/auth/realms/redhat-external/apis/beta/acs/v1/",
        ))
        assert s.gma_api_base_url.startswith("https://")

    def test_http_rejected_when_dcr_enabled(self):
        with pytest.raises(ValidationError, match="GMA_API_BASE_URL must use https://"):
            Settings(**_base_kwargs(
                dcr_enabled=True,
                gma_api_base_url="http://internal-gma:8080/apis/beta/acs/v1/",
            ))

    def test_http_allowed_when_dcr_disabled(self):
        s = Settings(**_base_kwargs(
            dcr_enabled=False,
            gma_api_base_url="http://localhost/apis/beta/acs/v1/",
        ))
        assert s.gma_api_base_url.startswith("http://")


# ---------------------------------------------------------------------------
# 4. OTEL exporter endpoint validation
# ---------------------------------------------------------------------------


class TestOtelEndpointValidation:
    """Ensure OTEL endpoints use http/https when tracing is enabled."""

    def test_http_endpoint_accepted(self):
        s = Settings(**_base_kwargs(
            otel_enabled=True,
            otel_exporter_type="otlp",
            otel_exporter_otlp_endpoint="http://localhost:4317",
        ))
        assert s.otel_exporter_otlp_endpoint == "http://localhost:4317"

    def test_https_endpoint_accepted(self):
        s = Settings(**_base_kwargs(
            otel_enabled=True,
            otel_exporter_type="otlp-http",
            otel_exporter_otlp_http_endpoint="https://otel-collector.internal:4318",
        ))
        assert s.otel_exporter_otlp_http_endpoint == "https://otel-collector.internal:4318"

    def test_file_scheme_rejected(self):
        with pytest.raises(ValidationError, match="http:// or https://"):
            Settings(**_base_kwargs(
                otel_enabled=True,
                otel_exporter_type="otlp",
                otel_exporter_otlp_endpoint="file:///tmp/traces",
            ))

    def test_validation_skipped_when_otel_disabled(self):
        """No validation when OTEL is disabled."""
        s = Settings(**_base_kwargs(
            otel_enabled=False,
            otel_exporter_type="otlp",
            otel_exporter_otlp_endpoint="gopher://bad",
        ))
        assert s.otel_exporter_otlp_endpoint == "gopher://bad"

    def test_validation_skipped_for_console_exporter(self):
        """Console exporter does not use endpoints."""
        s = Settings(**_base_kwargs(
            otel_enabled=True,
            otel_exporter_type="console",
            otel_exporter_otlp_endpoint="gopher://bad",
        ))
        assert s.otel_exporter_otlp_endpoint == "gopher://bad"


# ---------------------------------------------------------------------------
# 5. Redirect URI validation (GMA client)
# ---------------------------------------------------------------------------


class TestRedirectUriValidation:
    """Verify redirect URI parsing blocks SSRF bypass attempts."""

    @pytest.fixture
    def gma_client(self):
        from lightspeed_agent.dcr.gma_client import GMAClient

        return GMAClient(
            api_base_url="https://sso.example.com/apis/beta/acs/v1/",
            client_id="test-id",
            client_secret="test-secret",
            token_endpoint="https://sso.example.com/token",
        )

    @pytest.mark.asyncio
    async def test_https_uri_accepted(self, gma_client):
        """Normal https redirect should pass validation (then fail at HTTP level)."""
        from lightspeed_agent.dcr.gma_client import GMAClientError

        # Will fail at the HTTP call, but should not fail at validation
        with pytest.raises(GMAClientError) as exc_info:
            await gma_client.create_tenant(
                order_id="test",
                redirect_uris=["https://app.example.com/callback"],
            )
        # If we get here with an HTTP error, validation passed
        assert "Invalid redirect URI" not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_http_localhost_accepted(self, gma_client):
        from lightspeed_agent.dcr.gma_client import GMAClientError

        with pytest.raises(GMAClientError) as exc_info:
            await gma_client.create_tenant(
                order_id="test",
                redirect_uris=["http://localhost:8080/callback"],
            )
        assert "Invalid redirect URI" not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_http_127_0_0_1_accepted(self, gma_client):
        from lightspeed_agent.dcr.gma_client import GMAClientError

        with pytest.raises(GMAClientError) as exc_info:
            await gma_client.create_tenant(
                order_id="test",
                redirect_uris=["http://127.0.0.1:3000/callback"],
            )
        assert "Invalid redirect URI" not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_http_non_localhost_rejected(self, gma_client):
        from lightspeed_agent.dcr.gma_client import GMAClientError

        with pytest.raises(GMAClientError, match="Invalid redirect URI"):
            await gma_client.create_tenant(
                order_id="test",
                redirect_uris=["http://evil.com/callback"],
            )

    @pytest.mark.asyncio
    async def test_localhost_subdomain_bypass_blocked(self, gma_client):
        """http://localhost.attacker.com must be rejected (old startswith check allowed it)."""
        from lightspeed_agent.dcr.gma_client import GMAClientError

        with pytest.raises(GMAClientError, match="Invalid redirect URI"):
            await gma_client.create_tenant(
                order_id="test",
                redirect_uris=["http://localhost.attacker.com/callback"],
            )

    @pytest.mark.asyncio
    async def test_file_scheme_rejected(self, gma_client):
        from lightspeed_agent.dcr.gma_client import GMAClientError

        with pytest.raises(GMAClientError, match="Invalid redirect URI"):
            await gma_client.create_tenant(
                order_id="test",
                redirect_uris=["file:///etc/passwd"],
            )

    @pytest.mark.asyncio
    async def test_ftp_scheme_rejected(self, gma_client):
        from lightspeed_agent.dcr.gma_client import GMAClientError

        with pytest.raises(GMAClientError, match="Invalid redirect URI"):
            await gma_client.create_tenant(
                order_id="test",
                redirect_uris=["ftp://internal:21/data"],
            )


# ---------------------------------------------------------------------------
# 6. Redis URL scheme validation
# ---------------------------------------------------------------------------


class TestRedisUrlSchemeValidation:
    """Verify RATE_LIMIT_REDIS_URL requires redis:// or rediss:// scheme."""

    def _make_settings(self, **overrides: object) -> Settings:
        return Settings(**_base_kwargs(**overrides))

    def test_redis_scheme_allowed(self):
        from lightspeed_agent.ratelimit.middleware import RedisRateLimiter

        settings = self._make_settings(rate_limit_redis_url="redis://localhost:6379/0")
        env = _env_without_k_service()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("lightspeed_agent.ratelimit.middleware.get_settings", return_value=settings),
        ):
            limiter = RedisRateLimiter()
            assert limiter is not None

    def test_rediss_scheme_allowed(self):
        from lightspeed_agent.ratelimit.middleware import RedisRateLimiter

        settings = self._make_settings(
            rate_limit_redis_url="rediss://redis.internal:6380/0",
            rate_limit_redis_ca_cert="/certs/ca.pem",
        )
        with patch(
            "lightspeed_agent.ratelimit.middleware.get_settings", return_value=settings
        ):
            limiter = RedisRateLimiter()
            assert limiter is not None

    def test_http_scheme_rejected(self):
        from lightspeed_agent.ratelimit.middleware import RedisRateLimiter

        settings = self._make_settings(
            rate_limit_redis_url="http://169.254.169.254/latest/meta-data",
        )
        with (
            patch("lightspeed_agent.ratelimit.middleware.get_settings", return_value=settings),
            pytest.raises(ValueError, match="redis:// or rediss://"),
        ):
            RedisRateLimiter()

    def test_file_scheme_rejected(self):
        from lightspeed_agent.ratelimit.middleware import RedisRateLimiter

        settings = self._make_settings(rate_limit_redis_url="file:///etc/passwd")
        with (
            patch("lightspeed_agent.ratelimit.middleware.get_settings", return_value=settings),
            pytest.raises(ValueError, match="redis:// or rediss://"),
        ):
            RedisRateLimiter()
