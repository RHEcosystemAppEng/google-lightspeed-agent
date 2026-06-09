"""MCP response integrity fingerprinting plugin.

Computes and logs a SHA-256 fingerprint of every MCP tool result,
enabling forensic tracing and post-incident analysis of tool output.
Each log entry includes the tool name, request ID, audit context,
fingerprint, and result size for correlation.

Note: this plugin provides an auditable trail for forensic analysis,
not real-time authenticity verification.  The ``default=str``
serialisation is not stable across Python versions for non-JSON-native
types, so fingerprints of results containing such types should be
treated as best-effort.
"""

import hashlib
import json
import logging
from typing import Any

from google.adk.plugins.base_plugin import BasePlugin
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from lightspeed_agent.auth.middleware import (
    get_request_id,
    get_request_order_id,
    get_request_org_id,
    get_request_user_id,
)

logger = logging.getLogger(__name__)


class IntegrityFingerprintPlugin(BasePlugin):
    """ADK plugin that logs SHA-256 fingerprints of MCP tool results."""

    def __init__(self) -> None:
        super().__init__(name="integrity_fingerprint")

    async def after_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        result: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Compute and log a SHA-256 fingerprint of the tool result."""
        serialization = "json"
        try:
            serialized = json.dumps(result, sort_keys=True, default=str)
        except (TypeError, ValueError):
            serialized = str(result)
            serialization = "fallback"
            logger.warning(
                "JSON serialization failed for tool result; "
                "falling back to str() — fingerprint may not be reproducible"
            )

        fingerprint = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        tool_name = getattr(tool, "name", type(tool).__name__)
        request_id = get_request_id()

        logger.info(
            "MCP result fingerprint "
            "(event_type=mcp_result_fingerprint, tool=%s, request_id=%s, "
            "user_id=%s, org_id=%s, order_id=%s, "
            "fingerprint=%s, length=%d, serialization=%s)",
            tool_name,
            request_id,
            get_request_user_id(),
            get_request_org_id(),
            get_request_order_id(),
            fingerprint,
            len(serialized),
            serialization,
        )

        return None
