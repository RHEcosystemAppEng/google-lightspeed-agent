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
