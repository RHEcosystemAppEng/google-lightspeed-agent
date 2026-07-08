"""A2UI schema management and catalog access."""

from functools import lru_cache

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.catalog import A2uiCatalog
from a2ui.schema.constants import VERSION_0_9
from a2ui.schema.manager import A2uiSchemaManager


@lru_cache(maxsize=1)
def get_a2ui_schema_manager() -> A2uiSchemaManager:
    """Create and cache the A2UI schema manager with the basic catalog (v0.9)."""
    catalog_config = BasicCatalog.get_config(version=VERSION_0_9)
    return A2uiSchemaManager(
        version=VERSION_0_9,
        catalogs=[catalog_config],
    )


def get_a2ui_catalog() -> A2uiCatalog:
    """Get the A2UI catalog for the Basic Catalog v0.9."""
    return get_a2ui_schema_manager().get_selected_catalog()


def get_insights_a2ui_examples() -> str:
    """Get domain-specific A2UI examples for Red Hat Insights data."""
    from lightspeed_agent.a2ui.examples import INSIGHTS_A2UI_EXAMPLES

    return INSIGHTS_A2UI_EXAMPLES
