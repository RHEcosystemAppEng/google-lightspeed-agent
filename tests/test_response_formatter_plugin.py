"""Tests for the response formatter plugin."""

from unittest.mock import MagicMock

import pytest
from google.genai import types

from lightspeed_agent.api.a2a.response_formatter_plugin import (
    FIRST_RESPONSE_NOTICE,
    ResponseFormatterPlugin,
)


def _make_event(*, text: str = "Hello", is_final: bool = True, author: str = "agent"):
    """Build a minimal mock Event with text content."""
    part = types.Part(text=text)
    content = types.Content(parts=[part], role="model")

    event = MagicMock()
    event.content = content
    event.author = author
    event.is_final_response.return_value = is_final
    return event


def _make_invocation_context(session_events: list | None = None):
    """Build a mock InvocationContext with a session containing the given events."""
    ctx = MagicMock()
    ctx.session.events = session_events or []
    return ctx


class TestResponseFormatterPluginFirstNotice:
    """Tests for first-response notice injection."""

    @pytest.mark.asyncio
    async def test_prepends_notice_on_first_response(self):
        """The notice should be prepended when no prior agent text exists."""
        plugin = ResponseFormatterPlugin()
        event = _make_event(text="Here is your answer.")
        ctx = _make_invocation_context(session_events=[])

        result = await plugin.on_event_callback(
            invocation_context=ctx, event=event
        )

        assert result is event
        assert result.content.parts[0].text.startswith(FIRST_RESPONSE_NOTICE)
        assert result.content.parts[0].text.endswith("Here is your answer.")

    @pytest.mark.asyncio
    async def test_skips_notice_on_subsequent_response(self):
        """The notice should NOT be prepended when prior agent text exists."""
        plugin = ResponseFormatterPlugin()
        event = _make_event(text="Follow-up answer.")

        prior_event = _make_event(text="Previous answer.", author="agent")
        ctx = _make_invocation_context(session_events=[prior_event])

        result = await plugin.on_event_callback(
            invocation_context=ctx, event=event
        )

        assert result is event
        assert result.content.parts[0].text == "Follow-up answer."

    @pytest.mark.asyncio
    async def test_skips_non_final_events(self):
        """Non-final events (function calls, partials) should not be modified."""
        plugin = ResponseFormatterPlugin()
        event = _make_event(text="partial text", is_final=False)
        ctx = _make_invocation_context()

        result = await plugin.on_event_callback(
            invocation_context=ctx, event=event
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_skips_events_without_content(self):
        """Events with no content should not be modified."""
        plugin = ResponseFormatterPlugin()
        event = MagicMock()
        event.is_final_response.return_value = True
        event.content = None
        ctx = _make_invocation_context()

        result = await plugin.on_event_callback(
            invocation_context=ctx, event=event
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_skips_events_without_text_parts(self):
        """Events with parts but no text (e.g., function calls) should pass through."""
        plugin = ResponseFormatterPlugin()
        part = types.Part(function_call=types.FunctionCall(name="tool", args={}))
        content = types.Content(parts=[part], role="model")

        event = MagicMock()
        event.is_final_response.return_value = True
        event.content = content
        ctx = _make_invocation_context()

        result = await plugin.on_event_callback(
            invocation_context=ctx, event=event
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_prior_user_events_do_not_count(self):
        """User-authored events should not prevent the first-response notice."""
        plugin = ResponseFormatterPlugin()
        event = _make_event(text="Agent response.")

        user_event = _make_event(text="User question.", author="user")
        ctx = _make_invocation_context(session_events=[user_event])

        result = await plugin.on_event_callback(
            invocation_context=ctx, event=event
        )

        assert result is event
        assert result.content.parts[0].text.startswith(FIRST_RESPONSE_NOTICE)

    @pytest.mark.asyncio
    async def test_prior_agent_events_without_text_do_not_count(self):
        """Agent events without text content should not prevent the notice."""
        plugin = ResponseFormatterPlugin()
        event = _make_event(text="Agent response.")

        # Prior agent event with function call only (no text)
        prior_event = MagicMock()
        prior_event.author = "agent"
        prior_event.content = types.Content(
            parts=[types.Part(function_call=types.FunctionCall(name="t", args={}))],
            role="model",
        )
        ctx = _make_invocation_context(session_events=[prior_event])

        result = await plugin.on_event_callback(
            invocation_context=ctx, event=event
        )

        assert result is event
        assert result.content.parts[0].text.startswith(FIRST_RESPONSE_NOTICE)

    @pytest.mark.asyncio
    async def test_multi_part_event_prepends_to_first_text(self):
        """When an event has multiple parts, notice goes before the first text part."""
        plugin = ResponseFormatterPlugin()
        parts = [
            types.Part(function_call=types.FunctionCall(name="tool", args={})),
            types.Part(text="Actual answer."),
        ]
        content = types.Content(parts=parts, role="model")

        event = MagicMock()
        event.is_final_response.return_value = True
        event.content = content
        ctx = _make_invocation_context(session_events=[])

        result = await plugin.on_event_callback(
            invocation_context=ctx, event=event
        )

        assert result is event
        # First part (function call) should be untouched
        assert result.content.parts[0].function_call is not None
        # Second part (text) should have the notice prepended
        assert result.content.parts[1].text.startswith(FIRST_RESPONSE_NOTICE)
        assert result.content.parts[1].text.endswith("Actual answer.")
