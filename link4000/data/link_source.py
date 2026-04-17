"""Abstract base class for link source plugins."""

from abc import ABC, abstractmethod

from link4000.data.loader_types import SourceEntry


class LinkSource(ABC):
    """Abstract base class for link source plugins.

    Subclasses must implement the `fetch` method to return entries from
    their respective sources. The `is_available` property can be overridden
    to indicate whether the source is available on the current platform.
    """

    name: str = ""
    source_tag: str = ""

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
