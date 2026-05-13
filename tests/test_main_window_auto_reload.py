"""Unit tests for auto-reload timer functionality in MainWindow."""

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

    # Override config path and reset cache
    original_path = config_mod._CONFIG_PATH
    original_cached = config_mod._config
    config_mod._CONFIG_PATH = str(config_file)
    config_mod._config = None

    # Ensure config is created with defaults before test writes custom
    config_mod.ensure_config_exists()

    yield str(config_file)

    # Restore original
    config_mod._CONFIG_PATH = original_path
    config_mod._config = original_cached


class TestAutoReloadTimer:
    """Test MainWindow auto-reload timer behavior."""

    def test_timer_starts_with_default_interval_and_enabled_sources(self, temp_config):
        """Timer is created when reload_interval_minutes > 0 and sources enabled."""
        # Default config has reload_interval_minutes = 15 and sources enabled.
        win = MainWindow()

        assert win._auto_reload_timer is not None
        assert win._auto_reload_timer.isActive()
        # Interval in milliseconds: 15 minutes = 900,000 ms
        assert win._auto_reload_timer.interval() == 15 * 60 * 1000

        win.close()
        win.deleteLater()

    def test_timer_not_started_when_interval_zero(self, temp_config):
        """Timer is not created when reload_interval_minutes = 0."""
        with open(temp_config, "w") as f:
            f.write("""
[global]
reload_interval_minutes = 0
""")
        from link4000.utils import config as config_mod

        config_mod._config = None

        win = MainWindow()

        assert win._auto_reload_timer is None

        win.close()
        win.deleteLater()

    def test_timer_not_started_when_no_enabled_sources(self, temp_config):
        """Timer is not created when all sources are disabled."""
        with open(temp_config, "w") as f:
            f.write("""
[sources.recent_windows]
enabled = false

[sources.recent_linux_gnome]
enabled = false

[sources.office_recent]
enabled = false

[sources.edge_favorites]
enabled = false

[sources.edge_history]
enabled = false

[global]
reload_interval_minutes = 15
""")
        from link4000.utils import config as config_mod

        config_mod._config = None

        win = MainWindow()

        assert win._auto_reload_timer is None

        win.close()
        win.deleteLater()

    def test_timer_stops_on_close(self, temp_config):
        """Timer is stopped when window is closed."""
        win = MainWindow()

        timer = win._auto_reload_timer
        assert timer is not None and timer.isActive()

        # Simulate close event
        from PySide6.QtGui import QCloseEvent

        event = QCloseEvent()
        win.closeEvent(event)

        # After closeEvent, timer should be stopped and set to None
        assert win._auto_reload_timer is None
        # timer should have been stopped
        assert not timer.isActive()

        win.deleteLater()
