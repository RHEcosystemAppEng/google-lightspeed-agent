from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest

from lightspeed_agent.rotation.pubsub_jwt import PubSubCertificateCache
from lightspeed_agent.rotation.workflow import RotationEvent, RotationWorkflow, parse_rotation_event


@dataclass
class FakeSecretWriter:
    calls: list[tuple[str, str, bytes]]

    def add_secret_version(self, project_id: str, secret_name: str, secret_value: bytearray) -> str:
        self.calls.append((project_id, secret_name, bytes(secret_value)))
        return f"projects/{project_id}/secrets/{secret_name}/versions/2"


@dataclass
class FakeProvider:
    value: bytes = b"next-secret-value"

    def get_next_secret_value(self, event: RotationEvent) -> bytearray:
        assert event.secret_name in {
            "redhat-sso-client-secret",
            "gma-client-secret",
        }
        return bytearray(self.value)


def test_parse_rotation_event_returns_none_for_non_rotation() -> None:
    result = parse_rotation_event(
        {"eventType": "SECRET_UPDATE", "secretId": "projects/p/secrets/s"}
    )
    assert result is None


def test_parse_rotation_event_parses_secret_rotate() -> None:
    result = parse_rotation_event(
        {
            "eventType": "SECRET_ROTATE",
            "secretId": "projects/test-project/secrets/redhat-sso-client-secret",
        }
    )
    assert result is not None
    assert result.project_id == "test-project"
    assert result.secret_name == "redhat-sso-client-secret"


def test_workflow_ignores_unsupported_secret() -> None:
    writer = FakeSecretWriter(calls=[])
    provider = FakeProvider()
    workflow = RotationWorkflow(secret_writer=writer, value_provider=provider)

    result = workflow.handle_event(
        attributes={
            "eventType": "SECRET_ROTATE",
            "secretId": "projects/test-project/secrets/unsupported-secret",
        }
    )

    assert result.status == "ignored"
    assert result.reason == "unsupported_secret"
    assert writer.calls == []


def test_workflow_rotates_supported_secret() -> None:
    writer = FakeSecretWriter(calls=[])
    provider = FakeProvider(value=b"brand-new-value")
    workflow = RotationWorkflow(secret_writer=writer, value_provider=provider)

    result = workflow.handle_event(
        attributes={
            "eventType": "SECRET_ROTATE",
            "secretId": "projects/test-project/secrets/gma-client-secret",
        },
    )

    assert result.status == "rotated"
    assert result.secret_name == "gma-client-secret"
    assert result.secret_version == "projects/test-project/secrets/gma-client-secret/versions/2"
    assert writer.calls == [("test-project", "gma-client-secret", b"brand-new-value")]


@pytest.mark.asyncio
async def test_certificate_cache_parses_x509_pem_format() -> None:
    """Should parse X.509 PEM certificates returned by Google OAuth v1 endpoint."""
    cache = PubSubCertificateCache()

    # Valid X.509 PEM certificate format (self-signed test cert)
    cert_data = {
        "test-key-id": (
            "-----BEGIN CERTIFICATE-----\n"
            "MIICtDCCAZygAwIBAgIUDyF5NVWvQdW92NQyZ+8muSDzQWUwDQYJKoZIhvcNAQEL\n"
            "BQAwFDESMBAGA1UEAwwJdGVzdC1jZXJ0MB4XDTI2MDQyNjExMTgxNVoXDTI3MDQy\n"
            "NjExMTgxNVowFDESMBAGA1UEAwwJdGVzdC1jZXJ0MIIBIjANBgkqhkiG9w0BAQEF\n"
            "AAOCAQ8AMIIBCgKCAQEAz/lRq+GRzANbrFdg0HmYO1589h3C2gsVZxwdOFNcQyPI\n"
            "8fyBuhh5X967NjzeXtiIphp5H2+jFYwJPSij054862htGwGGt6qzH8Qrsqf36Lnk\n"
            "sFXQNVnyMhqqZpZA3agNtK+t7py1KX7XgrtLXPs66dlrpzH66d4rlXFE6T9/yQdD\n"
            "mQeKicSwk90iQa7tvBAVfm7eK5Zm56HEy2tzP76JZswLLPUBOkSqPIxhTKtVpiiU\n"
            "30xbzYyJhF59BKqVvPg6FJXeUauaRvfL9IamcAftA06CYIIl+Pjts7cJTwI0qbCL\n"
            "cCMtYy3lyIEc/Tyk/Z1wjevLkYmC56eJsCj88c+QeQIDAQABMA0GCSqGSIb3DQEB\n"
            "CwUAA4IBAQBZZOo9jZvLEdubB1gXlGYcOevkOJ92XwlocpQIxMg9oitkmqANrY5R\n"
            "6zFDCBT+9C6+STkWiD3WW30wT3/XandBO8iTcckfr/iyzEW6NlkXY7WEPBy1WR0b\n"
            "HrREUh/8XuqjGSDD8+bgxIqyi7U5LQu4S3ZOUMV+/X5jaLDr5uWDGFDK998ID2gT\n"
            "pqWPheZqdA/IXXQ6s7YXWkUGV77sTC3aqnT8IcfFKnzuiCavFzkD5F9+M0E3NDyl\n"
            "BKeYDZIq3P2YEbksCv3GjOfmLYvHALR0h9YrGKTuToOWdZc7t+Z2cqK2cSXOFd3b\n"
            "fG0y8U7CY0+Q2Qs2CoAyxbHc2kEyUjTy\n"
            "-----END CERTIFICATE-----\n"
        ),
    }

    async def mock_get(*args, **kwargs):
        response = AsyncMock()
        response.json = lambda: cert_data
        response.raise_for_status = lambda: None
        return response

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client_class.return_value.__aenter__.return_value = mock_client

        await cache._fetch_certificates()

    # Verify the certificate was parsed and public key was extracted
    assert len(cache._certificates) == 1
    assert "test-key-id" in cache._certificates
    # Public key should be PEM-encoded string starting with BEGIN PUBLIC KEY
    public_key_pem = cache._certificates["test-key-id"]
    assert isinstance(public_key_pem, str)
    assert public_key_pem.startswith("-----BEGIN PUBLIC KEY-----")
    assert public_key_pem.endswith("-----END PUBLIC KEY-----\n")


@pytest.mark.asyncio
async def test_certificate_cache_handles_malformed_cert() -> None:
    """Should skip malformed certificates and continue parsing others."""
    cache = PubSubCertificateCache()

    cert_data = {
        "bad-cert": "not-a-valid-pem-cert",
        "good-cert": (
            "-----BEGIN CERTIFICATE-----\n"
            "MIICtDCCAZygAwIBAgIUDyF5NVWvQdW92NQyZ+8muSDzQWUwDQYJKoZIhvcNAQEL\n"
            "BQAwFDESMBAGA1UEAwwJdGVzdC1jZXJ0MB4XDTI2MDQyNjExMTgxNVoXDTI3MDQy\n"
            "NjExMTgxNVowFDESMBAGA1UEAwwJdGVzdC1jZXJ0MIIBIjANBgkqhkiG9w0BAQEF\n"
            "AAOCAQ8AMIIBCgKCAQEAz/lRq+GRzANbrFdg0HmYO1589h3C2gsVZxwdOFNcQyPI\n"
            "8fyBuhh5X967NjzeXtiIphp5H2+jFYwJPSij054862htGwGGt6qzH8Qrsqf36Lnk\n"
            "sFXQNVnyMhqqZpZA3agNtK+t7py1KX7XgrtLXPs66dlrpzH66d4rlXFE6T9/yQdD\n"
            "mQeKicSwk90iQa7tvBAVfm7eK5Zm56HEy2tzP76JZswLLPUBOkSqPIxhTKtVpiiU\n"
            "30xbzYyJhF59BKqVvPg6FJXeUauaRvfL9IamcAftA06CYIIl+Pjts7cJTwI0qbCL\n"
            "cCMtYy3lyIEc/Tyk/Z1wjevLkYmC56eJsCj88c+QeQIDAQABMA0GCSqGSIb3DQEB\n"
            "CwUAA4IBAQBZZOo9jZvLEdubB1gXlGYcOevkOJ92XwlocpQIxMg9oitkmqANrY5R\n"
            "6zFDCBT+9C6+STkWiD3WW30wT3/XandBO8iTcckfr/iyzEW6NlkXY7WEPBy1WR0b\n"
            "HrREUh/8XuqjGSDD8+bgxIqyi7U5LQu4S3ZOUMV+/X5jaLDr5uWDGFDK998ID2gT\n"
            "pqWPheZqdA/IXXQ6s7YXWkUGV77sTC3aqnT8IcfFKnzuiCavFzkD5F9+M0E3NDyl\n"
            "BKeYDZIq3P2YEbksCv3GjOfmLYvHALR0h9YrGKTuToOWdZc7t+Z2cqK2cSXOFd3b\n"
            "fG0y8U7CY0+Q2Qs2CoAyxbHc2kEyUjTy\n"
            "-----END CERTIFICATE-----\n"
        ),
    }

    async def mock_get(*args, **kwargs):
        response = AsyncMock()
        response.json = lambda: cert_data
        response.raise_for_status = lambda: None
        return response

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client_class.return_value.__aenter__.return_value = mock_client

        await cache._fetch_certificates()

    # Should have skipped the bad cert but parsed the good one
    assert len(cache._certificates) == 1
    assert "good-cert" in cache._certificates
    assert "bad-cert" not in cache._certificates
