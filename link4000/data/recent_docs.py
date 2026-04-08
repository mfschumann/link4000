"""Read recently-opened files from the OS native recent-files infrastructure.

Supported platforms:
  - Windows  (%AppData%\\Microsoft\\Windows\\Recent .lnk files via pywin32 IShellLinkW)
  - Linux / GNOME  (~/.local/share/recently-used.xbel)
  - Others         (empty list)
"""

from __future__ import annotations

import os
import sys
import urllib.parse
from collections import namedtuple
from datetime import datetime
from pathlib import Path

from link4000.utils.path_utils import resolve_lnk

RecentEntry = namedtuple(
    "RecentEntry", ["url", "title", "created_at", "updated_at", "last_accessed"]
)


def fetch_recent_entries() -> list[RecentEntry]:
    """Return recently-opened files from the OS, newest first."""
    if sys.platform == "win32":
        return _fetch_windows()
    elif sys.platform.startswith("linux"):
        return _fetch_linux_gnome()
    return []


# ---------------------------------------------------------------------------
# Windows  –  %AppData%\Microsoft\Windows\Recent
# Each .lnk file is parsed via pywin32's pythoncom + IShellLinkW / IPersistFile.
# ---------------------------------------------------------------------------


def _fetch_windows() -> list[RecentEntry]:
    """Fetch recently-opened files on Windows via .lnk shortcuts in the Recent folder.

    Returns:
        A list of ``RecentEntry`` values sorted by modification time, newest
        first, limited to the 200 most recent items.
    """
    recent_folder = (
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Recent"
    )

    if not recent_folder.exists():
        return []

    entries: list[RecentEntry] = []
    for lnk_path in sorted(
        recent_folder.glob("*.lnk"), key=lambda p: p.stat().st_mtime, reverse=True
    )[:200]:
        target, title = resolve_lnk(lnk_path)
        if not target:
            continue

        try:
            mtime = datetime.fromtimestamp(lnk_path.stat().st_mtime)
        except Exception:
            mtime = datetime.now()

        entries.append(
            RecentEntry(
                url=target,
                title=title,
                created_at=mtime,
                updated_at=mtime,
                last_accessed=mtime,
            )
        )

    return entries


# ---------------------------------------------------------------------------
# Linux / GNOME  –  ~/.local/share/recently-used.xbel
# XML format defined by the freedesktop.org specification.
# ---------------------------------------------------------------------------


def _fetch_linux_gnome() -> list[RecentEntry]:
    """Fetch recently-opened files on Linux/Gnome from ``recently-used.xbel``.

    Parses the freedesktop.org XBEL bookmark file and extracts file:// entries
    with their timestamps.

    Returns:
        A list of ``RecentEntry`` values sorted by last-accessed time, newest
        first.
    """
    xbel_path = Path.home() / ".local" / "share" / "recently-used.xbel"
    if not xbel_path.exists():
        return []

    entries: list[RecentEntry] = []

    try:
        import xml.etree.ElementTree as ET

        tree = ET.parse(xbel_path)
        root = tree.getroot()
        if root is None:
            return []

        xbel_ns = "http://www.freedesktop.org/standards/xbel/1.0/"

        for bookmark in root.findall("bookmark"):
            href = bookmark.get("href", "")
            if not href.startswith("file://"):
                continue

            # URL-decode the path (handles spaces, umlauts, %20, %2520, etc.)
            url = urllib.parse.unquote(href[7:])
            if not url:
                continue

            title_el = bookmark.find("title")
            title = (
                title_el.text
                if title_el is not None and title_el.text
                else Path(url).name
            )

            created_at: datetime | None = None
            updated_at: datetime | None = None
            last_accessed: datetime | None = None

            raw_added = bookmark.get("added")
            raw_modified = bookmark.get("modified")
            raw_visited = bookmark.get("visited")

            def parse_ts(raw: str | None) -> datetime | None:
                """Parse an ISO-8601 timestamp string, normalising the ``Z`` suffix.

                Args:
                    raw: An ISO-8601 datetime string, or None.

                Returns:
                    A naive ``datetime`` on success, or None if *raw* is falsy
                    or cannot be parsed.
                """
                if not raw:
                    return None
                # Normalise Z suffix to +00:00 for fromisoformat, then strip tzinfo
                # to keep all datetimes naive and comparable with datetime.now()
                normalized = raw.replace("Z", "+00:00")
                try:
                    return datetime.fromisoformat(normalized).replace(tzinfo=None)
                except Exception:
                    return None

            created_at = parse_ts(raw_added)
            updated_at = parse_ts(raw_modified)
            last_accessed = parse_ts(raw_visited)

            # Fall back to <metadata><application> if not on bookmark element
            if created_at is None or updated_at is None or last_accessed is None:
                for meta in bookmark.findall("metadata"):
                    for app in meta.findall(f"{{{xbel_ns}}}application"):
                        if created_at is None:
                            created_at = parse_ts(app.get("added"))
                        if updated_at is None:
                            updated_at = parse_ts(app.get("modified"))
                        if last_accessed is None:
                            last_accessed = parse_ts(app.get("visited"))

            now = datetime.now()
            if created_at is None:
                created_at = now
            if updated_at is None:
                updated_at = now
            if last_accessed is None:
                try:
                    last_accessed = datetime.fromtimestamp(Path(url).stat().st_mtime)
                except Exception:
                    last_accessed = now

            entries.append(
                RecentEntry(
                    url=url,
                    title=title,
                    created_at=created_at,
                    updated_at=updated_at,
                    last_accessed=last_accessed,
                )
            )
    except Exception:
        pass

    entries.sort(key=lambda e: e.last_accessed, reverse=True)
    return entries
