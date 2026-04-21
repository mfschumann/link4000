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
        "recent_windows": {"enabled": True, "max_age_days": 0},
        "recent_linux_gnome": {"enabled": True, "max_age_days": 0},
        "office_recent": {"enabled": True, "max_age_days": 0},
        "edge_favorites": {"enabled": True},
        "edge_history": {"enabled": True, "max_age_days": 30},
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
    """Return the list of enabled source plugin names.

    Checks the 'enabled' config option for each registered source plugin.
    Sources default to enabled (True) if not explicitly configured.

    Returns:
        List of source names that should be loaded.
    """
    from link4000.data.source_registry import SourceRegistry

    SourceRegistry._ensure_plugins_loaded()
    registered = SourceRegistry.get_registered_sources()

    enabled = []
    for name in registered:
        source_cfg = get_source_config(name)
        if source_cfg.get("enabled", True):
            enabled.append(name)
    return enabled


def get_source_config(source_name: str) -> dict:
    """Return the configuration dictionary for a specific source plugin.

    Reads from [sources.<source_name>] section in config.toml, merging with
    defaults defined in _DEFAULTS.

    Args:
        source_name: The name of the source plugin (e.g., "recent_windows").

    Returns:
        Dictionary of configuration options for the source plugin.
    """
    cfg = _get_config()
    sources_cfg = cfg.get("sources", _DEFAULTS["sources"])

    default_source_cfg = _DEFAULTS["sources"].get(source_name, {})

    stored_source_cfg = sources_cfg.get(source_name, {})

    merged = default_source_cfg.copy()
    merged.update(stored_source_cfg)
    return merged


def get_azure_cli_path() -> str:
    """Return the path to the Azure CLI executable.

    Reads from [onedrive] azure_cli_path config option.
    Defaults to "az" (PATH lookup) if not configured.

    Returns:
        Path to Azure CLI executable or "az" for PATH lookup.
    """
    cfg = _get_config()
    onedrive_cfg = cfg.get("onedrive", {})
    return onedrive_cfg.get("azure_cli_path", "az")


def get_full_config() -> dict:
    """Return the full configuration with defaults merged.

    Returns a complete configuration dictionary with all default values,
    where user-defined values override the defaults.

    Returns:
        Complete configuration dictionary with defaults merged.
    """
    import copy

    user_cfg = _get_config()
    full_cfg = copy.deepcopy(_DEFAULTS)

    def merge_dict(base: dict, override: dict) -> dict:
        """Recursively merge override dict into base dict."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                merge_dict(base[key], value)
            else:
                base[key] = value
        return base

    merge_dict(full_cfg, user_cfg)
    return full_cfg


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

# Per-source configuration options:
# Each source can have its own config section under [sources.<source_name>]
# Set enabled = false to disable a source (defaults to true).

# Windows recent files config:
[sources.recent_windows]
# Set to false to disable this source
enabled = true
# Maximum age in days for recent items (0 = no limit)
max_age_days = 0

# Linux/GNOME recent files config:
[sources.recent_linux_gnome]
# Set to false to disable this source
enabled = true
# Maximum age in days for recent items (0 = no limit)
max_age_days = 0

# Office recent documents config:
[sources.office_recent]
# Set to false to disable this source
enabled = true
# Maximum age in days for recent items (0 = no limit)
max_age_days = 0

# Edge browser favorites config:
[sources.edge_favorites]
# Set to false to disable this source
enabled = true

# Edge browser history config:
[sources.edge_history]
# Set to false to disable this source
enabled = true
# Maximum age in days for history items (0 = no limit)
max_age_days = 30

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

# OneDrive/SharePoint resolution configuration
# Optional: override the Azure CLI executable path
# azure_cli_path = "az"  # Default: "az" (uses PATH lookup)
# Examples: "C:/Program Files/Microsoft SDKs/Azure/az.exe", "/usr/local/bin/az"
"""

    with open(_CONFIG_PATH, "w") as f:
        f.write(default_config)
