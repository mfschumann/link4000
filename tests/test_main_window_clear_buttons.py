"""Unit tests for the search/filter clear buttons in MainWindow."""

import pytest

try:
    from link4000.ui.main_window import MainWindow
    from link4000.utils.enums import TagMatchMode

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


class TestClearButtons:
    """Tests for the split search/filter clear buttons."""

    def test_clear_search_clears_only_search(self, temp_config):
        """The search '✕' clears the search text but keeps active filters."""
        win = MainWindow()

        win._search_input.setText("report")
        win._apply_search()
        win._selected_tags = {"work"}
        win._proxy_model.set_selected_tags({"work"}, TagMatchMode.OR, set())
        win._update_tag_filter_button()

        win._clear_search_button.click()

        assert win._search_input.text() == ""
        assert win._proxy_model._search_text == ""
        assert win._selected_tags == {"work"}
        assert win._proxy_model._selected_tags == {"work"}

        win.close()
        win.deleteLater()

    def test_clear_filters_clears_only_filters(self, temp_config):
        """The filter '✕' clears tag/type filters but keeps the search text."""
        win = MainWindow()

        win._search_input.setText("report")
        win._apply_search()
        win._selected_tags = {"work"}
        win._selected_types = {"file"}
        win._match_mode = TagMatchMode.AND
        win._proxy_model.set_selected_tags(
            {"work"}, TagMatchMode.AND, {"file"}
        )
        win._update_tag_filter_button()

        win._clear_filters_button.click()

        assert win._selected_tags == set()
        assert win._selected_types == set()
        assert win._match_mode == TagMatchMode.OR
        assert win._proxy_model._selected_tags == set()
        assert win._proxy_model._selected_types == set()
        # Search text is untouched
        assert win._search_input.text() == "report"
        assert win._proxy_model._search_text == "report"

        win.close()
        win.deleteLater()

    def test_filter_button_bold_with_only_tags(self, temp_config):
        """Filter button is bold when only tags are selected."""
        win = MainWindow()

        win._selected_tags = {"work"}
        win._selected_types = set()
        win._update_tag_filter_button()

        assert win._tag_filter_button.font().bold() is True

        win.close()
        win.deleteLater()

    def test_filter_button_bold_with_only_types(self, temp_config):
        """Filter button is bold when only types are selected."""
        win = MainWindow()

        win._selected_tags = set()
        win._selected_types = {"file"}
        win._update_tag_filter_button()

        assert win._tag_filter_button.font().bold() is True

        win.close()
        win.deleteLater()

    def test_filter_button_not_bold_without_filters(self, temp_config):
        """Filter button is not bold when no filters are selected."""
        win = MainWindow()

        win._selected_tags = set()
        win._selected_types = set()
        win._update_tag_filter_button()

        assert win._tag_filter_button.font().bold() is False

        win.close()
        win.deleteLater()
