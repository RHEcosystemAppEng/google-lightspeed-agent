"""A2UI schema management and catalog access."""

from functools import lru_cache

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.catalog import A2uiCatalog
from a2ui.schema.constants import VERSION_0_8
from a2ui.schema.manager import A2uiSchemaManager


@lru_cache(maxsize=1)
def get_a2ui_schema_manager() -> A2uiSchemaManager:
    """Create and cache the A2UI schema manager with the basic catalog (v0.8)."""
    catalog_config = BasicCatalog.get_config(version=VERSION_0_8)
    return A2uiSchemaManager(
        version=VERSION_0_8,
        catalogs=[catalog_config],
    )


def get_a2ui_catalog() -> A2uiCatalog:
    """Get the A2UI catalog for the Basic Catalog v0.8."""
    return get_a2ui_schema_manager().get_selected_catalog()


def get_insights_a2ui_examples() -> str:
    """Get domain-specific A2UI examples for Red Hat Insights data."""
    from lightspeed_agent.a2ui.examples import INSIGHTS_A2UI_EXAMPLES

    return INSIGHTS_A2UI_EXAMPLES


def generate_a2ui_instruction(base_instruction: str) -> str:
    """Augment the base agent instruction with A2UI rendering capabilities.

    Kept for backward compatibility. New code should use
    SendA2uiToClientToolset with get_a2ui_catalog() and
    get_insights_a2ui_examples() instead.

    Args:
        base_instruction: The original agent system prompt.

    Returns:
        Combined instruction with A2UI schema and examples appended.
    """
    schema_manager = get_a2ui_schema_manager()
    result: str = schema_manager.generate_system_prompt(
        role_description=base_instruction,
        include_schema=True,
        include_examples=True,
    )
    return result
