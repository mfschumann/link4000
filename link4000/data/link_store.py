"""Persistent storage for Link objects backed by a local JSON file.

Provides the ``LinkStore`` class which handles CRUD operations, search, bulk
tag management, import/export, and an exclusion list for recently-seen URLs.
All data is persisted to ``~/.link4000/links.json`` by default.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from link4000.data.loader_types import SourceEntry
from link4000.data.link_source import LinkSource
from link4000.data.source_registry import SourceRegistry
from link4000.models.link import Link
from link4000.utils.config import get_links_file_path


@SourceRegistry.register
class JsonStoreSource(LinkSource):
    """Link source for loading links from the JSON store."""

    name = "json_store"
    source_tag = "json_store"

    def fetch(self) -> list[SourceEntry]:
        """Fetch all links from the JSON store as SourceEntry objects."""
        store = LinkStore()
        links = store.get_all()

        entries: list[SourceEntry] = []
        for link in links:
            entries.append(
                SourceEntry(
                    url=link.url,
                    title=link.title,
                    created_at=link.created_at,
                    updated_at=link.updated_at,
                    last_accessed=link.last_accessed,
                    source_tag=self.source_tag,
                )
            )

        return entries


class LinkStore:
    """Manages a collection of Link objects persisted to a JSON file.

    Supports CRUD operations, full-text search, bulk tag updates, link
    import, and an exclusion list for URLs sourced from recent-docs or
    favorites integrations.

    Attributes:
        _filepath: Path to the JSON storage file.
        _links: In-memory list of Link objects.
        _excluded_recent_urls: Set of URLs excluded from recent-docs import.
    """

    def __init__(self, filepath: Optional[str] = None) -> None:
        """Initialize the store and load existing data.

        Args:
            filepath: Path to the JSON file. If None, uses the path from
                the application config (typically ``~/.link4000/links.json``).
        """
        if filepath is None:
            links_path = get_links_file_path()
            self._filepath = Path(links_path)
            self._dir = self._filepath.parent
            self._dir.mkdir(exist_ok=True)
        else:
            self._filepath = Path(filepath)
            self._dir = self._filepath.parent

        self._links: List[Link] = []
        self._excluded_recent_urls: set[str] = set()
        self._load()

    def _load(self) -> None:
        """Load links and excluded URLs from the JSON file into memory.

        If the file does not exist or contains invalid JSON, both lists are
        reset to empty.
        """
        if self._filepath.exists():
            try:
                with open(self._filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    links_data = data.get("links", [])
                    self._links = [Link.from_dict(d) for d in links_data]
                    self._excluded_recent_urls = set(
                        data.get("excluded_recent_urls", [])
                    )
            except (json.JSONDecodeError, IOError):
                self._links = []
                self._excluded_recent_urls = set()
        else:
            self._links = []
            self._excluded_recent_urls = set()

    def save(self) -> None:
        """Persist the current state of links and excluded URLs to the JSON file."""
        data = {
            "links": [link.to_dict() for link in self._links],
            "excluded_recent_urls": sorted(self._excluded_recent_urls),
        }
        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_all(self) -> List[Link]:
        """Return a shallow copy of all stored links.

        Returns:
            A new list containing all Link objects in the store.
        """
        return self._links.copy()

    def add(self, link: Link) -> None:
        """Add a new link to the store and persist.

        A UUID is generated for the link if it does not already have an id.

        Args:
            link: The Link object to add.
        """
        if not link.id:
            link.id = str(uuid.uuid4())
        self._links.append(link)
        self.save()

    def update(self, link: Link) -> None:
        """Replace an existing link (matched by id) and persist.

        The link's ``updated_at`` timestamp is automatically set to now.

        Args:
            link: The Link object with updated fields. Must have a valid id.
        """
        for i, link_item in enumerate(self._links):
            if link_item.id == link.id:
                link.updated_at = datetime.now()
                self._links[i] = link
                break
        self.save()

    def delete(self, link_id: str) -> None:
        """Remove a link by its id and persist.

        Args:
            link_id: The unique identifier of the link to remove.
        """
        self._links = [
            link_item for link_item in self._links if link_item.id != link_id
        ]
        self.save()

    def update_last_accessed(self, link_id: str) -> None:
        """Set the ``last_accessed`` timestamp of a link to now and persist.

        Args:
            link_id: The unique identifier of the link to update.
        """
        for i, link_item in enumerate(self._links):
            if link_item.id == link_id:
                self._links[i].last_accessed = datetime.now()
                break
        self.save()

    def find_by_url(self, url: str) -> "Optional[Link]":
        """Return the first Link whose URL/path matches *url* (case-insensitive)."""
        url_lower = url.lower()
        for link in self._links:
            if link.url.lower() == url_lower:
                return link
        return None

    def search(self, query: str) -> List[Link]:
        """Search links by title, URL, or tags (case-insensitive substring match).

        Args:
            query: The search term. An empty string returns all links.

        Returns:
            A list of Link objects matching the query.
        """
        if not query:
            return self.get_all()
        q = query.lower()
        return [
            link_item
            for link_item in self._links
            if q in link_item.title.lower()
            or q in link_item.url.lower()
            or any(q in t.lower() for t in link_item.tags)
        ]

    def import_links(
        self, other_links: List[Link], override: bool = False
    ) -> tuple[int, int, int]:
        """
        Import links from another list. If override=False, skip links whose URL
        already exists. If override=True, update existing links with the same URL.
        """
        existing_urls = {link.url.lower() for link in self._links}
        skipped = 0
        updated = 0

        for link in other_links:
            url_lower = link.url.lower()
            if url_lower in existing_urls:
                if override:
                    for i, existing in enumerate(self._links):
                        if existing.url.lower() == url_lower:
                            link.id = existing.id
                            link.created_at = existing.created_at
                            link.updated_at = datetime.now()
                            self._links[i] = link
                            updated += 1
                            break
                else:
                    skipped += 1
            else:
                self._links.append(link)
                existing_urls.add(url_lower)

        self.save()
        return len(other_links) - skipped - updated, skipped, updated

    def bulk_update_tags(
        self, link_ids: List[str], tags_to_add: List[str], tags_to_remove: List[str]
    ) -> None:
        """
        Add and/or remove tags from multiple links.

        Args:
            link_ids: List of link IDs to update
            tags_to_add: Tags to add to each link (preserving existing tags)
            tags_to_remove: Tags to remove from each link
        """
        if not link_ids:
            return

        tags_to_remove_lower = {t.lower() for t in tags_to_remove}

        for i, link in enumerate(self._links):
            if link.id in link_ids:
                new_tags = list(link.tags)

                if tags_to_remove:
                    new_tags = [
                        t for t in new_tags if t.lower() not in tags_to_remove_lower
                    ]

                if tags_to_add:
                    for tag in tags_to_add:
                        if tag.lower() not in {t.lower() for t in new_tags}:
                            new_tags.append(tag)

                self._links[i].tags = new_tags
                self._links[i].updated_at = datetime.now()

        self.save()

    def bulk_delete(self, link_ids: List[str]) -> None:
        """
        Delete multiple links by their IDs.

        Args:
            link_ids: List of link IDs to delete
        """
        if not link_ids:
            return
        self._links = [
            link_item for link_item in self._links if link_item.id not in link_ids
        ]
        self.save()

    def add_excluded_recent_url(self, url: str) -> None:
        """Add a URL to the excluded recent/favorites list."""
        self._excluded_recent_urls.add(url)
        self.save()

    def get_excluded_recent_urls(self) -> set[str]:
        """Return the set of excluded recent/favorite URLs."""
        return self._excluded_recent_urls.copy()
