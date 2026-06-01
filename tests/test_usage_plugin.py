"""Tests for usage tracking plugin persistence behavior."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from lightspeed_agent.api.a2a import usage_plugin


class TestUsageTrackingPlugin:
    """Tests for persistence behavior in usage plugin callbacks."""

    @pytest.mark.asyncio
    async def test_before_run_persists_request_increment_when_order_present(
        self, monkeypatch
    ):
        """Persist request_count=1 for a valid request order."""
        repo = MagicMock()
        repo.increment_usage = AsyncMock()
        monkeypatch.setattr(usage_plugin, "get_usage_repository", lambda: repo)
        monkeypatch.setattr(usage_plugin, "get_request_order_id", lambda: "order-123")
        monkeypatch.setattr(usage_plugin, "get_request_client_id", lambda: "client-abc")

        plugin = usage_plugin.UsageTrackingPlugin()
        await plugin.before_run_callback(invocation_context=None)

        repo.increment_usage.assert_awaited_once_with(
            order_id="order-123",
            client_id="client-abc",
            request_count=1,
            input_tokens=0,
            output_tokens=0,
            tool_calls=0,
        )

    @pytest.mark.asyncio
    async def test_before_run_skips_persistence_when_order_missing(self, monkeypatch):
        """Do not persist increments if request context has no order."""
        repo = MagicMock()
        repo.increment_usage = AsyncMock()
        monkeypatch.setattr(usage_plugin, "get_usage_repository", lambda: repo)
        monkeypatch.setattr(usage_plugin, "get_request_order_id", lambda: None)
        monkeypatch.setattr(usage_plugin, "get_request_client_id", lambda: None)

        plugin = usage_plugin.UsageTrackingPlugin()
        await plugin.before_run_callback(invocation_context=None)

        repo.increment_usage.assert_not_called()

    @pytest.mark.asyncio
    async def test_before_run_passes_none_client_id_when_missing(self, monkeypatch):
        """Pass client_id=None when order exists but client_id is absent."""
        repo = MagicMock()
        repo.increment_usage = AsyncMock()
        monkeypatch.setattr(usage_plugin, "get_usage_repository", lambda: repo)
        monkeypatch.setattr(usage_plugin, "get_request_order_id", lambda: "order-dev")
        monkeypatch.setattr(usage_plugin, "get_request_client_id", lambda: None)

        plugin = usage_plugin.UsageTrackingPlugin()
        await plugin.before_run_callback(invocation_context=None)

        repo.increment_usage.assert_awaited_once_with(
            order_id="order-dev",
            client_id=None,
            request_count=1,
            input_tokens=0,
            output_tokens=0,
            tool_calls=0,
        )

    @pytest.mark.asyncio
    async def test_after_model_persists_input_output_tokens(self, monkeypatch):
        """Persist LLM token counts for a valid order."""
        repo = MagicMock()
        repo.increment_usage = AsyncMock()
        llm_response = MagicMock()
        llm_response.usage_metadata = MagicMock(
            prompt_token_count=11, candidates_token_count=7
        )
        monkeypatch.setattr(usage_plugin, "get_usage_repository", lambda: repo)
        monkeypatch.setattr(usage_plugin, "get_request_order_id", lambda: "order-abc")
        monkeypatch.setattr(usage_plugin, "get_request_client_id", lambda: "client-xyz")

        plugin = usage_plugin.UsageTrackingPlugin()
        await plugin.after_model_callback(callback_context=None, llm_response=llm_response)

        repo.increment_usage.assert_awaited_once_with(
            order_id="order-abc",
            client_id="client-xyz",
            request_count=0,
            input_tokens=11,
            output_tokens=7,
            tool_calls=0,
        )

    @pytest.mark.asyncio
    async def test_after_tool_persists_tool_call_increment(self, monkeypatch):
        """Persist tool_calls=1 for tool callback events."""
        repo = MagicMock()
        repo.increment_usage = AsyncMock()
        monkeypatch.setattr(usage_plugin, "get_usage_repository", lambda: repo)
        monkeypatch.setattr(usage_plugin, "get_request_order_id", lambda: "order-tools")
        monkeypatch.setattr(usage_plugin, "get_request_client_id", lambda: "client-tools")
        tool = MagicMock()
        tool.name = "test_tool"

        plugin = usage_plugin.UsageTrackingPlugin()
        await plugin.after_tool_callback(
            tool=tool,
            tool_args={},
            tool_context=None,
            result={},
        )

        repo.increment_usage.assert_awaited_once_with(
            order_id="order-tools",
            client_id="client-tools",
            request_count=0,
            input_tokens=0,
            output_tokens=0,
            tool_calls=1,
        )

    @pytest.mark.asyncio
    async def test_after_tool_callback_increments_tool_counter(self, monkeypatch):
        """Verify after_tool_callback calls increment_tool_call."""
        repo = MagicMock()
        repo.increment_usage = AsyncMock()
        monkeypatch.setattr(usage_plugin, "get_usage_repository", lambda: repo)
        monkeypatch.setattr(usage_plugin, "get_request_order_id", lambda: "order-001")
        monkeypatch.setattr(usage_plugin, "get_request_client_id", lambda: "client-aaa")
        mock_increment = MagicMock()
        monkeypatch.setattr(usage_plugin, "increment_tool_call", mock_increment)
        tool = MagicMock()
        tool.name = "advisor_list_recommendations"

        plugin = usage_plugin.UsageTrackingPlugin()
        await plugin.after_tool_callback(
            tool=tool,
            tool_args={},
            tool_context=None,
            result={},
        )

        mock_increment.assert_called_once_with(
            tool_name="advisor_list_recommendations",
        )
