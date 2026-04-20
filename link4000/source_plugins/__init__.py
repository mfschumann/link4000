"""Source plugins package for link4000.

This package contains all link source plugins. Each plugin is a subclass of
LinkSource that implements the fetch() method to return entries from a specific
source (e.g., Windows recent files, Edge favorites, etc.).

Plugins are automatically registered with SourceRegistry via the
@SourceRegistry.register decorator at import time. The source_plugins/__init__.py
module imports all plugin modules to ensure they get registered.
"""

from link4000.source_plugins.edge_favorites import EdgeFavoritesSource
from link4000.source_plugins.edge_history import EdgeHistorySource
from link4000.source_plugins.office_recent_docs import OfficeRecentSource
from link4000.source_plugins.recent_docs_windows import RecentDocsWindowsSource
from link4000.source_plugins.recent_docs_linux_gnome import RecentDocsLinuxGnomeSource

__all__ = [
    "EdgeFavoritesSource",
    "EdgeHistorySource",
    "OfficeRecentSource",
    "RecentDocsWindowsSource",
    "RecentDocsLinuxGnomeSource",
]