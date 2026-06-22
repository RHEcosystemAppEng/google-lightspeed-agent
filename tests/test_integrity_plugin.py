"""Tests for the MCP response integrity fingerprinting plugin."""

import hashlib
import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from lightspeed_agent.api.a2a.integrity_plugin import IntegrityFingerprintPlugin


def _make_tool(name: str = "test_tool") -> MagicMock:
    tool = MagicMock()
    tool.name = name
    return tool


class TestIntegrityFingerprintPlugin:
    """Tests for IntegrityFingerprintPlugin after_tool_callback."""

    @pytest.mark.asyncio
    async def test_returns_none(self):
        """Callback should never modify the result."""
        plugin = IntegrityFingerprintPlugin()
        result = {"data": "some value"}

        with patch(
            "lightspeed_agent.api.a2a.integrity_plugin.get_request_id",
            return_value="req-1",
        ):
            got = await plugin.after_tool_callback(
                tool=_make_tool(),
                tool_args={},
                tool_context=MagicMock(),
                result=result,
            )

        assert got is None

    @pytest.mark.asyncio
    async def test_logs_fingerprint_with_tool_name(self, caplog):
        """Log entry should include the tool name."""
        plugin = IntegrityFingerprintPlugin()

        with (
            patch("lightspeed_agent.api.a2a.integrity_plugin.get_request_id", return_value="req-1"),
            caplog.at_level(logging.INFO),
        ):
            await plugin.after_tool_callback(
                tool=_make_tool("advisor__get_active_rules"),
                tool_args={},
                tool_context=MagicMock(),
                result={"rules": []},
            )

        assert any("advisor__get_active_rules" in r.message for r in caplog.records)
        assert any("mcp_result_fingerprint" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_logs_request_id(self, caplog):
        """Log entry should include the request_id from context."""
        plugin = IntegrityFingerprintPlugin()

        with (
            patch(
                "lightspeed_agent.api.a2a.integrity_plugin.get_request_id",
                return_value="abc-123-def",
            ),
            caplog.at_level(logging.INFO),
        ):
            await plugin.after_tool_callback(
                tool=_make_tool(),
                tool_args={},
                tool_context=MagicMock(),
                result={"data": "value"},
            )

        assert any("abc-123-def" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_fingerprint_is_deterministic(self, caplog):
        """Same result should produce the same fingerprint across calls."""
        plugin = IntegrityFingerprintPlugin()
        result = {"hosts": [{"id": 1}, {"id": 2}]}

        fingerprints = []
        for _ in range(2):
            caplog.clear()
            with (
                patch(
                    "lightspeed_agent.api.a2a.integrity_plugin.get_request_id",
                    return_value="req-1",
                ),
                caplog.at_level(logging.INFO),
            ):
                await plugin.after_tool_callback(
                    tool=_make_tool(),
                    tool_args={},
                    tool_context=MagicMock(),
                    result=result,
                )
            for record in caplog.records:
                if "fingerprint=" in record.message:
                    start = record.message.index("fingerprint=") + len("fingerprint=")
                    end = record.message.index(",", start)
                    fingerprints.append(record.message[start:end])

        assert len(fingerprints) == 2
        assert fingerprints[0] == fingerprints[1]

    @pytest.mark.asyncio
    async def test_fingerprint_changes_with_different_result(self, caplog):
        """Different results should produce different fingerprints."""
        plugin = IntegrityFingerprintPlugin()

        fingerprints = []
        for data in [{"a": 1}, {"a": 2}]:
            caplog.clear()
            with (
                patch(
                    "lightspeed_agent.api.a2a.integrity_plugin.get_request_id",
                    return_value="req-1",
                ),
                caplog.at_level(logging.INFO),
            ):
                await plugin.after_tool_callback(
                    tool=_make_tool(),
                    tool_args={},
                    tool_context=MagicMock(),
                    result=data,
                )
            for record in caplog.records:
                if "fingerprint=" in record.message:
                    start = record.message.index("fingerprint=") + len("fingerprint=")
                    end = record.message.index(",", start)
                    fingerprints.append(record.message[start:end])

        assert len(fingerprints) == 2
        assert fingerprints[0] != fingerprints[1]

    @pytest.mark.asyncio
    async def test_handles_non_serializable_result(self, caplog):
        """When json.dumps raises, fall back to str() and log a warning."""
        plugin = IntegrityFingerprintPlugin()
        result = {"data": "value"}
        expected_serialized = str(result)
        expected_fp = hashlib.sha256(expected_serialized.encode("utf-8")).hexdigest()

        with (
            patch(
                "lightspeed_agent.api.a2a.integrity_plugin.get_request_id",
                return_value="req-1",
            ),
            patch(
                "lightspeed_agent.api.a2a.integrity_plugin.json.dumps",
                side_effect=TypeError("not serializable"),
            ),
            caplog.at_level(logging.DEBUG),
        ):
            got = await plugin.after_tool_callback(
                tool=_make_tool(),
                tool_args={},
                tool_context=MagicMock(),
                result=result,
            )

        assert got is None
        assert any("mcp_result_fingerprint" in r.message for r in caplog.records)
        assert any("serialization=fallback" in r.message for r in caplog.records)
        assert any(
            r.levelno == logging.WARNING and "fingerprint may not be reproducible" in r.message
            for r in caplog.records
        )
        logged_fp = None
        for record in caplog.records:
            if "fingerprint=" in record.message:
                start = record.message.index("fingerprint=") + len("fingerprint=")
                end = record.message.index(",", start)
                logged_fp = record.message[start:end]
        assert logged_fp == expected_fp

    @pytest.mark.asyncio
    async def test_logs_result_length(self, caplog):
        """Log entry should include the serialized result length."""
        plugin = IntegrityFingerprintPlugin()
        result = {"key": "value"}
        expected_length = len(json.dumps(result, sort_keys=True, default=str))

        with (
            patch(
                "lightspeed_agent.api.a2a.integrity_plugin.get_request_id",
                return_value="req-1",
            ),
            caplog.at_level(logging.INFO),
        ):
            await plugin.after_tool_callback(
                tool=_make_tool(),
                tool_args={},
                tool_context=MagicMock(),
                result=result,
            )

        assert any(f"length={expected_length}" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_fingerprint_matches_expected_sha256(self, caplog):
        """Fingerprint should match manually computed SHA-256."""
        plugin = IntegrityFingerprintPlugin()
        result = {"answer": 42}
        serialized = json.dumps(result, sort_keys=True, default=str)
        expected = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        with (
            patch(
                "lightspeed_agent.api.a2a.integrity_plugin.get_request_id",
                return_value="req-1",
            ),
            caplog.at_level(logging.INFO),
        ):
            got = await plugin.after_tool_callback(
                tool=_make_tool(),
                tool_args={},
                tool_context=MagicMock(),
                result=result,
            )

        assert got is None
        logged_fingerprint = None
        for record in caplog.records:
            if "fingerprint=" in record.message:
                start = record.message.index("fingerprint=") + len("fingerprint=")
                end = record.message.index(",", start)
                logged_fingerprint = record.message[start:end]
        assert logged_fingerprint == expected

    @pytest.mark.asyncio
    async def test_none_request_id_logged(self, caplog):
        """When no request_id is set, None should appear in the log."""
        plugin = IntegrityFingerprintPlugin()

        with (
            patch(
                "lightspeed_agent.api.a2a.integrity_plugin.get_request_id",
                return_value=None,
            ),
            caplog.at_level(logging.INFO),
        ):
            await plugin.after_tool_callback(
                tool=_make_tool(),
                tool_args={},
                tool_context=MagicMock(),
                result={"data": "value"},
            )

        assert any("request_id=None" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_logs_audit_fields(self, caplog):
        """Log entry should include user_id, org_id, and order_id."""
        plugin = IntegrityFingerprintPlugin()

        with (
            patch(
                "lightspeed_agent.api.a2a.integrity_plugin.get_request_id",
                return_value="req-1",
            ),
            patch(
                "lightspeed_agent.api.a2a.integrity_plugin.get_request_user_id",
                return_value="user-42",
            ),
            patch(
                "lightspeed_agent.api.a2a.integrity_plugin.get_request_org_id",
                return_value="org-7",
            ),
            patch(
                "lightspeed_agent.api.a2a.integrity_plugin.get_request_order_id",
                return_value="order-99",
            ),
            caplog.at_level(logging.INFO),
        ):
            await plugin.after_tool_callback(
                tool=_make_tool(),
                tool_args={},
                tool_context=MagicMock(),
                result={"data": "value"},
            )

        assert any("user_id=user-42" in r.message for r in caplog.records)
        assert any("org_id=org-7" in r.message for r in caplog.records)
        assert any("order_id=order-99" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_logs_serialization_json(self, caplog):
        """Normal JSON serialization should log serialization=json."""
        plugin = IntegrityFingerprintPlugin()

        with (
            patch(
                "lightspeed_agent.api.a2a.integrity_plugin.get_request_id",
                return_value="req-1",
            ),
            caplog.at_level(logging.INFO),
        ):
            await plugin.after_tool_callback(
                tool=_make_tool(),
                tool_args={},
                tool_context=MagicMock(),
                result={"key": "value"},
            )

        assert any("serialization=json" in r.message for r in caplog.records)
