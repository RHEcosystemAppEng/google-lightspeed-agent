"""Core agent definition using Google ADK with Gemini 2.5 Flash."""

import logging
import os
import pathlib
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.planners import PlanReActPlanner
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset

from lightspeed_agent.config import get_settings
from lightspeed_agent.core.gemini_retry import http_retry_options_from_settings

logger = logging.getLogger(__name__)

# Base agent instruction — identity and priority definitions.
# Detailed behavioral rules are loaded as ADK AI Skills from SKILL.md files.
AGENT_INSTRUCTION = """You are the Red Hat Lightspeed Agent for Google Cloud, \
an AI assistant specialized in helping users manage their Red Hat infrastructure. \
You have access to Red Hat Insights tools spanning Advisor, Inventory, Vulnerability, \
Planning, Subscription Management, Access Management, and Content Sources.

## Instruction Priority
Sections are labeled by priority:
- **[STRICT]** — Must always be followed. Violations are never acceptable.
- **[PREFERRED]** — Follow unless there is a clear, context-specific reason not to.
- **[GUIDANCE]** — Style and formatting preferences; use good judgment.
"""


def _load_skills_from_dir(directory: pathlib.Path) -> dict[str, Any]:
    """Load skills from a directory, returning a dict keyed by skill name."""
    if not directory.is_dir():
        return {}
    skills = {}
    for d in sorted(directory.iterdir()):
        if d.is_dir() and (d / "SKILL.md").exists():
            skill = load_skill_from_dir(d)
            skills[skill.name] = skill
    return skills


def _load_skills(skills_dir: str | None) -> SkillToolset | None:
    """Load ADK AI Skills: bundled defaults + optional external overlay.

    Always loads bundled skills from core/skills/. When skills_dir is set,
    also loads from that directory — external skills with the same name
    override the bundled version.
    """
    bundled_dir = pathlib.Path(__file__).parent / "skills"
    skills = _load_skills_from_dir(bundled_dir)
    if skills:
        logger.info("Loaded %d bundled skills from %s", len(skills), bundled_dir)

    if skills_dir:
        external_dir = pathlib.Path(skills_dir)
        external = _load_skills_from_dir(external_dir)
        if external:
            overridden = set(skills.keys()) & set(external.keys())
            if overridden:
                logger.info("External skills overriding bundled: %s", ", ".join(sorted(overridden)))
            skills.update(external)
            logger.info(
                "Loaded %d external skills from %s (%d total)",
                len(external),
                external_dir,
                len(skills),
            )

    if not skills:
        logger.info("No skills found")
        return None
    return SkillToolset(skills=list(skills.values()))


def _setup_environment() -> None:
    """Set up environment variables for Google ADK."""
    settings = get_settings()

    # Configure Vertex AI or Google AI Studio
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = str(settings.google_genai_use_vertexai).upper()

    if settings.google_genai_use_vertexai:
        if settings.google_cloud_project:
            os.environ["GOOGLE_CLOUD_PROJECT"] = settings.google_cloud_project
        os.environ["GOOGLE_CLOUD_LOCATION"] = settings.google_cloud_location
    elif settings.google_api_key:
        os.environ["GOOGLE_API_KEY"] = settings.google_api_key


def create_agent() -> LlmAgent:
    """Create the Lightspeed Agent with MCP tools.

    This function creates an LlmAgent with the Red Hat Lightspeed MCP toolset.
    The caller's JWT token is forwarded to the MCP server via a header_provider
    so the MCP server can authenticate on behalf of the calling user.

    Returns:
        Configured LlmAgent instance.
    """
    _setup_environment()
    settings = get_settings()

    retry_opts = http_retry_options_from_settings(settings)
    gemini_model = Gemini(
        model=settings.gemini_model,
        retry_options=retry_opts,
    )
    logger.info(
        "Gemini HTTP retry: attempts=%s initial_delay=%ss max_delay=%ss exp_base=%s jitter=%s",
        settings.gemini_http_retry_attempts,
        settings.gemini_http_retry_initial_delay,
        settings.gemini_http_retry_max_delay,
        settings.gemini_http_retry_exp_base,
        settings.gemini_http_retry_jitter,
    )

    tools: list[Any] = []

    try:
        from lightspeed_agent.tools import READ_ONLY_TOOLS, create_insights_toolset

        logger.info(
            f"Creating MCP toolset with transport={settings.mcp_transport_mode}, "
            f"url={settings.mcp_server_url}"
        )
        tool_filter = READ_ONLY_TOOLS if settings.mcp_read_only else None
        mcp_toolset = create_insights_toolset(
            tool_filter=tool_filter,
        )
        tools = [mcp_toolset]
        logger.info(
            f"Created agent with MCP tools (read_only={settings.mcp_read_only}, "
            f"model={settings.gemini_model})"
        )
    except Exception as e:
        logger.warning(f"Failed to create MCP toolset: {e}", exc_info=True)
        logger.info("Agent created without MCP tools")

    skill_toolset = _load_skills(settings.skills_dir)
    if skill_toolset:
        tools.append(skill_toolset)

    return LlmAgent(
        name=settings.agent_name,
        model=gemini_model,
        description=settings.agent_description,
        static_instruction=AGENT_INSTRUCTION,
        tools=tools,
        planner=PlanReActPlanner(),
    )


# Root agent instance for ADK CLI compatibility
root_agent = create_agent()
