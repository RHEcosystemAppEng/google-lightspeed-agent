"""Aggregation tool for counting resources via MCP tools."""

import json
import logging
import threading
from typing import Any

from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.mcp_tool.mcp_session_manager import (
    MCPSessionManager,
    SseConnectionParams,
    StdioConnectionParams,
    StreamableHTTPConnectionParams,
)
from google.adk.tools.tool_context import ToolContext

from lightspeed_agent.tools.mcp_config import MCPServerConfig
from lightspeed_agent.tools.mcp_headers import create_mcp_header_provider

logger = logging.getLogger(__name__)

# Map of MCP tool names to the response field paths for extracting total count.
# JSON:API style tools return meta.total_items, others return meta.count or total.
TOOL_TOTAL_PATHS: dict[str, tuple[str, ...]] = {
    # Vulnerability tools (JSON:API)
    "vulnerability__get_cves": ("meta", "total_items"),
    "vulnerability__get_cve_systems": ("meta", "total_items"),
    "vulnerability__get_system_cves": ("meta", "total_items"),
    "vulnerability__get_systems": ("meta", "total_items"),
    # Inventory tools
    "inventory__list_hosts": ("total",),
    # Advisor tools
    "advisor__get_active_rules": ("meta", "count"),
    "advisor__get_hosts_hitting_a_rule": ("meta", "count"),
    "advisor__get_hosts_details_hitting_a_rule": ("meta", "count"),
    "advisor__get_rule_by_text_search": ("meta", "count"),
    # Content sources
    "content-sources__list_repositories": ("meta", "count"),
    # Image builder
    "image-builder__get_blueprints": ("meta", "count"),
    "image-builder__get_composes": ("meta", "count"),
    # RHSM
    "rhsm__get_activation_keys": ("meta", "count"),
}

COUNTABLE_TOOLS = set(TOOL_TOTAL_PATHS.keys())

_session_manager: MCPSessionManager | None = None
_session_manager_lock = threading.Lock()


def _get_session_manager() -> MCPSessionManager:
    """Lazily initialize the MCP session manager (thread-safe)."""
    global _session_manager  # noqa: PLW0603
    if _session_manager is not None:
        return _session_manager
    with _session_manager_lock:
        if _session_manager is not None:
            return _session_manager
        config = MCPServerConfig.from_settings()
        conn_params: (
            StdioConnectionParams
            | SseConnectionParams
            | StreamableHTTPConnectionParams
        )
        if config.transport_mode == "stdio":
            from mcp import StdioServerParameters

            server_params = StdioServerParameters(
                command=config.get_stdio_command(),
                args=config.get_stdio_args(),
            )
            conn_params = StdioConnectionParams(server_params=server_params)
        elif config.transport_mode == "sse":
            conn_params = SseConnectionParams(
                url=f"{config.server_url}/sse",
            )
        elif config.transport_mode == "http":
            conn_params = StreamableHTTPConnectionParams(
                url=config.get_http_url(),
            )
        else:
            raise ValueError(
                f"Unsupported transport mode: {config.transport_mode}"
            )
        _session_manager = MCPSessionManager(
            connection_params=conn_params,
        )
    return _session_manager


def _extract_total(
    response_data: dict[str, Any], path: tuple[str, ...]
) -> int | None:
    """Extract total count from response data following the given path."""
    current: Any = response_data
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return int(current) if current is not None else None


async def count_resources(
    tool_context: ToolContext,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Count total resources matching filters by calling an MCP tool with minimal data fetch.

    Use this tool when the user asks "how many" questions about their Red Hat
    infrastructure. Instead of fetching all pages of data, this tool makes a
    single API call with limit=1 to efficiently retrieve just the total count
    from response metadata.

    Supports counting across all resource types: CVEs, hosts/systems, advisor
    rules/recommendations, repositories, blueprints, composes, and activation
    keys.

    Args:
        tool_context: ADK tool context (injected automatically).
        tool_name: The MCP tool to call (e.g., "vulnerability__get_cves",
            "inventory__list_hosts"). Must be one of the supported countable
            tools.
        arguments: Optional filters to apply (e.g., {"severity": "Critical",
            "known_exploit": true}). The tool's normal filter parameters are
            supported.

    Returns:
        A dict with the count result: {"total": N, "tool": "...", "filters": {...}}
        Or an error dict if the tool is not supported or the call fails.
    """
    if tool_name not in COUNTABLE_TOOLS:
        supported = sorted(COUNTABLE_TOOLS)
        return {
            "error": f"Tool '{tool_name}' is not supported for counting.",
            "supported_tools": supported,
        }

    call_args = dict(arguments) if arguments else {}
    call_args["limit"] = 1

    try:
        manager = _get_session_manager()
        header_provider = create_mcp_header_provider()
        headers = header_provider(tool_context)
        session = await manager.create_session(headers=headers)

        result = await session.call_tool(tool_name, call_args)

        if result.isError:
            error_text = ""
            if result.content:
                error_text = getattr(
                    result.content[0], "text", str(result.content[0])
                )
            logger.error(
                "MCP tool %s returned error: %s", tool_name, error_text
            )
            return {
                "error": f"MCP tool '{tool_name}' returned an error.",
                "details": error_text,
            }

        if not result.content:
            return {
                "error": f"MCP tool '{tool_name}' returned empty response.",
            }

        raw_text = getattr(result.content[0], "text", None)
        if raw_text is None:
            return {
                "error": (
                    f"MCP tool '{tool_name}' returned non-text response."
                ),
            }

        response_data = json.loads(raw_text)
        path = TOOL_TOTAL_PATHS[tool_name]
        total = _extract_total(response_data, path)

        if total is None:
            logger.warning(
                "Could not extract total from %s response at path %s",
                tool_name,
                path,
            )
            return {
                "error": (
                    f"Could not extract total count from"
                    f" '{tool_name}' response."
                ),
                "path_tried": list(path),
            }

        filters = (
            {k: v for k, v in call_args.items() if k != "limit"}
            if arguments
            else {}
        )
        return {"total": total, "tool": tool_name, "filters": filters}

    except json.JSONDecodeError as exc:
        logger.error(
            "Failed to parse JSON from %s: %s", tool_name, exc
        )
        return {
            "error": (
                f"Failed to parse response from '{tool_name}' as JSON."
            ),
        }
    except Exception as exc:
        logger.error(
            "Error calling MCP tool %s: %s",
            tool_name,
            exc,
            exc_info=True,
        )
        return {
            "error": f"Failed to call MCP tool '{tool_name}': {exc}",
        }


def create_aggregation_tool() -> FunctionTool:
    """Create the aggregation FunctionTool for the agent."""
    return FunctionTool(func=count_resources)
