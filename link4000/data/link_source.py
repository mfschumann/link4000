"""Abstract base class for link source plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from link4000.data.loader_types import SourceEntry


class LinkSource(ABC):
    """Abstract base class for link source plugins.

    Subclasses must implement the `fetch` method to return entries from
    their respective sources. The `is_available` property can be overridden
    to indicate whether the source is available on the current platform.

    Configuration options can be defined using the `config_schema` class
    attribute. Each option is a tuple of (name, type, default, description).
    """

    name: str = ""
    source_tag: str = ""
    config_schema: list[tuple[str, type, Any, str]] = []
    _config: dict[str, Any] | None = None

    @abstractmethod
    def fetch(self) -> list[SourceEntry]:
        """Fetch entries from the source.

        Returns:
            A list of SourceEntry objects sorted by last_accessed (newest first).
        """

    @property
    def is_available(self) -> bool:
        """Check if the source is available on the current platform.

        Returns:
            True if the source can be used, False otherwise.
        """
        return True

    def get_config(self) -> dict[str, Any]:
        """Return configuration values for this plugin from config.toml.

        Uses values from [sources.<plugin_name>] section, falling back to
        defaults defined in config_schema.

        Returns:
            Dictionary mapping option names to their values.
        """
        if self._config is not None:
            return self._config

        from link4000.utils.config import get_source_config

        stored_config = get_source_config(self.name)
        config: dict[str, Any] = {}

        for name, typ, default, _description in self.config_schema:
            if name in stored_config:
                config[name] = stored_config[name]
            else:
                config[name] = default

        self._config = config
        return config

    def _filter_by_age(self, entries: list[SourceEntry], max_age_days: int) -> list[SourceEntry]:
        """Filter entries by maximum age in days.

        Args:
            entries: List of SourceEntry objects to filter.
            max_age_days: Maximum age in days (0 or negative means no filter).

        Returns:
            Filtered list of entries.
        """
        if max_age_days <= 0:
            return entries

        from datetime import datetime, timedelta

        cutoff = datetime.now() - timedelta(days=max_age_days)
        return [e for e in entries if e.last_accessed and e.last_accessed >= cutoff]
