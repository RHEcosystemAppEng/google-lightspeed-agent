"""Secret rotation workflow primitives.

This module provides a small, testable workflow that:
1) parses Secret Manager Pub/Sub event attributes
2) filters to supported secrets
3) requests a new secret value from a provider
4) stores a new Secret Manager version

Actual secret generation is delegated to provider implementations.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

SUPPORTED_SECRET_NAMES = frozenset(
    {
        "redhat-sso-client-secret",
        "gma-client-secret",
    }
)


@dataclass(frozen=True)
class RotationEvent:
    """Parsed Secret Manager rotation event."""

    project_id: str
    secret_name: str


@dataclass(frozen=True)
class RotationResult:
    """Outcome returned by the workflow handler."""

    status: str
    reason: str
    secret_name: str | None = None
    secret_version: str | None = None


class SecretManagerVersionWriter(Protocol):
    """Protocol for writing a new Secret Manager version."""

    def add_secret_version(self, project_id: str, secret_name: str, secret_value: bytearray) -> str:
        """Add a new secret version and return its full resource name."""


class SecretValueProvider(Protocol):
    """Protocol for generating/acquiring the next secret value."""

    def get_next_secret_value(self, event: RotationEvent) -> bytearray:
        """Return the next value for the rotated secret."""


def parse_rotation_event(attributes: Mapping[str, str]) -> RotationEvent | None:
    """Parse Secret Manager event attributes into a RotationEvent.

    Expected Secret Manager attributes include:
    - eventType: e.g. SECRET_ROTATE
    - secretId: projects/<project>/secrets/<secret-name>
    """
    event_type = attributes.get("eventType", "")
    if event_type != "SECRET_ROTATE":
        return None

    secret_id = attributes.get("secretId", "")
    parts = secret_id.split("/")
    if len(parts) != 4 or parts[0] != "projects" or parts[2] != "secrets":
        return None

    project_id = parts[1]
    secret_name = parts[3]
    if not project_id or not secret_name:
        return None

    return RotationEvent(project_id=project_id, secret_name=secret_name)


class RotationWorkflow:
    """Workflow that handles Secret Manager rotation notifications."""

    def __init__(
        self,
        *,
        secret_writer: SecretManagerVersionWriter,
        value_provider: SecretValueProvider,
    ) -> None:
        self._secret_writer = secret_writer
        self._value_provider = value_provider

    def handle_event(
        self,
        *,
        attributes: Mapping[str, str],
    ) -> RotationResult:
        """Handle one rotation event notification.

        Returns a RotationResult for all outcomes, including ignored/unsupported
        events, so push and pull consumers can ack cleanly without catching.
        Exceptions from the secret writer propagate so Pub/Sub retries on
        transient GCP failures.
        """
        event = parse_rotation_event(attributes)
        if event is None:
            return RotationResult(status="ignored", reason="not_a_secret_rotate_event")

        if event.secret_name not in SUPPORTED_SECRET_NAMES:
            return RotationResult(
                status="ignored",
                reason="unsupported_secret",
                secret_name=event.secret_name,
            )

        next_value = self._value_provider.get_next_secret_value(event)
        try:
            version_name = self._secret_writer.add_secret_version(
                event.project_id,
                event.secret_name,
                next_value,
            )
        finally:
            # Zero the mutable buffer regardless of success or failure.
            for i in range(len(next_value)):
                next_value[i] = 0

        return RotationResult(
            status="rotated",
            reason="secret_version_added",
            secret_name=event.secret_name,
            secret_version=version_name,
        )
