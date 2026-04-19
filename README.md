# Link4000 - Link Manager

A cross-platform desktop application for managing bookmarks and file shortcuts with tagging support.

[![Python Version](https://img.shields.io/badge/python-3.13-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## Overview

Link4000 allows you to:
- Store and organize URLs and file paths with custom tags
- Search and filter links by title, tags, or type
- View recently used files from Windows, Linux (GNOME), or macOS
- Import favorites from Microsoft Edge browser
- Access Microsoft Office recent documents (Windows)
- Open links in your default browser or file manager

## Installation and Running

### First time setup with conda-lock
Assuming you have conda installed and channels configured in `~/.condarc`.

Install conda-lock:
```bash
conda install -n base conda-lock
```
With access to an anaconda subscription, install the `conda-subscription` environment:
```bash
conda-lock install -n link4000 conda-subscription-lock.yml
```
Without access to an anaconda subscription, install the environment that uses `conda-forge` instead:
```bash
conda-lock install -n link4000 conda-forge-lock.yml
```

### Activate environment & run
```bash
conda activate link4000
python main.py
```

### Sync the environment
After running `git pull` to update your repository, make sure to run
```bash
conda-lock install -n link4000 conda-subscription-lock.yml
```
(or the `forge` variant) in order to sync your environment to the lock file that may have been updated by pulling.

## Usage

### Running the Application

```bash
python main.py
```

### Command-Line Options

```bash
# Import links from a JSON file
python main.py --import links.json

# Import and overwrite existing links with the same URL
python main.py --import links.json --override-existing
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

Configuration is stored in `~/.link4000/config.toml`:

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

# Load recent files from MS Office (Windows-only), Windows and Linux (Gnome)
# load_recent_files = true

# Load favorites from Edge browser
# load_favorites = true

[onedrive]
# OneDrive/SharePoint resolution: No configuration needed!
# Simply ensure Azure CLI is installed and user has run 'az login'.
# The app will automatically use the credentials from Azure CLI.
# If not logged in, run: az login

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

## Building a Single-File Windows Executable 

Build the executable:
```bash
pyinstaller link4000.spec
```

The executable will be created at `dist/Link4000.exe`. 

**Note**: The executable generated using this approach is only suitable 
for your personal use. When redistributing it to others, make sure to 
comply with all applicable licenses (e.g. LGPLv3 for redistribution of PySide6).  

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
│   ├── recent_docs.py   # Recent files (Windows/Linux)
│   ├── edge_favorites.py # Edge browser favorites
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
- **Sorting**: Sort by created date, modified date, or last accessed
- **System Tray**: Configurable close-to-tray and minimize-to-tray behavior
- **Clipboard Integration**: Pre-fill URL from clipboard when adding links
- **Drag & Drop**: (Planned) Import links by dragging files
- **Import/Export**: JSON format for portability

## Platform-Specific Features

| Feature             | Windows | Linux     | macOS |
|---------------------|---------|-----------|-------|
| Recent Files        | ✅       | ✅ (GNOME) | -     |
| Edge Favorites      | ✅       | ✅         | ✅     |
| Office Recent       | ✅       | -         | -     |
| UNC Path Resolution | ✅       | -         | -     |

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions are welcome! Please ensure:
1. Code follows the project's type hint style
2. New features include docstrings
3. Tests pass before submitting PR
