"""Unit tests for AddLinkDialog."""

from unittest.mock import patch

import pytest

from link4000.models.link import Link

try:
    from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: F401

    from link4000.ui.add_link_dialog import AddLinkDialog

    _has_pyside6 = True
except ImportError:
    _has_pyside6 = False

pytestmark = pytest.mark.skipif(not _has_pyside6, reason="PySide6 not available")

_mock_warning = patch("link4000.ui.add_link_dialog.QMessageBox.warning", return_value=0)


class TestAddLinkDialogAddMode:
    """Tests for AddLinkDialog in add mode (no existing link)."""

    def test_window_title_add(self):
        """Add mode dialog shows 'Add Link' in the window title."""
        dlg = AddLinkDialog()
        assert dlg.windowTitle() == "Add Link"

    def test_fields_empty_by_default(self):
        """All input fields are empty when no arguments are passed."""
        dlg = AddLinkDialog()
        assert dlg._title_input.text() == ""
        assert dlg._url_input.text() == ""
        assert dlg._tags_input.text() == ""

    def test_constructor_prefills_url(self):
        """Providing a URL prefills the URL input field."""
        dlg = AddLinkDialog(url="https://example.com")
        assert dlg._url_input.text() == "https://example.com"

    def test_constructor_prefills_title_from_file_path(self):
        """A file path URL is used to auto-fill the title with the filename."""
        dlg = AddLinkDialog(url="/some/path/document.pdf")
        assert dlg._title_input.text() == "document.pdf"

    def test_get_link_after_save(self):
        """After saving, get_link returns a Link with correct title, URL, and tags."""
        dlg = AddLinkDialog()
        dlg._title_input.setText("My Link")
        dlg._url_input.setText("https://example.com")
        dlg._tags_input.setText("work, important")
        dlg._on_save()
        link = dlg.get_link()
        assert link is not None
        assert link.title == "My Link"
        assert link.url == "https://example.com"
        assert link.tags == ["work", "important"]

    def test_tag_parsing_strips_whitespace(self):
        """Tag input is split on commas and surrounding whitespace is removed."""
        dlg = AddLinkDialog()
        dlg._title_input.setText("T")
        dlg._url_input.setText("https://example.com")
        dlg._tags_input.setText("  work ,  important  , ")
        dlg._on_save()
        link = dlg.get_link()
        assert link.tags == ["work", "important"]

    def test_validation_empty_title(self):
        """Saving with an empty title shows a warning and does not accept the dialog."""
        dlg = AddLinkDialog()
        dlg._title_input.setText("")
        dlg._url_input.setText("https://example.com")
        with _mock_warning:
            dlg._on_save()
        # Should not accept — dialog should still be open
        assert not dlg.result()

    def test_validation_empty_url(self):
        """Saving with an empty URL shows a warning and does not accept the dialog."""
        dlg = AddLinkDialog()
        dlg._title_input.setText("My Link")
        dlg._url_input.setText("")
        with _mock_warning:
            dlg._on_save()
        assert not dlg.result()

    def test_no_delete_button_in_add_mode(self):
        """Add mode does not provide a delete button."""
        dlg = AddLinkDialog()
        assert not hasattr(dlg, "_delete_button")


class TestAddLinkDialogEditMode:
    """Tests for AddLinkDialog in edit mode (existing link)."""

    def test_window_title_edit(self):
        """Edit mode dialog shows 'Edit Link' in the window title."""
        link = Link(title="Edit Me", url="https://example.com", tags=["a"])
        dlg = AddLinkDialog(link=link)
        assert dlg.windowTitle() == "Edit Link"

    def test_fields_populated_from_link(self):
        """Input fields are populated with the existing link's data."""
        link = Link(title="Edit Me", url="https://example.com", tags=["a", "b"])
        dlg = AddLinkDialog(link=link)
        assert dlg._title_input.text() == "Edit Me"
        assert dlg._url_input.text() == "https://example.com"
        assert dlg._tags_input.text() == "a, b"

    def test_edit_updates_original_link(self):
        """Saving edits mutates the original link object in place."""
        link = Link(title="Old", url="https://old.com", tags=[])
        dlg = AddLinkDialog(link=link)
        dlg._title_input.setText("New")
        dlg._url_input.setText("https://new.com")
        dlg._tags_input.setText("updated")
        dlg._on_save()
        assert link.title == "New"
        assert link.url == "https://new.com"
        assert link.tags == ["updated"]

    def test_has_delete_button_in_edit_mode(self):
        """Edit mode includes a delete button."""
        link = Link(title="X", url="https://x.com")
        dlg = AddLinkDialog(link=link)
        assert hasattr(dlg, "_delete_button")

    def test_title_not_auto_filled_in_edit_mode(self):
        """When editing, the title should not auto-fill from URL changes."""
        link = Link(title="Custom Title", url="https://old.com")
        dlg = AddLinkDialog(link=link)
        dlg._url_input.setText("/new/path/file.txt")
        assert dlg._title_input.text() == "Custom Title"


class TestAddLinkDialogTagCompletion:
    """Tests for tag auto-completion."""

    def test_completer_created_with_tags(self):
        """A tag completer is created when available tags are provided."""
        dlg = AddLinkDialog(all_tags={"work", "personal", "project"})
        assert hasattr(dlg, "_completer")

    def test_no_completer_without_tags(self):
        """No tag completer is created when no tags are available."""
        dlg = AddLinkDialog(all_tags=set())
        assert not hasattr(dlg, "_completer")

    def test_update_completer_filters_matches(self):
        """Completer suggestions are filtered to matching tags as the user types."""
        dlg = AddLinkDialog(all_tags={"work", "personal", "project"})
        dlg._tags_input.setText("wor")
        dlg._on_tags_text_changed("wor")
        model = dlg._completer.model()
        completions = [model.data(model.index(i, 0)) for i in range(model.rowCount())]
        assert "work" in completions
        assert "personal" not in completions

    def test_completer_preserves_existing_tag_capitalization(self):
        """Suggestions use the original tag's capitalization, not user's input."""
        dlg = AddLinkDialog(all_tags={"Foo", "Bar", "Baz"})
        dlg._tags_input.setText("f")
        dlg._on_tags_text_changed("f")
        model = dlg._completer.model()
        completions = [model.data(model.index(i, 0)) for i in range(model.rowCount())]
        assert "Foo" in completions
        assert "fFoo" not in completions

    def test_completer_preserves_arbitrary_capitalization(self):
        """Suggestions preserve any capitalization like FOO, foO, etc."""
        dlg = AddLinkDialog(all_tags={"FOO", "foO", "Foo"})
        dlg._tags_input.setText("f")
        dlg._on_tags_text_changed("f")
        model = dlg._completer.model()
        completions = [model.data(model.index(i, 0)) for i in range(model.rowCount())]
        assert "FOO" in completions
        assert "foO" in completions
        assert "Foo" in completions
        assert "fFOO" not in completions
