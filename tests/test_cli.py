"""Unit tests for --config CLI argument."""

import pytest
from unittest.mock import patch

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
