"""Tests for the aggregation/counting tool.

Covers:
- _extract_total helper (path traversal on nested dicts)
- count_resources function (mocked MCP session, all resource types)
- Error handling (unsupported tool, MCP failures, bad responses)
- create_aggregation_tool factory
- COUNTABLE_TOOLS / TOOL_TOTAL_PATHS consistency
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from lightspeed_agent.tools.aggregation import (
    COUNTABLE_TOOLS,
    TOOL_TOTAL_PATHS,
    _extract_total,
    count_resources,
    create_aggregation_tool,
)
from mcp.types import CallToolResult, TextContent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mcp_response(json_data: dict) -> CallToolResult:
    """Build a mock CallToolResult wrapping the given JSON payload."""
    content = TextContent(type="text", text=json.dumps(json_data))
    return CallToolResult(content=[content])


def _mock_session_manager(response: CallToolResult) -> tuple[AsyncMock, AsyncMock]:
    """Return (mock_session_manager, mock_session) wired to return *response*."""
    mock_session = AsyncMock()
    mock_session.call_tool.return_value = response
    mock_sm = AsyncMock()
    mock_sm.create_session.return_value = mock_session
    return mock_sm, mock_session


# ---------------------------------------------------------------------------
# 1. _extract_total helper tests
# ---------------------------------------------------------------------------

class TestExtractTotal:
    """Tests for the _extract_total path-traversal helper."""

    def test_jsonapi_meta_total_items(self):
        """Extract from JSON:API path ('meta', 'total_items')."""
        data = {"data": [], "meta": {"total_items": 342}, "links": {}}
        assert _extract_total(data, ("meta", "total_items")) == 342

    def test_flat_total(self):
        """Extract from flat path ('total',)."""
        data = {"total": 150, "count": 50, "page": 1, "results": []}
        assert _extract_total(data, ("total",)) == 150

    def test_nested_meta_count(self):
        """Extract from nested path ('meta', 'count')."""
        data = {"meta": {"count": 87}, "links": {}, "data": []}
        assert _extract_total(data, ("meta", "count")) == 87

    def test_missing_key_at_first_level(self):
        """Missing key at the first level returns None."""
        data = {"data": []}
        assert _extract_total(data, ("meta", "total_items")) is None

    def test_missing_key_at_second_level(self):
        """Missing key at a deeper level returns None."""
        data = {"meta": {"other_field": 10}}
        assert _extract_total(data, ("meta", "total_items")) is None

    def test_none_value(self):
        """None value at the target key returns None."""
        data = {"meta": {"total_items": None}}
        assert _extract_total(data, ("meta", "total_items")) is None

    def test_empty_dict(self):
        """Empty dict returns None for any path."""
        assert _extract_total({}, ("meta", "total_items")) is None

    def test_non_dict_input(self):
        """Non-dict input returns None."""
        assert _extract_total("not-a-dict", ("meta",)) is None
        assert _extract_total(42, ("total",)) is None
        assert _extract_total(None, ("total",)) is None
        assert _extract_total([], ("total",)) is None

    def test_zero_is_valid(self):
        """A total of 0 is a legitimate count, not None."""
        data = {"meta": {"total_items": 0}}
        assert _extract_total(data, ("meta", "total_items")) == 0


# ---------------------------------------------------------------------------
# 2. count_resources function tests (mocked MCP session)
# ---------------------------------------------------------------------------

class TestCountResources:
    """Tests for count_resources across all supported resource types."""

    # -- Vulnerability tools ------------------------------------------------

    @patch("lightspeed_agent.tools.aggregation._get_session_manager")
    @patch("lightspeed_agent.tools.aggregation.create_mcp_header_provider")
    async def test_count_vulnerability_cves(self, mock_header_provider, mock_get_sm):
        """Vulnerability: get_cves with JSON:API response returns meta.total_items."""
        response = make_mcp_response(
            {"data": [], "meta": {"total_items": 342, "limit": 1, "offset": 0}, "links": {}}
        )
        mock_sm, _ = _mock_session_manager(response)
        mock_get_sm.return_value = mock_sm
        mock_header_provider.return_value = lambda ctx: {"Authorization": "Bearer test"}

        result = await count_resources(
            tool_context=MagicMock(),
            tool_name="vulnerability__get_cves",
        )
        assert result["total"] == 342

    @patch("lightspeed_agent.tools.aggregation._get_session_manager")
    @patch("lightspeed_agent.tools.aggregation.create_mcp_header_provider")
    async def test_count_vulnerability_cves_filtered(self, mock_header_provider, mock_get_sm):
        """Vulnerability: get_cves with severity filter returns correct count."""
        response = make_mcp_response(
            {"data": [], "meta": {"total_items": 18, "limit": 1, "offset": 0}, "links": {}}
        )
        mock_sm, mock_session = _mock_session_manager(response)
        mock_get_sm.return_value = mock_sm
        mock_header_provider.return_value = lambda ctx: {"Authorization": "Bearer test"}

        result = await count_resources(
            tool_context=MagicMock(),
            tool_name="vulnerability__get_cves",
            arguments={"severity": "Critical"},
        )
        assert result["total"] == 18
        # Verify limit=1 was injected
        call_args = mock_session.call_tool.call_args
        passed_args = call_args[1].get("arguments") or call_args[0][1]
        assert passed_args.get("limit") == 1

    @patch("lightspeed_agent.tools.aggregation._get_session_manager")
    @patch("lightspeed_agent.tools.aggregation.create_mcp_header_provider")
    async def test_count_vulnerability_system_cves(self, mock_header_provider, mock_get_sm):
        """Vulnerability: get_system_cves returns meta.total_items."""
        response = make_mcp_response(
            {"data": [], "meta": {"total_items": 55, "limit": 1, "offset": 0}, "links": {}}
        )
        mock_sm, _ = _mock_session_manager(response)
        mock_get_sm.return_value = mock_sm
        mock_header_provider.return_value = lambda ctx: {"Authorization": "Bearer test"}

        result = await count_resources(
            tool_context=MagicMock(),
            tool_name="vulnerability__get_system_cves",
        )
        assert result["total"] == 55

    # -- Inventory tools ----------------------------------------------------

    @patch("lightspeed_agent.tools.aggregation._get_session_manager")
    @patch("lightspeed_agent.tools.aggregation.create_mcp_header_provider")
    async def test_count_inventory_hosts(self, mock_header_provider, mock_get_sm):
        """Inventory: list_hosts returns top-level 'total'."""
        response = make_mcp_response(
            {"total": 150, "count": 1, "page": 1, "per_page": 1, "results": []}
        )
        mock_sm, _ = _mock_session_manager(response)
        mock_get_sm.return_value = mock_sm
        mock_header_provider.return_value = lambda ctx: {"Authorization": "Bearer test"}

        result = await count_resources(
            tool_context=MagicMock(),
            tool_name="inventory__list_hosts",
        )
        assert result["total"] == 150

    @patch("lightspeed_agent.tools.aggregation._get_session_manager")
    @patch("lightspeed_agent.tools.aggregation.create_mcp_header_provider")
    async def test_count_inventory_hosts_filtered(self, mock_header_provider, mock_get_sm):
        """Inventory: list_hosts with OS filter returns correct count."""
        response = make_mcp_response(
            {"total": 42, "count": 1, "page": 1, "per_page": 1, "results": []}
        )
        mock_sm, mock_session = _mock_session_manager(response)
        mock_get_sm.return_value = mock_sm
        mock_header_provider.return_value = lambda ctx: {"Authorization": "Bearer test"}

        result = await count_resources(
            tool_context=MagicMock(),
            tool_name="inventory__list_hosts",
            arguments={"operating_system": "RHEL 9"},
        )
        assert result["total"] == 42

    # -- Advisor tools ------------------------------------------------------

    @patch("lightspeed_agent.tools.aggregation._get_session_manager")
    @patch("lightspeed_agent.tools.aggregation.create_mcp_header_provider")
    async def test_count_advisor_active_rules(self, mock_header_provider, mock_get_sm):
        """Advisor: get_active_rules returns meta.count."""
        response = make_mcp_response(
            {"meta": {"count": 87}, "links": {}, "data": []}
        )
        mock_sm, _ = _mock_session_manager(response)
        mock_get_sm.return_value = mock_sm
        mock_header_provider.return_value = lambda ctx: {"Authorization": "Bearer test"}

        result = await count_resources(
            tool_context=MagicMock(),
            tool_name="advisor__get_active_rules",
        )
        assert result["total"] == 87

    # -- Content sources tools ----------------------------------------------

    @patch("lightspeed_agent.tools.aggregation._get_session_manager")
    @patch("lightspeed_agent.tools.aggregation.create_mcp_header_provider")
    async def test_count_content_sources_repositories(self, mock_header_provider, mock_get_sm):
        """Content sources: list_repositories returns meta.count."""
        response = make_mcp_response(
            {"meta": {"count": 23}, "links": {}, "data": []}
        )
        mock_sm, _ = _mock_session_manager(response)
        mock_get_sm.return_value = mock_sm
        mock_header_provider.return_value = lambda ctx: {"Authorization": "Bearer test"}

        result = await count_resources(
            tool_context=MagicMock(),
            tool_name="content-sources__list_repositories",
        )
        assert result["total"] == 23

    # -- Image builder tools ------------------------------------------------

    @patch("lightspeed_agent.tools.aggregation._get_session_manager")
    @patch("lightspeed_agent.tools.aggregation.create_mcp_header_provider")
    async def test_count_image_builder_blueprints(self, mock_header_provider, mock_get_sm):
        """Image builder: get_blueprints returns meta.count."""
        response = make_mcp_response(
            {"meta": {"count": 5}, "links": {}, "data": []}
        )
        mock_sm, _ = _mock_session_manager(response)
        mock_get_sm.return_value = mock_sm
        mock_header_provider.return_value = lambda ctx: {"Authorization": "Bearer test"}

        result = await count_resources(
            tool_context=MagicMock(),
            tool_name="image-builder__get_blueprints",
        )
        assert result["total"] == 5

    # -- RHSM tools ---------------------------------------------------------

    @patch("lightspeed_agent.tools.aggregation._get_session_manager")
    @patch("lightspeed_agent.tools.aggregation.create_mcp_header_provider")
    async def test_count_rhsm_activation_keys(self, mock_header_provider, mock_get_sm):
        """RHSM: get_activation_keys returns meta.count."""
        response = make_mcp_response(
            {"meta": {"count": 12}, "links": {}, "data": []}
        )
        mock_sm, _ = _mock_session_manager(response)
        mock_get_sm.return_value = mock_sm
        mock_header_provider.return_value = lambda ctx: {"Authorization": "Bearer test"}

        result = await count_resources(
            tool_context=MagicMock(),
            tool_name="rhsm__get_activation_keys",
        )
        assert result["total"] == 12

    # -- Zero count is valid ------------------------------------------------

    @patch("lightspeed_agent.tools.aggregation._get_session_manager")
    @patch("lightspeed_agent.tools.aggregation.create_mcp_header_provider")
    async def test_count_returns_zero(self, mock_header_provider, mock_get_sm):
        """A total of 0 is returned correctly, not treated as missing."""
        response = make_mcp_response(
            {"data": [], "meta": {"total_items": 0}, "links": {}}
        )
        mock_sm, _ = _mock_session_manager(response)
        mock_get_sm.return_value = mock_sm
        mock_header_provider.return_value = lambda ctx: {"Authorization": "Bearer test"}

        result = await count_resources(
            tool_context=MagicMock(),
            tool_name="vulnerability__get_cves",
        )
        assert result["total"] == 0

    # -- Arguments forwarding -----------------------------------------------

    @patch("lightspeed_agent.tools.aggregation._get_session_manager")
    @patch("lightspeed_agent.tools.aggregation.create_mcp_header_provider")
    async def test_arguments_forwarded_with_limit_override(
        self, mock_header_provider, mock_get_sm
    ):
        """User-supplied arguments are forwarded, and limit is always set to 1."""
        response = make_mcp_response(
            {"total": 99, "count": 1, "page": 1, "per_page": 1, "results": []}
        )
        mock_sm, mock_session = _mock_session_manager(response)
        mock_get_sm.return_value = mock_sm
        mock_header_provider.return_value = lambda ctx: {"Authorization": "Bearer test"}

        await count_resources(
            tool_context=MagicMock(),
            tool_name="inventory__list_hosts",
            arguments={"operating_system": "RHEL 8", "limit": 50},
        )

        call_args = mock_session.call_tool.call_args
        passed_args = call_args[1].get("arguments") or call_args[0][1]
        # limit should be overridden to 1
        assert passed_args["limit"] == 1
        # original filter preserved
        assert passed_args["operating_system"] == "RHEL 8"

    # -- No arguments (defaults to empty) -----------------------------------

    @patch("lightspeed_agent.tools.aggregation._get_session_manager")
    @patch("lightspeed_agent.tools.aggregation.create_mcp_header_provider")
    async def test_no_arguments_defaults_empty(self, mock_header_provider, mock_get_sm):
        """Calling without arguments still works (defaults to empty dict)."""
        response = make_mcp_response(
            {"meta": {"count": 10}, "links": {}, "data": []}
        )
        mock_sm, mock_session = _mock_session_manager(response)
        mock_get_sm.return_value = mock_sm
        mock_header_provider.return_value = lambda ctx: {"Authorization": "Bearer test"}

        result = await count_resources(
            tool_context=MagicMock(),
            tool_name="advisor__get_active_rules",
        )
        assert result["total"] == 10


# ---------------------------------------------------------------------------
# 3. Error handling tests
# ---------------------------------------------------------------------------

class TestCountResourcesErrors:
    """Tests for error conditions in count_resources."""

    async def test_unsupported_tool_returns_error(self):
        """An unsupported tool name returns an error dict without calling MCP."""
        result = await count_resources(
            tool_context=MagicMock(),
            tool_name="nonexistent__tool",
        )
        assert "error" in result

    async def test_unsupported_tool_error_contains_tool_name(self):
        """Error message for unsupported tool contains the tool name."""
        result = await count_resources(
            tool_context=MagicMock(),
            tool_name="fake__tool",
        )
        assert "fake__tool" in result["error"]

    @patch("lightspeed_agent.tools.aggregation._get_session_manager")
    @patch("lightspeed_agent.tools.aggregation.create_mcp_header_provider")
    async def test_mcp_exception_returns_error(self, mock_header_provider, mock_get_sm):
        """MCP call raising an exception returns an error dict."""
        mock_session = AsyncMock()
        mock_session.call_tool.side_effect = RuntimeError("MCP connection failed")
        mock_sm = AsyncMock()
        mock_sm.create_session.return_value = mock_session
        mock_get_sm.return_value = mock_sm
        mock_header_provider.return_value = lambda ctx: {"Authorization": "Bearer test"}

        result = await count_resources(
            tool_context=MagicMock(),
            tool_name="vulnerability__get_cves",
        )
        assert "error" in result

    @patch("lightspeed_agent.tools.aggregation._get_session_manager")
    @patch("lightspeed_agent.tools.aggregation.create_mcp_header_provider")
    async def test_non_json_response_returns_error(self, mock_header_provider, mock_get_sm):
        """Response text that is not valid JSON returns an error."""
        content = TextContent(type="text", text="<html>Server Error</html>")
        response = CallToolResult(content=[content])
        mock_sm, _ = _mock_session_manager(response)
        mock_get_sm.return_value = mock_sm
        mock_header_provider.return_value = lambda ctx: {"Authorization": "Bearer test"}

        result = await count_resources(
            tool_context=MagicMock(),
            tool_name="vulnerability__get_cves",
        )
        assert "error" in result

    @patch("lightspeed_agent.tools.aggregation._get_session_manager")
    @patch("lightspeed_agent.tools.aggregation.create_mcp_header_provider")
    async def test_missing_total_path_returns_error(self, mock_header_provider, mock_get_sm):
        """JSON response without the expected total field returns error/fallback."""
        response = make_mcp_response({"data": [], "links": {}})
        mock_sm, _ = _mock_session_manager(response)
        mock_get_sm.return_value = mock_sm
        mock_header_provider.return_value = lambda ctx: {"Authorization": "Bearer test"}

        result = await count_resources(
            tool_context=MagicMock(),
            tool_name="vulnerability__get_cves",
        )
        assert "error" in result

    @patch("lightspeed_agent.tools.aggregation._get_session_manager")
    @patch("lightspeed_agent.tools.aggregation.create_mcp_header_provider")
    async def test_empty_content_list_returns_error(self, mock_header_provider, mock_get_sm):
        """Empty content list from MCP returns an error."""
        response = CallToolResult(content=[])
        mock_sm, _ = _mock_session_manager(response)
        mock_get_sm.return_value = mock_sm
        mock_header_provider.return_value = lambda ctx: {"Authorization": "Bearer test"}

        result = await count_resources(
            tool_context=MagicMock(),
            tool_name="vulnerability__get_cves",
        )
        assert "error" in result

    @patch("lightspeed_agent.tools.aggregation._get_session_manager")
    @patch("lightspeed_agent.tools.aggregation.create_mcp_header_provider")
    async def test_session_creation_failure_returns_error(
        self, mock_header_provider, mock_get_sm
    ):
        """If session creation raises, count_resources returns error dict."""
        mock_sm = AsyncMock()
        mock_sm.create_session.side_effect = ConnectionError("Cannot reach MCP server")
        mock_get_sm.return_value = mock_sm
        mock_header_provider.return_value = lambda ctx: {"Authorization": "Bearer test"}

        result = await count_resources(
            tool_context=MagicMock(),
            tool_name="vulnerability__get_cves",
        )
        assert "error" in result


# ---------------------------------------------------------------------------
# 4. create_aggregation_tool factory tests
# ---------------------------------------------------------------------------

class TestCreateAggregationTool:
    """Tests for the create_aggregation_tool factory function."""

    def test_returns_function_tool(self):
        """Factory returns a FunctionTool instance."""
        from google.adk.tools import FunctionTool

        tool = create_aggregation_tool()
        assert isinstance(tool, FunctionTool)

    def test_tool_name_is_count_resources(self):
        """Tool name is 'count_resources'."""
        tool = create_aggregation_tool()
        assert tool.name == "count_resources"

    def test_tool_has_description(self):
        """Tool has a non-empty description."""
        tool = create_aggregation_tool()
        assert tool.description
        assert len(tool.description) > 10


# ---------------------------------------------------------------------------
# 5. COUNTABLE_TOOLS and TOOL_TOTAL_PATHS consistency tests
# ---------------------------------------------------------------------------

class TestToolMappings:
    """Tests for COUNTABLE_TOOLS and TOOL_TOTAL_PATHS consistency."""

    def test_all_countable_tools_have_total_paths(self):
        """Every entry in COUNTABLE_TOOLS has a corresponding TOOL_TOTAL_PATHS entry."""
        for tool_name in COUNTABLE_TOOLS:
            assert tool_name in TOOL_TOTAL_PATHS, (
                f"{tool_name} is in COUNTABLE_TOOLS but missing from TOOL_TOTAL_PATHS"
            )

    def test_total_paths_values_are_string_tuples(self):
        """All TOOL_TOTAL_PATHS values are tuples containing only strings."""
        for tool_name, path in TOOL_TOTAL_PATHS.items():
            assert isinstance(path, tuple), (
                f"Path for {tool_name} should be a tuple, got {type(path)}"
            )
            for element in path:
                assert isinstance(element, str), (
                    f"Path element for {tool_name} should be str, got {type(element)}: {element}"
                )

    def test_total_paths_are_nonempty(self):
        """No path in TOOL_TOTAL_PATHS is empty."""
        for tool_name, path in TOOL_TOTAL_PATHS.items():
            assert len(path) > 0, f"Path for {tool_name} is empty"

    # Spot-check known tools from each category

    def test_vulnerability_cves_present(self):
        """vulnerability__get_cves is a countable tool."""
        assert "vulnerability__get_cves" in COUNTABLE_TOOLS

    def test_vulnerability_systems_present(self):
        """vulnerability__get_systems is a countable tool."""
        assert "vulnerability__get_systems" in COUNTABLE_TOOLS

    def test_inventory_list_hosts_present(self):
        """inventory__list_hosts is a countable tool."""
        assert "inventory__list_hosts" in COUNTABLE_TOOLS

    def test_advisor_active_rules_present(self):
        """advisor__get_active_rules is a countable tool."""
        assert "advisor__get_active_rules" in COUNTABLE_TOOLS

    def test_content_sources_present(self):
        """content-sources__list_repositories is a countable tool."""
        assert "content-sources__list_repositories" in COUNTABLE_TOOLS

    def test_image_builder_blueprints_present(self):
        """image-builder__get_blueprints is a countable tool."""
        assert "image-builder__get_blueprints" in COUNTABLE_TOOLS

    def test_rhsm_activation_keys_present(self):
        """rhsm__get_activation_keys is a countable tool."""
        assert "rhsm__get_activation_keys" in COUNTABLE_TOOLS

    def test_vulnerability_tools_use_meta_total_items(self):
        """Vulnerability tools use the ('meta', 'total_items') path."""
        assert TOOL_TOTAL_PATHS["vulnerability__get_cves"] == ("meta", "total_items")

    def test_inventory_tools_use_total(self):
        """Inventory tools use the ('total',) path."""
        assert TOOL_TOTAL_PATHS["inventory__list_hosts"] == ("total",)

    def test_advisor_tools_use_meta_count(self):
        """Advisor tools use the ('meta', 'count') path."""
        assert TOOL_TOTAL_PATHS["advisor__get_active_rules"] == ("meta", "count")
