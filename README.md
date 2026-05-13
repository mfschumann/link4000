# Link4000 - Link Manager

A cross-platform desktop application for managing bookmarks and file shortcuts with tagging support.

[![Python Version](https://img.shields.io/badge/python-3.13-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## Overview

Link4000 allows you to:
- Store and organize URLs and file paths with custom tags
- Search and filter links by title, tags, or type
- View recently used files from Windows, Linux (GNOME), or macOS
- Import favorites and browsing history from Microsoft Edge browser
- Access Microsoft Office recent documents (Windows)
- Open links in your default browser or file manager

## Installation and Running

### First time setup with pixi
Assuming you have [pixi](https://pixi.sh) installed.

Install runtime dependencies and set up the default environment:
```bash
pixi install
```

**Environments**

This project defines three environments:

- **default**: Installs all dependencies needed to _run_ link4000 from Anaconda default channels (main, services).
- **test**: Similar to `default`, but with all dependencies needed to run the unit tests.
- **dev**: Installs dependencies needed to _develop_ link4000 from `conda-forge`.


To install a non-default environment run (e.g. for the `dev` environment):
```bash
pixi install -e dev
```

Note: All `pixi` commands shown below can be run in one of the two non-default environments by adding `-e dev` or `-e test`.

### Sync the environment
After running `git pull` to update your repository, make sure to run
```bash
pixi install
```
in order to sync your environment to the lock file that may have been updated by pulling.

## Usage

### Running the Application

```bash
pixi run python main.py
```

### Command-Line Options

Use a non-default config file:
```bash
pixi run python main.py --config path/to/config.toml
```

Import links from a JSON file:
```bash
pixi run python main.py --import links.json
```

Import and overwrite existing links with the same URL:
```bash
pixi run python main.py --import links.json --override-existing
```

All available command line arguments:
```bash
pixi run python main.py --help
```

### JSON Import Format

The application supports two JSON formats:

**Current Format:**
```json
{
  "links": [
    {
      "id": "uuid-here",
      "title": "Example",
      "url": "https://example.com",
      "tags": ["work", "important"],
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-02T00:00:00",
      "last_accessed": "2024-01-03T00:00:00"
    }
  ],
  "excluded_recent_urls": []
}
```

**Legacy Format** (deprecated):
```json
[
  {
    "name": "Example",
    "path": "https://example.com",
    "keywords": ["work", "important"]
  }
]
```

## Configuration

Configuration is stored in `~/.link4000/config.toml` (default) or in the path passed as the `--config` command line argument:

```toml
[global]
# Path to the links.json file (leave empty for default)
# links_file = ""

# Theme for icons: "light" or "dark"
# theme = "light"

# Regex patterns for detecting SharePoint/OneDrive URLs
# sharepoint_patterns = [
#     'sharepoint\\.com/.*',
#     'onedrive\\.live\\.com/.*',
# ]

# Regex patterns for excluding recent items from the link list.
# Recent items whose URL or path matches any pattern will be filtered out.
# exclusion_patterns = [
#     '.*\\.internal\\.company\\.com.*',
#     '.*/temp/.*',
# ]

# Window close and minimize behavior:
#   "close_to_tray"   - X button hides to tray, minimize goes to taskbar (default)
#   "minimize_to_tray" - minimize hides to tray, X button closes normally
#   "normal"           - minimize to taskbar and close normally (no tray icon)
# tray_behavior = "close_to_tray"

# Auto-reload interval for dynamic sources in minutes (default 15).
# Set to 0 to disable automatic reloading.
# reload_interval_minutes = 15

[sources]
# Source plugins configuration.
# Set enabled = false to disable a source (defaults to true).
# Available sources:
#   - recent_windows: Recent files on Windows
#   - recent_linux_gnome: Recent files on Linux/GNOME
#   - office_recent: Recent Office documents (Windows)
#   - edge_favorites: Microsoft Edge browser favorites
#   - edge_history: Microsoft Edge browser browsing history

# Windows recent files
[sources.recent_windows]
enabled = true
# Maximum age in days (0 = no limit)
max_age_days = 0

# Linux/GNOME recent files
[sources.recent_linux_gnome]
enabled = true
# Maximum age in days (0 = no limit)
max_age_days = 0

# Office recent documents
[sources.office_recent]
enabled = true
# Maximum age in days (0 = no limit)
max_age_days = 0

# Edge browser favorites
[sources.edge_favorites]
enabled = true

# Edge browser history
[sources.edge_history]
enabled = true
# Maximum age in days (0 = no limit)
max_age_days = 30

[colors]
web = "#0066CC"
folder = "#FF9500"
file = "#333333"
sharepoint = "#7038C8"
unknown = "#999999"

# File extension colors (case-insensitive)
# [extensions]
# ".pdf" = "#E53935"
# ".docx" = "#1565C0"
```


## Project Structure

```
link4000/
├── __init__.py          # Package initialization
├── models/
│   ├── link.py          # Link data model
│   └── link_model.py    # Qt table model for links
├── utils/
│   ├── config.py        # Configuration management
│   └── path_utils.py    # URL/path utilities
├── data/
│   ├── link_store.py    # Link persistence
│   ├── link_source.py   # Abstract base class for source plugins
│   ├── source_registry.py # Plugin registry
│   └── loader_types.py  # Source entry types
├── source_plugins/  # Source plugin implementations
│   ├── __init__.py  # Auto-registers all plugins
│   ├── recent_docs_windows.py # Windows recent files
│   ├── recent_docs_linux_gnome.py # Linux/GNOME recent files
│   ├── edge_favorites.py # Edge browser favorites
│   ├── edge_history.py # Edge browser history
│   └── office_recent_docs.py # Office recent documents
└── ui/
    ├── main_window.py        # Main application window
    ├── add_link_dialog.py    # Add/edit link dialog
    ├── bulk_edit_tags_dialog.py # Bulk tag editing
    └── tag_filter_window.py  # Tag/type filter dialog

tests/                   # Unit tests
main.py                  # Application entry point
```

## Features

- **Tag Management**: Add, edit, and filter links by tags
- **Search**: Find links by title, URL, or tags
- **Filter Modes**: Tag filtering supports three modes: match ANY tag (OR), ALL tags (AND), or NONE of the selected tags
- **Sorting**: Sort by created date, modified date, or last accessed
- **System Tray**: Configurable close-to-tray and minimize-to-tray behavior
- **Clipboard Integration**: Pre-fill URL from clipboard when adding links
- **Drag & Drop**: (Planned) Import links by dragging files
- **Import/Export**: JSON format for portability
- **Source Plugins**: Configurable source plugins with per-source options (e.g., age limits for recent files)

## Platform-Specific Features

| Feature             | Windows | Linux     | macOS |
|---------------------|---------|-----------|-------|
| Recent Files        | ✅       | ✅ (GNOME) | -     |
| Edge Favorites      | ✅       | ✅         | ✅     |
| Edge History        | ✅       | ✅         | ✅     |
| Office Recent       | ✅       | -         | -     |
| UNC Path Resolution | ✅       | -         | -     |

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions are welcome! Please ensure:
1. Code follows the project's type hint style
2. New features include docstrings
3. Tests pass before submitting PR
