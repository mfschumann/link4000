"""
Link4000 - Link Manager Application

A desktop application for managing bookmarks/links with tagging support.
"""

import sys
import os
import json
import argparse
from typing import Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import QFile, QDir

from link4000.ui.main_window import MainWindow
from link4000.models.link import Link
from link4000.data.link_store import LinkStore


def _setup_resources_path() -> None:
    """Configure Qt resource search path for bundled resources."""
    if getattr(sys, "_MEIPASS", None):
        base_path: str = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    resources_path = os.path.join(base_path, "resources")
    if QDir(resources_path).exists():
        QDir.addSearchPath("resources", resources_path)


# Initialize resource paths on module load
_setup_resources_path()


def _get_app_icon() -> QIcon:
    """Return the application icon from resources or system theme."""
    icon_paths: list[str] = ["resources:icon.svg"]
    for path in icon_paths:
        if QFile.exists(path):
            return QIcon(path)
    return QIcon.fromTheme(
        "link", QIcon.fromTheme("insert-link", QIcon.fromTheme("chain"))
    )


class LinkManagerApp:
    """Main application controller for Link4000."""

    def __init__(self) -> None:
        self._app: QApplication = QApplication(sys.argv)
        self._app.setApplicationName("Link4000")
        self._app.setApplicationDisplayName("Link Manager")
        self._app.setWindowIcon(_get_app_icon())
        self._window: Optional[MainWindow] = None

    def run(self) -> int:
        """Show the main window and run the application event loop."""
        self._window = MainWindow()
        self._window.show()
        return self._app.exec()


def _detect_schema(data: dict | list) -> str:
    """Detect whether the input data uses 'legacy' or 'current' schema.

    Args:
        data: Parsed JSON data (dict or list)

    Returns:
        'legacy' if data uses keywords instead of tags, 'current' otherwise
    """
    if isinstance(data, list):
        return "legacy"
    links = data.get("links", [])
    if not links:
        return "current"
    first_link = links[0]
    if "keywords" in first_link:
        return "legacy"
    return "current"


def _import_links(source_path: str, override: bool = False) -> int:
    """Import links from a JSON file into the configured links.json.

    Args:
        source_path: Path to the source JSON file
        override: If True, overwrite existing links with the same URL

    Returns:
        Exit code (0 for success, 1 for error)
    """
    source_path = os.path.expanduser(source_path)

    if not os.path.exists(source_path):
        print(f"Error: File not found: {source_path}")
        return 1

    try:
        with open(source_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {source_path}: {e}")
        return 1

    schema = _detect_schema(data)

    if schema == "legacy":
        if not isinstance(data, list):
            print(f"Error: Expected a list for legacy schema, got {type(data)}")
            return 1
        links_data = data
    else:
        links_data = data.get("links", [])

    if not links_data:
        print("No links found in the source file.")
        return 0

    print(f"Detected {schema} schema ({len(links_data)} links)")

    if schema == "legacy":
        links: list[Link] = [Link.from_legacy_dict(d) for d in links_data]
    else:
        links = [Link.from_dict(d) for d in links_data]

    store = LinkStore()
    added, skipped, updated = store.import_links(links, override=override)

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


def _print_config_section(name: str, section: dict) -> None:
    """Print a config section as TOML.

    Args:
        name: Section name (e.g., "global", "colors")
        section: Dictionary of config values
    """
    print(f"[{name}]")
    for key, value in section.items():
        if isinstance(value, list):
            print(f'{key} = {value!r}')
        elif isinstance(value, bool):
            print(f"{key} = {'true' if value else 'false'}")
        elif isinstance(value, str):
            print(f'{key} = "{value}"')
        else:
            print(f"{key} = {value!r}")


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
        _print_config_section("global", full_cfg.get("global", {}))
        print()
        for source_name, source_cfg in full_cfg.get("sources", {}).items():
            print(f"[sources.{source_name}]")
            for key, value in source_cfg.items():
                print(f"{key} = {value!r}")
            print()
        _print_config_section("colors", full_cfg.get("colors", {}))
        print()
        ext_cfg = full_cfg.get("extensions", {})
        if ext_cfg:
            _print_config_section("extensions", ext_cfg)
            print()
        onedrive_cfg = full_cfg.get("onedrive", {})
        if onedrive_cfg:
            print("[onedrive]")
            for key, value in onedrive_cfg.items():
                print(f"{key} = {value!r}")
            print()
        return 0

    if args.import_file:
        return _import_links(args.import_file, args.override_existing)

    app = LinkManagerApp()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
