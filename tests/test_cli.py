"""Unit tests for CLI arguments."""

import sys
import pytest
from unittest.mock import patch

try:
    if hasattr(__import__('sys'), 'version_info') and sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
except ImportError:
    import tomli as tomllib

from link4000.utils import config


class TestConfigCliArg:
    """Test --config command-line argument sets the config path."""

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

    def test_config_arg_sets_path(self, tmp_path):
        """--config PATH calls set_config_path before the app starts."""
        target = tmp_path / "cli.toml"
        target.write_text('[global]\ntheme = "dark"\n')

        from main import main

        with (
            patch("sys.argv", ["main.py", "--config", str(target)]),
            patch("main.LinkManagerApp") as MockApp,
        ):
            MockApp.return_value.run.return_value = 0
            main()

        assert config._CONFIG_PATH == str(target)
        assert config.get_theme() == "dark"

    def test_config_arg_with_import(self, tmp_path):
        """--config works together with --import."""
        config_file = tmp_path / "cli.toml"
        config_file.write_text(f'[global]\nlinks_file = "{tmp_path / "links.json"}"\n')

        import_file = tmp_path / "source.json"
        import_file.write_text("[]")

        from main import main

        with patch(
            "sys.argv",
            ["main.py", "--config", str(config_file), "--import", str(import_file)],
        ):
            result = main()

        assert result == 0

    def test_no_config_arg_uses_default(self):
        """Without --config, the default config path is used."""
        from link4000.utils.config import _DEFAULT_CONFIG_PATH
        from main import main

        with patch("sys.argv", ["main.py"]), patch("main.LinkManagerApp") as MockApp:
            MockApp.return_value.run.return_value = 0
            main()

        assert config._CONFIG_PATH == _DEFAULT_CONFIG_PATH

    def test_show_default_config_outputs_valid_toml(self, tmp_path, capsys):
        """--show-default-config outputs valid TOML that can be parsed."""
        from main import main

        with patch("sys.argv", ["main.py", "--show-default-config"]):
            result = main()
            
        assert result == 0
        
        # Capture stdout and verify it's valid TOML
        captured = capsys.readouterr()
        output = captured.out
        
        # Write output to file and verify it's valid TOML
        config_file = tmp_path / "default_config.toml"
        config_file.write_text(output)
        parsed = tomllib.load(open(config_file, "rb"))
        
        # Check that we got expected sections
        assert "global" in parsed
        assert "sources" in parsed
        assert "colors" in parsed
        assert parsed["global"]["theme"] == "light"
        assert parsed["sources"]["edge_history"]["max_age_days"] == 30

    def test_show_config_with_user_overrides(self, tmp_path, capsys):
        """--show-config outputs valid TOML with user overrides when config file exists."""
        from main import main
        from link4000.utils.config import set_config_path

        # Create a temporary config with user overrides
        user_config = tmp_path / "user_config.toml"
        user_config.write_text("""
[global]
theme = "dark"
tray_behavior = "normal"

[sources.edge_history]
enabled = false
max_age_days = 7
""")
        
        # Set the config path to our user config
        set_config_path(str(user_config))

        with patch("sys.argv", ["main.py", "--show-config"]):
            result = main()
            
        assert result == 0
        
        # Capture stdout and verify it's valid TOML
        captured = capsys.readouterr()
        output = captured.out
        
        # Write output to file and verify it's valid TOML
        config_file = tmp_path / "active_config.toml"
        config_file.write_text(output)
        parsed = tomllib.load(open(config_file, "rb"))
        
        # Check that user overrides are present
        assert parsed["global"]["theme"] == "dark"
        assert parsed["global"]["tray_behavior"] == "normal"
        assert parsed["sources"]["edge_history"]["enabled"] is False
        assert parsed["sources"]["edge_history"]["max_age_days"] == 7
        
        # Check that defaults are still present for unspecified values
        assert parsed["global"]["links_file"] == ""
        assert parsed["sources"]["edge_favorites"]["enabled"] is True
