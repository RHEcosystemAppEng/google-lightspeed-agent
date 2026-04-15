"""Response formatter plugin.

Injects the first-response legal notice at the application layer so
the LLM does not need to track conversation state or remember to
include verbatim boilerplate.  The notice is prepended to the first
final text response in each session.
"""

import logging

from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event
from google.adk.plugins.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

FIRST_RESPONSE_NOTICE = (
    "You are interacting with the Red Hat Lightspeed Agent, which can answer questions "
    "about your Red Hat account, subscription, system configuration, and related details. "
    "This feature uses AI technology. Interactions may be used to improve Red Hat's "
    "products or services.\n\n"
    "Always review AI-generated content prior to use.\n\n"
)


class ResponseFormatterPlugin(BasePlugin):
    """ADK plugin that injects the first-response legal notice."""

    def __init__(self) -> None:
        super().__init__(name="response_formatter")

    async def on_event_callback(
        self, *, invocation_context: InvocationContext, event: Event
    ) -> Event | None:
        """Prepend the first-response notice on the first agent text response."""
        if not event.is_final_response():
            return None

        if not event.content or not event.content.parts:
            return None

        # Find the first text part
        first_text_idx = None
        for i, part in enumerate(event.content.parts):
            if part.text:
                first_text_idx = i
                break

        if first_text_idx is None:
            return None

        if self._is_first_agent_response(invocation_context.session.events):
            event.content.parts[first_text_idx].text = (
                FIRST_RESPONSE_NOTICE + event.content.parts[first_text_idx].text
            )
            logger.debug("Prepended first-response notice to agent response")

        return event

    @staticmethod
    def _is_first_agent_response(session_events: list[Event]) -> bool:
        """Return True when no prior agent event in the session contains text."""
        for ev in session_events:
            if ev.author == "user":
                continue
            if ev.content and ev.content.parts:
                for part in ev.content.parts:
                    if part.text:
                        return False
        return True
