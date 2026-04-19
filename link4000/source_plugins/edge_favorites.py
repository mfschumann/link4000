r"""Link source plugin for Microsoft Edge browser favorites.

Supported platforms:
  - Windows  (%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Bookmarks)
  - Linux    (~/.config/microsoft-edge/Default/Bookmarks)
  - macOS    (~/Library/Application Support/Microsoft Edge/Default/Bookmarks)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from link4000.data.loader_types import SourceEntry
from link4000.data.link_source import LinkSource
from link4000.data.source_registry import SourceRegistry


@SourceRegistry.register
class EdgeFavoritesSource(LinkSource):
    """Link source for Microsoft Edge favorites."""

    name = "edge_favorites"
    source_tag = "edge_favorites"

    @property
    def is_available(self) -> bool:
        """Check if Edge favorites are available."""
        return self._get_bookmarks_path() is not None

    def fetch(self) -> list[SourceEntry]:
        """Return favorites from Microsoft Edge, newest first based on date_added."""
        bookmarks_path = self._get_bookmarks_path()
        if not bookmarks_path:
            return []
        return self._fetch_favorites_from_path(bookmarks_path)

    def _get_bookmarks_path(self) -> Path | None:
        """Return the path to the Edge Bookmarks file for the current platform."""
        if sys.platform == "win32":
            base = Path(os.environ.get("LOCALAPPDATA", ""))
            path = base / "Microsoft" / "Edge" / "User Data" / "Default" / "Bookmarks"
        elif sys.platform.startswith("linux"):
            path = Path.home() / ".config" / "microsoft-edge" / "Default" / "Bookmarks"
        elif sys.platform == "darwin":
            path = (
                Path.home()
                / "Library"
                / "Application Support"
                / "Microsoft Edge"
                / "Default"
                / "Bookmarks"
            )
        else:
            return None

        return path if path.exists() else None

    def _parse_timestamp(self, microseconds: int) -> datetime:
        """Convert Edge's WebKit timestamp (microseconds since 1601-01-01) to datetime."""
        try:
            unix_timestamp = (microseconds / 1_000_000) - 11644473600
            return datetime.fromtimestamp(unix_timestamp, tz=timezone.utc).replace(
                tzinfo=None
            )
        except (ValueError, OSError):
            return datetime.now()

    def _extract_favorites(self, node: dict, entries: list[SourceEntry]) -> None:
        """Recursively extract favorites from a bookmark node."""
        node_type = node.get("type", "")
        children = node.get("children", [])

        if node_type == "url":
            url = node.get("url", "")
            name = node.get("name", "")
            date_added = node.get("date_added", 0)

            if url and name:
                created_at = self._parse_timestamp(int(date_added))
                entries.append(
                    SourceEntry(
                        url=url,
                        title=name,
                        created_at=created_at,
                        updated_at=created_at,
                        last_accessed=created_at,
                        source_tag=self.source_tag,
                    )
                )
        elif node_type == "folder" and children:
            for child in children:
                self._extract_favorites(child, entries)

    def _fetch_favorites_from_path(self, bookmarks_path: Path) -> list[SourceEntry]:
        """Read and parse the Edge Bookmarks file."""
        entries: list[SourceEntry] = []

        try:
            with open(bookmarks_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return entries

        roots = data.get("roots", {})
        for root_key in ("bookmark_bar", "other", "synced"):
            root = roots.get(root_key, {})
            self._extract_favorites(root, entries)

        entries.sort(key=lambda e: e.created_at, reverse=True)
        return entries