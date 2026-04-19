"""Data model for a saved link with metadata and serialization support."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from link4000.utils.path_utils import (
    get_link_type as _get_link_type,
    get_file_extension as _get_file_extension,
)


@dataclass
class Link:
    """A saved link with title, URL, tags, and metadata.

    Attributes:
        title: Display title of the link.
        url: The URL or path the link points to.
        tags: List of tags associated with the link.
        id: Unique identifier (UUID string).
        created_at: Timestamp when the link was created.
        updated_at: Timestamp when the link was last modified.
        last_accessed: Timestamp when the link was last opened.
        source_tag: Tag identifying the source (e.g., "recent", "office_recent",
            "edge_favorites"). Empty for stored links.
    """

    title: str
    url: str
    tags: List[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    source_tag: str = field(default="")
    _cached_link_type: Optional[str] = field(default=None, repr=False)
    _cached_file_extension: Optional[str] = field(default=None, repr=False)

    @property
    def link_type(self) -> str:
        """Returns the resolved link type, cached after first computation."""
        if self._cached_link_type is None:
            self._cached_link_type = _get_link_type(self.url)
        return self._cached_link_type

    @property
    def file_extension(self) -> str:
        """Returns the file extension (e.g. '.pdf'), cached after first computation."""
        if self._cached_file_extension is None:
            self._cached_file_extension = _get_file_extension(self.url)
        return self._cached_file_extension

    def to_dict(self) -> dict:
        """Serializes the link to a dictionary with ISO-formatted timestamps."""
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "source_tag": self.source_tag,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Link":
        """Creates a Link instance from a dictionary produced by to_dict.

        Args:
            data: Dictionary containing link fields with ISO-formatted timestamps.
        """
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            title=data.get("title", ""),
            url=data.get("url", ""),
            tags=data.get("tags", []),
            source_tag=data.get("source_tag", ""),
            created_at=datetime.fromisoformat(
                data.get("created_at", datetime.now().isoformat())
            ),
            updated_at=datetime.fromisoformat(
                data.get("updated_at", datetime.now().isoformat())
            ),
            last_accessed=datetime.fromisoformat(
                data.get("last_accessed", datetime.now().isoformat())
            ),
        )

    @classmethod
    def from_legacy_dict(cls, data: dict) -> "Link":
        """Create a Link from a legacy JSON schema (keywords instead of tags, no timestamps)."""
        return cls(
            title=data.get("name", ""),
            url=data.get("path", ""),
            tags=data.get("keywords", []),
        )
