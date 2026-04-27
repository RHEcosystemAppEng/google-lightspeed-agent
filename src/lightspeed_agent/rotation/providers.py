"""Secret value provider implementations for rotation workflows.

This module supports pluggable providers for different secret sources.
Each secret can be retrieved from its own API/service:
- Red Hat SSO secrets → Red Hat Identity API
- GMA secrets → Google Marketplace API
- etc.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from lightspeed_agent.rotation.workflow import RotationEvent

logger = logging.getLogger(__name__)


class MissingSecretValueError(RuntimeError):
    """Raised when no value is available for a rotation event."""


class SecretValueProvider(ABC):
    """Base class for secret value providers.

    Each provider retrieves secret values from a specific source
    (API, service, environment, etc.) and returns them as mutable
    bytearrays for secure memory handling.

    Subclasses must implement:
    - _fetch_secret_from_api(): API-specific secret retrieval logic

    Subclasses inherit:
    - validate_secret_value(): Shared validation logic
    - get_next_secret_value(): Template method that orchestrates fetch + validate + convert
    """

    @abstractmethod
    def _fetch_secret_from_api(self, event: RotationEvent) -> str:
        """Fetch secret value from the provider's API.

        This is the only method subclasses need to implement.
        Each provider calls its specific API here.

        Args:
            event: The rotation event containing secret metadata

        Returns:
            The new secret value as a string

        Raises:
            MissingSecretValueError: If the secret cannot be retrieved from the API
        """

    def validate_secret_value(self, value: str, secret_name: str) -> None:
        """Validate that a secret meets minimum security requirements.

        This method is inherited by all provider subclasses.

        Args:
            value: The secret value to validate
            secret_name: Name of the secret (for error messages)

        Raises:
            ValueError: If the secret doesn't meet minimum requirements
        """
        # OAuth 2.0 client secrets should be at least 32 bytes
        byte_len = len(value.encode("utf-8"))
        if byte_len < 32:
            raise ValueError(
                f"Secret value for '{secret_name}' is too short "
                f"({byte_len} bytes). Minimum: 32 bytes for OAuth client secrets."
            )

        # Basic entropy check: require at least 10 unique characters
        unique_chars = len(set(value))
        if unique_chars < 10:
            raise ValueError(
                f"Secret value for '{secret_name}' has insufficient entropy "
                f"(only {unique_chars} unique characters)."
            )

    def get_next_secret_value(self, event: RotationEvent) -> bytearray:
        """Get the next secret value for rotation (template method).

        This method orchestrates the rotation workflow:
        1. Fetch secret from API (calls abstract method)
        2. Validate secret quality (calls inherited method)
        3. Convert to mutable bytearray

        Subclasses should NOT override this - override _fetch_secret_from_api() instead.

        Args:
            event: The rotation event containing secret metadata

        Returns:
            The new secret value as a mutable bytearray

        Raises:
            MissingSecretValueError: If the secret cannot be retrieved
            ValueError: If the secret doesn't meet validation requirements
        """
        # 1. Fetch from API (abstract - each provider implements differently)
        secret_value = self._fetch_secret_from_api(event)

        # 2. Validate (concrete - same for all providers)
        self.validate_secret_value(secret_value, event.secret_name)

        # 3. Convert to bytearray (concrete - same for all providers)
        # bytearray(str, encoding) encodes directly into a mutable buffer,
        # avoiding an explicit intermediate bytes object at the Python level.
        return bytearray(secret_value, "utf-8")


class RedHatSSOSecretProvider(SecretValueProvider):
    """Provider for Red Hat SSO client secrets.

    Retrieves new OAuth client secrets from Red Hat Identity API.

    TODO: Implement integration with Red Hat Identity Management API
          to generate/rotate OAuth client secrets for SSO.
    """

    def _fetch_secret_from_api(self, event: RotationEvent) -> str:
        """Fetch next Red Hat SSO client secret from Red Hat Identity API.

        TODO: Replace this placeholder with actual Red Hat Identity API call:
              1. Authenticate with Red Hat Identity API
              2. Request new client secret for the SSO client
              3. Return the generated secret as a string

        Args:
            event: Rotation event with project_id and secret_name

        Returns:
            New client secret as string

        Raises:
            MissingSecretValueError: If API call fails
        """
        raise NotImplementedError(
            "Red Hat SSO secret provider not yet implemented. "
            "Implement _fetch_secret_from_api() with Red Hat Identity API integration."
        )


class GMASecretProvider(SecretValueProvider):
    """Provider for GMA (Google Marketplace API) client secrets.

    Retrieves new OAuth client secrets from Google Marketplace Admin API.

    TODO: Implement integration with GMA API to generate/rotate
          OAuth client secrets for marketplace integration.
    """

    def _fetch_secret_from_api(self, event: RotationEvent) -> str:
        """Fetch next GMA client secret from Google Marketplace API.

        TODO: Replace this placeholder with actual GMA API call:
              1. Authenticate with GMA API (using GMA service credentials)
              2. Request new client secret regeneration
              3. Return the generated secret as a string

        Args:
            event: Rotation event with project_id and secret_name

        Returns:
            New client secret as string

        Raises:
            MissingSecretValueError: If API call fails
        """
        raise NotImplementedError(
            "GMA secret provider not yet implemented. "
            "Implement _fetch_secret_from_api() with GMA API integration."
        )


class SecretProviderRegistry:
    """Registry that routes secrets to their appropriate providers.

    Maps secret names to provider instances. This allows each secret
    to be retrieved from a different source (API, service, etc.).

    Implements the SecretValueProvider protocol from workflow.py (duck typing),
    but does NOT inherit from the ABC since it doesn't fetch from an API itself -
    it delegates to registered providers.

    Usage:
        registry = SecretProviderRegistry()
        registry.register("redhat-sso-client-secret", RedHatSSOSecretProvider())
        registry.register("gma-client-secret", GMASecretProvider())

        # Use directly in RotationWorkflow:
        workflow = RotationWorkflow(value_provider=registry, ...)
        result = workflow.handle_event(...)
    """

    def __init__(self) -> None:
        self._providers: dict[str, SecretValueProvider] = {}
        self._default_provider: SecretValueProvider | None = None

    def register(self, secret_name: str, provider: SecretValueProvider) -> None:
        """Register a provider for a specific secret.

        Args:
            secret_name: The secret name (e.g., "redhat-sso-client-secret")
            provider: The provider instance to use for this secret
        """
        self._providers[secret_name] = provider
        logger.info("Registered provider %s for secret '%s'", type(provider).__name__, secret_name)

    def set_default_provider(self, provider: SecretValueProvider) -> None:
        """Set the default provider for secrets without specific providers.

        Args:
            provider: The provider to use as fallback
        """
        self._default_provider = provider
        logger.info("Set default provider to %s", type(provider).__name__)

    def get_provider(self, secret_name: str) -> SecretValueProvider:
        """Get the provider for a specific secret.

        Args:
            secret_name: The secret name to look up

        Returns:
            The provider instance for this secret

        Raises:
            MissingSecretValueError: If no provider is registered for this secret
        """
        provider = self._providers.get(secret_name)
        if provider is not None:
            return provider

        if self._default_provider is not None:
            logger.info(
                "Using default provider %s for secret '%s'",
                type(self._default_provider).__name__,
                secret_name,
            )
            return self._default_provider

        raise MissingSecretValueError(
            f"No provider registered for secret '{secret_name}' and no default provider set."
        )

    def get_next_secret_value(self, event: RotationEvent) -> bytearray:
        """Get the next secret value by delegating to the appropriate provider.

        Looks up the provider for the secret name in the event and delegates
        the actual retrieval to that provider.

        Args:
            event: The rotation event containing secret metadata

        Returns:
            The new secret value as a mutable bytearray

        Raises:
            MissingSecretValueError: If no provider is registered or retrieval fails
            ValueError: If the secret doesn't meet validation requirements
        """
        provider = self.get_provider(event.secret_name)
        return provider.get_next_secret_value(event)


def create_default_registry() -> SecretProviderRegistry:
    """Create the default provider registry.

    Register API-based providers for each secret type.

    TODO: Implement the provider classes:
          - RedHatSSOSecretProvider: Integrate with Red Hat Identity API
          - GMASecretProvider: Integrate with Google Marketplace API

    Returns:
        Configured SecretProviderRegistry instance
    """
    registry = SecretProviderRegistry()

    # TODO: Uncomment when provider implementations are ready
    # registry.register("redhat-sso-client-secret", RedHatSSOSecretProvider())
    # registry.register("gma-client-secret", GMASecretProvider())

    logger.info("Created provider registry (providers not yet registered)")
    return registry
