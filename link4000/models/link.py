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
        description: Optional free-text description of the link.
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
    description: str = field(default="")
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    source_tag: str = field(default="")
    _cached_link_type: Optional[str] = field(default=None, repr=False)
    _cached_file_extension: Optional[str] = field(default=None, repr=False)
    _search_blob: Optional[str] = field(default=None, repr=False)

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

    def reset_type_cache(self) -> None:
        """Invalidate the cached link type, file extension, and search index.

        Should be called after mutating ``url``, ``title``, ``tags``, or
        ``description`` so that the type and search data are re-evaluated
        on the next access.
        """
        self._cached_link_type = None
        self._cached_file_extension = None
        self._search_blob = None

    @property
    def tags_lower(self) -> frozenset:
        """Return the link tags as a lowercased frozenset for filtering.

        Computed on demand from the current tags; no separate cache is
        needed since tag filtering reads it once per filter pass at most.
        """
        return frozenset(t.lower() for t in self.tags)

    def ensure_computed(self) -> None:
        """Precompute type, extension, and search blob, caching all of them.

        Warms the lazy ``link_type``/``file_extension`` caches (which may
        perform filesystem checks) and builds the lowercased search blob
        used by the proxy filter. Call this once after a ``Link`` list is
        built and before handing it to the GUI thread, so that filtering
        and painting never trigger I/O or repeated ``lower()`` calls.
        """
        _ = self.link_type
        _ = self.file_extension
        if self._search_blob is None:
            self._search_blob = (
                f"{self.title}\n{self.url}\n{' '.join(self.tags)}\n"
                f"{self.description}"
            ).lower()

    @property
    def search_blob(self) -> str:
        """Return the lowercased search blob, computing it if needed."""
        if self._search_blob is None:
            self.ensure_computed()
        return self._search_blob

    def to_dict(self) -> dict:
        """Serializes the link to a dictionary with ISO-formatted timestamps."""
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "tags": self.tags,
            "description": self.description,
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
            description=data.get("description", ""),
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
