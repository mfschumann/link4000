"""Unit tests for UI state persistence (ui_state module)."""

import json
import os
import pytest
import tomli_w

from link4000.utils import ui_state
import link4000.utils.config as config_mod

try:
    from link4000.models.link_model import LinkTableModel

    _has_pyside6 = True
except ImportError:
    _has_pyside6 = False

pytestmark = pytest.mark.skipif(not _has_pyside6, reason="PySide6 not available")


@pytest.fixture
def temp_config_and_state(tmp_path, monkeypatch):
    """Point the config (and thus the state file) at a temporary directory.

    ``links_file`` is written into the temporary config so that
    ``get_ui_state_file_path()`` resolves inside ``tmp_path`` instead of the
    user's real ``~/.link4000`` directory. The config is written with
    ``tomli_w`` because Windows paths contain backslashes, which would be
    interpreted as TOML escape sequences inside a hand-written basic string.
    """
    config_dir = tmp_path / ".link4000"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"
    links_file = tmp_path / "links.json"

    original_path = config_mod._CONFIG_PATH
    original_cached = config_mod._config
    config_mod._CONFIG_PATH = str(config_file)
    config_mod._config = None

    with open(config_file, "wb") as f:
        tomli_w.dump({"global": {"links_file": str(links_file)}}, f)

    yield str(config_file)

    config_mod._CONFIG_PATH = original_path
    config_mod._config = original_cached


class TestGetUiStateFilePath:
    def test_returns_json_path(self, temp_config_and_state):
        """Path is ui_state.json in the links directory."""
        path = ui_state.get_ui_state_file_path()
        assert path.endswith("ui_state.json")
        assert os.path.isabs(path)


class TestLoadUiState:
    def test_missing_file_returns_empty(self, temp_config_and_state, monkeypatch):
        """Missing file returns {}."""
        state = ui_state.load_ui_state()
        assert state == {}

    def test_corrupt_json_returns_empty(self, temp_config_and_state, monkeypatch):
        """Corrupt JSON returns {}."""
        path = ui_state.get_ui_state_file_path()
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not valid json")
        state = ui_state.load_ui_state()
        assert state == {}

    def test_empty_object(self, temp_config_and_state, monkeypatch):
        """Empty JSON object returns {}."""
        path = ui_state.get_ui_state_file_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump({}, f)
        state = ui_state.load_ui_state()
        assert state == {}

    def test_valid_state(self, temp_config_and_state, monkeypatch):
        """Valid JSON returns parsed dict."""
        path = ui_state.get_ui_state_file_path()
        test_data = {
            "search_text": "report",
            "selected_tags": ["work"],
            "match_mode": "OR",
            "selected_types": ["file"],
            "sorting_active": True,
            "sort_column": LinkTableModel.COL_TITLE,
            "sort_order": "asc",
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)
        state = ui_state.load_ui_state()
        assert state == test_data

    def test_extra_keys_ignored(self, temp_config_and_state, monkeypatch):
        """Unknown keys are preserved but callers ignore them."""
        path = ui_state.get_ui_state_file_path()
        test_data = {
            "search_text": "test",
            "unknown_key": "should_not_cause_issues",
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)
        state = ui_state.load_ui_state()
        assert state["search_text"] == "test"


class TestSaveUiState:
    def test_writes_json(self, temp_config_and_state, monkeypatch):
        """State is written as valid JSON."""
        test_state = {
            "search_text": "hello",
            "selected_tags": ["work", "personal"],
            "match_mode": "AND",
            "selected_types": [],
            "sorting_active": False,
            "sort_column": LinkTableModel.COL_LAST_ACCESSED,
            "sort_order": "desc",
        }
        ui_state.save_ui_state(test_state)

        path = ui_state.get_ui_state_file_path()
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == test_state

    def test_creates_directory(self, temp_config_and_state, monkeypatch):
        """Parent directory is created if missing."""
        config_dir = os.path.dirname(config_mod._CONFIG_PATH)
        new_dir = os.path.join(config_dir, "subdir", "nested")
        monkeypatch.setattr(
            ui_state,
            "get_ui_state_file_path",
            lambda: os.path.join(new_dir, "ui_state.json"),
        )

        test_state = {"search_text": ""}
        ui_state.save_ui_state(test_state)
        assert os.path.exists(os.path.join(new_dir, "ui_state.json"))


class TestRoundTrip:
    def test_round_trip_preserves_state(self, temp_config_and_state):
        """Saved state can be loaded back."""
        original = {
            "search_text": "my search",
            "selected_tags": ["work"],
            "match_mode": "AND",
            "selected_types": ["file", "folder"],
            "sorting_active": True,
            "sort_column": LinkTableModel.COL_TITLE,
            "sort_order": "asc",
        }
        ui_state.save_ui_state(original)
        loaded = ui_state.load_ui_state()
        assert loaded == original
