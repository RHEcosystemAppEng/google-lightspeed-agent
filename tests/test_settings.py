"""Tests for application settings guards."""

import logging
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from lightspeed_agent.api.app import _check_mcp_url_security
from lightspeed_agent.config import Settings


def _env_without_k_service() -> dict[str, str]:
    """Return a copy of os.environ without K_SERVICE."""
    return {k: v for k, v in os.environ.items() if k != "K_SERVICE"}


def _cloud_run_env(**overrides: str) -> dict[str, str]:
    """Env dict simulating Cloud Run with all production guards neutralized.

    Sets K_SERVICE and disables DEBUG, SKIP_JWT_VALIDATION, and DATABASE_URL
    by default, so tests targeting one guard don't accidentally trigger another.
    """
    base = {
        "K_SERVICE": "lightspeed-agent",
        "SKIP_JWT_VALIDATION": "false",
        "DEBUG": "false",
        "DATABASE_URL": "postgresql+asyncpg://localhost/test",
    }
    base.update(overrides)
    return base


class TestSkipJwtProductionGuard:
    """Verify SKIP_JWT_VALIDATION cannot be enabled in Cloud Run."""

    def test_skip_jwt_allowed_without_k_service(self):
        """SKIP_JWT_VALIDATION=true is fine when K_SERVICE is unset."""
        with patch.dict(os.environ, _env_without_k_service(), clear=True):
            settings = Settings(skip_jwt_validation=True)
            assert settings.skip_jwt_validation is True

    def test_skip_jwt_blocked_in_cloud_run(self):
        """SKIP_JWT_VALIDATION=true must fail when K_SERVICE is set."""
        with (
            patch.dict(os.environ, _cloud_run_env(), clear=False),
            pytest.raises(ValidationError, match="not allowed in Cloud Run"),
        ):
            Settings(skip_jwt_validation=True)

    def test_no_skip_jwt_allowed_in_cloud_run(self):
        """SKIP_JWT_VALIDATION=false (default) is fine in Cloud Run."""
        with patch.dict(os.environ, _cloud_run_env(), clear=False):
            settings = Settings(skip_jwt_validation=False)
            assert settings.skip_jwt_validation is False

    def test_skip_jwt_defaults_to_false(self):
        """Default value of skip_jwt_validation is False."""
        with patch.dict(
            os.environ,
            _env_without_k_service() | {"SKIP_JWT_VALIDATION": "false"},
            clear=True,
        ):
            settings = Settings(skip_jwt_validation=False)
            assert settings.skip_jwt_validation is False


class TestDebugProductionWarning:
    """Verify DEBUG=true in Cloud Run logs a warning (not an error)."""

    def test_debug_allowed_without_k_service(self, caplog):
        """DEBUG=true is fine when K_SERVICE is unset — no warning."""
        with patch.dict(os.environ, _env_without_k_service(), clear=True):
            with caplog.at_level(logging.WARNING, logger="lightspeed_agent.config.settings"):
                settings = Settings(debug=True)
            assert settings.debug is True
            assert "DEBUG=true is active in Cloud Run" not in caplog.text

    def test_debug_warns_in_cloud_run(self, caplog):
        """DEBUG=true must log a warning when K_SERVICE is set."""
        with patch.dict(os.environ, _cloud_run_env(), clear=False):
            with caplog.at_level(logging.WARNING, logger="lightspeed_agent.config.settings"):
                settings = Settings(debug=True)
            assert settings.debug is True
            assert "DEBUG=true is active in Cloud Run" in caplog.text

    def test_no_debug_no_warning_in_cloud_run(self, caplog):
        """DEBUG=false (default) is fine in Cloud Run — no warning."""
        with patch.dict(os.environ, _cloud_run_env(), clear=False):
            with caplog.at_level(logging.WARNING, logger="lightspeed_agent.config.settings"):
                settings = Settings(debug=False)
            assert settings.debug is False
            assert "DEBUG=true is active in Cloud Run" not in caplog.text

    def test_debug_defaults_to_false(self):
        """Default value of debug is False."""
        env = {k: v for k, v in os.environ.items() if k not in ("K_SERVICE", "DEBUG")}
        with patch.dict(os.environ, env, clear=True):
            settings = Settings()
            assert settings.debug is False


class TestSqliteProductionGuard:
    """Verify SQLite database URLs are blocked in Cloud Run."""

    def test_sqlite_blocked_in_cloud_run(self):
        """SQLite database_url must fail when K_SERVICE is set."""
        with (
            patch.dict(
                os.environ,
                _cloud_run_env(DATABASE_URL="sqlite+aiosqlite:///./test.db"),
                clear=False,
            ),
            pytest.raises(ValidationError, match="SQLite DATABASE_URL is not allowed"),
        ):
            Settings(skip_jwt_validation=False)

    def test_sqlite_allowed_without_k_service(self):
        """SQLite database_url is fine when K_SERVICE is unset (local dev)."""
        with patch.dict(os.environ, _env_without_k_service(), clear=True):
            settings = Settings()
            assert settings.database_url.startswith("sqlite")

    def test_postgresql_allowed_in_cloud_run(self):
        """PostgreSQL database_url is fine when K_SERVICE is set."""
        with patch.dict(os.environ, _cloud_run_env(), clear=False):
            settings = Settings(skip_jwt_validation=False)
            assert settings.database_url == "postgresql+asyncpg://localhost/test"

    def test_sqlite_session_database_url_blocked_in_cloud_run(self):
        """SQLite session_database_url must fail when K_SERVICE is set."""
        with (
            patch.dict(os.environ, _cloud_run_env(), clear=False),
            pytest.raises(ValidationError, match="SQLite SESSION_DATABASE_URL is not allowed"),
        ):
            Settings(
                skip_jwt_validation=False,
                session_database_url="sqlite+aiosqlite:///./sessions.db",
            )

    def test_sqlite_case_insensitive_blocked(self):
        """SQLite check is case-insensitive."""
        with (
            patch.dict(
                os.environ,
                _cloud_run_env(DATABASE_URL="SQLite+aiosqlite:///./test.db"),
                clear=False,
            ),
            pytest.raises(ValidationError, match="SQLite DATABASE_URL is not allowed"),
        ):
            Settings(skip_jwt_validation=False)


class TestSkillsDirSetting:
    """Tests for the skills_dir configuration setting."""

    def test_skills_dir_default_none(self):
        """skills_dir defaults to None."""
        settings = Settings()
        assert settings.skills_dir is None

    def test_skills_dir_from_env(self, monkeypatch):
        """skills_dir can be set via SKILLS_DIR env var."""
        monkeypatch.setenv("SKILLS_DIR", "/opt/custom-skills")
        settings = Settings(skills_dir="/opt/custom-skills")
        assert settings.skills_dir == "/opt/custom-skills"


class TestSkipOrderValidationGuard:
    """Verify SKIP_ORDER_VALIDATION cannot be enabled in Cloud Run."""

    def _env_without_k_service(self) -> dict[str, str]:
        """Return a copy of os.environ without K_SERVICE."""
        return {k: v for k, v in os.environ.items() if k != "K_SERVICE"}

    def test_skip_order_allowed_without_k_service(self):
        """SKIP_ORDER_VALIDATION=true is fine when K_SERVICE is unset."""
        with patch.dict(os.environ, self._env_without_k_service(), clear=True):
            settings = Settings(skip_order_validation=True)
            assert settings.skip_order_validation is True

    def test_skip_order_blocked_in_cloud_run(self):
        """SKIP_ORDER_VALIDATION=true must fail when K_SERVICE is set."""
        with (
            patch.dict(os.environ, {"K_SERVICE": "lightspeed-agent"}, clear=False),
            pytest.raises(ValidationError, match="not allowed in Cloud Run"),
        ):
            Settings(skip_order_validation=True)

    def test_skip_order_defaults_to_false(self):
        """Default value of skip_order_validation is False."""
        with patch.dict(os.environ, self._env_without_k_service(), clear=True):
            settings = Settings()
            assert settings.skip_order_validation is False


class TestSkipDcrJwtValidationDefault:
    """Verify skip_dcr_jwt_validation default value."""

    def test_skip_dcr_jwt_validation_defaults_to_false(self):
        """Default value of skip_dcr_jwt_validation is False."""
        env = {k: v for k, v in os.environ.items() if k != "K_SERVICE"}
        with patch.dict(os.environ, env, clear=True):
            settings = Settings()
            assert settings.skip_dcr_jwt_validation is False


class TestSkipDcrJwtValidationGuard:
    """Verify SKIP_DCR_JWT_VALIDATION cannot be enabled in Cloud Run."""

    def _env_without_k_service(self) -> dict[str, str]:
        """Return a copy of os.environ without K_SERVICE."""
        return {k: v for k, v in os.environ.items() if k != "K_SERVICE"}

    def test_skip_dcr_jwt_allowed_without_k_service(self):
        """SKIP_DCR_JWT_VALIDATION=true is fine when K_SERVICE is unset."""
        with patch.dict(os.environ, self._env_without_k_service(), clear=True):
            settings = Settings(skip_dcr_jwt_validation=True)
            assert settings.skip_dcr_jwt_validation is True

    def test_skip_dcr_jwt_blocked_in_cloud_run(self):
        """SKIP_DCR_JWT_VALIDATION=true must fail when K_SERVICE is set."""
        with (
            patch.dict(os.environ, {"K_SERVICE": "lightspeed-agent"}, clear=False),
            pytest.raises(ValidationError, match="not allowed in Cloud Run"),
        ):
            Settings(skip_dcr_jwt_validation=True)


class TestSkipPubsubOidcVerificationGuard:
    """Verify SKIP_PUBSUB_OIDC_VERIFICATION cannot be enabled in Cloud Run."""

    def _env_without_k_service(self) -> dict[str, str]:
        return {k: v for k, v in os.environ.items() if k != "K_SERVICE"}

    def test_skip_pubsub_oidc_defaults_to_false(self):
        """Default value of skip_pubsub_oidc_verification is False."""
        with patch.dict(os.environ, self._env_without_k_service(), clear=True):
            settings = Settings()
            assert settings.skip_pubsub_oidc_verification is False

    def test_skip_pubsub_oidc_allowed_without_k_service(self):
        """SKIP_PUBSUB_OIDC_VERIFICATION=true is fine when K_SERVICE is unset."""
        with patch.dict(os.environ, self._env_without_k_service(), clear=True):
            settings = Settings(skip_pubsub_oidc_verification=True)
            assert settings.skip_pubsub_oidc_verification is True

    def test_skip_pubsub_oidc_blocked_in_cloud_run(self):
        """SKIP_PUBSUB_OIDC_VERIFICATION=true must fail when K_SERVICE is set."""
        with (
            patch.dict(os.environ, {"K_SERVICE": "lightspeed-agent"}, clear=False),
            pytest.raises(ValidationError, match="not allowed in Cloud Run"),
        ):
            Settings(skip_pubsub_oidc_verification=True)


class TestMcpUrlSecurityCheck:
    """Verify _check_mcp_url_security catches insecure MCP URLs."""

    @staticmethod
    def _settings(
        transport_mode: str = "http",
        server_url: str = "http://localhost:8080",
    ) -> SimpleNamespace:
        return SimpleNamespace(
            mcp_transport_mode=transport_mode,
            mcp_server_url=server_url,
        )

    def _env_without_k_service(self) -> dict[str, str]:
        return {k: v for k, v in os.environ.items() if k != "K_SERVICE"}

    def test_stdio_mode_skips_check(self):
        """stdio transport doesn't use mcp_server_url — no warning or error."""
        with patch.dict(os.environ, {"K_SERVICE": "agent"}, clear=False):
            _check_mcp_url_security(
                self._settings(transport_mode="stdio", server_url="http://remote.example.com")
            )

    def test_https_url_no_warning(self, caplog):
        """HTTPS URL should never trigger a warning."""
        with (
            patch.dict(os.environ, self._env_without_k_service(), clear=True),
            caplog.at_level(logging.WARNING),
        ):
            _check_mcp_url_security(self._settings(server_url="https://mcp.example.com"))
        assert caplog.text == ""

    def test_https_case_insensitive(self, caplog):
        """Uppercase HTTPS scheme should be accepted."""
        with (
            patch.dict(os.environ, self._env_without_k_service(), clear=True),
            caplog.at_level(logging.WARNING),
        ):
            _check_mcp_url_security(self._settings(server_url="HTTPS://mcp.example.com"))
        assert caplog.text == ""

    def test_localhost_http_no_warning(self, caplog):
        """HTTP to localhost is safe — no warning."""
        with (
            patch.dict(os.environ, self._env_without_k_service(), clear=True),
            caplog.at_level(logging.WARNING),
        ):
            _check_mcp_url_security(self._settings(server_url="http://localhost:8080"))
        assert caplog.text == ""

    def test_ipv4_loopback_no_warning(self, caplog):
        """HTTP to 127.0.0.1 is safe — no warning."""
        with (
            patch.dict(os.environ, self._env_without_k_service(), clear=True),
            caplog.at_level(logging.WARNING),
        ):
            _check_mcp_url_security(self._settings(server_url="http://127.0.0.1:8080"))
        assert caplog.text == ""

    def test_ipv6_loopback_no_warning(self, caplog):
        """HTTP to [::1] is safe — no warning."""
        with (
            patch.dict(os.environ, self._env_without_k_service(), clear=True),
            caplog.at_level(logging.WARNING),
        ):
            _check_mcp_url_security(self._settings(server_url="http://[::1]:8080"))
        assert caplog.text == ""

    def test_non_localhost_http_warns_in_dev(self, caplog):
        """Non-localhost HTTP in dev (no K_SERVICE) logs a warning."""
        with (
            patch.dict(os.environ, self._env_without_k_service(), clear=True),
            caplog.at_level(logging.WARNING),
        ):
            _check_mcp_url_security(self._settings(server_url="http://mcp.example.com"))
        assert "unencrypted HTTP" in caplog.text
        assert "mcp.example.com" in caplog.text

    def test_non_localhost_http_raises_in_production(self):
        """Non-localhost HTTP in Cloud Run (K_SERVICE set) raises ValueError."""
        with (
            patch.dict(os.environ, {"K_SERVICE": "lightspeed-agent"}, clear=False),
            pytest.raises(ValueError, match="unencrypted HTTP"),
        ):
            _check_mcp_url_security(self._settings(server_url="http://mcp.example.com"))

    def test_empty_url_no_warning(self, caplog):
        """Empty URL should not trigger any check."""
        with (
            patch.dict(os.environ, self._env_without_k_service(), clear=True),
            caplog.at_level(logging.WARNING),
        ):
            _check_mcp_url_security(self._settings(server_url=""))
        assert caplog.text == ""
