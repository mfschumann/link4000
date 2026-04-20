"""Dialog for filtering links by tags and link types.

Provides a two-list interface where users can select one or more tags
and link types to filter the displayed links. Supports AND/OR matching
for tags, live preview of the filter via signals, and restoring the
original state on cancel or close.
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QRadioButton,
    QLabel,
    QWidget,
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QFont, QCloseEvent

from link4000.utils.config import get_color_for_link


class TagFilterWindow(QDialog):
    """Dialog for selecting tags and link types to filter the link list.

    Displays two list widgets side by side: one for tags and one for types.
    Users can select multiple items in each list and choose between AND/OR
    matching for tags. Selections are emitted as signals for live preview
    and final confirmation.

    Attributes:
        tags_and_types_selected: Signal emitted on OK with the final selection
            as (tags, match_all, types).
        filter_preview: Signal emitted on every selection change for live
            preview as (tags, match_all, types).
        _dynamic_tags: Tuple of tag names that are dynamically generated
            (e.g. "recent", "favorite") and displayed in italics.
        _link_types: Set of known link type strings.
    """

    tags_and_types_selected = Signal(set, bool, set)  # (tags, tag_match_all, types)
    filter_preview = Signal(set, bool, set)  # Preview filter as selection changes
    _dynamic_tags = (
        "favorite",  # from json_store
        "recent",  # from recent_docs plugins
        "office_recent",  # from office_recent_docs plugin
        "edge_favorites",  # from edge_favorites plugin
        "edge_history",  # from edge_history plugin
    )
    _link_types = {"web", "folder", "file", "sharepoint", "unknown"}

    def __init__(
        self,
        parent: QWidget | None = None,
        all_tags: set[str] | None = None,
        selected_tags: set[str] | None = None,
        match_all: bool = False,
        all_types: set[str] | None = None,
        selected_types: set[str] | None = None,
    ) -> None:
        """Initialize the tag and type filter dialog.

        Args:
            parent: The parent widget.
            all_tags: Set of all available tag names.
            selected_tags: Set of tags that should be pre-selected.
            match_all: If True, tags are matched with AND logic; otherwise OR.
            all_types: Set of all available link type names.
            selected_types: Set of types that should be pre-selected.
        """
        super().__init__(parent)
        self._all_tags = all_tags or set()
        self._selected_tags = selected_tags or set()
        self._match_all = match_all
        self._all_types = all_types or set()
        self._selected_types = selected_types or set()

        self._original_tags = set(selected_tags)
        self._original_match_all = match_all
        self._original_types = set(selected_types)

        self.setWindowTitle("Filter by Tags and Types")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self._setup_ui()

    def _sort_types(self, types: set[str]) -> list[str]:
        """Sort link types, grouping known types before file extensions.

        Args:
            types: Iterable of type name strings.

        Returns:
            A sorted list of known link types followed by sorted file
            extensions.
        """
        link_types = sorted([t for t in types if t in self._link_types])
        extensions = sorted([t for t in types if t not in self._link_types])
        return link_types + extensions

    def _sort_tags(self, tags: set[str]) -> list[str]:
        """Sort tags, placing dynamic tags before regular tags.

        Args:
            tags: Iterable of tag name strings.

        Returns:
            A sorted list of dynamic tags followed by sorted regular tags.
        """
        dynamic = sorted([t for t in tags if t in self._dynamic_tags])
        regular = sorted([t for t in tags if t not in self._dynamic_tags])
        return dynamic + regular

    def _setup_ui(self) -> None:
        """Set up the dialog's user interface with tag and type list widgets."""
        layout = QVBoxLayout(self)

        lists_layout = QHBoxLayout()

        tags_widget = QWidget()
        tags_layout = QVBoxLayout(tags_widget)

        tags_label = QLabel("Tags:")
        tags_layout.addWidget(tags_label)

        self._tags_list = QListWidget()
        self._tags_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._tags_list.itemSelectionChanged.connect(self._on_selection_changed)
        for tag in self._sort_tags(self._all_tags):
            self._tags_list.addItem(tag)
        for i in range(self._tags_list.count()):
            item = self._tags_list.item(i)
            if item.text() in self._selected_tags:
                item.setSelected(True)
            if item.text() in self._dynamic_tags:
                font = QFont()
                font.setItalic(True)
                item.setFont(font)
        tags_layout.addWidget(self._tags_list)

        self._tag_and_radio = QRadioButton("Match ALL tags (AND)")
        self._tag_or_radio = QRadioButton("Match ANY tag (OR)")
        self._tag_and_radio.toggled.connect(self._on_selection_changed)
        if self._match_all:
            self._tag_and_radio.setChecked(True)
        else:
            self._tag_or_radio.setChecked(True)
        tags_layout.addWidget(self._tag_and_radio)
        tags_layout.addWidget(self._tag_or_radio)

        lists_layout.addWidget(tags_widget)

        types_widget = QWidget()
        types_layout = QVBoxLayout(types_widget)

        types_label = QLabel("Types:")
        types_layout.addWidget(types_label)

        self._types_list = QListWidget()
        self._types_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._types_list.itemSelectionChanged.connect(self._on_selection_changed)
        sorted_types = self._sort_types(self._all_types)
        for type_item in sorted_types:
            self._types_list.addItem(type_item)
        for i in range(self._types_list.count()):
            item = self._types_list.item(i)
            if item.text() in self._selected_types:
                item.setSelected(True)
            type_text = item.text()
            if type_text.startswith("."):
                link_type = "file"
                ext = type_text
            else:
                link_type = type_text
                ext = ""
            color = get_color_for_link(type_text, link_type, ext)
            item.setForeground(color)
        types_layout.addWidget(self._types_list)

        lists_layout.addWidget(types_widget)

        layout.addLayout(lists_layout)

        button_layout = QHBoxLayout()

        self._clear_button = QPushButton("Clear")
        self._clear_button.clicked.connect(self._on_clear)
        button_layout.addWidget(self._clear_button)

        button_layout.addStretch()

        self._ok_button = QPushButton("OK")
        self._ok_button.clicked.connect(self._on_ok)
        self._ok_button.setDefault(True)
        button_layout.addWidget(self._ok_button)

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.clicked.connect(self._on_cancel)
        button_layout.addWidget(self._cancel_button)

        layout.addLayout(button_layout)

    def _restore_original_state(self) -> None:
        """Restore tag, type, and match-mode selections to their initial values."""
        if not hasattr(self, "_types_list") or not hasattr(self, "_tags_list"):
            return
        for i in range(self._tags_list.count()):
            item = self._tags_list.item(i)
            item.setSelected(item.text() in self._original_tags)
        for i in range(self._types_list.count()):
            item = self._types_list.item(i)
            item.setSelected(item.text() in self._original_types)
        if self._original_match_all:
            self._tag_and_radio.setChecked(True)
        else:
            self._tag_or_radio.setChecked(True)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle the window close event by restoring original state and ignoring.

        Args:
            event: The close event.
        """
        self._restore_original_state()
        self.filter_preview.emit(
            self._original_tags, self._original_match_all, self._original_types
        )
        super().reject()
        event.ignore()

    def reject(self) -> None:
        """Handle dialog rejection by restoring original state and emitting preview."""
        self._restore_original_state()
        self.filter_preview.emit(
            self._original_tags, self._original_match_all, self._original_types
        )
        super().reject()

    def _on_selection_changed(self) -> None:
        """Emit a filter preview signal whenever the selection changes."""
        if not hasattr(self, "_types_list") or not hasattr(self, "_tags_list"):
            return
        selected_tags = {item.text() for item in self._tags_list.selectedItems()}
        selected_types = {item.text() for item in self._types_list.selectedItems()}
        tag_match_all = self._tag_and_radio.isChecked()
        self.filter_preview.emit(selected_tags, tag_match_all, selected_types)

    def _on_clear(self) -> None:
        """Deselect all items in both the tags and types list widgets."""
        if not hasattr(self, "_types_list") or not hasattr(self, "_tags_list"):
            return
        for i in range(self._tags_list.count()):
            self._tags_list.item(i).setSelected(False)
        for i in range(self._types_list.count()):
            self._types_list.item(i).setSelected(False)

    def _on_cancel(self) -> None:
        """Handle cancel by restoring original state and rejecting the dialog."""
        self._restore_original_state()
        self.filter_preview.emit(
            self._original_tags, self._original_match_all, self._original_types
        )
        self.reject()

    def _on_ok(self) -> None:
        """Confirm the current selection and accept the dialog."""
        selected_tags = {item.text() for item in self._tags_list.selectedItems()}
        selected_types = {item.text() for item in self._types_list.selectedItems()}
        tag_match_all = self._tag_and_radio.isChecked()
        self.tags_and_types_selected.emit(selected_tags, tag_match_all, selected_types)
        self.accept()

    def get_selected_tags(self) -> set[str]:
        """Return the set of tags that were selected on dialog open.

        Returns:
            The set of originally selected tag names.
        """
        return self._selected_tags
