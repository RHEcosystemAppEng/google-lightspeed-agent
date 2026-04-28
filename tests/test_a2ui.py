"""Tests for A2UI integration."""

from unittest.mock import patch

from lightspeed_agent.a2ui.prompt import generate_a2ui_instruction, get_a2ui_schema_manager
from lightspeed_agent.api.a2a.agent_card import build_agent_card
from lightspeed_agent.core.agent import AGENT_INSTRUCTION


class TestA2uiPrompt:
    """Tests for A2UI prompt generation."""

    def test_schema_manager_creates_successfully(self):
        """Test A2UI schema manager initializes with basic catalog."""
        manager = get_a2ui_schema_manager()
        assert manager is not None

    def test_generate_a2ui_instruction_contains_base(self):
        """Test augmented instruction preserves the original agent instruction."""
        result = generate_a2ui_instruction(AGENT_INSTRUCTION)
        assert "Red Hat Lightspeed Agent" in result

    def test_generate_a2ui_instruction_adds_schema(self):
        """Test augmented instruction includes A2UI component schema."""
        result = generate_a2ui_instruction(AGENT_INSTRUCTION)
        assert len(result) > len(AGENT_INSTRUCTION)

    def test_generate_a2ui_instruction_returns_string(self):
        """Test generate_a2ui_instruction returns a string."""
        result = generate_a2ui_instruction("Test role")
        assert isinstance(result, str)
        assert len(result) > 0


class TestAgentCardA2ui:
    """Tests for A2UI in AgentCard."""

    def _clear_card_cache(self):
        """Clear lru_cache on agent card builders so settings changes take effect."""
        from lightspeed_agent.api.a2a.agent_card import get_agent_card_dict

        build_agent_card.cache_clear()
        get_agent_card_dict.cache_clear()

    def test_agent_card_has_a2ui_extension_when_enabled(self):
        """Test AgentCard includes A2UI extension when A2UI_ENABLED=true."""
        from lightspeed_agent.config import get_settings

        settings = get_settings()
        original = settings.a2ui_enabled
        settings.a2ui_enabled = True
        self._clear_card_cache()
        try:
            card = build_agent_card()
            extensions = card.capabilities.extensions
            a2ui_uris = [e.uri for e in extensions]
            assert "https://a2ui.org/a2a-extension/a2ui/v0.8" in a2ui_uris
        finally:
            settings.a2ui_enabled = original
            self._clear_card_cache()

    def test_agent_card_no_a2ui_extension_when_disabled(self):
        """Test AgentCard omits A2UI extension when A2UI_ENABLED=false."""
        from lightspeed_agent.config import get_settings

        settings = get_settings()
        original = settings.a2ui_enabled
        settings.a2ui_enabled = False
        self._clear_card_cache()
        try:
            card = build_agent_card()
            extensions = card.capabilities.extensions
            a2ui_uris = [e.uri for e in extensions]
            assert "https://a2ui.org/a2a-extension/a2ui/v0.8" not in a2ui_uris
        finally:
            settings.a2ui_enabled = original
            self._clear_card_cache()

    def test_agent_card_output_modes_include_a2ui_when_enabled(self):
        """Test output modes include A2UI MIME type when enabled."""
        from lightspeed_agent.config import get_settings

        settings = get_settings()
        original = settings.a2ui_enabled
        settings.a2ui_enabled = True
        self._clear_card_cache()
        try:
            card = build_agent_card()
            assert "application/json+a2ui" in card.default_output_modes
            assert "text/plain" in card.default_output_modes
        finally:
            settings.a2ui_enabled = original
            self._clear_card_cache()

    def test_agent_card_output_modes_text_only_when_disabled(self):
        """Test output modes are text-only when A2UI is disabled."""
        from lightspeed_agent.config import get_settings

        settings = get_settings()
        original = settings.a2ui_enabled
        settings.a2ui_enabled = False
        self._clear_card_cache()
        try:
            card = build_agent_card()
            assert card.default_output_modes == ["text/plain"]
        finally:
            settings.a2ui_enabled = original
            self._clear_card_cache()

    def test_agent_card_a2ui_extension_params(self):
        """Test A2UI extension declares standard catalog."""
        from lightspeed_agent.config import get_settings

        settings = get_settings()
        original = settings.a2ui_enabled
        settings.a2ui_enabled = True
        self._clear_card_cache()
        try:
            card = build_agent_card()
            a2ui_ext = next(
                e for e in card.capabilities.extensions
                if "a2ui" in e.uri
            )
            assert "supportedCatalogIds" in a2ui_ext.params
            assert a2ui_ext.params["acceptsInlineCatalogs"] is True
        finally:
            settings.a2ui_enabled = original
            self._clear_card_cache()

    def test_agent_card_still_has_dcr_extension_with_a2ui(self):
        """Test DCR extension remains present when A2UI is enabled."""
        from lightspeed_agent.config import get_settings

        settings = get_settings()
        original = settings.a2ui_enabled
        settings.a2ui_enabled = True
        self._clear_card_cache()
        try:
            card = build_agent_card()
            extensions = card.capabilities.extensions
            dcr_uris = [e.uri for e in extensions if "dcr" in e.uri]
            assert len(dcr_uris) == 1
        finally:
            settings.a2ui_enabled = original
            self._clear_card_cache()


class TestAgentCreationA2ui:
    """Tests for A2UI integration in agent creation."""

    @patch("lightspeed_agent.core.agent.LlmAgent")
    @patch("lightspeed_agent.tools.create_insights_toolset", side_effect=ImportError)
    def test_create_agent_uses_a2ui_instruction_when_enabled(
        self, _mock_tools, mock_llm_agent
    ):
        """Test agent is created with A2UI-augmented instruction when enabled."""
        from lightspeed_agent.config import get_settings
        from lightspeed_agent.core.agent import create_agent

        settings = get_settings()
        original = settings.a2ui_enabled
        settings.a2ui_enabled = True
        try:
            create_agent()
            call_kwargs = mock_llm_agent.call_args[1]
            instruction = call_kwargs["instruction"]
            assert len(instruction) > len(AGENT_INSTRUCTION)
        finally:
            settings.a2ui_enabled = original

    @patch("lightspeed_agent.core.agent.LlmAgent")
    @patch("lightspeed_agent.tools.create_insights_toolset", side_effect=ImportError)
    def test_create_agent_uses_plain_instruction_when_disabled(
        self, _mock_tools, mock_llm_agent
    ):
        """Test agent uses plain instruction when A2UI is disabled."""
        from lightspeed_agent.config import get_settings
        from lightspeed_agent.core.agent import create_agent

        settings = get_settings()
        original = settings.a2ui_enabled
        settings.a2ui_enabled = False
        try:
            create_agent()
            call_kwargs = mock_llm_agent.call_args[1]
            assert call_kwargs["instruction"] == AGENT_INSTRUCTION
        finally:
            settings.a2ui_enabled = original
