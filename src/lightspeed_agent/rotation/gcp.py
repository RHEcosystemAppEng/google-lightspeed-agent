"""Google Cloud adapters for secret rotation workflows."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class GoogleSecretManagerVersionWriter:
    """Write secret versions using google-cloud-secret-manager."""

    def __init__(self) -> None:
        # Imported lazily so this module can be imported in environments where
        # google-cloud-secret-manager is not installed.
        from google.cloud import secretmanager  # type: ignore[import-not-found]

        self._client = secretmanager.SecretManagerServiceClient()

    def add_secret_version(self, project_id: str, secret_name: str, secret_value: bytearray) -> str:
        """Add a new secret version to Google Secret Manager.

        Args:
            project_id: GCP project ID
            secret_name: Name of the secret
            secret_value: The secret payload as a bytearray

        Returns:
            Full resource name of the created version
            (e.g., "projects/my-project/secrets/my-secret/versions/123")

        Raises:
            google.api_core.exceptions.GoogleAPIError: For all GCP API errors.
            Exceptions are logged and re-raised to trigger Pub/Sub retry.
        """
        parent = f"projects/{project_id}/secrets/{secret_name}"

        try:
            response = self._client.add_secret_version(
                request={"parent": parent, "payload": {"data": bytes(secret_value)}}
            )
            version_name = str(response.name)

            logger.info(
                "Successfully added secret version (project_id=%s, secret_name=%s, version=%s)",
                project_id,
                secret_name,
                version_name,
            )
            return version_name

        except Exception as e:
            # Log the error with context before re-raising
            # This helps diagnose issues while still allowing Pub/Sub to retry
            logger.exception(
                "Failed to add secret version to Secret Manager "
                "(project_id=%s, secret_name=%s, error_type=%s)",
                project_id,
                secret_name,
                type(e).__name__,
            )
            raise
