"""Unit tests for the Edge favorites source plugin (folder-to-tag conversion)."""

import json
from datetime import datetime

import pytest

from link4000.data.loader_types import SourceEntry
from link4000.source_plugins.edge_favorites import EdgeFavoritesSource

# Realistic WebKit timestamp (microseconds since 1601-01-01), ~2025.
_TIMESTAMP = 13390000000000000


def _bookmark_folder(name: str, children: list) -> dict:
    """Build an Edge bookmark folder node."""
    return {"type": "folder", "name": name, "children": children}


def _bookmark_url(name: str, url: str) -> dict:
    """Build an Edge bookmark url node."""
    return {
        "type": "url",
        "name": name,
        "url": url,
        "date_added": _TIMESTAMP,
    }


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


@pytest.fixture
def write_config(tmp_path):
    """Write a config.toml for the plugin and reset the config cache.

    Returns a function taking the TOML content string.
    """

    def _write(content: str) -> None:
        from link4000.utils import config as config_mod

        config_file = tmp_path / "config.toml"
        config_file.write_text(content, encoding="utf-8")
        config_mod._CONFIG_PATH = str(config_file)
        config_mod._config = None

    return _write


def _write_bookmarks(
    path, bookmark_bar_children: list, other_children: list | None = None
) -> None:
    """Write a minimal Edge Bookmarks JSON file."""
    roots = {
        "bookmark_bar": _bookmark_folder("Bookmarks bar", bookmark_bar_children),
    }
    if other_children is not None:
        roots["other"] = _bookmark_folder("Other favorites", other_children)
    path.write_text(json.dumps({"roots": roots}), encoding="utf-8")


def _fetch(
    tmp_path, bookmark_bar_children: list, other_children: list | None = None
) -> list:
    """Write a bookmarks file and fetch entries from it."""
    bookmarks = tmp_path / "Bookmarks"
    _write_bookmarks(bookmarks, bookmark_bar_children, other_children)
    source = EdgeFavoritesSource()
    return source._fetch_favorites_from_path(bookmarks)


def _entry_by_url(entries: list, url: str) -> SourceEntry:
    """Return the entry with the given url."""
    return next(e for e in entries if e.url == url)


class TestFolderTags:
    """Test folder-to-tag conversion (default config)."""

    def test_folder_names_become_tags(self, tmp_path):
        """Nested folder names are added as tags, root name is not."""
        entries = _fetch(
            tmp_path,
            [
                _bookmark_folder(
                    "Work", [_bookmark_url("Example", "https://example.com")]
                )
            ],
        )
        entry = _entry_by_url(entries, "https://example.com")
        assert entry.extra_tags == ["Work"]

    def test_bookmarks_bar_root_not_tagged(self, tmp_path):
        """A url directly in the bookmarks bar gets no extra tags."""
        entries = _fetch(tmp_path, [_bookmark_url("Example", "https://example.com")])
        entry = _entry_by_url(entries, "https://example.com")
        assert entry.extra_tags == []

    def test_german_bookmarks_bar_name_excluded(self, tmp_path):
        """The German bookmarks bar name never becomes a tag."""
        bookmarks = tmp_path / "Bookmarks"
        bookmarks.write_text(
            json.dumps(
                {
                    "roots": {
                        "bookmark_bar": _bookmark_folder(
                            "Lesezeichenleiste",
                            [_bookmark_url("Example", "https://example.com")],
                        )
                    }
                }
            ),
            encoding="utf-8",
        )
        source = EdgeFavoritesSource()
        entries = source._fetch_favorites_from_path(bookmarks)
        entry = _entry_by_url(entries, "https://example.com")
        assert entry.extra_tags == []

    def test_other_root_folder_is_tagged(self, tmp_path):
        """Folders below the 'other' root (e.g. 'Other favorites') become tags."""
        entries = _fetch(
            tmp_path,
            [],
            other_children=[_bookmark_url("Example", "https://example.com")],
        )
        entry = _entry_by_url(entries, "https://example.com")
        assert entry.extra_tags == ["Other favorites"]

    def test_duplicate_segments_deduped(self, tmp_path):
        """Same-named nested folders produce the tag only once."""
        entries = _fetch(
            tmp_path,
            [
                _bookmark_folder(
                    "Work",
                    [
                        _bookmark_folder(
                            "Work", [_bookmark_url("Example", "https://example.com")]
                        )
                    ],
                )
            ],
        )
        entry = _entry_by_url(entries, "https://example.com")
        assert entry.extra_tags == ["Work"]


class TestFolderTagsDisabled:
    """Test the folder_tags_enabled toggle."""

    def test_disabled_yields_no_extra_tags(self, tmp_path):
        """With folder_tags_enabled = false, no extra tags are produced."""
        bookmarks = tmp_path / "Bookmarks"
        _write_bookmarks(
            bookmarks,
            [
                _bookmark_folder(
                    "Work", [_bookmark_url("Example", "https://example.com")]
                )
            ],
        )
        source = EdgeFavoritesSource()
        source._config = {"folder_tags_enabled": False}
        entries = source._fetch_favorites_from_path(bookmarks)
        assert all(e.extra_tags == [] for e in entries)

    def test_disabled_via_config_file(self, tmp_path, write_config):
        """The toggle is read from [sources.edge_favorites] in config.toml."""
        write_config(
            """
[sources.edge_favorites]
folder_tags_enabled = false
"""
        )
        bookmarks = tmp_path / "Bookmarks"
        _write_bookmarks(
            bookmarks,
            [
                _bookmark_folder(
                    "Work", [_bookmark_url("Example", "https://example.com")]
                )
            ],
        )
        source = EdgeFavoritesSource()
        entries = source._fetch_favorites_from_path(bookmarks)
        assert all(e.extra_tags == [] for e in entries)


class TestFolderNameExclusionPatterns:
    """Test the folder_name_exclusion_patterns option."""

    def test_root_folder_excluded_via_pattern(self, tmp_path):
        """A pattern matching the root removes it from the tags."""
        bookmarks = tmp_path / "Bookmarks"
        bookmarks.write_text(
            json.dumps(
                {
                    "roots": {
                        "bookmark_bar": _bookmark_folder(
                            "Favoritenleiste",
                            [
                                _bookmark_folder(
                                    "toller",
                                    [
                                        _bookmark_folder(
                                            "Pfad",
                                            [
                                                _bookmark_url(
                                                    "Example", "https://example.com"
                                                )
                                            ],
                                        )
                                    ],
                                )
                            ],
                        )
                    }
                }
            ),
            encoding="utf-8",
        )
        source = EdgeFavoritesSource()
        source._config = {"folder_name_exclusion_patterns": ["^/Favoritenleiste/"]}
        entries = source._fetch_favorites_from_path(bookmarks)
        entry = _entry_by_url(entries, "https://example.com")
        assert entry.extra_tags == ["toller", "Pfad"]

    def test_multiple_patterns(self, tmp_path):
        """All configured patterns are applied sequentially to the folder path."""
        source = EdgeFavoritesSource()
        source._config = {"folder_name_exclusion_patterns": ["^/a/", "^b/"]}
        tags = source._folder_path_to_tags("/a/b/c")
        assert tags == ["c"]

    def test_middle_segment_excluded(self, tmp_path):
        """Patterns also remove segments in the middle of the path.

        Matched parts are removed literally, so patterns should include the
        trailing delimiter to keep the remaining segments separated.
        """
        source = EdgeFavoritesSource()
        source._config = {"folder_name_exclusion_patterns": ["internal/"]}
        tags = source._folder_path_to_tags("/company/internal/project")
        assert tags == ["company", "project"]

    def test_invalid_pattern_skipped(self, tmp_path):
        """Invalid regexes are skipped without breaking valid ones."""
        source = EdgeFavoritesSource()
        source._config = {"folder_name_exclusion_patterns": ["([", "^/x/"]}
        tags = source._folder_path_to_tags("/x/y")
        assert tags == ["y"]

    def test_non_string_pattern_skipped(self, tmp_path):
        """Non-string pattern entries are skipped without raising."""
        source = EdgeFavoritesSource()
        source._config = {"folder_name_exclusion_patterns": [42]}
        assert source._folder_path_to_tags("/a") == ["a"]

    def test_patterns_via_config_file(self, tmp_path, write_config):
        """Exclusion patterns are read from [sources.edge_favorites] in config.toml."""
        write_config(
            r"""
[sources.edge_favorites]
folder_name_exclusion_patterns = ["^/Bookmarks bar/"]
"""
        )
        bookmarks = tmp_path / "Bookmarks"
        _write_bookmarks(
            bookmarks,
            [
                _bookmark_folder(
                    "Sub", [_bookmark_url("Example", "https://example.com")]
                )
            ],
        )
        source = EdgeFavoritesSource()
        entries = source._fetch_favorites_from_path(bookmarks)
        entry = _entry_by_url(entries, "https://example.com")
        assert entry.extra_tags == ["Sub"]


class TestSourceEntryExtraTags:
    """Test the extra_tags field on SourceEntry."""

    def test_default_is_empty_list(self):
        """extra_tags defaults to an empty list."""
        entry = SourceEntry(
            url="https://example.com",
            title="Example",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            last_accessed=datetime.now(),
            source_tag="test",
        )
        assert entry.extra_tags == []
