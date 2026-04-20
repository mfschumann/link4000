"""Plugin registry for link sources."""

from typing import List

from link4000.data.link_source import LinkSource
from link4000.utils.config import get_enabled_sources


class SourceRegistry:
    """Registry for link source plugins.

    Sources are registered using the `@SourceRegistry.register` decorator.
    The registry provides access to enabled sources based on configuration.
    """

    _sources: dict[str, type[LinkSource]] = {}

    @classmethod
    def register(cls, source_class: type[LinkSource]) -> type[LinkSource]:
        """Register a link source plugin.

        Args:
            source_class: The LinkSource subclass to register.

        Returns:
            The unchanged source_class for use as a decorator.
        """
        cls._sources[source_class.name] = source_class
        return source_class

    @classmethod
    def get_registered_sources(cls) -> dict[str, type[LinkSource]]:
        """Return all registered source classes.

        Returns:
            Dictionary mapping source name to source class.
        """
        return cls._sources.copy()

    @classmethod
    def _ensure_plugins_loaded(cls) -> None:
        """Import source modules so plugin classes register themselves.

        Registration happens via `@SourceRegistry.register` at import time.
        """
        # Import the source_plugins package which imports all plugin modules
        import link4000.source_plugins  # noqa: F401

    @classmethod
    def get_enabled_sources(cls) -> List[LinkSource]:
        """Return instantiated sources that are both registered and enabled in config.

        Returns:
            List of LinkSource instances that should be loaded.
        """
        cls._ensure_plugins_loaded()
        enabled_names = get_enabled_sources()
        sources: List[LinkSource] = []

        for name in enabled_names:
            if name in cls._sources:
                source_class = cls._sources[name]
                instance = source_class()
                if instance.is_available:
                    sources.append(instance)

        return sources
