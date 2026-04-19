"""Link source plugin for Linux/GNOME recent documents.

This module provides the RecentDocsLinuxGnomeSource class that fetches
recently-opened files on Linux/GNOME from the native recently-used.xbel file
located at ~/.local/share/recently-used.xbel.
"""

from __future__ import annotations

import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

from link4000.data.loader_types import SourceEntry
from link4000.data.link_source import LinkSource
from link4000.data.source_registry import SourceRegistry


@SourceRegistry.register
class RecentDocsLinuxGnomeSource(LinkSource):
    """Link source for Linux/GNOME recent files.

    Reads from ~/.local/share/recently-used.xbel (GNOME recent files).
    """

    name = "recent_linux_gnome"
    source_tag = "recent"

    @property
    def is_available(self) -> bool:
        """Check if Linux/GNOME recent files source is available."""
        return sys.platform.startswith("linux")

    def fetch(self) -> list[SourceEntry]:
        """Fetch recently-opened files on Linux/GNOME from recently-used.xbel.

        Returns:
            A list of SourceEntry objects representing recent files.
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