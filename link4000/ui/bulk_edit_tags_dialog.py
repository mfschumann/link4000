"""Dialog for bulk adding or removing tags from multiple selected items.

Provides a simple interface for users to specify comma-separated tags
to add to or remove from a set of previously selected link items. Includes
auto-completion support based on existing tags.
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCompleter,
    QWidget,
)
from PySide6.QtCore import Qt, QStringListModel


class BulkEditTagsDialog(QDialog):
    """Dialog for bulk editing tags on multiple selected link items.

    Supports two modes: adding tags to or removing tags from a set of
    selected items. Provides tag auto-completion based on existing tags.

    Attributes:
        MODE_ADD: Mode constant for adding tags.
        MODE_REMOVE: Mode constant for removing tags.
    """

    MODE_ADD = "add"
    MODE_REMOVE = "remove"

    def __init__(
        self, parent: QWidget | None, mode: str, selected_count: int, all_tags: set[str]
    ) -> None:
        """Initialize the bulk edit tags dialog.

        Args:
            parent: The parent widget.
            mode: One of MODE_ADD or MODE_REMOVE to determine the action.
            selected_count: The number of items that will be affected.
            all_tags: A collection of all existing tags for auto-completion.
        """
        super().__init__(parent)
        self._mode = mode
        self._selected_count = selected_count
        self._all_tags = all_tags

        self.setWindowTitle(f"{'Add' if mode == self.MODE_ADD else 'Remove'} Tags")
        self.setMinimumWidth(400)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog's user interface components."""
        layout = QVBoxLayout(self)

        action = "Add to" if self._mode == self.MODE_ADD else "Remove from"
        label = QLabel(f"{action} {self._selected_count} selected item(s):")
        layout.addWidget(label)

        self._tags_input = QLineEdit()
        self._tags_input.setPlaceholderText("comma, separated, tags")

        if self._all_tags:
            self._completer = QCompleter()
            self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self._completer.setCompletionMode(
                QCompleter.CompletionMode.InlineCompletion
            )
            self._tags_input.setCompleter(self._completer)
            self._tags_input.textChanged.connect(self._on_tags_text_changed)
            self._update_completer("")

        layout.addWidget(self._tags_input)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._ok_button = QPushButton("OK")
        self._ok_button.setDefault(True)
        self._ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self._ok_button)

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_button)

        layout.addLayout(button_layout)

    def _on_tags_text_changed(self, text: str) -> None:
        """Handle tag input text changes and update the completer model.

        Extracts the current (last) tag being typed after the most recent
        comma separator and refreshes the auto-completion suggestions.

        Args:
            text: The full current text in the tags input field.
        """
        if "," in text:
            current = text.rsplit(",", 1)[-1].strip()
        else:
            current = text.strip()
        self._update_completer(current)

    def _update_completer(self, current: str) -> None:
        """Update the auto-completer model with matching tag suggestions.

        Filters all known tags by the current partial input, excluding
        tags that have already been entered, and builds completion strings
        that include the existing input prefix.

        Args:
            current: The partial tag string to match against.
        """
        input_text = self._tags_input.text()
        if current:
            matches = [t for t in self._all_tags if current.lower() in t.lower()]
            link_tags = [t.strip().lower() for t in input_text.rsplit(",")[:-1]]
            matches = [m for m in matches if m not in link_tags]
        else:
            matches = list(self._all_tags)

        if input_text:
            matches_with_input = [
                input_text[: -1 * len(current)] + m for m in sorted(matches)
            ]
        else:
            matches_with_input = sorted(matches)

        self._completer.setModel(QStringListModel(matches_with_input, self._completer))

    def get_tags(self) -> list[str]:
        """Return the list of tags entered by the user.

        Returns:
            A list of non-empty, stripped tag strings parsed from
            comma-separated input.
        """
        text = self._tags_input.text()
        return [t.strip() for t in text.split(",") if t.strip()]
