"""Qt table model and proxy model for displaying and filtering links."""

from typing import List
from datetime import datetime
from PySide6.QtCore import (
    Qt,
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
)
from PySide6.QtWidgets import QWidget

from link4000.models.link import Link
from PySide6.QtGui import QFont
from link4000.utils.config import get_color_for_link


def format_relative_date(dt: datetime) -> str:
    """Formats a datetime as a human-readable relative date string.

    Args:
        dt: The datetime to format.

    Returns:
        A string like "just now", "5 minutes ago", "Jan 15", etc.
    """
    now = datetime.now()
    diff = now - dt

    seconds = diff.total_seconds()

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    elif dt.strftime("%Y") == now.strftime("%Y"):
        return dt.strftime("%b %d")
    else:
        return dt.strftime("%b %Y")


class LinkTableModel(QAbstractTableModel):
    """QAbstractTableModel subclass exposing Link data for a Qt table view.

    Supports standard links and a separate 'recent' section appended after
    the main list.
    """

    COL_TITLE = 0
    COL_TAGS = 1
    COL_LAST_ACCESSED = 2
    COL_EDIT = 3
    COL_COPY = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initializes the table model with empty link lists and column headers."""
        super().__init__(parent)
        self._links: List[Link] = []
        self._recent_links: List[Link] = []
        self._headers = ["Title", "Tags", "Last Accessed", "", ""]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Returns the total number of rows (standard + recent links)."""
        return len(self._links) + len(self._recent_links)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Returns the number of columns in the model."""
        return len(self._headers)

    def data(
        self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        """Returns data for the given index and item role.

        Supports DisplayRole, ToolTipRole, FontRole, ForegroundRole, UserRole,
        and custom sort roles (UserRole+1, UserRole+2).
        """
        if not index.isValid():
            return None

        link = self._link_for_row(index.row())
        if link is None:
            return None

        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == self.COL_TITLE:
                return link.title
            elif col == self.COL_TAGS:
                if link.is_recent:
                    return "recent"
                if link.is_favorite:
                    return "favorite"
                return ", ".join(link.tags)
            elif col == self.COL_LAST_ACCESSED:
                return format_relative_date(link.last_accessed)
            elif col in (self.COL_EDIT, self.COL_COPY):
                return ""

        if role == Qt.ItemDataRole.ToolTipRole:
            if col == self.COL_TITLE:
                tooltip = link.url
                tooltip += (
                    f"\n\nCreated: {link.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                tooltip += (
                    f"\nModified: {link.updated_at.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                tooltip += "\n\nClick to open • Double-click to edit"
                return tooltip
            elif col == self.COL_TAGS:
                return "Double-click to edit"
            elif col == self.COL_LAST_ACCESSED:
                return link.last_accessed.strftime("%Y-%m-%d %H:%M:%S")
            elif col == self.COL_EDIT:
                return "Click to edit"
            elif col == self.COL_COPY:
                return "Click to copy URL"

        if role == Qt.ItemDataRole.FontRole:
            if link.is_recent or link.is_favorite:
                font = QFont()
                font.setItalic(True)
                return font
            return None

        if role == Qt.ItemDataRole.ForegroundRole:
            if col == self.COL_TITLE:
                link_type = link.link_type
                ext = link.file_extension
                return get_color_for_link(link.url, link_type, ext)
            return None

        if role == Qt.ItemDataRole.UserRole:
            return link.id

        if role == Qt.ItemDataRole.UserRole + 1:
            if col == self.COL_LAST_ACCESSED:
                return link.last_accessed
            elif col == self.COL_TITLE:
                return link.created_at
            elif col == self.COL_TAGS:
                return link.tags[0] if link.tags else ""

        if role == Qt.ItemDataRole.UserRole + 2:
            if col == self.COL_TITLE:
                return link.created_at
            elif col == self.COL_TAGS:
                return link.updated_at

        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        """Returns the header text for the given section and orientation."""
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            return self._headers[section]
        return None

    def set_links(self, links: List[Link]) -> None:
        """Replaces the main link list with the given list."""
        self.beginResetModel()
        self._links = links
        self.endResetModel()

    def set_recent_links(self, recent: List[Link]) -> None:
        """Replaces the recent links list with the given list."""
        self.beginResetModel()
        self._recent_links = recent
        self.endResetModel()

    def append_links(self, links: List[Link]) -> None:
        """Appends links to the main list, notifying the view of new rows."""
        self.beginInsertRows(
            QModelIndex(), len(self._links), len(self._links) + len(links) - 1
        )
        self._links.extend(links)
        self.endInsertRows()

    def append_recent_links(self, recent: List[Link]) -> None:
        """Appends links to the recent list, notifying the view of new rows."""
        self.beginInsertRows(
            QModelIndex(),
            len(self._links) + len(self._recent_links),
            len(self._links) + len(self._recent_links) + len(recent) - 1,
        )
        self._recent_links.extend(recent)
        self.endInsertRows()

    def _link_for_row(self, row: int) -> Link | None:
        """Resolves a row index to its corresponding Link, or None if out of range."""
        n = len(self._links)
        if row < n:
            return self._links[row]
        r = row - n
        if 0 <= r < len(self._recent_links):
            return self._recent_links[r]
        return None

    def get_link(self, row: int) -> Link | None:
        """Returns the Link at the given row index, or None if invalid."""
        return self._link_for_row(row)

    def get_link_by_id(self, link_id: str) -> Link | None:
        """Returns the Link with the given ID, or None if not found."""
        for link in self._links:
            if link.id == link_id:
                return link
        for link in self._recent_links:
            if link.id == link_id:
                return link
        return None


class LinkSortFilterModel(QSortFilterProxyModel):
    """Sort-filter proxy that filters links by search text, tags, and link types."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initializes the proxy model with empty filter state."""
        super().__init__(parent)
        self._search_text = ""
        self._search_terms = []
        self._selected_tags = set()
        self._match_all = False
        self._selected_types = set()

    def set_search_text(self, text: str) -> None:
        """Sets the search text filter and invalidates the current filter."""
        self._search_text = text.lower()
        self._search_terms = [term for term in text.lower().split() if term]
        self.invalidateFilter()

    def set_selected_tags(
        self, tags: set, match_all: bool = False, types: set | None = None
    ) -> None:
        """Sets tag and link-type filters and invalidates the current filter.

        Args:
            tags: Set of tag strings to filter on.
            match_all: If True, a link must have every tag to be accepted.
            types: Optional set of link type strings (or file extensions) to include.
        """
        self._selected_tags = tags
        self._match_all = match_all
        self._selected_types = types if types is not None else set()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Returns True if the row passes all active filters (search, tags, types)."""
        model = self.sourceModel()
        if not model:
            return True

        link = model.get_link(source_row)
        if not link:
            return True

        if self._search_terms:
            for term in self._search_terms:
                if not (
                    term in link.title.lower()
                    or term in link.url.lower()
                    or any(term in t.lower() for t in link.tags)
                ):
                    return False

        if self._selected_tags:
            if self._match_all:
                if not all(tag in link.tags for tag in self._selected_tags):
                    return False
            else:
                if not any(tag in link.tags for tag in self._selected_tags):
                    return False

        if self._selected_types:
            link_type = link.link_type
            link_ext = link.file_extension
            link_type_key = link_ext if link_ext else link_type
            if link_type_key not in self._selected_types:
                return False

        return True

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        """Compares two model indexes for sorting using custom sort roles."""
        source_model = self.sourceModel()
        if not source_model:
            return super().lessThan(left, right)

        role = self.sortRole()

        if role == Qt.ItemDataRole.UserRole + 1:
            left_link = source_model.get_link(left.row())
            right_link = source_model.get_link(right.row())
            if left_link and right_link:
                col = left.column()
                if col == LinkTableModel.COL_TITLE:
                    return left_link.created_at < right_link.created_at
                elif col == LinkTableModel.COL_LAST_ACCESSED:
                    return left_link.last_accessed < right_link.last_accessed
                elif col == LinkTableModel.COL_TAGS:
                    return (left_link.tags[0] if left_link.tags else "") < (
                        right_link.tags[0] if right_link.tags else ""
                    )

        elif role == Qt.ItemDataRole.UserRole + 2:
            left_link = source_model.get_link(left.row())
            right_link = source_model.get_link(right.row())
            if left_link and right_link:
                col = left.column()
                if col == LinkTableModel.COL_TITLE:
                    return left_link.created_at < right_link.created_at
                elif col == LinkTableModel.COL_TAGS:
                    return left_link.updated_at < right_link.updated_at

        return super().lessThan(left, right)
