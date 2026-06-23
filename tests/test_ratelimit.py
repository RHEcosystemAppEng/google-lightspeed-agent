"""Tests for Redis rate limiter TLS validation, principal resolution, and middleware order."""

import os
from unittest.mock import MagicMock, patch

import pytest

from lightspeed_agent.config import Settings
from lightspeed_agent.ratelimit.middleware import RateLimitMiddleware


class TestRedisRateLimiterTlsValidation:
    """Verify TLS checks in RedisRateLimiter.__init__."""

    def _make_settings(self, **overrides: str) -> Settings:
        """Create a Settings instance with the given rate-limit overrides."""
        return Settings(**overrides)

    def test_plain_redis_allowed_without_k_service(self):
        """Plain redis:// is fine when K_SERVICE is unset (local dev)."""
        from lightspeed_agent.ratelimit.middleware import RedisRateLimiter

        env = {k: v for k, v in os.environ.items() if k != "K_SERVICE"}
        settings = self._make_settings(rate_limit_redis_url="redis://localhost:6379/0")
        with (
            patch.dict(os.environ, env, clear=True),
            patch("lightspeed_agent.ratelimit.middleware.get_settings", return_value=settings),
        ):
            limiter = RedisRateLimiter()
            assert limiter is not None

    def test_plain_redis_blocked_in_cloud_run(self):
        """Plain redis:// must fail when K_SERVICE is set."""
        from lightspeed_agent.ratelimit.middleware import RedisRateLimiter

        settings = self._make_settings(rate_limit_redis_url="redis://localhost:6379/0")
        with (
            patch.dict(os.environ, {"K_SERVICE": "lightspeed-agent"}, clear=False),
            patch("lightspeed_agent.ratelimit.middleware.get_settings", return_value=settings),
            pytest.raises(ValueError, match="Redis TLS is required in Cloud Run"),
        ):
            RedisRateLimiter()

    def test_rediss_without_ca_cert_blocked(self):
        """rediss:// without CA cert must fail."""
        from lightspeed_agent.ratelimit.middleware import RedisRateLimiter

        settings = self._make_settings(
            rate_limit_redis_url="rediss://localhost:6380/0",
            rate_limit_redis_ca_cert="",
        )
        with (
            patch("lightspeed_agent.ratelimit.middleware.get_settings", return_value=settings),
            pytest.raises(ValueError, match="RATE_LIMIT_REDIS_CA_CERT must be set"),
        ):
            RedisRateLimiter()

    def test_rediss_with_ca_cert_allowed(self):
        """rediss:// with CA cert is accepted."""
        from lightspeed_agent.ratelimit.middleware import RedisRateLimiter

        settings = self._make_settings(
            rate_limit_redis_url="rediss://localhost:6380/0",
            rate_limit_redis_ca_cert="/certs/ca.pem",
        )
        with patch(
            "lightspeed_agent.ratelimit.middleware.get_settings", return_value=settings
        ):
            limiter = RedisRateLimiter()
            assert limiter is not None


class TestResolvePrincipals:
    """Tests for RateLimitMiddleware._resolve_principals."""

    @staticmethod
    def _make_request(
        *,
        order_id=None,
        user=None,
        client_host="192.168.1.42",
        has_client=True,
    ) -> MagicMock:
        request = MagicMock()
        state = MagicMock(spec=[])
        if order_id is not None:
            state.order_id = order_id
        if user is not None:
            state.user = user
        request.state = state
        if has_client:
            request.client = MagicMock()
            request.client.host = client_host
        else:
            request.client = None
        return request

    def test_falls_back_to_ip_when_no_auth_state(self):
        request = self._make_request(client_host="10.0.0.1")
        assert RateLimitMiddleware._resolve_principals(request) == ["ip:10.0.0.1"]

    def test_uses_order_id(self):
        request = self._make_request(order_id="order-abc")
        assert RateLimitMiddleware._resolve_principals(request) == ["order:order-abc"]

    def test_uses_user_id(self):
        user = MagicMock()
        user.user_id = "user-def"
        request = self._make_request(user=user)
        assert RateLimitMiddleware._resolve_principals(request) == ["user:user-def"]

    def test_uses_client_id_when_no_user_id(self):
        user = MagicMock()
        user.user_id = None
        user.client_id = "client-ghi"
        request = self._make_request(user=user)
        assert RateLimitMiddleware._resolve_principals(request) == ["client:client-ghi"]

    def test_order_and_user_both_present(self):
        user = MagicMock()
        user.user_id = "user-def"
        request = self._make_request(order_id="order-abc", user=user)
        result = RateLimitMiddleware._resolve_principals(request)
        assert result == ["order:order-abc", "user:user-def"]

    def test_no_client_returns_unknown(self):
        request = self._make_request(has_client=False)
        assert RateLimitMiddleware._resolve_principals(request) == ["ip:unknown"]


class TestAgentMiddlewareOrder:
    """Verify the agent service stacks Auth before RateLimit."""

    def test_auth_runs_before_ratelimit(self):
        from lightspeed_agent.auth.middleware import AuthenticationMiddleware

        with patch("lightspeed_agent.ratelimit.middleware.get_settings") as mock_settings:
            settings = Settings()
            mock_settings.return_value = settings
            with patch(
                "lightspeed_agent.ratelimit.middleware.Redis.from_url"
            ):
                from lightspeed_agent.api.app import create_app

                app = create_app()

        middleware_classes = [m.cls for m in app.user_middleware]
        auth_idx = middleware_classes.index(AuthenticationMiddleware)
        rate_idx = middleware_classes.index(RateLimitMiddleware)
        assert auth_idx < rate_idx, (
            "AuthenticationMiddleware must be outermost (lower index) "
            "so it runs before RateLimitMiddleware on incoming requests"
        )
