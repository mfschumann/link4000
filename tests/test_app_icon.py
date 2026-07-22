"""Unit tests for the application icon loader."""

import sys
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QDir

from link4000.utils import app_icon, config


@pytest.fixture(autouse=True)
def _restore_state():
    """Save and restore config and Qt search path state after each test."""
    original_config_path = config._CONFIG_PATH
    original_config = config._config
    original_search_paths = list(QDir.searchPaths("resources"))
    yield
    config._CONFIG_PATH = original_config_path
    config._config = original_config
    QDir.setSearchPaths("resources", original_search_paths)


_VALID_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
    '<rect width="16" height="16" fill="red"/></svg>'
)


def _write_test_icons(resources_dir):
    """Create both light and dark icons so theme does not affect the test."""
    (resources_dir / "icon.svg").write_text(_VALID_SVG)
    (resources_dir / "icon_dark.svg").write_text(_VALID_SVG)


class TestGetAppIcon:
    """Tests for ``app_icon.get_app_icon``."""

    def test_returns_non_null_icon(self):
        """The icon loader returns a valid QIcon when bundled resources exist."""
        icon = app_icon.get_app_icon()
        assert not icon.isNull()

    def test_uses_light_icon_by_default(self, tmp_path):
        """With the default light theme, the loader requests icon.svg."""
        config_path = tmp_path / "config.toml"
        config_path.write_text('[global]\ntheme = "light"\n')
        config.set_config_path(str(config_path))

        with (
            patch.object(app_icon, "QIcon") as mock_qicon,
            patch.object(app_icon, "QFile") as mock_qfile,
        ):
            mock_qicon.return_value = MagicMock()
            mock_qfile.exists.return_value = True
            app_icon.get_app_icon()

        requested_paths = [
            str(call.args[0]) for call in mock_qicon.call_args_list if call.args
        ]
        assert any("icon.svg" in p for p in requested_paths)
        assert not any("icon_dark.svg" in p for p in requested_paths)

    def test_uses_dark_icon_when_theme_is_dark(self, tmp_path):
        """With theme="dark", the loader requests icon_dark.svg."""
        config_path = tmp_path / "config.toml"
        config_path.write_text('[global]\ntheme = "dark"\n')
        config.set_config_path(str(config_path))

        with (
            patch.object(app_icon, "QIcon") as mock_qicon,
            patch.object(app_icon, "QFile") as mock_qfile,
        ):
            mock_qicon.return_value = MagicMock()
            mock_qfile.exists.return_value = True
            app_icon.get_app_icon()

        requested_paths = [
            str(call.args[0]) for call in mock_qicon.call_args_list if call.args
        ]
        assert any("icon_dark.svg" in p for p in requested_paths)

    def test_loads_from_pyinstaller_bundle(self, tmp_path, monkeypatch):
        """When sys._MEIPASS is set, the loader looks inside the bundle."""
        resources_dir = tmp_path / "resources"
        resources_dir.mkdir()
        _write_test_icons(resources_dir)
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

        icon = app_icon.get_app_icon()
        assert not icon.isNull()

    def test_resource_search_path_not_duplicated(self, tmp_path, monkeypatch):
        """Calling the loader repeatedly does not add duplicate search paths."""
        resources_dir = tmp_path / "resources"
        resources_dir.mkdir()
        _write_test_icons(resources_dir)
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

        app_icon.get_app_icon()
        app_icon.get_app_icon()

        paths = QDir.searchPaths("resources")
        assert paths.count(str(tmp_path / "resources")) == 1
