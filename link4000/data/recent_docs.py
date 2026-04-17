"""Read recently-opened files from the OS native recent-files infrastructure.

Supported platforms:
  - Windows  (%AppData%\Microsoft\Windows\Recent .lnk files via pywin32 IShellLinkW)
  - Linux / GNOME  (~/.local/share/recently-used.xbel)
  - Others         (empty list)
"""

from __future__ import annotations

import os
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

from link4000.data.loader_types import SourceEntry
from link4000.data.link_source import LinkSource
from link4000.data.source_registry import SourceRegistry
from link4000.utils.path_utils import resolve_lnk, resolve_unc_path


@SourceRegistry.register
class WindowsRecentSource(LinkSource):
    """Link source for Windows recent files."""

    name = "recent"
    source_tag = "recent"

    @property
    def is_available(self) -> bool:
        """Check if Windows recent files are available."""
        return sys.platform == "win32"

    def fetch(self) -> list[SourceEntry]:
        """Fetch recently-opened files on Windows via .lnk shortcuts.

        Returns:
            A list of SourceEntry values sorted by modification time, newest
            first, limited to the 200 most recent items.
        """
        recent_folder = (
            Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Recent"
        )

        if not recent_folder.exists():
            return []

        entries: list[SourceEntry] = []
        for lnk_path in sorted(
            recent_folder.glob("*.lnk"), key=lambda p: p.stat().st_mtime, reverse=True
        )[:200]:
            target, title = resolve_lnk(lnk_path)
            if not target:
                continue

            target = resolve_unc_path(target)

            try:
                mtime = datetime.fromtimestamp(lnk_path.stat().st_mtime)
            except Exception:
                mtime = datetime.now()

            entries.append(
                SourceEntry(
                    url=target,
                    title=title,
                    created_at=mtime,
                    updated_at=mtime,
                    last_accessed=mtime,
                    source_tag=self.source_tag,
                )
            )

        return entries


@SourceRegistry.register
class GnomeRecentSource(LinkSource):
    """Link source for GNOME recent files."""

    name = "gnome_recent"
    source_tag = "recent"

    @property
    def is_available(self) -> bool:
        """Check if GNOME recent files are available."""
        return sys.platform.startswith("linux")

    def fetch(self) -> list[SourceEntry]:
        """Fetch recently-opened files on Linux/Gnome from recently-used.xbel.

        Parses the freedesktop.org XBEL bookmark file and extracts file:// entries
        with their timestamps.

        Returns:
            A list of SourceEntry values sorted by last-accessed time, newest first.
        """
        xbel_path = Path.home() / ".local" / "share" / "recently-used.xbel"
        if not xbel_path.exists():
            return []

        entries: list[SourceEntry] = []

        try:
            import xml.etree.ElementTree as elmTree

            tree = elmTree.parse(xbel_path)
            root = tree.getroot()
            if root is None:
                return []

            xbel_ns = "http://www.freedesktop.org/standards/xbel/1.0/"

            for bookmark in root.findall("bookmark"):
                href = bookmark.get("href", "")
                if not href.startswith("file://"):
                    continue

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
                    if not raw:
                        return None
                    normalized = raw.replace("Z", "+00:00")
                    try:
                        return datetime.fromisoformat(normalized).replace(tzinfo=None)
                    except Exception:
                        return None

                created_at = parse_ts(raw_added)
                updated_at = parse_ts(raw_modified)
                last_accessed = parse_ts(raw_visited)

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
                        last_accessed = datetime.fromtimestamp(
                            Path(url).stat().st_mtime
                        )
                    except Exception:
                        last_accessed = now

                entries.append(
                    SourceEntry(
                        url=url,
                        title=title,
                        created_at=created_at,
                        updated_at=updated_at,
                        last_accessed=last_accessed,
                        source_tag=self.source_tag,
                    )
                )
        except Exception:
            pass

        entries.sort(key=lambda e: e.last_accessed, reverse=True)
        return entries


def fetch_recent_entries() -> list[SourceEntry]:
    """Return recently-opened files from the OS, newest first."""
    sources = SourceRegistry.get_enabled_sources()
    entries: list[SourceEntry] = []
    for source in sources:
        if source.name in ("recent", "gnome_recent"):
            entries.extend(source.fetch())
    return entries
