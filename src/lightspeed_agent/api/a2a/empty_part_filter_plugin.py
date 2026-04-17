"""Empty part filter plugin.

Works around a Google ADK bug (https://github.com/google/adk-python/issues/5341)
where ``Part(text='')`` falls through the A2A part converter
(``convert_genai_part_to_a2a_part``) because ``if part.text:`` treats
empty strings as falsy, producing the warning::

    Cannot convert unsupported part for Google GenAI part: …

When these empty parts are the *only* content in a model response the
A2A message ends up with zero parts and the client sees "broken
thinking" with no actual answer.

This plugin intercepts the LLM response in ``after_model_callback``,
strips parts that are genuinely empty (no text, no thought, no
function call, no data — nothing), and replaces an entirely-empty
response with a user-visible fallback so the conversation can
continue.
"""

import logging

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.genai import types

logger = logging.getLogger(__name__)

_FALLBACK_TEXT = (
    "I encountered a temporary issue while generating my response. "
    "Please try sending your message again."
)


def _is_empty_part(part: types.Part) -> bool:
    """Return ``True`` if *part* carries no usable content.

    A part is considered empty when ``text`` is set to an empty string
    and every other content field is ``None``.  Parts that participate
    in the thinking chain (``thought`` / ``thought_signature``) are
    preserved even when their text is empty.

    Uses ``model_dump(exclude_none=True)`` so the check stays correct
    automatically if the SDK adds new part fields in the future.
    """
    if part.text is None or part.text != "":
        return False

    # Part has text='' — keep it if it's part of a thought chain.
    if part.thought is not None or part.thought_signature is not None:
        return False

    # Check whether any other content field is set.  Using model_dump
    # so the check stays correct automatically if the SDK adds new
    # part fields in the future.
    remaining = part.model_dump(
        exclude={"text", "thought", "thought_signature"},
        exclude_none=True,
    )
    return len(remaining) == 0


class EmptyPartFilterPlugin(BasePlugin):
    """ADK plugin that strips empty ``Part(text='')`` from model responses.

    When *all* parts in a response are empty, replaces the response
    with a short fallback message so the user is not left staring at
    a broken thinking indicator.
    """

    def __init__(self) -> None:
        super().__init__(name="empty_part_filter")

    async def after_model_callback(
        self,
        *,
        callback_context: CallbackContext,
        llm_response: LlmResponse,
    ) -> LlmResponse | None:
        if (
            not llm_response
            or not llm_response.content
            or not llm_response.content.parts
        ):
            return None

        original_count = len(llm_response.content.parts)
        filtered = [p for p in llm_response.content.parts if not _is_empty_part(p)]
        removed = original_count - len(filtered)

        if removed == 0:
            return None

        logger.warning(
            "Stripped %d empty part(s) from model response (%d parts remaining)",
            removed,
            len(filtered),
        )

        if filtered:
            # Some parts survived — just drop the empty ones.
            llm_response.content.parts = filtered
            return None

        # Every part was empty → replace with a fallback so the user
        # gets an actual response instead of broken thinking.
        logger.warning(
            "Model response contained only empty parts; "
            "replacing with fallback message"
        )
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text=_FALLBACK_TEXT)],
            ),
        )
