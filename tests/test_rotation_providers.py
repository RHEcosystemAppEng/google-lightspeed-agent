"""Tests for rotation secret value validation and template method pattern."""

from __future__ import annotations

import pytest

from lightspeed_agent.rotation.providers import SecretValueProvider
from lightspeed_agent.rotation.workflow import RotationEvent


class TestSecretValueProvider:
    """Test the abstract base class validation logic."""

    class FakeProvider(SecretValueProvider):
        """Fake provider for testing inherited methods."""

        def __init__(self, secret_to_return: str) -> None:
            self.secret_to_return = secret_to_return

        def _fetch_secret_from_api(self, event: RotationEvent) -> str:
            """Return the pre-configured secret."""
            return self.secret_to_return

    def test_validation_rejects_too_short(self) -> None:
        """Secret validation should reject secrets shorter than 32 bytes."""
        short_secret = "short-val!"  # Only 10 bytes
        provider = self.FakeProvider(short_secret)

        with pytest.raises(ValueError, match="too short.*10 bytes.*Minimum: 32 bytes"):
            provider.validate_secret_value(short_secret, "test-secret")

    def test_validation_rejects_low_entropy(self) -> None:
        """Secret validation should reject secrets with low entropy."""
        # 40-byte secret with only 2 unique characters (low entropy)
        low_entropy_secret = "a" * 39 + "b"
        provider = self.FakeProvider(low_entropy_secret)

        with pytest.raises(ValueError, match="insufficient entropy.*only 2 unique characters"):
            provider.validate_secret_value(low_entropy_secret, "test-secret")

    def test_validation_accepts_valid_secret(self) -> None:
        """Secret validation should accept secrets meeting all requirements."""
        # Valid 32+ byte secret with 10+ unique characters
        valid_secret = "abcdefghij1234567890KLMNOPQRSTUV"
        provider = self.FakeProvider(valid_secret)

        # Should not raise
        provider.validate_secret_value(valid_secret, "test-secret")

    def test_template_method_orchestrates_fetch_validate_convert(self) -> None:
        """Template method should fetch, validate, and convert to bytearray."""
        valid_secret = "abcdefghij1234567890KLMNOPQRSTUV"
        provider = self.FakeProvider(valid_secret)

        event = RotationEvent(project_id="test-proj", secret_name="test-secret")
        result = provider.get_next_secret_value(event)

        # Should return bytearray of the secret
        assert isinstance(result, bytearray)
        assert bytes(result) == valid_secret.encode("utf-8")

    def test_template_method_rejects_invalid_secret(self) -> None:
        """Template method should validate and reject invalid secrets."""
        invalid_secret = "tooshort"  # Only 8 bytes
        provider = self.FakeProvider(invalid_secret)

        event = RotationEvent(project_id="test-proj", secret_name="test-secret")

        with pytest.raises(ValueError, match="too short"):
            provider.get_next_secret_value(event)
