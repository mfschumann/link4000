"""Application icon loading utilities for Link4000.

Handles loading the bundled SVG application icon in both development and
PyInstaller-bundled environments, with light/dark theme awareness.
"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QDir, QFile
from PySide6.QtGui import QIcon

from link4000.utils.config import get_theme

_RESOURCES_PREFIX = "resources"
_LIGHT_ICON = "icon.svg"
_DARK_ICON = "icon_dark.svg"


def _resources_base_path() -> str:
    """Return the directory that contains the ``resources`` folder.

    In a PyInstaller one-file/one-dir bundle, files are extracted to
    ``sys._MEIPASS``. In development, the resources folder is at the project
    root, which is two directories above this module.

    Returns:
        Absolute path to the directory containing the ``resources`` folder.
    """
    if getattr(sys, "_MEIPASS", None):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _register_resource_search_path() -> None:
    """Register the resources directory under the Qt ``resources:`` prefix.

    The prefix is only registered once per unique path so repeated calls do not
    accumulate duplicate search entries.
    """
    resources_path = os.path.join(_resources_base_path(), "resources")
    if not QDir(resources_path).exists():
        return

    existing = set(QDir.searchPaths(_RESOURCES_PREFIX))
    if resources_path not in existing:
        QDir.addSearchPath(_RESOURCES_PREFIX, resources_path)


def get_app_icon() -> QIcon:
    """Return the application icon, theme-aware, from bundled resources.

    Loads the light or dark SVG icon depending on the configured ``theme``
    value. Falls back to system theme icons if no bundled icon is found.

    Returns:
        A ``QIcon`` instance for the application, window, or tray icon.
    """
    _register_resource_search_path()

    theme = get_theme()
    icon_name = _DARK_ICON if theme == "dark" else _LIGHT_ICON
    icon_path = f"{_RESOURCES_PREFIX}:{icon_name}"

    if QFile.exists(icon_path):
        return QIcon(icon_path)

    return QIcon.fromTheme(
        "link", QIcon.fromTheme("insert-link", QIcon.fromTheme("chain"))
    )
