"""Link source plugin for Windows recent documents.

This module provides the RecentDocsWindowsSource class that fetches
recently-opened files on Windows from the native recent-files infrastructure
(%AppData%\Microsoft\Windows\Recent .lnk files via pywin32 IShellLinkW).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

from link4000.data.loader_types import SourceEntry
from link4000.data.link_source import LinkSource
from link4000.data.source_registry import SourceRegistry
from link4000.utils.path_utils import resolve_lnk, resolve_unc_path


@SourceRegistry.register
class RecentDocsWindowsSource(LinkSource):
    """Link source for Windows recent files.

    Reads .lnk files from %AppData%\\Microsoft\\Windows\\Recent folder.
    """

    name = "recent_windows"
    source_tag = "recent"

    _recent_folder = (
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Recent"
    )

    @property
    def is_available(self) -> bool:
        """Check if Windows recent files source is available."""
        return sys.platform == "win32" and self._recent_folder.exists()

    def fetch(self) -> list[SourceEntry]:
        """Fetch recently-opened files on Windows via .lnk shortcuts.

        Returns:
            A list of SourceEntry objects representing recent files.
        """
        if not self.is_available:
            return []

        entries: list[SourceEntry] = []
        for lnk_path in sorted(
            self._recent_folder.glob("*.lnk"), key=lambda p: p.stat().st_mtime, reverse=True
        ):
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