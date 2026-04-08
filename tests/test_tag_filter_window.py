"""Unit tests for TagFilterWindow."""

import pytest

try:
    from PySide6.QtWidgets import QApplication  # noqa: F401
    from PySide6.QtTest import QSignalSpy

    from link4000.ui.tag_filter_window import TagFilterWindow

    _has_pyside6 = True
except ImportError:
    _has_pyside6 = False

pytestmark = pytest.mark.skipif(not _has_pyside6, reason="PySide6 not available")


def _select_items(list_widget, texts):
    """Programmatically select items in a QListWidget by text."""
    for i in range(list_widget.count()):
        item = list_widget.item(i)
        item.setSelected(item.text() in texts)


class TestTagFilterWindowInit:
    """Tests for TagFilterWindow initialization and widget state."""

    def test_preselects_tags(self):
        """Tags passed as selected are highlighted on initialization."""
        dlg = TagFilterWindow(
            all_tags={"work", "personal", "project"},
            selected_tags={"work"},
            selected_types=set(),
        )
        selected = {
            dlg._tags_list.item(i).text()
            for i in range(dlg._tags_list.count())
            if dlg._tags_list.item(i).isSelected()
        }
        assert selected == {"work"}

    def test_preselects_types(self):
        """Types passed as selected are highlighted on initialization."""
        dlg = TagFilterWindow(
            all_types={"web", "folder", "file"},
            selected_types={"web"},
            selected_tags=set(),
        )
        selected = {
            dlg._types_list.item(i).text()
            for i in range(dlg._types_list.count())
            if dlg._types_list.item(i).isSelected()
        }
        assert selected == {"web"}

    def test_match_all_radio_checked(self):
        """The 'match all' radio button is checked when match_all is True."""
        dlg = TagFilterWindow(
            all_tags={"a"}, selected_tags={"a"}, match_all=True, selected_types=set()
        )
        assert dlg._tag_and_radio.isChecked()

    def test_match_any_radio_checked(self):
        """The 'match any' radio button is checked when match_all is False."""
        dlg = TagFilterWindow(
            all_tags={"a"}, selected_tags={"a"}, match_all=False, selected_types=set()
        )
        assert dlg._tag_or_radio.isChecked()

    def test_dynamic_tags_are_italic(self):
        """Dynamic tags (e.g. 'recent', 'favorite') are rendered in italic font."""
        dlg = TagFilterWindow(
            all_tags={"work", "recent", "favorite"},
            selected_tags=set(),
            selected_types=set(),
        )
        for i in range(dlg._tags_list.count()):
            item = dlg._tags_list.item(i)
            if item.text() in ("recent", "favorite"):
                assert item.font().italic()
            else:
                assert not item.font().italic()

    def test_tags_sorted_dynamics_first(self):
        """Dynamic tags appear before regular tags, each group sorted alphabetically."""
        dlg = TagFilterWindow(
            all_tags={"work", "recent", "personal", "favorite"},
            selected_tags=set(),
            selected_types=set(),
        )
        tags = [dlg._tags_list.item(i).text() for i in range(dlg._tags_list.count())]
        dynamic = [t for t in tags if t in TagFilterWindow._dynamic_tags]
        regular = [t for t in tags if t not in TagFilterWindow._dynamic_tags]
        assert dynamic == sorted(dynamic)
        assert regular == sorted(regular)


class TestTagFilterWindowSignals:
    """Tests for TagFilterWindow signals emitted on user interactions."""

    def test_ok_emits_tags_and_types_selected(self):
        """Clicking OK emits the tags_and_types_selected signal with current selections."""
        dlg = TagFilterWindow(
            all_tags={"work", "personal"},
            selected_tags={"work"},
            all_types={"web", "folder"},
            selected_types={"web"},
        )
        spy = QSignalSpy(dlg.tags_and_types_selected)
        dlg._on_ok()
        assert spy.count() == 1
        tags, match_all, types = spy.at(0)
        assert tags == {"work"}
        assert match_all is False
        assert types == {"web"}

    def test_ok_with_match_all(self):
        """OK emits signal with match_all=True when the AND radio is selected."""
        dlg = TagFilterWindow(
            all_tags={"a", "b"},
            selected_tags={"a", "b"},
            match_all=True,
            selected_types=set(),
        )
        spy = QSignalSpy(dlg.tags_and_types_selected)
        dlg._on_ok()
        tags, match_all, types = spy.at(0)
        assert match_all is True

    def test_selection_change_emits_filter_preview(self):
        """Changing tag selection emits the filter_preview signal with updated state."""
        dlg = TagFilterWindow(
            all_tags={"work", "personal", "project"},
            selected_tags=set(),
            selected_types=set(),
        )
        spy = QSignalSpy(dlg.filter_preview)
        _select_items(dlg._tags_list, {"personal"})
        assert spy.count() >= 1
        tags, match_all, types = spy.at(spy.count() - 1)
        assert tags == {"personal"}

    def test_clear_deselects_all(self):
        """Clicking Clear removes all tag and type selections."""
        dlg = TagFilterWindow(
            all_tags={"work", "personal"},
            selected_tags={"work", "personal"},
            all_types={"web"},
            selected_types={"web"},
        )
        dlg._on_clear()
        assert len(dlg._tags_list.selectedItems()) == 0
        assert len(dlg._types_list.selectedItems()) == 0

    def test_cancel_restores_original(self):
        """Cancel restores the filter preview to the original tag selection."""
        dlg = TagFilterWindow(
            all_tags={"work", "personal"},
            selected_tags={"work"},
            selected_types=set(),
        )
        spy = QSignalSpy(dlg.filter_preview)
        _select_items(dlg._tags_list, {"personal"})
        dlg._on_cancel()
        tags, match_all, types = spy.at(spy.count() - 1)
        assert tags == {"work"}

    def test_reject_restores_original(self):
        """Rejecting the dialog (e.g. pressing Escape) restores original selections."""
        dlg = TagFilterWindow(
            all_tags={"work", "personal"},
            selected_tags={"work"},
            match_all=True,
            selected_types=set(),
        )
        spy = QSignalSpy(dlg.filter_preview)
        _select_items(dlg._tags_list, {"personal"})
        dlg.reject()
        tags, match_all, types = spy.at(spy.count() - 1)
        assert tags == {"work"}
        assert match_all is True
