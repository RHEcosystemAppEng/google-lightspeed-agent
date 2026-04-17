"""Tests for the empty part filter plugin."""

import logging
from unittest.mock import MagicMock

import pytest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from lightspeed_agent.api.a2a.empty_part_filter_plugin import (
    _FALLBACK_TEXT,
    EmptyPartFilterPlugin,
    _is_empty_part,
)

# ---------------------------------------------------------------------------
# _is_empty_part unit tests
# ---------------------------------------------------------------------------


class TestIsEmptyPart:
    """Unit tests for the _is_empty_part helper."""

    def test_empty_text_no_other_fields(self):
        """A Part with text='' and nothing else is empty."""
        part = types.Part(text="")
        assert _is_empty_part(part) is True

    def test_none_text_is_not_empty(self):
        """A Part with text=None is not considered empty (different semantics)."""
        part = types.Part(text=None)
        assert _is_empty_part(part) is False

    def test_non_empty_text_is_not_empty(self):
        part = types.Part(text="hello")
        assert _is_empty_part(part) is False

    def test_empty_text_with_thought_preserved(self):
        """Thinking parts should be kept even when text is empty."""
        part = types.Part(text="", thought=True)
        assert _is_empty_part(part) is False

    def test_empty_text_with_thought_signature_preserved(self):
        """Parts with a thought_signature should be kept."""
        part = types.Part(text="", thought_signature=b"\x00\x01")
        assert _is_empty_part(part) is False

    def test_empty_text_with_function_call_preserved(self):
        part = types.Part(
            text="",
            function_call=types.FunctionCall(name="foo", args={}),
        )
        assert _is_empty_part(part) is False

    def test_empty_text_with_inline_data_preserved(self):
        part = types.Part(
            text="",
            inline_data=types.Blob(mime_type="text/plain", data=b"data"),
        )
        assert _is_empty_part(part) is False


# ---------------------------------------------------------------------------
# EmptyPartFilterPlugin tests
# ---------------------------------------------------------------------------


class TestEmptyPartFilterPlugin:
    """Tests for EmptyPartFilterPlugin.after_model_callback."""

    @pytest.mark.asyncio
    async def test_no_content_returns_none(self):
        """Responses without content should pass through."""
        plugin = EmptyPartFilterPlugin()
        response = LlmResponse(content=None)
        result = await plugin.after_model_callback(
            callback_context=MagicMock(),
            llm_response=response,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_parts_list_returns_none(self):
        """Responses with an empty parts list should pass through."""
        plugin = EmptyPartFilterPlugin()
        response = LlmResponse(
            content=types.Content(role="model", parts=[]),
        )
        result = await plugin.after_model_callback(
            callback_context=MagicMock(),
            llm_response=response,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_normal_text_passes_through(self):
        """A response with real text should not be modified."""
        plugin = EmptyPartFilterPlugin()
        response = LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text="Hello!")],
            ),
        )
        result = await plugin.after_model_callback(
            callback_context=MagicMock(),
            llm_response=response,
        )
        assert result is None
        assert len(response.content.parts) == 1
        assert response.content.parts[0].text == "Hello!"

    @pytest.mark.asyncio
    async def test_strips_empty_parts_keeps_real_ones(self):
        """Empty parts should be removed while real parts survive."""
        plugin = EmptyPartFilterPlugin()
        response = LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(text=""),
                    types.Part(text="Real answer"),
                    types.Part(text=""),
                ],
            ),
        )
        result = await plugin.after_model_callback(
            callback_context=MagicMock(),
            llm_response=response,
        )
        # Returns None (mutation in place), but parts should be filtered.
        assert result is None
        assert len(response.content.parts) == 1
        assert response.content.parts[0].text == "Real answer"

    @pytest.mark.asyncio
    async def test_all_empty_parts_returns_fallback(self):
        """When every part is empty, a fallback response should be returned."""
        plugin = EmptyPartFilterPlugin()
        response = LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text=""), types.Part(text="")],
            ),
        )
        result = await plugin.after_model_callback(
            callback_context=MagicMock(),
            llm_response=response,
        )
        assert result is not None
        assert result.content is not None
        assert len(result.content.parts) == 1
        assert result.content.parts[0].text == _FALLBACK_TEXT

    @pytest.mark.asyncio
    async def test_thought_parts_not_stripped(self):
        """Thinking parts with empty text should survive."""
        plugin = EmptyPartFilterPlugin()
        response = LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text="", thought=True)],
            ),
        )
        result = await plugin.after_model_callback(
            callback_context=MagicMock(),
            llm_response=response,
        )
        assert result is None
        assert len(response.content.parts) == 1

    @pytest.mark.asyncio
    async def test_warning_logged_on_strip(self, caplog):
        """A warning should be logged when parts are stripped."""
        plugin = EmptyPartFilterPlugin()
        response = LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(text=""),
                    types.Part(text="kept"),
                ],
            ),
        )
        with caplog.at_level(logging.WARNING):
            await plugin.after_model_callback(
                callback_context=MagicMock(),
                llm_response=response,
            )

        assert any("Stripped 1 empty part" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_warning_logged_on_full_fallback(self, caplog):
        """A warning should be logged when the entire response is replaced."""
        plugin = EmptyPartFilterPlugin()
        response = LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text="")],
            ),
        )
        with caplog.at_level(logging.WARNING):
            await plugin.after_model_callback(
                callback_context=MagicMock(),
                llm_response=response,
            )

        assert any("only empty parts" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_none_llm_response_returns_none(self):
        """A None response should pass through gracefully."""
        plugin = EmptyPartFilterPlugin()
        result = await plugin.after_model_callback(
            callback_context=MagicMock(),
            llm_response=None,
        )
        assert result is None
