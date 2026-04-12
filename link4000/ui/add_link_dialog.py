"""Dialog for adding or editing a single link entry.

Provides input fields for title, URL/path, and comma-separated tags.
Supports file/folder browsing, auto-filling the title from the URL/path,
and tag auto-completion from existing tags. Also supports deleting an
existing link in edit mode.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QCompleter,
    QFileDialog,
    QMenu,
    QWidget,
)
from typing import Optional

from PySide6.QtCore import Qt, QStringListModel, QPoint, Signal

from link4000.models.link import Link
from link4000.utils.path_utils import (
    is_file_path,
    resolve_lnk,
    resolve_unc_path,
    is_sharepoint_url,
    get_sharepoint_file_extension,
)


class AddLinkDialog(QDialog):
    """Dialog for creating or editing a link entry.

    In edit mode, populates fields from an existing Link and provides
    a delete button. In add mode, auto-fills the title from the URL or
    file path when the user has not set it manually.

    Attributes:
        delete_requested: Signal emitted when the user confirms deletion.
    """

    delete_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        link: Link | None = None,
        url: str = "",
        all_tags: set[str] | None = None,
    ) -> None:
        """Initialize the add/edit link dialog.

        Args:
            parent: The parent widget.
            link: An existing Link to edit, or None for creating a new link.
            url: Optional pre-filled URL or file path.
            all_tags: Set of existing tag names for auto-completion.
        """
        super().__init__(parent)
        self._link = link
        self._is_edit = link is not None
        self._all_tags = all_tags if all_tags else set()
        self._deleted = False
        self._title_manually_set = False
        self._auto_filling_title = False

        self.setWindowTitle("Edit Link" if self._is_edit else "Add Link")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("Title:"))
        self._title_input = QLineEdit()
        self._title_input.textChanged.connect(self._on_title_changed)
        title_layout.addWidget(self._title_input)
        layout.addLayout(title_layout)

        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("URL / Path:"))
        self._url_input = QLineEdit()
        self._url_input.textChanged.connect(self._on_url_changed)
        url_layout.addWidget(self._url_input)

        self._browse_button = QPushButton("…")
        self._browse_button.setFixedWidth(30)
        self._browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._browse_button.setToolTip("Browse for file or folder")
        self._browse_button.clicked.connect(self._on_browse_clicked)
        url_layout.addWidget(self._browse_button)

        layout.addLayout(url_layout)

        tags_layout = QHBoxLayout()
        tags_layout.addWidget(QLabel("Tags:"))
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
        tags_layout.addWidget(self._tags_input)
        layout.addLayout(tags_layout)

        button_layout = QHBoxLayout()

        if self._is_edit:
            self._delete_button = QPushButton("Delete")
            self._delete_button.setStyleSheet("color: #d32f2f;")
            self._delete_button.clicked.connect(self._on_delete_clicked)
            button_layout.addWidget(self._delete_button)

        button_layout.addStretch()

        self._save_button = QPushButton("Save")
        self._save_button.setDefault(True)
        self._save_button.clicked.connect(self._on_save)
        button_layout.addWidget(self._save_button)

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_button)

        layout.addLayout(button_layout)

        if link:
            self._title_input.setText(link.title)
            self._url_input.setText(link.url)
            self._tags_input.setText(", ".join(link.tags))
        elif url:
            self._url_input.setText(url)
            url = url.strip('"')
            if is_sharepoint_url(url):
                ext = get_sharepoint_file_extension(url)
                if ext:
                    import urllib.parse

                    parsed = urllib.parse.urlparse(url)
                    path = urllib.parse.unquote(parsed.path)
                    filename = path.rsplit("/", 1)[-1] if "/" in path else path
                    if filename:
                        self._auto_filling_title = True
                        self._title_input.setText(filename)
                        self._auto_filling_title = False
            elif is_file_path(url):
                basename = Path(url).name
                if basename:
                    self._auto_filling_title = True
                    self._title_input.setText(basename)
                    self._auto_filling_title = False

    # ------------------------------------------------------------------
    # Browse (Windows only)
    # ------------------------------------------------------------------

    def _on_browse_clicked(self) -> None:
        """Show a context menu to browse for a file or folder."""
        menu = QMenu(self._browse_button)
        file_action = menu.addAction("Choose File…")
        folder_action = menu.addAction("Choose Folder…")

        chosen = menu.exec(
            self._browse_button.mapToGlobal(QPoint(0, self._browse_button.height()))
        )
        if chosen == file_action:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Select File",
                "",
                "All Files (*)",
            )
            if path:
                self._set_path(path)
        elif chosen == folder_action:
            path = QFileDialog.getExistingDirectory(self, "Select Folder", "")
            if path:
                self._set_path(path)

    def _set_path(self, path: str) -> None:
        """Set the URL input from a browsed file or folder path.

        Normalizes path separators on Windows, resolves .lnk shortcut files
        to their targets (converting network drive paths to UNC), and
        auto-fills the title if the user has not set it manually.

        Args:
            path: The file or folder path selected by the user.
        """
        path = path.strip('"')

        lnk_title = ""
        if path.lower().endswith(".lnk"):
            target, lnk_title = resolve_lnk(Path(path))
            if target:
                path = target

        resolved = resolve_unc_path(path)
        self._url_input.setText(resolved)
        if not self._title_manually_set:
            # Use Path.name - normalize separators for cross-platform compatibility
            resolved_path = Path(resolved.replace("\\", "/")) if resolved else Path()
            basename = lnk_title if lnk_title else resolved_path.name
            if basename:
                self._auto_filling_title = True
                self._title_input.setText(basename)
                self._auto_filling_title = False

    def _on_url_changed(self, text: str) -> None:
        """Handle URL input changes and auto-fill the title for file paths.

        Args:
            text: The current text in the URL input field.
        """
        if not self._title_manually_set and not self._is_edit:
            text = text.strip('"')
            if is_file_path(text):
                basename = Path(text).name
                if basename:
                    self._auto_filling_title = True
                    self._title_input.setText(basename)
                    self._auto_filling_title = False

    def _on_title_changed(self, text: str) -> None:
        """Track whether the user has manually edited the title field.

        Args:
            text: The current text in the title input field.
        """
        if not self._auto_filling_title and not self._is_edit:
            self._title_manually_set = bool(text.strip())

    # ------------------------------------------------------------------
    # Tag auto-completion
    # ------------------------------------------------------------------

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
        tags already entered, and builds completion strings that include
        the existing input prefix.

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
            prefix = input_text[: -len(current)]
            matches_with_input = [prefix + m for m in sorted(matches)]
        else:
            matches_with_input = sorted(matches)

        self._completer.setModel(QStringListModel(matches_with_input, self._completer))

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        """Validate inputs and save the link, then accept the dialog."""
        title = self._title_input.text().strip()
        url = self._url_input.text().strip().strip('"')

        if not title:
            QMessageBox.warning(self, "Validation Error", "Title is required")
            return

        if not url:
            QMessageBox.warning(self, "Validation Error", "URL / Path is required")
            return

        if is_file_path(url):
            url = resolve_unc_path(url)

        tags = [t.strip() for t in self._tags_input.text().split(",") if t.strip()]

        if self._is_edit:
            self._link.title = title
            self._link.url = url
            self._link.tags = tags
            self.link = self._link
        else:
            self.link = Link(title=title, url=url, tags=tags)

        self.accept()

    def _on_delete_clicked(self) -> None:
        """Confirm and delete the current link, emitting delete_requested."""
        reply = QMessageBox.question(
            self,
            "Delete Link",
            f"Are you sure you want to delete '{self._link.title}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._deleted = True
            self.delete_requested.emit()
            self.accept()

    def get_link(self) -> Optional[Link]:
        """Return the constructed Link object, or None if deleted.

        Returns:
            The Link created or edited by this dialog, or None if the
            user chose to delete the link.
        """
        return None if self._deleted else self.link
