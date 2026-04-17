"""Unified types for link source plugins."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class SourceEntry:
    """Unified entry type returned by all link source plugins.

    Attributes:
        url: The URL or file path of the entry.
        title: Display title of the entry.
        created_at: Timestamp when the entry was created.
        updated_at: Timestamp when the entry was last modified.
        last_accessed: Timestamp when the entry was last accessed.
        source_tag: Tag identifying the source (e.g., "recent", "office_recent",
            "edge_favorites", "json_store").
    """

    url: str
    title: str
    created_at: datetime
    updated_at: datetime
    last_accessed: datetime
    source_tag: str
