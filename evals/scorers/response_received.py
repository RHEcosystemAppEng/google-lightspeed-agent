"""Response validation scorer.

Validates that the agent returned a usable response before running
expensive LLM judges.
"""

from __future__ import annotations

from mlflow.genai.scorers import Scorer


class ResponseReceived(Scorer):
    """Validate that the agent returned a usable response.

    Pre-check before running expensive LLM judges. Fails if the response
    is empty, contains an error marker, or is too short to be meaningful.
    """

    name: str = "response_received"

    def __call__(self, *, inputs, outputs, expectations, **kwargs):
        response = outputs if isinstance(outputs, str) else str(outputs)
        if not response or not response.strip():
            return 0.0
        stripped = response.strip()
        if stripped.startswith("[ERROR]") or stripped.startswith("ERROR:"):
            return 0.0
        if len(stripped) < 10:
            return 0.0
        return 1.0
