"""Unit tests for BulkEditTagsDialog."""

import pytest

try:
    from PySide6.QtWidgets import QApplication  # noqa: F401

    from link4000.ui.bulk_edit_tags_dialog import BulkEditTagsDialog

    _has_pyside6 = True
except ImportError:
    _has_pyside6 = False

pytestmark = pytest.mark.skipif(not _has_pyside6, reason="PySide6 not available")


class TestBulkEditTagsDialog:
    """Tests for BulkEditTagsDialog in add and remove modes."""

    def test_add_mode_title(self):
        """Add mode dialog shows 'Add Tags' in the window title."""
        dlg = BulkEditTagsDialog(
            None, BulkEditTagsDialog.MODE_ADD, 3, {"work", "personal"}
        )
        assert dlg.windowTitle() == "Add Tags"

    def test_remove_mode_title(self):
        """Remove mode dialog shows 'Remove Tags' in the window title."""
        dlg = BulkEditTagsDialog(None, BulkEditTagsDialog.MODE_REMOVE, 2, {"work"})
        assert dlg.windowTitle() == "Remove Tags"

    def test_add_mode_tags_input_exists(self):
        """The tags input widget is present in add mode."""
        dlg = BulkEditTagsDialog(None, BulkEditTagsDialog.MODE_ADD, 5, set())
        assert dlg._tags_input is not None

    def test_get_tags_splits_commas(self):
        """get_tags splits comma-separated input into a list of tag strings."""
        dlg = BulkEditTagsDialog(None, BulkEditTagsDialog.MODE_ADD, 1, set())
        dlg._tags_input.setText("work, important, urgent")
        assert dlg.get_tags() == ["work", "important", "urgent"]

    def test_get_tags_strips_whitespace(self):
        """get_tags strips leading and trailing whitespace from each tag."""
        dlg = BulkEditTagsDialog(None, BulkEditTagsDialog.MODE_ADD, 1, set())
        dlg._tags_input.setText("  work ,  important  ")
        assert dlg.get_tags() == ["work", "important"]

    def test_get_tags_filters_empty(self):
        """get_tags filters out empty entries caused by consecutive commas."""
        dlg = BulkEditTagsDialog(None, BulkEditTagsDialog.MODE_ADD, 1, set())
        dlg._tags_input.setText("work,, ,important,")
        assert dlg.get_tags() == ["work", "important"]

    def test_get_tags_empty_input(self):
        """get_tags returns an empty list when the input field is empty."""
        dlg = BulkEditTagsDialog(None, BulkEditTagsDialog.MODE_ADD, 1, set())
        dlg._tags_input.setText("")
        assert dlg.get_tags() == []

    def test_completer_created_with_tags(self):
        """A tag completer is created when available tags are provided."""
        dlg = BulkEditTagsDialog(
            None, BulkEditTagsDialog.MODE_ADD, 1, {"work", "personal"}
        )
        assert hasattr(dlg, "_completer")

    def test_no_completer_without_tags(self):
        """No tag completer is created when no tags are available."""
        dlg = BulkEditTagsDialog(None, BulkEditTagsDialog.MODE_ADD, 1, set())
        assert not hasattr(dlg, "_completer")
