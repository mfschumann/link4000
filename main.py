"""
Link4000 - Link Manager Application

A desktop application for managing bookmarks/links with tagging support.
"""

import sys
import os
import logging
import traceback
import argparse
from typing import Optional

import tomli_w

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QFile
from PySide6.QtGui import QGuiApplication

from link4000.ui.main_window import MainWindow
from link4000.utils.app_icon import get_app_icon


def _setup_resources_path() -> None:
    """Configure Qt resource search path for bundled resources."""
    if getattr(sys, "_MEIPASS", None):
        base_path: str = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    resources_path = os.path.join(base_path, "resources")
    if QFile(resources_path).exists():
        from PySide6.QtCore import QDir

        QDir.addSearchPath("resources", resources_path)


# Initialize resource paths on module load
_setup_resources_path()


def _setup_logging() -> None:
    """Configure file and stderr logging, plus an unhandled-exception hook."""
    log_dir = os.path.join(os.path.expanduser("~"), ".link4000")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "link4000.log")

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )
    logging.info("Log file: %s", log_file)

    original_excepthook = sys.excepthook

    def excepthook(exc_type, exc_value, exc_tb):
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logging.critical("Unhandled exception:\n%s", tb_text)
        original_excepthook(exc_type, exc_value, exc_tb)

    sys.excepthook = excepthook


# Initialize logging before QApplication and UI setup
_setup_logging()


class LinkManagerApp:
    """Main application controller for Link4000."""

    def __init__(self) -> None:
        self._app: QApplication = QApplication.instance()
        if self._app is None:
            self._app = QApplication(sys.argv)
        self._app.setApplicationName("Link4000")
        self._app.setApplicationDisplayName("Link Manager")
        icon = get_app_icon()
        self._app.setWindowIcon(icon)
        self._window: Optional[MainWindow] = None

    def run(self) -> int:
        """Show the main window and run the application event loop."""
        hints = QGuiApplication.styleHints()
        if hints is not None and hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_color_scheme_changed)
        self._window = MainWindow()
        self._window.show()
        return self._app.exec()

    def _on_color_scheme_changed(self, scheme) -> None:
        """Handle OS color scheme changes at runtime.

        Args:
            scheme: The new Qt.ColorScheme value from the OS.
        """
        icon = get_app_icon()
        self._app.setWindowIcon(icon)
        if self._window is not None:
            self._window.refresh_theme()


def _import_links(source_path: str, override: bool = False) -> int:
    """Import links from a JSON file into the configured links.json.

    Args:
        source_path: Path to the source JSON file
        override: If True, overwrite existing links with the same URL

    Returns:
        Exit code (0 for success, 1 for error)
    """
    from link4000.utils.import_links import do_import

    added, skipped, updated, error = do_import(source_path, override)

    if error:
        print(f"Error: {error}")
        return 1

    parts: list[str] = []
    if added > 0:
        parts.append(f"{added} added")
    if skipped > 0:
        parts.append(f"{skipped} skipped")
    if updated > 0:
        parts.append(f"{updated} updated")
    msg = f"Imported: {', '.join(parts)}" if parts else "No changes"
    print(msg)

    return 0


def main() -> int:
    """Main entry point for the Link4000 application."""
    parser = argparse.ArgumentParser(
        description="Link4000 - Link Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                           Launch the GUI
  python main.py --config ~/my.toml        Use a custom config file
  python main.py --import links.json       Import links from JSON file
  python main.py --import links.json --override-existing  Import and overwrite duplicates
  python main.py --show-config             Output the active configuration
  python main.py --show-default-config     Output the default configuration
        """,
    )
    parser.add_argument(
        "--import",
        dest="import_file",
        metavar="FILE",
        help="Import links from FILE into links.json",
    )
    parser.add_argument(
        "--override-existing",
        action="store_true",
        help="When importing, overwrite existing links with the same URL",
    )
    parser.add_argument(
        "--config",
        dest="config_file",
        metavar="PATH",
        help="Path to the TOML config file (default: ~/.link4000/config.toml)",
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Output the active configuration as TOML and exit",
    )
    parser.add_argument(
        "--show-default-config",
        action="store_true",
        help="Output the default configuration as TOML and exit",
    )
    args = parser.parse_args()

    if args.config_file:
        from link4000.utils.config import set_config_path

        set_config_path(args.config_file)

    if args.show_config:
        from link4000.utils.config import get_full_config

        full_cfg = get_full_config()
        print("# Link4000 Active Configuration")
        print("# This shows all config values with defaults merged with user settings")
        print()
        print(tomli_w.dumps(full_cfg))
        return 0

    if args.show_default_config:
        from link4000.utils.config import _DEFAULTS

        print("# Link4000 Default Configuration")
        print("# This shows the built-in default values")
        print()
        print(tomli_w.dumps(_DEFAULTS))
        return 0

    if args.import_file:
        return _import_links(args.import_file, args.override_existing)

    app = LinkManagerApp()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
