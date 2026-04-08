"""Tests for usage tracking plugin persistence behavior."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lightspeed_agent.api.a2a import usage_plugin


class TestUsageTrackingPlugin:
    """Tests for persistence behavior in usage plugin callbacks."""

    @pytest.mark.asyncio
    async def test_before_run_persists_request_increment_when_order_present(self):
        """Persist request_count=1 for a valid request order."""
        repo = MagicMock()
        repo.increment_usage = AsyncMock()
        original_get_repo = usage_plugin.get_usage_repository
        original_get_order = usage_plugin.get_request_order_id
        usage_plugin.get_usage_repository = lambda: repo
        usage_plugin.get_request_order_id = lambda: "order-123"
        try:
            plugin = usage_plugin.UsageTrackingPlugin()
            await plugin.before_run_callback(invocation_context=None)
        finally:
            usage_plugin.get_usage_repository = original_get_repo
            usage_plugin.get_request_order_id = original_get_order

        repo.increment_usage.assert_awaited_once_with(
            order_id="order-123",
            request_count=1,
            input_tokens=0,
            output_tokens=0,
            tool_calls=0,
        )

    @pytest.mark.asyncio
    async def test_before_run_skips_persistence_when_order_missing(self):
        """Do not persist increments if request context has no order."""
        repo = MagicMock()
        repo.increment_usage = AsyncMock()
        original_get_repo = usage_plugin.get_usage_repository
        original_get_order = usage_plugin.get_request_order_id
        usage_plugin.get_usage_repository = lambda: repo
        usage_plugin.get_request_order_id = lambda: None
        try:
            plugin = usage_plugin.UsageTrackingPlugin()
            await plugin.before_run_callback(invocation_context=None)
        finally:
            usage_plugin.get_usage_repository = original_get_repo
            usage_plugin.get_request_order_id = original_get_order

        repo.increment_usage.assert_not_called()

    @pytest.mark.asyncio
    async def test_after_model_persists_input_output_tokens(self):
        """Persist LLM token counts for a valid order."""
        repo = MagicMock()
        repo.increment_usage = AsyncMock()
        llm_response = MagicMock()
        llm_response.usage_metadata = MagicMock(
            prompt_token_count=11, candidates_token_count=7
        )
        original_get_repo = usage_plugin.get_usage_repository
        original_get_order = usage_plugin.get_request_order_id
        usage_plugin.get_usage_repository = lambda: repo
        usage_plugin.get_request_order_id = lambda: "order-abc"
        try:
            plugin = usage_plugin.UsageTrackingPlugin()
            await plugin.after_model_callback(callback_context=None, llm_response=llm_response)
        finally:
            usage_plugin.get_usage_repository = original_get_repo
            usage_plugin.get_request_order_id = original_get_order

        repo.increment_usage.assert_awaited_once_with(
            order_id="order-abc",
            request_count=0,
            input_tokens=11,
            output_tokens=7,
            tool_calls=0,
        )

    @pytest.mark.asyncio
    async def test_after_tool_persists_tool_call_increment(self):
        """Persist tool_calls=1 for tool callback events."""
        repo = MagicMock()
        repo.increment_usage = AsyncMock()
        original_get_repo = usage_plugin.get_usage_repository
        original_get_order = usage_plugin.get_request_order_id
        usage_plugin.get_usage_repository = lambda: repo
        usage_plugin.get_request_order_id = lambda: "order-tools"
        tool = MagicMock()
        tool.name = "test_tool"
        try:
            plugin = usage_plugin.UsageTrackingPlugin()
            await plugin.after_tool_callback(
                tool=tool,
                tool_args={},
                tool_context=None,
                result={},
            )
        finally:
            usage_plugin.get_usage_repository = original_get_repo
            usage_plugin.get_request_order_id = original_get_order

        repo.increment_usage.assert_awaited_once_with(
            order_id="order-tools",
            request_count=0,
            input_tokens=0,
            output_tokens=0,
            tool_calls=1,
        )


def _tool_context(invocation_id: str) -> MagicMock:
    ctx = MagicMock()
    ctx.invocation_id = invocation_id
    return ctx


def _invocation_context(invocation_id: str) -> MagicMock:
    ctx = MagicMock()
    ctx.invocation_id = invocation_id
    return ctx


class TestUsageToolCallBudget:
    """Per-invocation tool budget (before_tool_callback)."""

    @pytest.mark.asyncio
    async def test_before_tool_no_enforcement_when_limit_zero(self):
        """With limit 0, every before_tool call is allowed."""
        settings = MagicMock(max_tool_calls_per_invocation=0)
        tool = MagicMock()
        tool.name = "t"
        tc = _tool_context("inv-a")
        with patch("lightspeed_agent.api.a2a.usage_plugin.get_settings", return_value=settings):
            plugin = usage_plugin.UsageTrackingPlugin()
            for _ in range(5):
                assert await plugin.before_tool_callback(
                    tool=tool, tool_args={}, tool_context=tc
                ) is None

    @pytest.mark.asyncio
    async def test_before_tool_blocks_after_limit(self):
        """Allow exactly N tool starts, then return a short-circuit error dict."""
        settings = MagicMock(max_tool_calls_per_invocation=2)
        tool = MagicMock()
        tool.name = "t"
        tc = _tool_context("inv-limit")
        with patch("lightspeed_agent.api.a2a.usage_plugin.get_settings", return_value=settings):
            plugin = usage_plugin.UsageTrackingPlugin()
            kwargs = {"tool": tool, "tool_args": {}, "tool_context": tc}
            assert await plugin.before_tool_callback(**kwargs) is None
            assert await plugin.before_tool_callback(**kwargs) is None
            blocked = await plugin.before_tool_callback(**kwargs)
            assert blocked is not None
            assert blocked["code"] == usage_plugin._TOOL_LIMIT_CODE
            assert "Exceeded maximum of 2" in blocked["error"]

    @pytest.mark.asyncio
    async def test_after_run_clears_budget_for_next_run_same_plugin(self):
        """after_run_callback drops counters so a new run can use the budget again."""
        settings = MagicMock(max_tool_calls_per_invocation=1)
        tool = MagicMock()
        tool.name = "t"
        tc = _tool_context("inv-reset")
        inv = _invocation_context("inv-reset")
        with patch("lightspeed_agent.api.a2a.usage_plugin.get_settings", return_value=settings):
            plugin = usage_plugin.UsageTrackingPlugin()
            kwargs = {"tool": tool, "tool_args": {}, "tool_context": tc}
            assert await plugin.before_tool_callback(**kwargs) is None
            blocked = await plugin.before_tool_callback(**kwargs)
            assert blocked is not None
            await plugin.after_run_callback(invocation_context=inv)
            assert await plugin.before_tool_callback(**kwargs) is None

