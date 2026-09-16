"""Unit tests for MainWindow UI state persistence (save on quit, restore on start)."""

import json
import os
import pytest
import tomli_w

try:
    from PySide6.QtCore import Qt
    from link4000.models.link import Link
    from link4000.ui.main_window import MainWindow
    from link4000.utils.enums import TagMatchMode
    from link4000.models.link_model import LinkTableModel
    from link4000.utils.ui_state import (
        get_ui_state_file_path,
        save_ui_state,
    )

    _has_pyside6 = True
except ImportError:
    _has_pyside6 = False

pytestmark = pytest.mark.skipif(not _has_pyside6, reason="PySide6 not available")


def _write_config(config_file, tray_behavior: str, links_file) -> None:
    """Write a minimal config file using a TOML writer.

    Using ``tomli_w`` avoids hand-escaping paths: Windows paths contain
    backslashes, which are escape sequences inside TOML basic strings.

    Args:
        config_file: Destination path of the config file.
        tray_behavior: Value for ``[global] tray_behavior``.
        links_file: Path stored in ``[global] links_file``.
    """
    config = {
        "global": {
            "tray_behavior": tray_behavior,
            "links_file": str(links_file),
        }
    }
    with open(config_file, "wb") as f:
        tomli_w.dump(config, f)


@pytest.fixture
def temp_config(tmp_path, monkeypatch):
    """Create a temporary config with links_file pointing to tmp_path."""
    from link4000.utils import config as config_mod

    config_dir = tmp_path / ".link4000"
    config_file = config_dir / "config.toml"
    links_file = tmp_path / "links.json"
    config_dir.mkdir()

    original_path = config_mod._CONFIG_PATH
    original_cached = config_mod._config
    config_mod._CONFIG_PATH = str(config_file)
    config_mod._config = None

    _write_config(config_file, "normal", links_file)

    yield str(config_file)

    config_mod._CONFIG_PATH = original_path
    config_mod._config = original_cached


class TestSaveOnTrueQuit:
    def test_close_to_tray_hide_does_not_save(self, temp_config, monkeypatch):
        """Hiding to tray via closeEvent does not write state file."""
        # Force the close_to_tray behavior regardless of the config file.
        monkeypatch.setattr(
            "link4000.ui.main_window.get_tray_behavior",
            lambda: "close_to_tray",
        )

        state_path = get_ui_state_file_path()

        win = MainWindow()
        win.show()

        assert not os.path.exists(state_path)

        from PySide6.QtGui import QCloseEvent

        event = QCloseEvent()
        win.closeEvent(event)

        assert not event.isAccepted()
        assert not os.path.exists(state_path)

        win.deleteLater()

    def test_normal_close_saves_state(self, temp_config, monkeypatch):
        """Normal close (tray_behavior=normal) saves state."""
        from PySide6.QtGui import QCloseEvent

        state_path = get_ui_state_file_path()
        win = MainWindow()
        win.show()

        event = QCloseEvent()
        win.closeEvent(event)

        assert event.isAccepted()
        assert os.path.exists(state_path)

        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        assert "search_text" in state
        assert "selected_tags" in state
        assert "match_mode" in state
        assert "sorting_active" in state

        win.deleteLater()

    def test_quit_saves_state(self, temp_config):
        """Quit via menu saves state."""
        state_path = get_ui_state_file_path()
        win = MainWindow()
        win.show()

        assert not os.path.exists(state_path)

        win._save_ui_state()

        assert os.path.exists(state_path)

        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        assert state["search_text"] == ""

        win.deleteLater()


class TestRestoreOnStart:
    def test_missing_state_keeps_defaults(self, temp_config):
        """Missing ui_state.json leaves default sort/search/filters."""
        assert not os.path.exists(get_ui_state_file_path())

        win = MainWindow()
        win.show()

        assert win._search_input.text() == ""
        assert win._proxy_model._search_text == ""
        assert win._selected_tags == set()
        assert win._current_sort_column == LinkTableModel.COL_LAST_ACCESSED

        win.deleteLater()

    def test_restore_search_text(self, temp_config):
        """Search text is restored on next start."""
        save_ui_state(
            {
                "search_text": "report",
                "selected_tags": [],
                "match_mode": "OR",
                "selected_types": [],
                "sorting_active": False,
                "sort_column": LinkTableModel.COL_LAST_ACCESSED,
                "sort_order": "desc",
            }
        )

        win = MainWindow()
        win.show()

        assert win._search_input.text() == "report"
        assert win._proxy_model._search_text == "report"

        win.deleteLater()

    def test_restore_tags_and_mode(self, temp_config):
        """Tag filters and match mode are restored when tags exist."""
        from link4000.data.link_store import LinkStore

        store = LinkStore()
        store.add(
            Link(
                title="Work Doc",
                url="https://work.example.com",
                tags=["work", "urgent"],
                id="test1",
                source_tag="",
            )
        )

        save_ui_state(
            {
                "search_text": "",
                "selected_tags": ["work"],
                "match_mode": "AND",
                "selected_types": [],
                "sorting_active": False,
                "sort_column": LinkTableModel.COL_LAST_ACCESSED,
                "sort_order": "desc",
            }
        )

        win = MainWindow()
        win.show()

        assert "work" in win._selected_tags
        assert win._match_mode == TagMatchMode.AND

        win.deleteLater()

    def test_stale_tags_pruned(self, temp_config):
        """Tags not in current link set are pruned during restore."""
        save_ui_state(
            {
                "search_text": "",
                "selected_tags": ["nonexistent"],
                "match_mode": "OR",
                "selected_types": [],
                "sorting_active": False,
                "sort_column": LinkTableModel.COL_LAST_ACCESSED,
                "sort_order": "desc",
            }
        )

        win = MainWindow()
        win.show()

        assert "nonexistent" not in win._selected_tags
        assert win._selected_tags == set()

        win.deleteLater()

    def test_restore_combo_sort(self, temp_config):
        """Combo-based sort (Created/Modified) is restored."""
        save_ui_state(
            {
                "search_text": "",
                "selected_tags": [],
                "match_mode": "OR",
                "selected_types": [],
                "sorting_active": True,
                "sort_column": LinkTableModel.COL_TITLE,
                "sort_order": "asc",
            }
        )

        win = MainWindow()
        win.show()

        assert win._sorting_active is True
        assert win._current_sort_column == LinkTableModel.COL_TITLE
        assert win._current_sort_order == Qt.SortOrder.AscendingOrder

        win.deleteLater()

    def test_restore_header_sort(self, temp_config):
        """Header-click sort is restored when sorting_active is False."""
        save_ui_state(
            {
                "search_text": "",
                "selected_tags": [],
                "match_mode": "OR",
                "selected_types": [],
                "sorting_active": False,
                "sort_column": LinkTableModel.COL_LAST_ACCESSED,
                "sort_order": "asc",
            }
        )

        win = MainWindow()
        win.show()

        assert win._sorting_active is False
        assert win._current_sort_column == LinkTableModel.COL_LAST_ACCESSED

        win.deleteLater()

    def test_restore_invalid_falls_back(self, temp_config):
        """Invalid values fall back to defaults without breaking other fields."""
        save_ui_state(
            {
                "search_text": "valid",
                "selected_tags": "not-a-list",
                "match_mode": "INVALID",
                "selected_types": "not-a-list",
                "sorting_active": "not-a-bool",
                "sort_column": 999,
                "sort_order": "invalid",
            }
        )

        win = MainWindow()
        win.show()

        assert win._search_input.text() == "valid"

        win.deleteLater()
