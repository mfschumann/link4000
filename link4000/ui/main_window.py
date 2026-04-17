"""Main window module for the Link4000 link manager application.

This module provides the primary GUI window, including the link table view,
search/filter/sort controls, system tray integration, and context menu actions
for managing stored, recent, and favorite links.
"""

import os
import sys
import subprocess
import webbrowser
import threading
from collections.abc import Callable
from datetime import datetime

from link4000.utils.path_utils import (
    is_url,
    is_file_path,
    to_office_uri,
    resolve_unc_path,
    matches_exclusion_pattern,
)
from link4000.models.link import Link
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableView,
    QLineEdit,
    QPushButton,
    QStatusBar,
    QMenu,
    QMessageBox,
    QHeaderView,
    QSystemTrayIcon,
    QItemDelegate,
    QApplication,
    QComboBox,
    QStyleOptionViewItem,
)
from PySide6.QtCore import (
    Qt,
    QEvent,
    QFile,
    QTimer,
    QPoint,
    QAbstractItemModel,
    QModelIndex,
)
from PySide6.QtGui import QAction, QPainter, QColor, QFont, QIcon, QCloseEvent

from link4000.data.link_store import LinkStore
from link4000.models.link_model import LinkTableModel, LinkSortFilterModel
from link4000.ui.add_link_dialog import AddLinkDialog
from link4000.ui.bulk_edit_tags_dialog import BulkEditTagsDialog
from link4000.ui.tag_filter_window import TagFilterWindow
from link4000.utils.config import (
    ensure_config_exists,
    get_theme,
    get_tray_behavior,
    get_enabled_sources,
)
from link4000.data.source_registry import SourceRegistry
from pathlib import Path


class ButtonDelegate(QItemDelegate):
    """A custom item delegate that renders clickable buttons in a table view.

    Paints a styled button in a specific column and handles mouse click events
    to trigger a callback with the associated link ID.

    Args:
        parent: The parent QObject (typically the QTableView).
        column: The column index where the button should be rendered.
        callback: A callable that accepts a link ID string when the button is clicked.
    """

    def __init__(
        self, parent: QWidget, column: int, callback: Callable[[str], None]
    ) -> None:
        """Initialize the ButtonDelegate.

        Args:
            parent: The parent QObject (typically the QTableView).
            column: The column index where the button should be rendered.
            callback: A callable that accepts a link ID string when the button
                is clicked.
        """
        super().__init__(parent)
        self._column = column
        self._callback = callback

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """Paint a rounded button with label text in the target column.

        For cells outside the target column, delegates to the default painting
        behavior.

        Args:
            painter: The QPainter used for drawing.
            option: The QStyleOptionViewItem with style options for the item.
            index: The QModelIndex of the item being painted.
        """
        if index.column() == self._column:
            painter.save()
            painter.setPen(Qt.PenStyle.NoPen)

            rect = option.rect
            margin = 2
            button_rect = rect.adjusted(margin, margin, -margin, -margin)

            color = QColor("#1976D2")
            painter.setBrush(color)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.drawRoundedRect(button_rect, 4, 4)

            painter.setPen(QColor("#FFFFFF"))
            font = painter.font()
            font.setPointSize(10)
            painter.setFont(font)

            text = "✎" if self._column == LinkTableModel.COL_EDIT else "📋"
            painter.drawText(button_rect, Qt.AlignmentFlag.AlignCenter, text)

            painter.restore()
        else:
            super().paint(painter, option, index)

    def editorEvent(
        self,
        event: QEvent,
        model: QAbstractItemModel,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:
        """Handle mouse release events on the button column.

        On a mouse button release, extracts the link ID from the item's
        UserRole data and invokes the callback. For non-target columns or
        other event types, delegates to the default behavior.

        Args:
            event: The QEvent to handle.
            model: The data model for the item.
            option: The QStyleOptionViewItem with style options.
            index: The QModelIndex of the item receiving the event.

        Returns:
            True if the event was handled, or the result of the default
            handler otherwise.
        """
        if index.column() == self._column:
            if event.type() == QEvent.Type.MouseButtonRelease:
                link_id = index.data(Qt.ItemDataRole.UserRole)
                if link_id:
                    self._callback(link_id)
                return True
        return super().editorEvent(event, model, option, index)


class MainWindow(QMainWindow):
    """Primary application window for Link4000.

    Provides a table view of stored, recent, and favorite links with search,
    filter, and sort capabilities. Includes system tray integration and
    right-click context menu actions for link management.
    """

    def __init__(self) -> None:
        """Initialize the MainWindow.

        Sets up the link store, internal state for filtering and sorting,
        and builds the UI and system tray.
        """
        super().__init__()
        self.setWindowTitle("Link4000 - Link Manager")
        self.setMinimumSize(800, 600)

        self._store = LinkStore()
        self._selected_tags = set()
        self._match_all = False
        self._all_tags = set()
        self._selected_types = set()
        self._all_types: set[str] | None = None
        self._current_sort_column = None
        self._current_sort_order = Qt.SortOrder.AscendingOrder
        self._sorting_active = False

        self._pending_search_text = ""
        self._search_timer = QTimer(self)
        self._search_timer.setInterval(150)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_search)

        self._pending_filter: tuple[set, bool, set] = (set(), False, set())
        self._filter_timer = QTimer(self)
        self._filter_timer.setInterval(150)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.timeout.connect(self._apply_filter_preview)

        self._click_timer = QTimer(self)
        self._click_timer.setInterval(300)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._execute_delayed_click)
        self._pending_click_index: QModelIndex | None = None

        ensure_config_exists()
        self._tray_behavior = get_tray_behavior()
        self._enabled_sources = get_enabled_sources()
        self._setup_ui()
        self._tray = None
        if self._tray_behavior != "normal":
            self._setup_tray()
        self._load_links()

    @staticmethod
    def _get_icon() -> QIcon | None:
        """Load the application icon based on the current theme.

        Searches for SVG or PNG icon files in the resources directory,
        falling back to system theme icons if no bundled icon is found.

        Returns:
            A QIcon instance for the application or tray icon.
        """
        if getattr(sys, "_MEIPASS", None):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.resolve()

        theme = get_theme()
        icon_name = "icon_dark.svg" if theme == "dark" else "icon.svg"

        icon_paths = [base_path.parent.parent / "resources" / icon_name]
        for path in icon_paths:
            if QFile(path).exists():
                return QIcon(str(path))
        return QIcon.fromTheme(
            "link", QIcon.fromTheme("insert-link", QIcon.fromTheme("chain"))
        )

    def _setup_tray(self) -> None:
        """Set up the system tray icon with a context menu.

        Creates a tray icon with "Show Window" and "Quit" menu actions,
        and connects the tray activation signal for toggling visibility.
        """
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(self._get_icon())
        self._tray.setToolTip("Link4000 - Link Manager")

        menu = QMenu(self)
        show_action = QAction("Show Window", self)
        show_action.triggered.connect(self.show)
        menu.addAction(show_action)

        menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._on_quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation events.

        Toggles window visibility when the tray icon is single-clicked.

        Args:
            reason: The QSystemTrayIcon.ActivationReason describing how the
                tray icon was activated.
        """
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show()

    def _on_quit(self) -> None:
        """Quit the application by hiding the tray icon and exiting the process."""
        if self._tray is not None:
            self._tray.hide()
        self.close()
        import sys

        sys.exit(0)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle the close event based on tray_behavior configuration.

        - "close_to_tray": hides the window to the system tray instead of quitting.
        - "minimize_to_tray" / "normal": accepts the close event and lets Qt close.

        Args:
            event: The QCloseEvent to handle.
        """
        if self._tray_behavior == "close_to_tray":
            event.ignore()
            self.hide()
        else:
            event.accept()

    def changeEvent(self, event: QEvent) -> None:
        """Handle window state changes for minimize-to-tray behavior.

        When tray_behavior is "minimize_to_tray", intercepts the minimize
        event and hides the window to the system tray instead.

        Args:
            event: The QEvent to handle.
        """
        if (
            event.type() == QEvent.Type.WindowStateChange
            and self._tray_behavior == "minimize_to_tray"
            and self.isMinimized()
        ):
            self.hide()
        else:
            super().changeEvent(event)

    def _setup_ui(self) -> None:
        """Build and configure all UI components.

        Creates the toolbar (search input, sort combo, filter and add buttons,
        reload button), the table view with its proxy model and button delegates,
        and the status bar.
        """
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search links...")
        self._search_input.textChanged.connect(self._on_search_changed)
        toolbar_layout.addWidget(self._search_input)

        self._clear_button = QPushButton("✕")
        self._clear_button.setToolTip("Clear search and filters")
        self._clear_button.setFixedWidth(30)
        self._clear_button.clicked.connect(self._on_clear_clicked)
        toolbar_layout.addWidget(self._clear_button)

        self._sort_combo = QComboBox()
        self._sort_combo.addItems(["Sort by", "Created", "Modified"])
        self._sort_combo.currentTextChanged.connect(self._on_sort_changed)
        toolbar_layout.addWidget(self._sort_combo)

        self._sort_combo.setCurrentText("Sort by")

        self._tag_filter_button = QPushButton("Filter")
        self._tag_filter_button.clicked.connect(self._on_tag_filter_clicked)
        toolbar_layout.addWidget(self._tag_filter_button)

        self._add_button = QPushButton("Add")
        self._add_button.clicked.connect(self._on_add_clicked)
        toolbar_layout.addWidget(self._add_button)

        self._reload_button = QPushButton("Reload")
        self._reload_button.setToolTip(
            "Reload stored links, recent files, and favorites"
        )
        self._reload_button.clicked.connect(self._load_links)
        toolbar_layout.addWidget(self._reload_button)

        layout.addWidget(toolbar)

        self._table_view = QTableView()
        self._model = LinkTableModel()
        self._proxy_model = LinkSortFilterModel()
        self._proxy_model.setSourceModel(self._model)
        self._table_view.setModel(self._proxy_model)

        self._header = self._table_view.horizontalHeader()
        self._header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._table_view.setColumnWidth(3, 30)
        self._table_view.setColumnWidth(4, 30)

        edit_delegate = ButtonDelegate(
            self._table_view, LinkTableModel.COL_EDIT, self._on_edit_button_clicked
        )
        self._table_view.setItemDelegateForColumn(
            LinkTableModel.COL_EDIT, edit_delegate
        )

        copy_delegate = ButtonDelegate(
            self._table_view, LinkTableModel.COL_COPY, self._on_copy_button_clicked
        )
        self._table_view.setItemDelegateForColumn(
            LinkTableModel.COL_COPY, copy_delegate
        )

        self._table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table_view.setSortingEnabled(True)
        self._table_view.clicked.connect(self._on_cell_clicked)
        self._table_view.doubleClicked.connect(self._on_cell_double_clicked)
        self._table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table_view.customContextMenuRequested.connect(self._on_context_menu)
        self._header.sectionClicked.connect(self._on_header_clicked)

        layout.addWidget(self._table_view)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

    def _load_links(self) -> None:
        """Load all stored links into the table model and refresh the UI.

        Retrieves all links from the store, populates the tag set, applies the
        default sort order (last accessed, descending), updates the status bar,
        and schedules asynchronous loading of recent entries and favorites.
        """
        if "json_store" in self._enabled_sources:
            stored = self._store.get_all()
        else:
            stored = []
        self._model.set_links(stored)

        # Pre-compute link types in background to avoid GUI freeze when
        # opening filter dialog (avoids blocking isdir()/isfile() calls)
        self._precompute_link_types_background(stored)

        self._all_tags = set()
        for link in stored:
            self._all_tags.update(link.tags)
        for source_name in self._enabled_sources:
            if source_name != "json_store":
                self._all_tags.add(source_name)

        self._proxy_model.setSortRole(Qt.ItemDataRole.UserRole + 1)
        self._proxy_model.sort(
            LinkTableModel.COL_LAST_ACCESSED, Qt.SortOrder.DescendingOrder
        )
        self._header.setSortIndicator(
            LinkTableModel.COL_LAST_ACCESSED, Qt.SortOrder.DescendingOrder
        )
        self._current_sort_column = LinkTableModel.COL_LAST_ACCESSED
        self._current_sort_order = Qt.SortOrder.DescendingOrder
        self._status_bar.showMessage("Loading stored links...")
        self._update_status()

        self._excluded_urls_lower = {
            url.lower() for url in self._store.get_excluded_recent_urls()
        }
        self._stored_urls = {link.url.lower() for link in stored}

        if self._enabled_sources:
            QTimer.singleShot(0, self._load_dynamic_sources)

    def _load_dynamic_sources(self) -> None:
        """Fetch entries from all enabled dynamic sources.

        Runs the fetch in a background thread to avoid blocking the UI.
        Newly discovered URLs that are not already stored or excluded
        are added to the model with their source_tag.
        """
        self._status_bar.showMessage("Loading dynamic sources...")

        def fetch_and_process():
            sources = SourceRegistry.get_enabled_sources()
            all_links = []

            for source in sources:
                if source.name == "json_store":
                    continue

                entries = source.fetch()
                for entry in entries:
                    url = entry.url
                    if sys.platform == "win32" and is_file_path(url):
                        url = resolve_unc_path(url)
                    if (
                        url.lower() in self._stored_urls
                        or url.lower() in self._excluded_urls_lower
                        or matches_exclusion_pattern(url)
                    ):
                        continue
                    self._stored_urls.add(url.lower())
                    link = Link(
                        title=entry.title,
                        url=url,
                        tags=[entry.source_tag],
                        id=f"{source.name}:{url}",
                        created_at=entry.created_at,
                        updated_at=entry.updated_at,
                        last_accessed=entry.last_accessed,
                        source_tag=entry.source_tag,
                    )
                    all_links.append(link)

            return all_links

        def on_finished(links):
            self._model.set_recent_links(links)
            self._update_status()

        self._run_in_background(fetch_and_process, on_finished)

    def _refresh_recent_background(self) -> None:
        """Refresh dynamic entries in the background without reloading stored links.

        Updates the excluded URLs and stored URLs sets, then triggers a background
        reload of dynamic entries. This is used after delete/edit operations to
        provide immediate feedback while loading items asynchronously.
        """
        self._excluded_urls_lower = {
            url.lower() for url in self._store.get_excluded_recent_urls()
        }
        stored = self._store.get_all()
        self._stored_urls = {link.url.lower() for link in stored}
        if self._enabled_sources:
            QTimer.singleShot(0, self._load_dynamic_sources)

    @staticmethod
    def _run_in_background(fetch_func: Callable, on_finished: Callable) -> None:
        """Execute a function in a background thread and deliver results on the main thread.

        Spawns a worker thread to run ``fetch_func`` and polls for completion
        using ``QTimer.singleShot``. When the result is available, calls
        ``on_finished`` with it on the main (UI) thread.

        Args:
            fetch_func: A callable returning the result to process.
            on_finished: A callable invoked with the result on the main thread.
        """
        result_holder = [None]

        def worker():
            result_holder[0] = fetch_func()

        def check_done():
            if result_holder[0] is not None:
                on_finished(result_holder[0])
            else:
                QTimer.singleShot(50, check_done)

        thread = threading.Thread(target=worker)
        thread.start()
        QTimer.singleShot(50, check_done)

    def _precompute_link_types_background(self, links: list) -> None:
        """Pre-compute link types in background to avoid GUI freeze.

        Runs the link type computation (including filesystem checks like isdir/isfile)
        in a background thread so the cache is populated before the filter
        dialog is opened. This prevents blocking the GUI thread when accessing
        link.link_type or link.file_extension.

        Args:
            links: List of Link objects to pre-compute types for.
        """
        # Capture links in closure for the background thread
        links_to_process = links

        def worker() -> None:
            for link in links_to_process:
                # Access properties to trigger caching. This runs isdir()/isfile() calls
                # but in the background thread, not the GUI thread.
                _ = link.link_type
                _ = link.file_extension

        def on_done() -> None:
            pass  # No action needed when done, cache is populated

        self._run_in_background(worker, on_done)

    def _update_status(self) -> None:
        """Update the status bar with current link counts.

        Displays the number of filtered links out of the total number of links.
        """
        total_count = self._model.rowCount()
        filtered_count = self._proxy_model.rowCount()
        self._status_bar.showMessage(f"{filtered_count} of {total_count} links")

    def _update_all_tags(self) -> None:
        """Update the all_tags set from current links in the model.

        Used after single link updates to refresh the tag set without
        doing a full reload of all stored links.
        """
        self._all_tags = set()
        for link in self._model._links:
            self._all_tags.update(link.tags)
        for source_name in self._enabled_sources:
            if source_name != "json_store":
                self._all_tags.add(source_name)

    def _on_search_changed(self, text: str) -> None:
        """Handle search input text changes.

        Debounces the search by restarting a short timer. The actual filter
        update is applied after the user pauses typing to keep the GUI
        responsive.

        Args:
            text: The current search text entered by the user.
        """
        self._pending_search_text = text
        self._search_timer.start()

    def _apply_search(self) -> None:
        """Apply the pending search text to the proxy model."""
        self._search_timer.stop()
        self._proxy_model.set_search_text(self._pending_search_text)
        self._update_status()

    def _on_clear_clicked(self) -> None:
        """Clear search text and active filters."""
        self._search_input.clear()
        self._proxy_model.set_search_text("")
        self._selected_tags = set()
        self._selected_types = set()
        self._match_all = False
        self._proxy_model.set_selected_tags(set(), False, set())
        self._update_tag_filter_button()
        self._update_status()

    def _on_sort_changed(self, text: str) -> None:
        """Handle sort combo box selection changes.

        Applies sorting based on the selected option ("Sort by", "Created",
        or "Modified"). Disables the header sort indicator when using the
        combo-based sort.

        Args:
            text: The currently selected sort option text.
        """
        if text == "Sort by":
            self._sorting_active = False
            self._header.setSortIndicatorShown(False)
            return

        sort_column = LinkTableModel.COL_TITLE

        if text == "Created":
            sort_column = LinkTableModel.COL_TITLE
        elif text == "Modified":
            sort_column = LinkTableModel.COL_TAGS

        self._current_sort_column = sort_column
        self._current_sort_order = Qt.SortOrder.DescendingOrder

        self._sorting_active = True
        self._header.setSortIndicatorShown(False)

        self._proxy_model.setSortRole(Qt.ItemDataRole.UserRole + 2)
        self._proxy_model.sort(sort_column, self._current_sort_order)

    def _on_header_clicked(self, section: int) -> None:
        """Handle clicks on the table header to toggle column sorting.

        Toggles sort direction for the clicked column and updates the sort
        indicator. Supports sorting by title, tags (used for modified date),
        and last accessed date.

        Args:
            section: The column index of the clicked header section.
        """
        if section == LinkTableModel.COL_TITLE:
            self._proxy_model.setSortRole(Qt.ItemDataRole.DisplayRole)
            if self._current_sort_column == LinkTableModel.COL_TITLE:
                if self._current_sort_order == Qt.SortOrder.AscendingOrder:
                    self._current_sort_order = Qt.SortOrder.DescendingOrder
                else:
                    self._current_sort_order = Qt.SortOrder.AscendingOrder
            else:
                self._current_sort_column = LinkTableModel.COL_TITLE
                self._current_sort_order = Qt.SortOrder.AscendingOrder
        elif section == LinkTableModel.COL_TAGS:
            self._proxy_model.setSortRole(Qt.ItemDataRole.UserRole + 1)
            if self._current_sort_column == LinkTableModel.COL_TAGS:
                if self._current_sort_order == Qt.SortOrder.AscendingOrder:
                    self._current_sort_order = Qt.SortOrder.DescendingOrder
                else:
                    self._current_sort_order = Qt.SortOrder.AscendingOrder
            else:
                self._current_sort_column = LinkTableModel.COL_TAGS
                self._current_sort_order = Qt.SortOrder.DescendingOrder
        elif section == LinkTableModel.COL_LAST_ACCESSED:
            self._proxy_model.setSortRole(Qt.ItemDataRole.UserRole + 1)
            if self._current_sort_column == LinkTableModel.COL_LAST_ACCESSED:
                if self._current_sort_order == Qt.SortOrder.AscendingOrder:
                    self._current_sort_order = Qt.SortOrder.DescendingOrder
                else:
                    self._current_sort_order = Qt.SortOrder.AscendingOrder
            else:
                self._current_sort_column = LinkTableModel.COL_LAST_ACCESSED
                self._current_sort_order = Qt.SortOrder.DescendingOrder
        else:
            return

        self._sorting_active = False
        self._header.setSortIndicatorShown(True)
        self._header.setSortIndicator(
            self._current_sort_column, self._current_sort_order
        )
        self._proxy_model.sort(self._current_sort_column, self._current_sort_order)
        self._update_sort_combo_from_column()

    def _update_sort_combo_from_column(self) -> None:
        """Synchronize the sort combo box with the current sort column.

        Updates the combo box selection to reflect the active sort column
        without triggering its signal handler.
        """
        self._sort_combo.blockSignals(True)
        if not self._sorting_active:
            self._sort_combo.setCurrentText("Sort by")
        elif self._current_sort_column == LinkTableModel.COL_TITLE:
            self._sort_combo.setCurrentText("Created")
        elif self._current_sort_column == LinkTableModel.COL_TAGS:
            self._sort_combo.setCurrentText("Modified")
        elif self._current_sort_column == LinkTableModel.COL_LAST_ACCESSED:
            self._sort_combo.setCurrentText("Sort by")
        self._sort_combo.blockSignals(False)

    def _get_all_types(self) -> set:
        """Collect all unique link types from the stored links.

        Returns:
            A set of type/extension strings representing the distinct link
            types found in the store (e.g. file extensions or URL types).
        """
        types = set()
        if "json_store" not in self._enabled_sources:
            return types

        for link in self._store.get_all():
            link_ext = link.file_extension
            if link_ext:
                types.add(link_ext)
            else:
                types.add(link.link_type)
        return types

    def _on_tag_filter_clicked(self) -> None:
        """Open the tag and type filter dialog.

        Lazily initializes the set of all link types, then opens a
        ``TagFilterWindow`` dialog with the current filter state. Connects
        the dialog's signals for live preview and final selection.
        """
        if self._all_types is None:
            self._all_types = self._get_all_types()
        dialog = TagFilterWindow(
            self,
            self._all_tags,
            self._selected_tags,
            self._match_all,
            self._all_types,
            self._selected_types,
        )
        dialog.tags_and_types_selected.connect(self._on_tags_and_types_selected)
        dialog.filter_preview.connect(self._on_filter_preview)
        dialog.exec()

    def _on_filter_preview(
        self, selected_tags: set, tag_match_all: bool, selected_types: set
    ) -> None:
        """Apply a live preview of tag/type filters from the filter dialog.

        Debounces the filter update by restarting a short timer. The actual
        filter is applied after a brief pause to keep the GUI responsive.

        Args:
            selected_tags: The set of currently selected tag strings.
            tag_match_all: If True, links must have all selected tags; otherwise any.
            selected_types: The set of currently selected type/extension strings.
        """
        self._pending_filter = (selected_tags, tag_match_all, selected_types)
        self._filter_timer.start()

    def _apply_filter_preview(self) -> None:
        """Apply the pending tag/type filter to the proxy model."""
        self._filter_timer.stop()
        selected_tags, tag_match_all, selected_types = self._pending_filter
        self._proxy_model.set_selected_tags(
            selected_tags, tag_match_all, selected_types
        )
        self._update_tag_filter_button()
        self._update_status()

    def _on_tags_and_types_selected(
        self, selected_tags: set, tag_match_all: bool, selected_types: set
    ) -> None:
        """Commit the final tag and type filter selection from the filter dialog.

        Persists the selected tags, match mode, and types to the instance
        state and applies them to the proxy model.

        Args:
            selected_tags: The set of selected tag strings to filter by.
            tag_match_all: If True, links must match all selected tags.
            selected_types: The set of selected type/extension strings.
        """
        self._selected_tags = selected_tags
        self._match_all = tag_match_all
        self._selected_types = selected_types
        self._proxy_model.set_selected_tags(
            selected_tags, tag_match_all, selected_types
        )
        self._update_tag_filter_button()
        self._update_status()

    def _update_tag_filter_button(self) -> None:
        """Update the filter button font to indicate active filters.

        Sets the button text to bold when tags are selected, and normal
        weight when no filters are active.
        """
        if self._selected_tags:
            font = QFont()
            font.setBold(True)
            self._tag_filter_button.setFont(font)
        else:
            font = QFont()
            font.setBold(False)
            self._tag_filter_button.setFont(font)

    def _on_add_clicked(self) -> None:
        """Handle the "Add" button click to create a new link.

        Reads the clipboard text and pre-fills the add dialog URL if the
        clipboard contains a valid URL or file path. After confirmation,
        saves the new link and reloads the list.
        """
        clipboard = QApplication.clipboard()
        clipboard_text = clipboard.text().strip()
        prefilled_url = ""

        if clipboard_text.startswith('"') and clipboard_text.endswith('"'):
            clipboard_text = clipboard_text[1:-1]

        if is_url(clipboard_text) or (
            sys.platform == "win32" and is_file_path(clipboard_text)
        ):
            prefilled_url = clipboard_text

        dialog = AddLinkDialog(self, url=prefilled_url, all_tags=self._all_tags)
        if dialog.exec():
            link = dialog.get_link()
            if link is None:
                return
            if not self._confirm_if_duplicate(link.url):
                return
            self._store.add(link)
            self._load_links()

    def _confirm_if_duplicate(self, url: str) -> bool:
        """
        Check whether *url* is already stored.  If it is, ask the user for
        confirmation.  Return True when the caller should proceed with saving,
        False when the user chose to abort.
        """
        existing = self._store.find_by_url(url)
        if existing is None:
            return True
        reply = QMessageBox.question(
            self,
            "Duplicate Entry",
            f'This URL / path is already saved as:\n\n"{existing.title}"\n\n'
            "Do you want to save it again?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _open_link(self, link):
        """Open *link* in the appropriate application (browser, file manager, etc.)."""
        self._store.update_last_accessed(link.id)
        link.last_accessed = datetime.now()
        target = link.url
        if sys.platform == "win32":
            office_uri = to_office_uri(target)
            if office_uri:
                target = office_uri
            try:
                os.startfile(target)
            except Exception:
                webbrowser.open(target)
        else:
            try:
                subprocess.run(["xdg-open", target], check=True)
            except Exception:
                webbrowser.open(target)

    @staticmethod
    def _open_recent(link):
        """Open a recent (non-stored) entry directly via the OS."""
        target = link.url
        if sys.platform == "win32":
            office_uri = to_office_uri(target)
            if office_uri:
                target = office_uri
            try:
                os.startfile(target)
            except Exception:
                webbrowser.open(target)
        else:
            try:
                subprocess.run(["xdg-open", target], check=True)
            except Exception:
                webbrowser.open(target)

    def _promote_recent(self, link):
        """Open the edit dialog pre-filled for a dynamic entry; on save, add to store."""
        promoted = Link(
            title=link.title,
            url=link.url,
            tags=[],
            id="",  # empty id signals store.add() to generate a fresh UUID
            source_tag="",
        )
        dialog = AddLinkDialog(self, link=promoted, all_tags=self._all_tags)
        if dialog.exec():
            saved = dialog.get_link()
            if saved is not None:
                self._store.add(saved)
                self._store.update_last_accessed(saved.id)
                self._load_links()

    def _promote_favorite(self, link):
        """Open the edit dialog pre-filled for a dynamic entry; on save, add to store."""
        self._promote_recent(link)

    @staticmethod
    def _open_parent_folder(link):
        """Open the parent folder of the given file path."""
        path = str(Path(link.url).parent)
        if not path:
            return
        if sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.run(["xdg-open", path], check=True)

    def _on_cell_clicked(self, index: QModelIndex) -> None:
        """Handle single clicks on table cells.

        When the title column is clicked, schedules opening the link after a
        short delay. If a double-click occurs within the delay, the single-click
        action is cancelled.

        Args:
            index: The QModelIndex of the clicked cell.
        """
        if index.column() == LinkTableModel.COL_TITLE:
            self._click_timer.stop()
            self._pending_click_index = index
            self._click_timer.start()

    def _execute_delayed_click(self) -> None:
        """Execute the delayed single-click action.

        Called by the click timer when no double-click occurred within the
        delay period.
        """
        if self._pending_click_index is not None:
            index = self._pending_click_index
            link_id = index.data(Qt.ItemDataRole.UserRole)
            if link_id:
                link = self._model.get_link_by_id(link_id)
                if link:
                    if link.source_tag:
                        self._open_recent(link)
                    else:
                        self._open_link(link)
            self._pending_click_index = None

    def _on_cell_double_clicked(self, index: QModelIndex) -> None:
        """Handle double clicks on table cells.

        Cancels any pending single-click action and opens the edit dialog
        for the clicked link.

        Args:
            index: The QModelIndex of the double-clicked cell.
        """
        self._click_timer.stop()
        self._pending_click_index = None
        link_id = index.data(Qt.ItemDataRole.UserRole)
        if link_id:
            link = self._model.get_link_by_id(link_id)
            if link:
                if link.source_tag:
                    self._promote_recent(link)
                else:
                    self._edit_link(link)

    def _on_edit_button_clicked(self, link_id: str) -> None:
        """Handle clicks on the inline Edit button in the table.

        Promotes recent/favorite entries via their respective dialogs, or
        opens the edit dialog for stored links.

        Args:
            link_id: The unique identifier of the link to edit.
        """
        link = self._model.get_link_by_id(link_id)
        if link:
            if link.source_tag:
                self._promote_recent(link)
            else:
                self._edit_link(link)

    def _on_copy_button_clicked(self, link_id: str) -> None:
        """Handle clicks on the inline Copy button in the table.

        Copies the link URL to the clipboard and updates the last-accessed
        timestamp for stored links.

        Args:
            link_id: The unique identifier of the link to copy.
        """
        link = self._model.get_link_by_id(link_id)
        if link:
            clipboard = QApplication.clipboard()
            clipboard.setText(link.url)
            self._status_bar.showMessage(f"Copied: {link.url}", 2000)
            if not link.source_tag:
                self._store.update_last_accessed(link.id)
                link.last_accessed = datetime.now()

    def _copy_url(self, link: Link) -> None:
        """Copy the link URL to the system clipboard.

        Args:
            link: The Link object whose URL should be copied.
        """
        clipboard = QApplication.clipboard()
        clipboard.setText(link.url)
        self._status_bar.showMessage(f"Copied: {link.url}", 2000)

    def _copy_parent_folder(self, link: Link) -> None:
        """Copy the parent folder path of the link to the system clipboard.

        Args:
            link: The Link object whose parent folder path should be copied.
        """
        parent = str(Path(link.url).parent)
        if parent:
            clipboard = QApplication.clipboard()
            clipboard.setText(parent)
            self._status_bar.showMessage(f"Copied: {parent}", 2000)

    def _get_selected_link(self) -> Link | None:
        """Retrieve the currently selected link from the table.

        Returns:
            The first selected Link object, or None if no row is selected.
        """
        rows = self._table_view.selectedIndexes()
        if rows:
            proxy_index = rows[0]
            source_index = self._proxy_model.mapToSource(proxy_index)
            return self._model.get_link(source_index.row())
        return None

    def _get_selected_links(self) -> list[Link]:
        """Retrieve all currently selected links from the table.

        Deduplicates by row index to handle multi-column selections correctly.

        Returns:
            A list of Link objects for all selected rows, or an empty list.
        """
        rows = self._table_view.selectedIndexes()
        if not rows:
            return []
        selected_rows = set()
        links = []
        for proxy_index in rows:
            row = proxy_index.row()
            if row not in selected_rows:
                selected_rows.add(row)
                source_index = self._proxy_model.mapToSource(proxy_index)
                link = self._model.get_link(source_index.row())
                if link:
                    links.append(link)
        return links

    def _on_context_menu(self, pos: QPoint) -> None:
        """Show a context menu for the selected table items.

        For a single selection, offers open, copy, edit, and delete actions
        (with file-specific options for file paths). For multi-selection,
        offers bulk add/remove tags and delete actions.

        Args:
            pos: The QPoint position where the context menu was requested.
        """
        selected_links = self._get_selected_links()
        if not selected_links:
            return

        menu = QMenu(self)

        if len(selected_links) == 1:
            link = selected_links[0]
            open_label = "Open Path" if is_file_path(link.url) else "Open URL"
            open_action = QAction(open_label, self)
            if link.source_tag:
                open_action.triggered.connect(lambda: self._open_recent(link))
            else:
                open_action.triggered.connect(lambda: self._open_link(link))
            menu.addAction(open_action)

            if is_file_path(link.url):
                parent_folder_action = QAction("Open Parent Folder", self)
                parent_folder_action.triggered.connect(
                    lambda: self._open_parent_folder(link)
                )
                menu.addAction(parent_folder_action)

                copy_path_action = QAction("Copy Path", self)
                copy_path_action.triggered.connect(lambda: self._copy_url(link))
                menu.addAction(copy_path_action)

                copy_parent_action = QAction("Copy Parent Folder", self)
                copy_parent_action.triggered.connect(
                    lambda: self._copy_parent_folder(link)
                )
                menu.addAction(copy_parent_action)
            else:
                copy_url_action = QAction("Copy URL", self)
                copy_url_action.triggered.connect(lambda: self._copy_url(link))
                menu.addAction(copy_url_action)

            edit_action = QAction("Edit", self)
            if link.source_tag:
                edit_action.triggered.connect(lambda: self._promote_recent(link))
            else:
                edit_action.triggered.connect(lambda: self._edit_link(link))
            menu.addAction(edit_action)
        else:
            add_tags_action = QAction("Add Tags...", self)
            add_tags_action.triggered.connect(
                lambda: self._bulk_add_tags(selected_links)
            )
            menu.addAction(add_tags_action)

            remove_tags_action = QAction("Remove Tags...", self)
            remove_tags_action.triggered.connect(
                lambda: self._bulk_remove_tags(selected_links)
            )
            menu.addAction(remove_tags_action)

        menu.addSeparator()
        count = len(selected_links)
        delete_label = f"Delete {count} Item{'s' if count > 1 else ''}"
        delete_action = QAction(delete_label, self)
        delete_action.triggered.connect(lambda: self._bulk_delete(selected_links))
        menu.addAction(delete_action)

        menu.exec(self._table_view.viewport().mapToGlobal(pos))

    def _bulk_add_tags(self, links: list[Link]) -> None:
        """Add tags to multiple links at once.

        Opens a bulk edit dialog for tag addition. Stored links are updated
        in-place, while recent/favorite entries are promoted to stored links
        with the new tags applied.

        Args:
            links: A list of Link objects to add tags to.
        """
        dialog = BulkEditTagsDialog(
            self, BulkEditTagsDialog.MODE_ADD, len(links), self._all_tags
        )
        if dialog.exec():
            tags_to_add = dialog.get_tags()
            if tags_to_add:
                stored_links = [link for link in links if not link.source_tag]
                link_ids = [link.id for link in stored_links]
                if link_ids:
                    self._store.bulk_update_tags(link_ids, tags_to_add, [])

                for link in links:
                    if link.source_tag:
                        new_tags = list(link.tags)
                        if link.source_tag in new_tags:
                            new_tags.remove(link.source_tag)
                        new_tags.extend(tags_to_add)
                        promoted = Link(
                            title=link.title,
                            url=link.url,
                            tags=new_tags,
                            id="",
                            source_tag="",
                        )
                        self._store.add(promoted)

                self._load_links()

    def _bulk_remove_tags(self, links: list[Link]) -> None:
        """Remove tags from multiple links at once.

        Opens a bulk edit dialog for tag removal. Stored links are updated
        in-place, while recent/favorite entries are promoted to stored links
        with the specified tags removed.

        Args:
            links: A list of Link objects to remove tags from.
        """
        dialog = BulkEditTagsDialog(
            self, BulkEditTagsDialog.MODE_REMOVE, len(links), self._all_tags
        )
        if dialog.exec():
            tags_to_remove = dialog.get_tags()
            if tags_to_remove:
                stored_links = [link for link in links if not link.source_tag]
                link_ids = [link.id for link in stored_links]
                if link_ids:
                    self._store.bulk_update_tags(link_ids, [], tags_to_remove)

                for link in links:
                    if link.source_tag:
                        new_tags = list(link.tags)
                        if link.source_tag in new_tags:
                            new_tags.remove(link.source_tag)
                        new_tags = [t for t in new_tags if t not in tags_to_remove]
                        promoted = Link(
                            title=link.title,
                            url=link.url,
                            tags=new_tags,
                            id="",
                            source_tag="",
                        )
                        self._store.add(promoted)

                self._load_links()

    def _bulk_delete(self, links):
        """Delete multiple links after user confirmation.

        Stored links are deleted from the store. Recent and favorite entries
        are excluded from future loads by adding their URLs to the exclusion
        list. The list is updated immediately and recent entries are refreshed
        in the background.

        Args:
            links: A list of Link objects to delete.
        """
        count = len(links)
        reply = QMessageBox.question(
            self,
            "Delete Links",
            f"Are you sure you want to delete {count} item(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            link_ids = [link.id for link in links if not link.source_tag]
            if link_ids:
                self._store.bulk_delete(link_ids)
            for link in links:
                if link.source_tag:
                    self._store.add_excluded_recent_url(link.url)
                self._model.remove_link(link.id)
            self._update_status()
            self._refresh_recent_background()

    def _edit_link(self, link):
        """Open the edit dialog for a stored link.

        Shows an ``AddLinkDialog`` pre-filled with the link data. Supports
        both updating and deleting the link. On save, the link is updated
        in the store and the model is updated immediately.

        Args:
            link: The Link object to edit.
        """
        dialog = AddLinkDialog(self, link=link, all_tags=self._all_tags)
        dialog.delete_requested.connect(lambda: self._handle_delete_from_edit(link))
        if dialog.exec():
            updated = dialog.get_link()
            if updated is not None:
                self._store.update(updated)
                self._model.update_link(updated)
                self._update_all_tags()

    def _handle_delete_from_edit(self, link: Link) -> None:
        """Handle deletion triggered from within the edit dialog.

        Removes the link from the model immediately and refreshes recent
        entries in the background.

        Args:
            link: The Link object being deleted.
        """
        self._store.delete(link.id)
        self._model.remove_link(link.id)
        self._update_status()
        self._refresh_recent_background()

    def _delete_link(self, link):
        """Delete a single link after user confirmation.

        Stored links are removed from the store. Recent and favorite entries
        are excluded from future loads by adding their URLs to the exclusion
        list. The list is updated immediately and recent entries are refreshed
        in the background.

        Args:
            link: The Link object to delete.
        """
        reply = QMessageBox.question(
            self,
            "Delete Link",
            f"Are you sure you want to delete '{link.title}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if link.source_tag:
                self._store.add_excluded_recent_url(link.url)
            else:
                self._store.delete(link.id)
            self._model.remove_link(link.id)
            self._update_status()
            self._refresh_recent_background()
