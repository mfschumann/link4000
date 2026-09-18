r"""Link source plugin for Microsoft Edge browser favorites.

Supported platforms:
  - Windows  (%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Bookmarks)
  - Linux    (~/.config/microsoft-edge/Default/Bookmarks)
  - macOS    (~/Library/Application Support/Microsoft Edge/Default/Bookmarks)
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from link4000.data.loader_types import SourceEntry
from link4000.data.link_source import LinkSource
from link4000.data.source_registry import SourceRegistry

logger = logging.getLogger(__name__)

# Folder names that should never become tags (top-level bookmarks bar roots).
_ROOT_FOLDER_NAMES = {"bookmarks bar", "bookmark bar", "lesezeichenleiste"}


@SourceRegistry.register
class EdgeFavoritesSource(LinkSource):
    """Link source for Microsoft Edge favorites."""

    name = "edge_favorites"
    source_tag = "edge_favorites"
    config_schema = [
        (
            "folder_tags_enabled",
            bool,
            True,
            "Convert the favorites folder path into tags",
        ),
        (
            "folder_name_exclusion_patterns",
            list,
            [],
            "Regex patterns; matched parts of the folder path are not converted to tags",
        ),
    ]

    @property
    def is_available(self) -> bool:
        """Check if Edge favorites are available."""
        return self._get_bookmarks_path() is not None

    def fetch(self) -> list[SourceEntry]:
        """Return favorites from Microsoft Edge, newest first based on date_added."""
        bookmarks_path = self._get_bookmarks_path()
        if bookmarks_path is None:
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
        """Convert Edge's WebKit timestamp (microseconds since 1601-01-01) to naive local datetime."""
        try:
            unix_timestamp = (microseconds / 1_000_000) - 11644473600
            # Convert UTC aware datetime to local naive datetime to match other sources
            return (
                datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
                .astimezone()
                .replace(tzinfo=None)
            )
        except (ValueError, OSError):
            return datetime.now()

    def _extract_favorites(
        self,
        node: dict,
        entries: list[SourceEntry],
        folder_parts: list[str] | None = None,
    ) -> None:
        """Recursively extract favorites from a bookmark node.

        Args:
            node: The bookmark node to process.
            entries: List to append extracted entries to.
            folder_parts: Folder names from the bookmarks root down to the
                current node; used to build the full folder path.
        """
        if folder_parts is None:
            folder_parts = []
        node_type = node.get("type", "")
        children = node.get("children", [])

        if node_type == "url":
            url = node.get("url", "")
            name = node.get("name", "")
            date_added = node.get("date_added", 0)

            if url and name:
                created_at = self._parse_timestamp(int(date_added))
                # Include ALL folder names (even excluded roots like the
                # bookmarks bar) so exclusion patterns can match them.
                folder_path = "/" + "/".join(folder_parts)
                entries.append(
                    SourceEntry(
                        url=url,
                        title=name,
                        created_at=created_at,
                        updated_at=created_at,
                        last_accessed=created_at,
                        source_tag=self.source_tag,
                        extra_tags=self._folder_path_to_tags(folder_path),
                    )
                )

        elif node_type == "folder" and children:
            folder_name = node.get("name", "")
            new_folder_parts = folder_parts + ([folder_name] if folder_name else [])

            for child in children:
                self._extract_favorites(child, entries, new_folder_parts)

    def _folder_path_to_tags(self, folder_path: str) -> list[str]:
        """Convert a folder path into tags according to the plugin config.

        If ``folder_tags_enabled`` is disabled, an empty list is returned.
        Otherwise every configured ``folder_name_exclusion_patterns`` regex is
        applied to the path and the matched parts are removed; the remaining
        path segments become tags. Segments equal to known bookmarks-bar root
        names and duplicates are dropped.

        Args:
            folder_path: Full folder path with leading slash, e.g.
                "/Favoritenleiste/toller/Pfad".

        Returns:
            List of tags derived from the folder path (may be empty).
        """
        config = self.get_config()
        if not config.get("folder_tags_enabled", True):
            return []

        path = folder_path
        for pattern in config.get("folder_name_exclusion_patterns", []):
            try:
                path = re.sub(pattern, "", path)
            except (re.error, TypeError):
                logger.warning(
                    "Skipping invalid folder_name_exclusion_patterns regex: %r",
                    pattern,
                )

        tags: list[str] = []
        for segment in path.split("/"):
            if not segment or segment.lower() in _ROOT_FOLDER_NAMES:
                continue
            if segment not in tags:
                tags.append(segment)
        return tags

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
