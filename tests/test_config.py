"""Unit tests for configuration management."""

import pytest

from link4000.utils import config

# Skip all tests if PySide6 is not available
try:
    from PySide6.QtGui import QColor  # noqa: F401

    _has_pyside6 = True
except ImportError:
    _has_pyside6 = False

pytestmark = pytest.mark.skipif(not _has_pyside6, reason="PySide6 not available")


class TestConfigDefaults:
    """Test default configuration values."""

    @pytest.fixture(autouse=True)
    def _isolate_from_live_config(self, tmp_path):
        """Ensure tests read defaults, not a live ~/.link4000/config.toml."""
        original_path = config._CONFIG_PATH
        original_cached = config._config
        config._CONFIG_PATH = str(tmp_path / "nonexistent_config.toml")
        config._config = None
        yield
        config._CONFIG_PATH = original_path
        config._config = original_cached

    def test_default_colors(self):
        """Test default color values."""
        from PySide6.QtGui import QColor

        # These should not raise exceptions
        color = config.get_color_for_link("https://example.com", "web", "")
        assert isinstance(color, QColor)

        color = config.get_color_for_link("/path/to/folder", "folder", "")
        assert isinstance(color, QColor)

        color = config.get_color_for_link("/path/to/file.txt", "file", ".txt")
        assert isinstance(color, QColor)

    def test_default_sharepoint_patterns(self):
        """Test default SharePoint patterns."""
        patterns = config.get_sharepoint_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0

    def test_default_links_file_path(self):
        """Test default links file path."""
        path = config.get_links_file_path()
        assert path.endswith("links.json")
        assert ".link4000" in path

    def test_default_theme(self):
        """Test default theme value."""
        theme = config.get_theme()
        assert theme in ["light", "dark"]

    def test_default_tray_behavior(self):
        """Test default tray behavior value."""
        behavior = config.get_tray_behavior()
        assert behavior == "close_to_tray"

    def test_default_enabled_sources(self):
        """Test default enabled sources list contains expected values."""
        sources = config.get_enabled_sources()
        assert isinstance(sources, list)
        assert "recent_windows" in sources
        assert "recent_linux_gnome" in sources
        assert "office_recent" in sources
        assert "edge_favorites" in sources
        assert "edge_history" in sources

    def test_default_exclusion_patterns(self):
        """Test default exclusion_patterns is an empty list."""
        patterns = config.get_exclusion_patterns()
        assert isinstance(patterns, list)
        assert patterns == []


class TestConfigWithFile:
    """Test configuration with custom config file."""

    @pytest.fixture
    def temp_config(self, tmp_path):
        """Create a temporary config file."""
        config_dir = tmp_path / ".link4000"
        config_dir.mkdir()

        # Temporarily override config path
        original_path = config._CONFIG_PATH
        config_file = config_dir / "config.toml"
        config._CONFIG_PATH = str(config_file)
        config._config = None  # Reset cached config

        yield str(config_file)

        # Restore original
        config._CONFIG_PATH = original_path
        config._config = None

    def test_custom_links_file(self, temp_config):
        """Test loading custom links file path."""
        with open(temp_config, "w") as f:
            f.write("""
[global]
links_file = "/custom/path/links.json"
""")

        path = config.get_links_file_path()
        assert path == "/custom/path/links.json"

    def test_custom_theme(self, temp_config):
        """Test loading custom theme."""
        with open(temp_config, "w") as f:
            f.write("""
[global]
theme = "dark"
""")

        theme = config.get_theme()
        assert theme == "dark"

    def test_custom_tray_behavior_close_to_tray(self, temp_config):
        """Test loading close_to_tray tray behavior."""
        with open(temp_config, "w") as f:
            f.write("""
[global]
tray_behavior = "close_to_tray"
""")

        behavior = config.get_tray_behavior()
        assert behavior == "close_to_tray"

    def test_custom_tray_behavior_minimize_to_tray(self, temp_config):
        """Test loading minimize_to_tray tray behavior."""
        with open(temp_config, "w") as f:
            f.write("""
[global]
tray_behavior = "minimize_to_tray"
""")

        behavior = config.get_tray_behavior()
        assert behavior == "minimize_to_tray"

    def test_custom_tray_behavior_normal(self, temp_config):
        """Test loading normal tray behavior."""
        with open(temp_config, "w") as f:
            f.write("""
[global]
tray_behavior = "normal"
""")

        behavior = config.get_tray_behavior()
        assert behavior == "normal"

    def test_invalid_tray_behavior_falls_back_to_default(self, temp_config):
        """Test that invalid tray behavior falls back to default."""
        with open(temp_config, "w") as f:
            f.write("""
[global]
tray_behavior = "invalid_value"
""")

        behavior = config.get_tray_behavior()
        assert behavior == "close_to_tray"

    def test_custom_enabled_sources(self, temp_config):
        """Test disabling a source via per-source enabled option."""
        with open(temp_config, "w") as f:
            f.write("""
[sources.recent_windows]
enabled = false
""")

        sources = config.get_enabled_sources()
        assert "recent_windows" not in sources
        assert "recent_linux_gnome" in sources  # still enabled by default

    def test_custom_colors(self, temp_config):
        """Test loading custom colors."""
        with open(temp_config, "w") as f:
            f.write("""
[colors]
web = "#FF0000"
folder = "#00FF00"
""")

        color = config.get_color_for_link("https://example.com", "web", "")
        assert color.name() == "#ff0000"

    def test_extension_colors(self, temp_config):
        """Test custom extension colors."""
        with open(temp_config, "w") as f:
            f.write("""
[extensions]
".pdf" = "#FF5500"
".docx" = "#0055FF"
""")

        color = config.get_color_for_link("file.pdf", "file", ".pdf")
        assert color.name() == "#ff5500"


class TestSetConfigPath:
    """Test set_config_path() overrides the config file location."""

    @pytest.fixture(autouse=True)
    def _restore_after(self):
        """Save and restore module-level config state after each test."""
        original_path = config._CONFIG_PATH
        original_default = config._DEFAULT_CONFIG_PATH
        original_cached = config._config
        yield
        config._CONFIG_PATH = original_path
        config._DEFAULT_CONFIG_PATH = original_default
        config._config = original_cached

    def test_sets_config_path(self, tmp_path):
        """set_config_path updates _CONFIG_PATH."""
        target = tmp_path / "custom.toml"
        target.write_text('[global]\ntheme = "dark"\n')
        config.set_config_path(str(target))
        assert config._CONFIG_PATH == str(target)

    def test_resets_cached_config(self):
        """set_config_path clears the cached config so it reloads."""
        config._config = {"colors": {"web": "#AAAAAA"}}
        config.set_config_path("/nonexistent/path.toml")
        assert config._config is None

    def test_expands_tilde(self):
        """set_config_path expands ~ to the home directory."""
        config.set_config_path("~/myconfig.toml")
        assert config._CONFIG_PATH.endswith("/myconfig.toml")
        assert "~" not in config._CONFIG_PATH

    def test_loads_from_overridden_path(self, tmp_path):
        """Config values come from the path set via set_config_path."""
        target = tmp_path / "alt.toml"
        target.write_text('[global]\ntheme = "dark"\n')
        config.set_config_path(str(target))
        assert config.get_theme() == "dark"

    def test_ensure_config_uses_overridden_path(self, tmp_path):
        """ensure_config_exists creates the file at the overridden path."""
        target = tmp_path / "new.toml"
        assert not target.exists()
        config.set_config_path(str(target))
        config.ensure_config_exists()
        assert target.exists()
        assert "[global]" in target.read_text()


class TestEnsureConfigExists:
    """Test config file creation."""

    def test_creates_config_if_missing(self, tmp_path, monkeypatch):
        """Test that config file is created if missing."""
        config_dir = tmp_path / ".link4000"
        config_file = config_dir / "config.toml"

        monkeypatch.setattr(config, "_CONFIG_PATH", str(config_file))
        config._config = None

        config.ensure_config_exists()

        assert config_file.exists()

        content = config_file.read_text()
        assert "[global]" in content
        assert "[sources.recent_windows]" in content
        assert "[colors]" in content
        assert "tray_behavior" in content
        assert "enabled =" in content


class TestGetAzureCliPath:
    """Test get_azure_cli_path function."""

    @pytest.fixture
    def temp_config(self, tmp_path):
        """Create a temporary config file."""
        config_dir = tmp_path / ".link4000"
        config_dir.mkdir()

        original_path = config._CONFIG_PATH
        config_file = config_dir / "config.toml"
        config._CONFIG_PATH = str(config_file)
        config._config = None

        yield str(config_file)

        config._CONFIG_PATH = original_path
        config._config = None

    def test_default_azure_cli_path(self, temp_config):
        """Test that default azure_cli_path is 'az'."""
        with open(temp_config, "w") as f:
            f.write("")
        path = config.get_azure_cli_path()
        assert path == "az"

    def test_custom_azure_cli_path(self, temp_config):
        """Test custom azure_cli_path configuration."""
        with open(temp_config, "w") as f:
            f.write("""
[onedrive]
azure_cli_path = "C:/Program Files/Azure/az.exe"
""")
        path = config.get_azure_cli_path()
        assert path == "C:/Program Files/Azure/az.exe"

    def test_custom_azure_cli_path_unix(self, temp_config):
        """Test custom azure_cli_path with unix path."""
        with open(temp_config, "w") as f:
            f.write("""
[onedrive]
azure_cli_path = "/usr/local/bin/az"
""")
        path = config.get_azure_cli_path()
        assert path == "/usr/local/bin/az"
