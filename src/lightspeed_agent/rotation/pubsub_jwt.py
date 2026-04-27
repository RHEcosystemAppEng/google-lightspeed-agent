"""Pub/Sub JWT validator for rotation endpoint verification.

This module validates OIDC tokens from Google Cloud Pub/Sub push subscriptions.
Unlike DCR's GoogleJWTValidator (which validates Google Cloud Marketplace
software_statement JWTs), this validates standard Google OAuth tokens used
to authenticate Pub/Sub push requests.

Security: Rotation events have no application-level auth (no software_statement).
Transport security via Pub/Sub OIDC tokens is the only security layer.
"""

import asyncio
import logging
import time
from typing import Any

import httpx
import jwt
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from jwt.exceptions import DecodeError, ExpiredSignatureError, InvalidTokenError

from lightspeed_agent.config import get_settings

logger = logging.getLogger(__name__)

# Google's OAuth certificate endpoint (v1 returns X.509 PEM format)
GOOGLE_OAUTH_CERTS_URL = "https://www.googleapis.com/oauth2/v1/certs"

# Expected issuer for Pub/Sub OIDC tokens
GOOGLE_OAUTH_ISSUER = "https://accounts.google.com"


class PubSubCertificateCache:
    """Cache for Google's X.509 certificates used to sign Pub/Sub OIDC tokens."""

    def __init__(self, cert_url: str = GOOGLE_OAUTH_CERTS_URL, cache_ttl: int = 3600):
        """Initialize the certificate cache.

        Args:
            cert_url: URL to fetch Google's X.509 certificates.
            cache_ttl: Cache time-to-live in seconds (default: 1 hour).
        """
        self._cert_url = cert_url
        self._cache_ttl = cache_ttl
        self._certificates: dict[str, Any] = {}
        self._last_fetch: float = 0
        self._lock = asyncio.Lock()

    async def get_public_key(self, kid: str) -> Any | None:
        """Get the public key for a given key ID.

        Args:
            kid: Key ID from JWT header.

        Returns:
            Public key or None if not found.
        """
        await self._ensure_fresh()
        return self._certificates.get(kid)

    async def _ensure_fresh(self) -> None:
        """Ensure the cache is fresh, fetching new certificates if needed."""
        current_time = time.monotonic()
        if current_time - self._last_fetch < self._cache_ttl and self._certificates:
            return

        async with self._lock:
            # Double-check after acquiring lock
            if current_time - self._last_fetch < self._cache_ttl and self._certificates:
                return

            await self._fetch_certificates()

    async def _fetch_certificates(self) -> None:
        """Fetch certificates from Google's endpoint."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self._cert_url, timeout=10.0)
                response.raise_for_status()
                certs_data = response.json()

            self._certificates = {}
            for kid, cert_pem in certs_data.items():
                try:
                    # Parse X.509 certificate and extract public key
                    cert = x509.load_pem_x509_certificate(cert_pem.encode())
                    public_key = cert.public_key()
                    # Convert to PEM format for jose library
                    pem = public_key.public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo,
                    )
                    self._certificates[kid] = pem.decode()
                except Exception as e:
                    logger.warning("Failed to parse certificate for kid %s: %s", kid, e)

            self._last_fetch = time.monotonic()
            logger.info("Fetched %d certificates from Google OAuth", len(self._certificates))

        except httpx.HTTPError as e:
            logger.error("Failed to fetch Google OAuth certificates: %s", e)
            if not self._certificates:
                raise RuntimeError(f"Failed to fetch certificates: {e}") from e

    async def force_refresh(self) -> None:
        """Force a refresh of the certificate cache."""
        self._last_fetch = 0
        await self._ensure_fresh()


class PubSubJWTValidator:
    """Validator for Google Pub/Sub OIDC push tokens."""

    def __init__(self, expected_audience: str | None = None):
        """Initialize the validator.

        Args:
            expected_audience: Expected audience (agent provider URL).
                             Uses settings.agent_provider_url if not provided.
        """
        self._settings = get_settings()
        self._expected_audience = expected_audience or self._settings.agent_provider_url
        self._cert_cache = PubSubCertificateCache()

    async def _decode_without_verification(self, token: str) -> dict[str, Any] | None:
        """Decode a token JWT without signature or issuer verification.

        Used in development mode (SKIP_JWT_VALIDATION=true) to allow testing
        with any OIDC token, not just Google's OAuth tokens.

        Returns:
            Claims dict on success, None on decode error.
        """
        logger.warning("Skipping Pub/Sub JWT signature/issuer validation - development mode")
        try:
            claims = jwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_exp": False,
                    "verify_aud": False,
                },
                algorithms=["RS256"],
            )
        except DecodeError as e:
            logger.warning("Failed to decode JWT (dev mode): %s", e)
            return None

        logger.info(
            "Dev mode: accepted Pub/Sub push token (iss: %s, aud: %s)",
            claims.get("iss"),
            claims.get("aud"),
        )
        return claims

    async def validate_push_token(self, token: str) -> dict[str, Any] | None:
        """Validate a Pub/Sub push token JWT from Google.

        Args:
            token: The JWT string to validate.

        Returns:
            Claims dict on success, None on failure (logs warnings).
        """
        if self._settings.skip_jwt_validation:
            return await self._decode_without_verification(token)

        try:
            # Decode header to get key ID
            unverified_header = jwt.get_unverified_header(token)
        except DecodeError as e:
            logger.warning("Failed to decode JWT header: %s", e)
            return None

        kid = unverified_header.get("kid")
        if not kid:
            logger.warning("JWT header missing 'kid' claim")
            return None

        # Verify algorithm is RS256
        alg = unverified_header.get("alg")
        if alg != "RS256":
            logger.warning("Unsupported algorithm: %s. Expected RS256", alg)
            return None

        # Get the signing key from Google's certificates
        public_key = await self._cert_cache.get_public_key(kid)
        if not public_key:
            # Key not found, try refreshing the cache
            await self._cert_cache.force_refresh()
            public_key = await self._cert_cache.get_public_key(kid)

        if not public_key:
            logger.warning("Key with ID '%s' not found in Google OAuth certificates", kid)
            return None

        # Validate and decode the JWT
        try:
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=self._expected_audience,
                issuer=GOOGLE_OAUTH_ISSUER,
                options={
                    "verify_aud": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_iss": True,
                    "require": ["iss", "iat", "exp", "aud", "sub"],
                },
            )
        except ExpiredSignatureError:
            logger.warning("Pub/Sub push token has expired")
            return None
        except InvalidTokenError as e:
            logger.warning("JWT validation failed: %s", e)
            return None

        logger.info(
            "Validated Pub/Sub push token (sub: %s, email: %s)",
            claims.get("sub"),
            claims.get("email"),
        )
        return claims


# Global validator instance
_pubsub_jwt_validator: PubSubJWTValidator | None = None


def get_pubsub_jwt_validator() -> PubSubJWTValidator:
    """Get the global Pub/Sub JWT validator instance.

    Returns:
        PubSubJWTValidator instance.
    """
    global _pubsub_jwt_validator
    if _pubsub_jwt_validator is None:
        _pubsub_jwt_validator = PubSubJWTValidator()
    return _pubsub_jwt_validator
