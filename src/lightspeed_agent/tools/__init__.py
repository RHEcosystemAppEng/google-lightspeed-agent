"""Tools module for MCP integration with Red Hat Insights."""

from lightspeed_agent.tools.a2a_skills import (
    ALL_SKILLS,
    READ_ONLY_SKILLS,
    Skill,
    get_skills_for_agent_card,
)
from lightspeed_agent.tools.aggregation import create_aggregation_tool
from lightspeed_agent.tools.insights_tools import (
    ALL_INSIGHTS_TOOLS,
    READ_ONLY_TOOLS,
    create_insights_toolset,
    get_insights_tools_for_cloud_run,
)
from lightspeed_agent.tools.mcp_config import MCPServerConfig
from lightspeed_agent.tools.mcp_headers import create_mcp_header_provider

__all__ = [
    # MCP Config
    "MCPServerConfig",
    # MCP Headers
    "create_mcp_header_provider",
    # Toolset creation
    "create_aggregation_tool",
    "create_insights_toolset",
    "get_insights_tools_for_cloud_run",
    # Tool lists
    "ALL_INSIGHTS_TOOLS",
    "READ_ONLY_TOOLS",
    # Skills
    "Skill",
    "ALL_SKILLS",
    "READ_ONLY_SKILLS",
    "get_skills_for_agent_card",
]
