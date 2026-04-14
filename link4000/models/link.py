"""Data model for a saved link with metadata and serialization support."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional


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
        is_recent: Whether the link was recently accessed.
        is_favorite: Whether the link is marked as a favorite.
    """

    def __init__(
        self,
        title: str = "",
        url: str = "",
        tags: Optional[List[str]] = None,
        id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        last_accessed: Optional[datetime] = None,
        is_recent: bool = False,
        is_favorite: bool = False,
    ) -> None:
        """Initialize a Link with optional URL resolution.

        Args:
            title: Display title of the link.
            url: The URL or path the link points to (will be resolved).
            tags: List of tags associated with the link.
            id: Unique identifier (UUID string).
            created_at: Timestamp when the link was created.
            updated_at: Timestamp when the link was last modified.
            last_accessed: Timestamp when the link was last opened.
            is_recent: Whether the link was recently accessed.
            is_favorite: Whether the link is marked as a favorite.
        """

        self._title = title
        self._url = ""
        self.tags = tags if tags is not None else []
        self.id = id if id is not None else str(uuid.uuid4())
        self.created_at = created_at if created_at is not None else datetime.now()
        self.updated_at = updated_at if updated_at is not None else datetime.now()
        self.last_accessed = last_accessed if last_accessed is not None else datetime.now()
        self.is_recent = is_recent
        self.is_favorite = is_favorite
        self._cached_link_type: Optional[str] = None
        self._cached_file_extension: Optional[str] = None

        # Resolve URL after all fields are set (so auto-fill can use title)
        if url:
            self.url = url

    def _resolve_url(self) -> None:
        """Resolve the URL and auto-fill title if needed."""
        from link4000.utils.path_utils import (
            resolve_path as _resolve_path,
            is_file_path as _is_file_path,
        )

        if self._url:
            resolved, resolved_title = _resolve_path(self._url)
            self._url = resolved
            if resolved_title and not self._title:
                self._title = resolved_title
            elif not self._title:
                if _is_file_path(resolved):
                    self._title = Path(resolved).name

    @property
    def title(self) -> str:
        """Returns the display title of the link."""
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        """Sets the title."""
        self._title = value

    @property
    def url(self) -> str:
        """Returns the resolved URL/path."""
        return self._url

    @url.setter
    def url(self, value: str) -> None:
        """Sets the URL with automatic path resolution and title auto-fill."""
        self._url = value
        if value:
            self._resolve_url()
            self._cached_link_type = None
            self._cached_file_extension = None

    @property
    def link_type(self) -> str:
        """Returns the resolved link type, cached after first computation."""
        from link4000.utils.path_utils import get_link_type as _get_link_type

        if self._cached_link_type is None:
            self._cached_link_type = _get_link_type(self.url)
        return self._cached_link_type

    @property
    def file_extension(self) -> str:
        """Returns the file extension (e.g. '.pdf'), cached after first computation."""
        from link4000.utils.path_utils import get_file_extension as _get_file_extension

        if self._cached_file_extension is None:
            self._cached_file_extension = _get_file_extension(self.url)
        return self._cached_file_extension

    def __repr__(self) -> str:
        """Returns a string representation of the Link."""
        return (
            f"Link(title={self.title!r}, url={self.url!r}, tags={self.tags!r}, "
            f"id={self.id!r}, is_recent={self.is_recent}, is_favorite={self.is_favorite})"
        )

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
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Link":
        """Creates a Link instance from a dictionary produced by to_dict.

        Args:
            data: Dictionary containing link fields with ISO-formatted timestamps.
        """
        link = cls(
            title=data.get("title", ""),
            url="",  # Don't pass URL to constructor - we'll set it directly to skip resolution
            tags=data.get("tags", []),
            id=data.get("id", str(uuid.uuid4())),
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
        # Skip resolution for existing stored URLs - set directly
        link._url = data.get("url", "")
        return link

    @classmethod
    def from_legacy_dict(cls, data: dict) -> "Link":
        """Create a Link from a legacy JSON schema (keywords instead of tags, no timestamps)."""
        link = cls(
            title=data.get("name", ""),
            url="",  # Don't pass to constructor
            tags=data.get("keywords", []),
        )
        # Skip resolution for existing stored URLs
        link._url = data.get("path", "")
        return link