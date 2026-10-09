r"""Link source plugin for Microsoft Edge browser history.

Supported platforms:
  - Windows  (%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\History)
  - Linux    (~/.config/microsoft-edge/Default/History)
  - macOS    (~/Library/Application Support/Microsoft Edge/Default/History)
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from link4000.data.loader_types import SourceEntry
from link4000.data.link_source import LinkSource
from link4000.data.source_registry import SourceRegistry


@SourceRegistry.register
class EdgeHistorySource(LinkSource):
    """Link source for Microsoft Edge browsing history."""

    name = "edge_history"
    source_tag = "edge_history"
    config_schema = [
        ("max_age_days", int, 30, "Maximum age in days for history items (0 = no limit)"),
    ]

    def _get_history_path(self) -> Path | None:
        """Return the path to the Edge History file for the current platform."""
        if sys.platform == "win32":
            base = Path(os.environ.get("LOCALAPPDATA", ""))
            path = base / "Microsoft" / "Edge" / "User Data" / "Default" / "History"
        elif sys.platform.startswith("linux"):
            path = Path.home() / ".config" / "microsoft-edge" / "Default" / "History"
        elif sys.platform == "darwin":
            path = (
                Path.home()
                / "Library"
                / "Application Support"
                / "Microsoft Edge"
                / "Default"
                / "History"
            )
        else:
            return None

        return path if path.exists() else None

    def _parse_timestamp(self, microseconds: int) -> datetime:
        """Convert Edge's WebKit timestamp (microseconds since 1601-01-01) to naive local datetime."""
        try:
            unix_timestamp = (microseconds / 1_000_000) - 11644473600
            # Convert UTC aware datetime to local naive datetime to match other sources
            return datetime.fromtimestamp(unix_timestamp, tz=timezone.utc).astimezone().replace(
                tzinfo=None
            )
        except (ValueError, OSError):
            return datetime.now()

    @staticmethod
    def _webkit_cutoff_micros(max_age_days: int) -> int:
        """Return the WebKit timestamp (microseconds since 1601-01-01 UTC) for the cutoff.

        Entries older than ``max_age_days`` fall below this value, so it can be
        used directly in a ``WHERE last_visit_time >= ?`` clause. Inverse of
        :meth:`_parse_timestamp`.

        Args:
            max_age_days: Maximum age in days for history items.

        Returns:
            The cutoff as a WebKit timestamp in microseconds.
        """
        unix_cutoff = datetime.now(timezone.utc).timestamp() - max_age_days * 86400
        return int((unix_cutoff + 11644473600) * 1_000_000)

    @property
    def is_available(self) -> bool:
        """Check if Edge history is available."""
        return self._get_history_path() is not None

    def fetch(self) -> list[SourceEntry]:
        """Fetch browsing history from Microsoft Edge, newest first based on last_visit_time."""
        history_path = self._get_history_path()
        if not self.is_available:
            return []

        return self._fetch_history_from_path(history_path)

    def _fetch_history_from_path(self, history_path: Path) -> list[SourceEntry]:
        """Read and parse the Edge History database.

        When ``max_age_days`` is positive, the age filter is applied in SQL
        via ``WHERE last_visit_time >= ?`` so old rows are never read into
        Python. Rows with a missing or zero ``last_visit_time`` are excluded
        by the cutoff comparison. With ``max_age_days <= 0`` all rows are
        returned.
        """
        entries: list[SourceEntry] = []

        max_age_days = self.get_config().get("max_age_days", 30)
        if not isinstance(max_age_days, int):
            max_age_days = 30

        history_copy_path = None
        try:
            import tempfile

            temp_dir = Path(tempfile.gettempdir())
            history_copy_path = temp_dir / f"link4000_edge_history_{os.getpid()}.db"

            import shutil

            shutil.copy2(history_path, history_copy_path)
        except Exception:
            pass

        db_path = history_copy_path if history_copy_path and history_copy_path.exists() else history_path

        try:
            import sqlite3

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if max_age_days > 0:
                cutoff = self._webkit_cutoff_micros(max_age_days)
                cursor.execute(
                    "SELECT url, title, last_visit_time FROM urls "
                    "WHERE last_visit_time >= ? ORDER BY last_visit_time DESC",
                    (cutoff,),
                )
            else:
                cursor.execute(
                    "SELECT url, title, last_visit_time FROM urls ORDER BY last_visit_time DESC"
                )
            rows = cursor.fetchall()

            for row in rows:
                url = row["url"]
                title = row["title"] or ""
                last_visit_time = row["last_visit_time"]

                if not url:
                    continue

                created_at = self._parse_timestamp(last_visit_time)

                entries.append(
                    SourceEntry(
                        url=url,
                        title=title,
                        created_at=created_at,
                        updated_at=created_at,
                        last_accessed=created_at,
                        source_tag=self.source_tag,
                    )
                )

            conn.close()
        except Exception:
            pass
        finally:
            if history_copy_path and history_copy_path.exists():
                try:
                    history_copy_path.unlink()
                except Exception:
                    pass

        # Rows arrive in DESC last_visit_time order from SQL in both
        # branches, so no Python re-sort is needed.
        return entries