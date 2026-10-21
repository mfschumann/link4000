"""Unit tests for SharePoint parent actions in the main window context menu."""

from unittest.mock import MagicMock, patch

import pytest

try:
    from link4000.models.link import Link
    from link4000.ui.main_window import MainWindow

    _has_pyside6 = True
except ImportError:
    _has_pyside6 = False

pytestmark = pytest.mark.skipif(not _has_pyside6, reason="PySide6 not available")


@pytest.fixture
def temp_config(tmp_path):
    """Create a temporary config file and patch the config module."""
    from link4000.utils import config as config_mod

    config_dir = tmp_path / ".link4000"
    config_file = config_dir / "config.toml"
    config_dir.mkdir()

    original_path = config_mod._CONFIG_PATH
    original_cached = config_mod._config
    config_mod._CONFIG_PATH = str(config_file)
    config_mod._config = None

    config_mod.ensure_config_exists()

    yield str(config_file)

    config_mod._CONFIG_PATH = original_path
    config_mod._config = original_cached


def _menu_action_texts(window: MainWindow, url: str) -> list[str]:
    """Return the context-menu action labels for a link with *url*."""
    link = Link(title="test", url=url)
    menu = window._build_context_menu([link])
    return [action.text() for action in menu.actions()]


class TestSharePointParentContextMenu:
    """Tests for Open/Copy Parent Folder actions on SharePoint links."""

    def test_sharepoint_file_has_parent_actions(self, temp_config):
        """A path-based SharePoint file gets open/copy parent actions."""
        win = MainWindow()
        try:
            texts = _menu_action_texts(
                win,
                "https://t.sharepoint.com/sites/S/Lib/Folder/File.docx",
            )
            assert "Open Parent Folder" in texts
            assert "Copy Parent Folder" in texts
        finally:
            win.close()
            win.deleteLater()

    def test_sharepoint_folder_has_parent_actions(self, temp_config):
        """A path-based SharePoint folder gets open/copy parent actions."""
        win = MainWindow()
        try:
            texts = _menu_action_texts(
                win,
                "https://t.sharepoint.com/sites/S/Lib/Folder",
            )
            assert "Open Parent Folder" in texts
            assert "Copy Parent Folder" in texts
        finally:
            win.close()
            win.deleteLater()

    def test_sharepoint_site_and_library_roots_have_no_parent_actions(
        self, temp_config
    ):
        """Site and library roots do not get parent actions."""
        win = MainWindow()
        try:
            for url in (
                "https://t.sharepoint.com/sites/S",
                "https://t.sharepoint.com/sites/S/Lib",
            ):
                texts = _menu_action_texts(win, url)
                assert "Open Parent Folder" not in texts
                assert "Copy Parent Folder" not in texts
        finally:
            win.close()
            win.deleteLater()

    def test_web_link_has_no_parent_actions(self, temp_config):
        """A normal web link does not get SharePoint parent actions."""
        win = MainWindow()
        try:
            texts = _menu_action_texts(win, "https://example.com/a/b/c")
            assert "Open Parent Folder" not in texts
            assert "Copy Parent Folder" not in texts
        finally:
            win.close()
            win.deleteLater()

    def test_sharepoint_share_token_has_no_parent_actions(self, temp_config):
        """A SharePoint share-token link does not get parent actions."""
        win = MainWindow()
        try:
            texts = _menu_action_texts(
                win,
                "https://t-my.sharepoint.com/:x:/p/user/ID",
            )
            assert "Open Parent Folder" not in texts
            assert "Copy Parent Folder" not in texts
        finally:
            win.close()
            win.deleteLater()

    def test_open_parent_url_opens_browser(self):
        """Opening a parent URL delegates to webbrowser.open."""
        url = "https://t.sharepoint.com/sites/S/Lib/Folder"
        with patch("link4000.ui.main_window.webbrowser.open") as mock_open:
            MainWindow._open_parent_url(url)
        mock_open.assert_called_once_with(url)

    def test_copy_parent_url_sets_clipboard(self, temp_config):
        """Copying a parent URL writes it to the clipboard."""
        win = MainWindow()
        try:
            clipboard = MagicMock()
            with patch(
                "link4000.ui.main_window.QApplication.clipboard",
                return_value=clipboard,
            ):
                win._copy_parent_url(
                    "https://t.sharepoint.com/sites/S/Lib/Folder"
                )
            clipboard.setText.assert_called_once_with(
                "https://t.sharepoint.com/sites/S/Lib/Folder"
            )
        finally:
            win.close()
            win.deleteLater()
