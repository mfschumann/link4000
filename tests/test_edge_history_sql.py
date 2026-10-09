"""Unit tests for Edge history SQL age filtering."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from link4000.source_plugins.edge_history import EdgeHistorySource


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path):
    """Ensure tests read defaults, not a live ~/.link4000/config.toml."""
    from link4000.utils import config as config_mod

    original_path = config_mod._CONFIG_PATH
    original_cached = config_mod._config
    config_mod._CONFIG_PATH = str(tmp_path / "nonexistent_config.toml")
    config_mod._config = None
    yield
    config_mod._CONFIG_PATH = original_path
    config_mod._config = original_cached


def _webkit_micros(dt: datetime) -> int:
    """Convert a datetime to a WebKit timestamp (microseconds since 1601-01-01 UTC)."""
    return int((dt.timestamp() + 11644473600) * 1_000_000)


def _write_history_db(path: Path, rows: list[tuple[str, str, int]]) -> None:
    """Write a minimal Edge History SQLite database."""
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE urls (url TEXT, title TEXT, last_visit_time INTEGER)")
    conn.executemany(
        "INSERT INTO urls (url, title, last_visit_time) VALUES (?, ?, ?)", rows
    )
    conn.commit()
    conn.close()


def _fetch(
    tmp_path, history_rows: list[tuple[str, str, int]], max_age_days: int | None = None
):
    """Write a History db and fetch entries with the given max_age_days."""
    history = tmp_path / "History"
    _write_history_db(history, history_rows)
    source = EdgeHistorySource()
    if max_age_days is not None:
        source._config = {"max_age_days": max_age_days}
    return source._fetch_history_from_path(history)


def _row(url: str, days_ago: float) -> tuple[str, str, int]:
    """Build a (url, title, last_visit_time) row visited days_ago days ago."""
    now = datetime.now(timezone.utc)
    visited = now.timestamp() - days_ago * 86400
    return (url, f"Title {url}", int((visited + 11644473600) * 1_000_000))


class TestSqlAgeFilter:
    """Test that max_age_days is enforced by the SQL query."""

    def test_old_rows_excluded(self, tmp_path):
        """Rows older than max_age_days are not returned."""
        entries = _fetch(
            tmp_path,
            [_row("https://recent.example", 1), _row("https://old.example", 60)],
            max_age_days=30,
        )
        urls = [e.url for e in entries]
        assert urls == ["https://recent.example"]

    def test_zero_max_age_returns_all(self, tmp_path):
        """max_age_days=0 disables the age filter and returns everything."""
        entries = _fetch(
            tmp_path,
            [_row("https://recent.example", 1), _row("https://old.example", 600)],
            max_age_days=0,
        )
        assert {e.url for e in entries} == {
            "https://recent.example",
            "https://old.example",
        }

    def test_ordering_desc(self, tmp_path):
        """Entries are ordered newest first."""
        entries = _fetch(
            tmp_path,
            [
                _row("https://older.example", 5),
                _row("https://newer.example", 1),
            ],
            max_age_days=30,
        )
        assert [e.url for e in entries] == [
            "https://newer.example",
            "https://older.example",
        ]

    def test_zero_timestamp_excluded(self, tmp_path):
        """Rows with last_visit_time=0 are excluded by the cutoff comparison."""
        entries = _fetch(
            tmp_path,
            [_row("https://recent.example", 1), ("https://zero.example", "Zero", 0)],
            max_age_days=30,
        )
        assert [e.url for e in entries] == ["https://recent.example"]

    def test_filter_by_age_not_called(self, tmp_path, monkeypatch):
        """The Python post-filter must not run; SQL enforces the cutoff."""

        def fail_filter(self, entries, max_age_days):
            raise AssertionError("_filter_by_age must not be called")

        monkeypatch.setattr(EdgeHistorySource, "_filter_by_age", fail_filter)
        entries = _fetch(tmp_path, [_row("https://recent.example", 1)], max_age_days=30)
        assert [e.url for e in entries] == ["https://recent.example"]

    def test_non_int_max_age_falls_back_to_default(self, tmp_path):
        """A non-int max_age_days falls back to the 30-day default."""
        entries = _fetch(
            tmp_path,
            [_row("https://recent.example", 1), _row("https://old.example", 60)],
            max_age_days="bogus",
        )
        assert [e.url for e in entries] == ["https://recent.example"]


class TestWebkitCutoff:
    """Test the WebKit cutoff computation."""

    def test_cutoff_roundtrip(self):
        """The cutoff is the inverse of _parse_timestamp within a day of tolerance."""
        source = EdgeHistorySource()
        cutoff = source._webkit_cutoff_micros(30)
        parsed = source._parse_timestamp(cutoff)
        now = datetime.now()
        age = (now - parsed).total_seconds() / 86400
        assert 29 <= age <= 31
