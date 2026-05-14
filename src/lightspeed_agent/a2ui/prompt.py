"""A2UI schema management and system prompt generation."""

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.constants import VERSION_0_8
from a2ui.schema.manager import A2uiSchemaManager


def get_a2ui_schema_manager() -> A2uiSchemaManager:
    """Create the A2UI schema manager with the basic catalog (v0.8)."""
    catalog_config = BasicCatalog.get_config(version=VERSION_0_8)
    return A2uiSchemaManager(
        version=VERSION_0_8,
        catalogs=[catalog_config],
    )


def generate_a2ui_instruction(base_instruction: str) -> str:
    """Augment the base agent instruction with A2UI rendering capabilities.

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
