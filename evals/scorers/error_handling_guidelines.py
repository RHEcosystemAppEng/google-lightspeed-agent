"""Error handling guidelines scorer for Lightspeed Agent responses.

Checks that the agent handles errors gracefully with no raw errors,
honest failure acknowledgment, helpful alternatives, and professional tone.
"""

from __future__ import annotations

from mlflow.genai.scorers import Guidelines


def ErrorHandlingGuidelines(model: str | None = None) -> Guidelines:  # noqa: N802
    """Pre-configured error-handling scorer for the Lightspeed Agent.

    Checks that the agent handles errors gracefully: no raw errors,
    honest failure acknowledgment, helpful alternatives, professional tone.

    Args:
        model: LLM model to use for judging (e.g. "openai:/Qwen/Qwen3-14B")

    Returns:
        Configured Guidelines scorer instance
    """
    return Guidelines(
        name="error_handling",
        model=model,
        description=(
            "LLM-as-judge error handling check for Lightspeed Agent responses. "
            "An LLM judge evaluates whether the agent handles errors and limitations gracefully, "
            "following 4 guidelines: "
            "(1) No raw errors — must not expose stack traces, HTTP codes, or exception messages; "
            "(2) Honest failures — must acknowledge limitations rather than hallucinating data; "
            "(3) Helpful alternatives — should suggest next steps when a request cannot be fulfilled; "
            "(4) Professional tone — must stay helpful even when reporting errors. "
            "Score: 'yes' = all guidelines followed, 'no' = at least one violated. "
            "Judge model provides a rationale explaining the verdict."
        ),
        guidelines=[
            (
                "If the agent encounters an error or cannot fulfill the request, "
                "it MUST NOT expose raw error messages, stack traces, HTTP status "
                "codes, or internal exception details to the user."
            ),
            (
                "When the agent cannot answer a question or a tool call fails, "
                "it MUST honestly acknowledge the limitation rather than "
                "fabricating or guessing an answer. Hallucinating data is worse "
                "than admitting uncertainty."
            ),
            (
                "When a request cannot be fulfilled, the agent SHOULD suggest "
                "alternative approaches, rephrasings, or next steps the user "
                "can take, rather than just saying 'I can't do that'."
            ),
            (
                "The agent MUST maintain a helpful and professional tone even "
                "when reporting errors or limitations. Responses should not be "
                "dismissive, overly terse, or apologetic to the point of being "
                "unhelpful."
            ),
        ],
    )
