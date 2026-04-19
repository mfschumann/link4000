"""Configuration loading and link color resolution for Link4000."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtGui import QColor

_DEFAULT_CONFIG_PATH = os.path.join(os.path.expanduser("~/.link4000"), "config.toml")
_CONFIG_PATH = _DEFAULT_CONFIG_PATH

_DEFAULTS = {
    "global": {
        "links_file": "",
        "sharepoint_patterns": [
            r"sharepoint\.com/.*",
            r"onedrive\.live\.com/.*",
        ],
        "exclusion_patterns": [],
        "theme": "light",
        "tray_behavior": "close_to_tray",
    },
    "sources": {
        "enabled": ["json_store", "recent_windows", "recent_linux_gnome", "office_recent", "edge_favorites"],
    },
    "colors": {
        "web": "#0066CC",
        "folder": "#FF9500",
        "file": "#333333",
        "sharepoint": "#7038C8",
        "unknown": "#999999",
    },
    "extensions": {},
}


def _load_config() -> dict:
    """Load config from ~/.link4000/config.toml, falling back to defaults."""
    if not os.path.exists(_CONFIG_PATH):
        return _DEFAULTS.copy()

    if sys.version_info >= (3, 11):
        import tomllib

        with open(_CONFIG_PATH, "rb") as f:
            return tomllib.load(f)
    else:
        try:
            import tomllib
        except ImportError:
            try:
                import tomli

                with open(_CONFIG_PATH, "rb") as f:
                    return tomli.load(f)
            except ImportError:
                return _DEFAULTS.copy()

    return _DEFAULTS.copy()


_config = None


def set_config_path(path: str) -> None:
    """Override the config file path.

    Must be called before any config access.  If the config has already been
    loaded it will be reloaded from the new path on next access.

    Args:
        path: Filesystem path to the TOML config file.
    """
    global _CONFIG_PATH, _config
    _CONFIG_PATH = os.path.expanduser(path)
    _config = None


def _get_config() -> dict:
    """Return the cached configuration dictionary, loading it on first access.

    Returns:
        The parsed TOML configuration as a nested dict.
    """
    global _config
    if _config is None:
        _config = _load_config()
    return _config


def get_color_for_link(url: str, link_type: str, extension: str = "") -> "QColor":
    """
    Return a QColor for the given link based on its type and extension.

    Args:
        url: The link URL/path
        link_type: One of "web", "folder", "file", "sharepoint", "unknown"
        extension: File extension (e.g., ".pdf") or empty string

    Returns:
        QColor for the foreground role
    """
    from PySide6.QtGui import QColor

    cfg = _get_config()
    colors = cfg.get("colors", _DEFAULTS["colors"])
    extensions = cfg.get("extensions", {})

    if link_type == "web":
        color_str = colors.get("web", _DEFAULTS["colors"]["web"])
    elif link_type == "folder":
        color_str = colors.get("folder", _DEFAULTS["colors"]["folder"])
    elif link_type == "sharepoint":
        color_str = colors.get("sharepoint", _DEFAULTS["colors"]["sharepoint"])
    elif link_type == "file":
        if extension:
            ext_lower = extension.lower()
            if ext_lower in extensions:
                color_str = extensions[ext_lower]
            elif ext_lower in _DEFAULTS["extensions"]:
                color_str = _DEFAULTS["extensions"][ext_lower]
            else:
                color_str = colors.get("file", _DEFAULTS["colors"]["file"])
        else:
            color_str = colors.get("file", _DEFAULTS["colors"]["file"])
    else:
        color_str = colors.get("unknown", _DEFAULTS["colors"]["unknown"])

    return QColor(color_str)


def get_sharepoint_patterns() -> list:
    """
    Return the list of regex patterns for detecting SharePoint URLs.
    """
    cfg = _get_config()
    global_cfg = cfg.get("global", {})
    return global_cfg.get(
        "sharepoint_patterns", _DEFAULTS["global"]["sharepoint_patterns"]
    )


def get_exclusion_patterns() -> list:
    """
    Return the list of glob patterns for excluding recent items from the link list.
    """
    cfg = _get_config()
    global_cfg = cfg.get("global", {})
    return global_cfg.get(
        "exclusion_patterns", _DEFAULTS["global"]["exclusion_patterns"]
    )


def get_links_file_path() -> str:
    """
    Return the path to links.json as configured in config.toml [global] section.
    If not configured (empty string) or config doesn't exist, returns the default
    path: ~/.link4000/links.json
    """
    cfg = _get_config()
    global_cfg = cfg.get("global", {})
    links_file = global_cfg.get("links_file", "")
    if links_file:
        return os.path.expanduser(links_file)
    return os.path.join(os.path.expanduser("~/.link4000"), "links.json")


def get_theme() -> str:
    """
    Return the theme setting from config.toml [global] section.
    Returns "light" or "dark". Default is "light".
    """
    cfg = _get_config()
    global_cfg = cfg.get("global", {})
    return global_cfg.get("theme", "light")


_TRAY_BEHAVIOR_VALUES = {"close_to_tray", "minimize_to_tray", "normal"}


def get_tray_behavior() -> str:
    """
    Return the tray behavior setting from config.toml [global] section.

    Returns one of:
    - "close_to_tray": X button hides to tray, minimize goes to taskbar (default)
    - "minimize_to_tray": minimize hides to tray, X button closes normally
    - "normal": minimize to taskbar and close normally (no tray icon)
    """
    cfg = _get_config()
    global_cfg = cfg.get("global", {})
    value = global_cfg.get("tray_behavior", _DEFAULTS["global"]["tray_behavior"])
    if value not in _TRAY_BEHAVIOR_VALUES:
        return _DEFAULTS["global"]["tray_behavior"]
    return value


def get_enabled_sources() -> list[str]:
    """Return the list of enabled source plugins.

    Returns:
        List of source names that should be loaded.
    """
    cfg = _get_config()
    sources_cfg = cfg.get("sources", _DEFAULTS["sources"])
    return sources_cfg.get("enabled", _DEFAULTS["sources"]["enabled"])


def ensure_config_exists() -> None:
    """Create default config.toml if it doesn't exist."""
    if os.path.exists(_CONFIG_PATH):
        return

    os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)

    default_config = """# Link4000 Configuration

[global]
# Path to the links.json file (leave empty for default: ~/.link4000/links.json)
# links_file = "/path/to/links.json"

# Theme for icons: "light" or "dark"
# theme = "light"

# Regex patterns for detecting SharePoint/OneDrive URLs (matched against the full URL)
# sharepoint_patterns = [
#     'sharepoint\\.com/.*',
#     'onedrive\\.live\\.com/.*',
# ]

# Regex patterns for excluding recent items from appearing in the link list.
# Items whose URL or path matches any pattern will be filtered out.
# exclusion_patterns = [
#     '.*\\.internal\\.company\\.com.*',
#     '.*/temp/.*',
# ]

# Window close and minimize behavior:
#   "close_to_tray"   - X button hides to tray, minimize goes to taskbar (default)
#   "minimize_to_tray" - minimize hides to tray, X button closes normally
#   "normal"           - minimize to taskbar and close normally (no tray icon)
# tray_behavior = "close_to_tray"

[sources]
# List of enabled link source plugins.
# Available sources: json_store, recent_windows (Windows), recent_linux_gnome (Linux/GNOME), office_recent (Windows), edge_favorites
# enabled = ["json_store", "recent_windows", "recent_linux_gnome", "office_recent", "edge_favorites"]

[colors]
web = "#0066CC"
folder = "#FF9500"
file = "#333333"
sharepoint = "#7038C8"
unknown = "#999999"

# File extension colors (case-insensitive)
# Uncomment and modify as needed:
# [extensions]
# ".pdf" = "#E53935"
# ".docx" = "#1565C0"
# ".xlsx" = "#43A047"
# ".py" = "#008000"
# ".txt" = "#757575"
# ".md" = "#000000"
"""

    with open(_CONFIG_PATH, "w") as f:
        f.write(default_config)
