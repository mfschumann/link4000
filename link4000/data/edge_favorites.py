r"""Read favorites from Microsoft Edge browser.

Supported platforms:
  - Windows  (%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Bookmarks)
  - Linux    (~/.config/microsoft-edge/Default/Bookmarks)
  - macOS    (~/Library/Application Support/Microsoft Edge/Default/Bookmarks)
"""

from __future__ import annotations

import json
import os
import sys
from collections import namedtuple
from datetime import datetime, timezone
from pathlib import Path

FavoriteEntry = namedtuple(
    "FavoriteEntry", ["url", "title", "created_at", "updated_at", "last_accessed"]
)


def fetch_edge_favorites() -> list[FavoriteEntry]:
    """Return favorites from Microsoft Edge, newest first based on date_added."""
    if sys.platform == "win32":
        return _fetch_windows()
    elif sys.platform.startswith("linux"):
        return _fetch_linux()
    elif sys.platform == "darwin":
        return _fetch_macos()
    return []


def _get_bookmarks_path() -> Path | None:
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


def _parse_timestamp(microseconds: int) -> datetime:
    """Convert Edge's WebKit timestamp (microseconds since 1601-01-01) to datetime."""
    try:
        unix_timestamp = (microseconds / 1_000_000) - 11644473600
        return datetime.fromtimestamp(unix_timestamp, tz=timezone.utc).replace(
            tzinfo=None
        )
    except (ValueError, OSError):
        return datetime.now()


def _extract_favorites(node: dict, entries: list[FavoriteEntry]) -> None:
    """Recursively extract favorites from a bookmark node."""
    node_type = node.get("type", "")
    children = node.get("children", [])

    if node_type == "url":
        url = node.get("url", "")
        name = node.get("name", "")
        date_added = node.get("date_added", 0)

        if url and name:
            created_at = _parse_timestamp(int(date_added))
            entries.append(
                FavoriteEntry(
                    url=url,
                    title=name,
                    created_at=created_at,
                    updated_at=created_at,
                    last_accessed=created_at,
                )
            )
    elif node_type == "folder" and children:
        for child in children:
            _extract_favorites(child, entries)


def _fetch_favorites_from_path(bookmarks_path: Path) -> list[FavoriteEntry]:
    """Read and parse the Edge Bookmarks file."""
    entries: list[FavoriteEntry] = []

    try:
        with open(bookmarks_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return entries

    roots = data.get("roots", {})
    for root_key in ("bookmark_bar", "other", "synced"):
        root = roots.get(root_key, {})
        _extract_favorites(root, entries)

    entries.sort(key=lambda e: e.created_at, reverse=True)
    return entries


def _fetch_windows() -> list[FavoriteEntry]:
    """Fetch Edge favorites on Windows from the default Bookmarks file.

    Returns:
        A list of ``FavoriteEntry`` values sorted by date added, newest first.
    """
    bookmarks_path = _get_bookmarks_path()
    if not bookmarks_path:
        return []
    return _fetch_favorites_from_path(bookmarks_path)


def _fetch_linux() -> list[FavoriteEntry]:
    """Fetch Edge favorites on Linux from the default Bookmarks file.

    Returns:
        A list of ``FavoriteEntry`` values sorted by date added, newest first.
    """
    bookmarks_path = _get_bookmarks_path()
    if not bookmarks_path:
        return []
    return _fetch_favorites_from_path(bookmarks_path)


def _fetch_macos() -> list[FavoriteEntry]:
    """Fetch Edge favorites on macOS from the default Bookmarks file.

    Returns:
        A list of ``FavoriteEntry`` values sorted by date added, newest first.
    """
    bookmarks_path = _get_bookmarks_path()
    if not bookmarks_path:
        return []
    return _fetch_favorites_from_path(bookmarks_path)
