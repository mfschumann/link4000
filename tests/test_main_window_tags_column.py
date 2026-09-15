"""Unit tests for the show_tags_column configuration option."""

import pytest

try:
    from link4000.models.link_model import LinkTableModel
    from link4000.ui.main_window import MainWindow

    _has_pyside6 = True
except ImportError:
    _has_pyside6 = False

pytestmark = pytest.mark.skipif(not _has_pyside6, reason="PySide6 not available")


@pytest.fixture
def temp_config(tmp_path):
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


class TestShowTagsColumn:
    """Tests for the visibility of the Tags column in the main window."""

    def test_tags_column_visible_by_default(self, temp_config):
        """The Tags column is shown when show_tags_column is not disabled."""
        win = MainWindow()

        assert not win._table_view.isColumnHidden(LinkTableModel.COL_TAGS)

        win.close()
        win.deleteLater()

    def test_tags_column_hidden_when_disabled(self, temp_config):
        """The Tags column is hidden when show_tags_column = false."""
        from link4000.utils import config as config_mod

        with open(temp_config, "w") as f:
            f.write("""
[global]
show_tags_column = false
""")
        # Reset the cached config so the new value is picked up.
        config_mod._config = None

        win = MainWindow()

        assert win._table_view.isColumnHidden(LinkTableModel.COL_TAGS)

        win.close()
        win.deleteLater()
