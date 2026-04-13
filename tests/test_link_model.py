"""Unit tests for link model (LinkTableModel, LinkSortFilterModel, format_relative_date)."""

from datetime import datetime, timedelta

import pytest

from link4000.models.link import Link

# Skip all tests if PySide6 is not available
try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication  # noqa: F401

    from link4000.models.link_model import (
        LinkSortFilterModel,
        LinkTableModel,
        format_relative_date,
    )

    _has_pyside6 = True
except ImportError:
    _has_pyside6 = False

pytestmark = pytest.mark.skipif(not _has_pyside6, reason="PySide6 not available")


# ---------------------------------------------------------------------------
# format_relative_date
# ---------------------------------------------------------------------------


class TestFormatRelativeDate:
    """Tests for the format_relative_date function."""

    def test_just_now(self):
        """Tests that a timestamp from now returns 'just now'."""
        assert format_relative_date(datetime.now()) == "just now"

    def test_thirty_seconds(self):
        """Tests that a timestamp 30 seconds ago returns 'just now'."""
        assert (
            format_relative_date(datetime.now() - timedelta(seconds=30)) == "just now"
        )

    def test_one_minute(self):
        """Tests that a timestamp 1 minute ago returns '1 minute ago'."""
        assert (
            format_relative_date(datetime.now() - timedelta(minutes=1))
            == "1 minute ago"
        )

    def test_multiple_minutes(self):
        """Tests that a timestamp several minutes ago returns the correct plural form."""
        assert (
            format_relative_date(datetime.now() - timedelta(minutes=5))
            == "5 minutes ago"
        )

    def test_one_hour(self):
        """Tests that a timestamp 1 hour ago returns '1 hour ago'."""
        assert format_relative_date(datetime.now() - timedelta(hours=1)) == "1 hour ago"

    def test_multiple_hours(self):
        """Tests that a timestamp several hours ago returns the correct plural form."""
        assert (
            format_relative_date(datetime.now() - timedelta(hours=3)) == "3 hours ago"
        )

    def test_one_day(self):
        """Tests that a timestamp 1 day ago returns '1 day ago'."""
        assert format_relative_date(datetime.now() - timedelta(days=1)) == "1 day ago"

    def test_multiple_days(self):
        """Tests that a timestamp several days ago returns the correct plural form."""
        assert format_relative_date(datetime.now() - timedelta(days=3)) == "3 days ago"

    def test_same_year_older_than_week(self):
        """Tests that dates older than a week but within the same year return 'Mon DD'."""
        dt = datetime.now() - timedelta(days=20)
        result = format_relative_date(dt)
        assert result == dt.strftime("%b %d")

    def test_different_year(self):
        """Tests that dates from a different year return 'Mon YYYY'."""
        dt = datetime.now() - timedelta(days=400)
        result = format_relative_date(dt)
        assert result == dt.strftime("%b %Y")


# ---------------------------------------------------------------------------
# LinkTableModel
# ---------------------------------------------------------------------------


def _make_link(
    title="Test",
    url="https://example.com",
    tags=None,
    is_recent=False,
    is_favorite=False,
):
    """Creates a Link instance with default or custom attributes for testing."""
    return Link(
        title=title,
        url=url,
        tags=tags or [],
        is_recent=is_recent,
        is_favorite=is_favorite,
    )


class TestLinkTableModel:
    """Tests for the LinkTableModel class."""

    def test_empty_model(self):
        """Tests that a freshly created model has zero rows and the expected column count."""
        model = LinkTableModel()
        assert model.rowCount() == 0
        assert model.columnCount() == 5

    def test_set_links(self):
        """Tests that setting links updates the row count correctly."""
        model = LinkTableModel()
        links = [_make_link("A"), _make_link("B")]
        model.set_links(links)
        assert model.rowCount() == 2

    def test_set_recent_links(self):
        """Tests that setting recent links updates the row count correctly."""
        model = LinkTableModel()
        model.set_recent_links([_make_link("R1", is_recent=True)])
        assert model.rowCount() == 1

    def test_links_and_recent_combined(self):
        """Tests that row count reflects both regular and recent links combined."""
        model = LinkTableModel()
        model.set_links([_make_link("A"), _make_link("B")])
        model.set_recent_links([_make_link("R1", is_recent=True)])
        assert model.rowCount() == 3

    def test_data_title(self):
        """Tests that the title column returns the correct link title."""
        model = LinkTableModel()
        model.set_links([_make_link("My Title")])
        idx = model.index(0, LinkTableModel.COL_TITLE)
        assert model.data(idx) == "My Title"

    def test_data_tags(self):
        """Tests that the tags column returns a comma-separated tag string."""
        model = LinkTableModel()
        model.set_links([_make_link(tags=["work", "important"])])
        idx = model.index(0, LinkTableModel.COL_TAGS)
        assert model.data(idx) == "work, important"

    def test_data_recent_tag(self):
        """Tests that recent links display 'recent' in the tags column."""
        model = LinkTableModel()
        model.set_recent_links([_make_link(is_recent=True)])
        idx = model.index(0, LinkTableModel.COL_TAGS)
        assert model.data(idx) == "recent"

    def test_data_favorite_tag(self):
        """Tests that favorite links display 'favorite' in the tags column."""
        model = LinkTableModel()
        model.set_recent_links([_make_link(is_favorite=True)])
        idx = model.index(0, LinkTableModel.COL_TAGS)
        assert model.data(idx) == "favorite"

    def test_data_user_role_returns_id(self):
        """Tests that UserRole returns the link's unique ID."""
        model = LinkTableModel()
        link = _make_link()
        model.set_links([link])
        idx = model.index(0, 0)
        assert model.data(idx, Qt.ItemDataRole.UserRole) == link.id

    def test_header_data(self):
        """Tests that horizontal header labels are correct for each column."""
        model = LinkTableModel()
        assert model.headerData(0, Qt.Orientation.Horizontal) == "Title"
        assert model.headerData(1, Qt.Orientation.Horizontal) == "Tags"
        assert model.headerData(2, Qt.Orientation.Horizontal) == "Last Accessed"

    def test_get_link(self):
        """Tests retrieving a link by its row index from the regular list."""
        model = LinkTableModel()
        links = [_make_link("A"), _make_link("B")]
        model.set_links(links)
        assert model.get_link(0).title == "A"
        assert model.get_link(1).title == "B"

    def test_get_link_recent(self):
        """Tests retrieving a recent link by row index when both lists are set."""
        model = LinkTableModel()
        model.set_links([_make_link("A")])
        model.set_recent_links([_make_link("R1", is_recent=True)])
        assert model.get_link(1).title == "R1"

    def test_get_link_by_id(self):
        """Tests retrieving a link by its unique ID from the regular list."""
        model = LinkTableModel()
        links = [_make_link("A"), _make_link("B")]
        model.set_links(links)
        assert model.get_link_by_id(links[1].id).title == "B"

    def test_get_link_by_id_in_recent(self):
        """Tests retrieving a recent link by its unique ID."""
        model = LinkTableModel()
        model.set_links([_make_link("A")])
        recent = _make_link("R1", is_recent=True)
        model.set_recent_links([recent])
        assert model.get_link_by_id(recent.id).title == "R1"

    def test_get_link_by_id_not_found(self):
        """Tests that looking up a nonexistent ID returns None."""
        model = LinkTableModel()
        assert model.get_link_by_id("nonexistent") is None

    def test_append_links(self):
        """Tests that appending links adds them after existing ones."""
        model = LinkTableModel()
        model.set_links([_make_link("A")])
        model.append_links([_make_link("B")])
        assert model.rowCount() == 2
        assert model.get_link(1).title == "B"

    def test_append_recent_links(self):
        """Tests that appending recent links adds them after regular links."""
        model = LinkTableModel()
        model.set_links([_make_link("A")])
        model.append_recent_links([_make_link("R1", is_recent=True)])
        assert model.rowCount() == 2
        assert model.get_link(1).title == "R1"

    def test_invalid_index(self):
        """Tests that data() returns None for an out-of-bounds index."""
        model = LinkTableModel()
        invalid = model.index(99, 0)
        assert model.data(invalid) is None

    def test_remove_link_from_main_list(self):
        """Tests that remove_link removes a link from the main list."""
        model = LinkTableModel()
        link_a = _make_link("A")
        link_b = _make_link("B")
        model.set_links([link_a, link_b])
        assert model.rowCount() == 2
        removed = model.remove_link(link_a.id)
        assert removed is True
        assert model.rowCount() == 1
        assert model.get_link(0).title == "B"

    def test_remove_link_from_recent_list(self):
        """Tests that remove_link removes a link from the recent list."""
        model = LinkTableModel()
        model.set_links([_make_link("A")])
        recent = _make_link("R1", is_recent=True)
        model.set_recent_links([recent])
        assert model.rowCount() == 2
        removed = model.remove_link(recent.id)
        assert removed is True
        assert model.rowCount() == 1

    def test_remove_link_not_found(self):
        """Tests that remove_link returns False when link is not found."""
        model = LinkTableModel()
        model.set_links([_make_link("A")])
        result = model.remove_link("nonexistent-id")
        assert result is False
        assert model.rowCount() == 1

    def test_update_link_in_main_list(self):
        """Tests that update_link updates a link in the main list."""
        model = LinkTableModel()
        link = _make_link("Original")
        model.set_links([link])
        updated = Link(
            title="Updated",
            url=link.url,
            tags=["newtag"],
            id=link.id,
        )
        result = model.update_link(updated)
        assert result is True
        assert model.get_link(0).title == "Updated"
        assert model.get_link(0).tags == ["newtag"]

    def test_update_link_in_recent_list(self):
        """Tests that update_link updates a link in the recent list."""
        model = LinkTableModel()
        model.set_links([_make_link("A")])
        recent = _make_link("R1", is_recent=True)
        model.set_recent_links([recent])
        updated = Link(
            title="Updated Recent",
            url=recent.url,
            tags=["recent"],
            id=recent.id,
            is_recent=True,
        )
        result = model.update_link(updated)
        assert result is True
        assert model.get_link(1).title == "Updated Recent"

    def test_update_link_not_found(self):
        """Tests that update_link returns False when link is not found."""
        model = LinkTableModel()
        model.set_links([_make_link("A")])
        nonexistent = _make_link("B")
        result = model.update_link(nonexistent)
        assert result is False


# ---------------------------------------------------------------------------
# LinkSortFilterModel
# ---------------------------------------------------------------------------


class TestLinkSortFilterModel:
    """Tests for the LinkSortFilterModel proxy class."""

    @staticmethod
    def _make_model(links=None, recent=None):
        """Creates a LinkTableModel and LinkSortFilterModel pair for testing."""
        source = LinkTableModel()
        if links:
            source.set_links(links)
        if recent:
            source.set_recent_links(recent)
        proxy = LinkSortFilterModel()
        proxy.setSourceModel(source)
        return proxy, source

    def test_no_filter_shows_all(self):
        """Tests that all links are visible when no filter is applied."""
        proxy, source = self._make_model(links=[_make_link("A"), _make_link("B")])
        assert proxy.rowCount() == 2

    def test_search_filters_by_title(self):
        """Tests that search text filters links by title."""
        proxy, _ = self._make_model(
            links=[
                _make_link("Python Guide"),
                _make_link("JavaScript Guide"),
            ]
        )
        proxy.set_search_text("python")
        assert proxy.rowCount() == 1

    def test_search_filters_by_url(self):
        """Tests that search text filters links by URL."""
        proxy, _ = self._make_model(
            links=[
                _make_link("A", url="https://python.org"),
                _make_link("B", url="https://javascript.com"),
            ]
        )
        proxy.set_search_text("python")
        assert proxy.rowCount() == 1

    def test_search_filters_by_tag(self):
        """Tests that search text filters links by tag."""
        proxy, _ = self._make_model(
            links=[
                _make_link("A", tags=["work"]),
                _make_link("B", tags=["personal"]),
            ]
        )
        proxy.set_search_text("work")
        assert proxy.rowCount() == 1

    def test_search_multiple_terms(self):
        """Tests that multiple search terms are combined with AND logic."""
        proxy, _ = self._make_model(
            links=[
                _make_link("Python Guide", tags=["work"]),
                _make_link("Python Tips", tags=["personal"]),
                _make_link("JavaScript Guide", tags=["work"]),
            ]
        )
        proxy.set_search_text("python work")
        assert proxy.rowCount() == 1

    def test_search_empty_shows_all(self):
        """Tests that clearing the search text restores all links to view."""
        proxy, _ = self._make_model(links=[_make_link("A"), _make_link("B")])
        proxy.set_search_text("x")
        proxy.set_search_text("")
        assert proxy.rowCount() == 2

    def test_tag_filter_any(self):
        """Tests that 'any' tag filter shows links matching at least one selected tag."""
        proxy, _ = self._make_model(
            links=[
                _make_link("A", tags=["work"]),
                _make_link("B", tags=["personal"]),
                _make_link("C", tags=["work", "important"]),
            ]
        )
        proxy.set_selected_tags({"work"}, match_all=False)
        assert proxy.rowCount() == 2

    def test_tag_filter_all(self):
        """Tests that 'all' tag filter shows links matching every selected tag."""
        proxy, _ = self._make_model(
            links=[
                _make_link("A", tags=["work"]),
                _make_link("B", tags=["personal"]),
                _make_link("C", tags=["work", "important"]),
            ]
        )
        proxy.set_selected_tags({"work", "important"}, match_all=True)
        assert proxy.rowCount() == 1

    def test_type_filter(self):
        """Tests that type filter shows only links of the selected type."""
        proxy, _ = self._make_model(
            links=[
                _make_link("A", url="https://example.com"),
                _make_link("B", url="/some/folder"),
            ]
        )
        proxy.set_selected_tags(set(), types={"web"})
        assert proxy.rowCount() == 1

    def test_combined_search_and_tag_filter(self):
        """Tests that search text and tag filter can be applied simultaneously."""
        proxy, _ = self._make_model(
            links=[
                _make_link("Python Guide", url="https://python.org", tags=["work"]),
                _make_link(
                    "Python Tips", url="https://tips.python.org", tags=["personal"]
                ),
                _make_link("JS Guide", url="https://js.org", tags=["work"]),
            ]
        )
        proxy.set_search_text("python")
        proxy.set_selected_tags({"work"}, match_all=False)
        assert proxy.rowCount() == 1
