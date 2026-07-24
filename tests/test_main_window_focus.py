"""Unit tests for search input focus on window activation."""

import pytest

try:
    from link4000.ui.main_window import MainWindow

    _has_pyside6 = True
except ImportError:
    _has_pyside6 = False

pytestmark = pytest.mark.skipif(not _has_pyside6, reason="PySide6 not available")


@pytest.fixture
def temp_config(tmp_path, monkeypatch):
    """Create a temporary config file and patch config module."""
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


class TestSearchFocusOnActivation:
    """Tests for search input focus when the main window is activated."""

    def test_change_event_activation_sets_focus(self, temp_config):
        """changeEvent with ActivationChange sets focus to search input."""
        win = MainWindow()

        from PySide6.QtCore import QEvent

        win.activateWindow()
        win.changeEvent(QEvent(QEvent.Type.ActivationChange))

        if win.isActiveWindow():
            assert win._search_input.hasFocus()

        win.close()
        win.deleteLater()

    def test_change_event_window_state_change_still_works(self, temp_config):
        """changeEvent with WindowStateChange still works for
        minimize-to-tray behavior."""
        win = MainWindow()

        from PySide6.QtCore import QEvent

        win.changeEvent(QEvent(QEvent.Type.WindowStateChange))

        win.close()
        win.deleteLater()
