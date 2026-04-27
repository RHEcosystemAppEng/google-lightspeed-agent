"""Tests for Pub/Sub JWT validator for rotation endpoint."""

import time
from unittest.mock import patch

import pytest

from lightspeed_agent.rotation.pubsub_jwt import (
    PubSubCertificateCache,
    PubSubJWTValidator,
    get_pubsub_jwt_validator,
)


class TestPubSubCertificateCache:
    """Tests for PubSubCertificateCache (Google OAuth certificate caching)."""

    @pytest.mark.asyncio
    async def test_certificate_cache_fetches_and_stores(self):
        """Test that the cache fetches and stores certificates."""
        # Mock the certificate parsing since we're testing the caching logic
        fake_public_key_pem = (
            "-----BEGIN PUBLIC KEY-----\nMOCK_PUBLIC_KEY\n-----END PUBLIC KEY-----"
        )

        cache = PubSubCertificateCache()

        # Mock the _fetch_certificates method to directly populate the cache
        async def mock_fetch():
            cache._certificates = {
                "key1": fake_public_key_pem,
                "key2": fake_public_key_pem,
            }
            cache._last_fetch = time.monotonic()

        with patch.object(cache, "_fetch_certificates", side_effect=mock_fetch):
            # First call should fetch
            public_key1 = await cache.get_public_key("key1")
            assert public_key1 == fake_public_key_pem
            assert cache._fetch_certificates.call_count == 1

            # Second call should use cache
            public_key2 = await cache.get_public_key("key2")
            assert public_key2 == fake_public_key_pem
            assert cache._fetch_certificates.call_count == 1  # No additional fetch


class TestPubSubJWTValidator:
    """Tests for PubSubJWTValidator (Pub/Sub OIDC token validation)."""

    @pytest.mark.asyncio
    async def test_validator_accepts_valid_token(self):
        """Test that a valid token with correct issuer and audience is accepted."""
        from lightspeed_agent.config import Settings

        # Create settings with skip_jwt_validation=False to test actual validation
        prod_settings = Settings(
            skip_jwt_validation=False,
            agent_provider_url="https://localhost:8000",
            debug=False,
        )

        # Mock get_settings to return prod_settings
        with patch("lightspeed_agent.rotation.pubsub_jwt.get_settings", return_value=prod_settings):
            # Create a mock token with valid claims
            mock_claims = {
                "iss": "https://accounts.google.com",
                "aud": "https://localhost:8000",
                "sub": "service-account@example.iam.gserviceaccount.com",
                "email": "service-account@example.iam.gserviceaccount.com",
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,
            }

            # Create a mock token string (we'll mock jwt.decode to return our claims)
            mock_token = "mock.jwt.token"
            mock_header = {"kid": "test-key-id", "alg": "RS256"}
            fake_public_key = "-----BEGIN PUBLIC KEY-----\nMOCK_KEY\n-----END PUBLIC KEY-----"

            validator = PubSubJWTValidator(expected_audience="https://localhost:8000")

            with (
                patch("jwt.get_unverified_header", return_value=mock_header),
                patch("jwt.decode", return_value=mock_claims),
                patch.object(
                    validator._cert_cache, "get_public_key", return_value=fake_public_key
                ),
            ):
                claims = await validator.validate_push_token(mock_token)

                assert claims is not None
                assert claims["iss"] == "https://accounts.google.com"
                assert claims["aud"] == "https://localhost:8000"
                assert claims["sub"] == "service-account@example.iam.gserviceaccount.com"

    @pytest.mark.asyncio
    async def test_validator_rejects_invalid_issuer(self):
        """Test that a token with wrong issuer returns None."""
        from jwt.exceptions import InvalidTokenError

        from lightspeed_agent.config import Settings

        # Create settings with skip_jwt_validation=False to test actual validation
        prod_settings = Settings(
            skip_jwt_validation=False,
            agent_provider_url="https://localhost:8000",
            debug=False,
        )

        # Mock get_settings to return prod_settings
        with patch("lightspeed_agent.rotation.pubsub_jwt.get_settings", return_value=prod_settings):
            mock_token = "mock.jwt.token"
            mock_header = {"kid": "test-key-id", "alg": "RS256"}
            fake_public_key = "-----BEGIN PUBLIC KEY-----\nMOCK_KEY\n-----END PUBLIC KEY-----"

            validator = PubSubJWTValidator(expected_audience="https://localhost:8000")

            with (
                patch("jwt.get_unverified_header", return_value=mock_header),
                # PyJWT will raise InvalidTokenError when issuer validation fails
                patch("jwt.decode", side_effect=InvalidTokenError("Invalid issuer")),
                patch.object(
                    validator._cert_cache, "get_public_key", return_value=fake_public_key
                ),
            ):
                claims = await validator.validate_push_token(mock_token)

                # Should return None due to invalid issuer
                assert claims is None

    @pytest.mark.asyncio
    async def test_validator_skips_verification_in_dev_mode(self):
        """Test that dev mode (SKIP_JWT_VALIDATION=true) bypasses verification."""
        from lightspeed_agent.config import Settings

        # Create settings with skip_jwt_validation=True
        dev_settings = Settings(
            skip_jwt_validation=True,
            agent_provider_url="https://localhost:8000",
            debug=True,
        )

        # Mock get_settings to return dev_settings
        with patch("lightspeed_agent.rotation.pubsub_jwt.get_settings", return_value=dev_settings):
            validator = PubSubJWTValidator(expected_audience="https://localhost:8000")

            # Create a token with any issuer (should be accepted in dev mode)
            mock_claims = {
                "iss": "https://any-issuer.com",
                "aud": "https://any-audience.com",
                "sub": "test-user",
            }

            mock_token = "mock.jwt.token"

            with patch("jwt.decode", return_value=mock_claims):
                claims = await validator.validate_push_token(mock_token)

                # In dev mode, should accept any token
                assert claims is not None
                assert claims["iss"] == "https://any-issuer.com"

    @pytest.mark.asyncio
    async def test_validator_rejects_missing_kid(self):
        """Test that a token with missing kid in header returns None."""
        from lightspeed_agent.config import Settings

        prod_settings = Settings(
            skip_jwt_validation=False,
            agent_provider_url="https://localhost:8000",
            debug=False,
        )

        with patch("lightspeed_agent.rotation.pubsub_jwt.get_settings", return_value=prod_settings):
            validator = PubSubJWTValidator(expected_audience="https://localhost:8000")
            mock_token = "mock.jwt.token"
            mock_header = {"alg": "RS256"}  # No kid

            with patch("jwt.get_unverified_header", return_value=mock_header):
                claims = await validator.validate_push_token(mock_token)
                assert claims is None

    @pytest.mark.asyncio
    async def test_validator_rejects_wrong_algorithm(self):
        """Test that a token with non-RS256 algorithm returns None."""
        from lightspeed_agent.config import Settings

        prod_settings = Settings(
            skip_jwt_validation=False,
            agent_provider_url="https://localhost:8000",
            debug=False,
        )

        with patch("lightspeed_agent.rotation.pubsub_jwt.get_settings", return_value=prod_settings):
            validator = PubSubJWTValidator(expected_audience="https://localhost:8000")
            mock_token = "mock.jwt.token"
            mock_header = {"kid": "test-key", "alg": "HS256"}  # Wrong algorithm

            with patch("jwt.get_unverified_header", return_value=mock_header):
                claims = await validator.validate_push_token(mock_token)
                assert claims is None

    @pytest.mark.asyncio
    async def test_validator_rejects_expired_token(self):
        """Test that an expired token returns None."""
        from jwt.exceptions import ExpiredSignatureError

        from lightspeed_agent.config import Settings

        prod_settings = Settings(
            skip_jwt_validation=False,
            agent_provider_url="https://localhost:8000",
            debug=False,
        )

        with patch("lightspeed_agent.rotation.pubsub_jwt.get_settings", return_value=prod_settings):
            validator = PubSubJWTValidator(expected_audience="https://localhost:8000")
            mock_token = "mock.jwt.token"
            mock_header = {"kid": "test-key", "alg": "RS256"}
            fake_public_key = "-----BEGIN PUBLIC KEY-----\nMOCK_KEY\n-----END PUBLIC KEY-----"

            with (
                patch("jwt.get_unverified_header", return_value=mock_header),
                patch("jwt.decode", side_effect=ExpiredSignatureError),
                patch.object(
                    validator._cert_cache, "get_public_key", return_value=fake_public_key
                ),
            ):
                claims = await validator.validate_push_token(mock_token)
                assert claims is None

    @pytest.mark.asyncio
    async def test_validator_refreshes_cache_on_missing_key(self):
        """Test that validator refreshes cert cache when key is not found."""
        from lightspeed_agent.config import Settings

        prod_settings = Settings(
            skip_jwt_validation=False,
            agent_provider_url="https://localhost:8000",
            debug=False,
        )

        with patch("lightspeed_agent.rotation.pubsub_jwt.get_settings", return_value=prod_settings):
            validator = PubSubJWTValidator(expected_audience="https://localhost:8000")
            mock_token = "mock.jwt.token"
            mock_header = {"kid": "test-key", "alg": "RS256"}
            mock_claims = {
                "iss": "https://accounts.google.com",
                "aud": "https://localhost:8000",
                "sub": "test@example.com",
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,
            }
            fake_public_key = "-----BEGIN PUBLIC KEY-----\nMOCK_KEY\n-----END PUBLIC KEY-----"

            with (
                patch("jwt.get_unverified_header", return_value=mock_header),
                patch("jwt.decode", return_value=mock_claims),
                # First call returns None, second call (after refresh) returns key
                patch.object(
                    validator._cert_cache,
                    "get_public_key",
                    side_effect=[None, fake_public_key],
                ),
                patch.object(validator._cert_cache, "force_refresh") as mock_refresh,
            ):
                claims = await validator.validate_push_token(mock_token)

                # Should have called force_refresh when key was not found
                mock_refresh.assert_called_once()
                # Should succeed after refresh
                assert claims is not None

    @pytest.mark.asyncio
    async def test_get_pubsub_jwt_validator_singleton(self):
        """Test that get_pubsub_jwt_validator returns singleton instance."""
        validator1 = get_pubsub_jwt_validator()
        validator2 = get_pubsub_jwt_validator()

        # Should be the same instance
        assert validator1 is validator2
