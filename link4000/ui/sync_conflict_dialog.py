"""Dialog for resolving synchronization conflicts between local and remote."""

from typing import Dict, List

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from link4000.data.sync import ConflictRecord


def _format_link_info(link) -> str:
    """Format a link's metadata into a compact read-only string.

    Args:
        link: The link to format.

    Returns:
        A multi-line string with title, URL, and tags.
    """
    tags = ", ".join(link.tags) if link.tags else "(no tags)"
    return f"Title:  {link.title}\nURL:    {link.url}\nTags:   {tags}"


class SyncConflictDialog(QDialog):
    """Dialog that presents synchronization conflicts and lets the user resolve them.

    For each :class:`ConflictRecord`, the user can choose to keep the local
    version, the remote version, or both. An "Apply to All" combo applies one
    choice to every conflict.
    """

    def __init__(self, parent: QWidget | None, conflicts: List[ConflictRecord]) -> None:
        """Initialize the conflict-resolution dialog.

        Args:
            parent: The parent widget.
            conflicts: The list of conflicts to resolve.
        """
        super().__init__(parent)
        self._conflicts = conflicts
        self.setWindowTitle("Resolve Sync Conflicts")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)

        apply_all_layout = QHBoxLayout()
        apply_all_layout.addWidget(QLabel("Apply to All:"))
        self._apply_all = QComboBox()
        self._apply_all.addItems(["None", "Keep Local", "Keep Remote", "Keep Both"])
        self._apply_all.currentTextChanged.connect(self._on_apply_all_changed)
        apply_all_layout.addWidget(self._apply_all)
        apply_all_layout.addStretch()
        layout.addLayout(apply_all_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)

        self._combos: Dict[str, QComboBox] = {}
        for conflict in conflicts:
            box = QGroupBox(conflict.describe())
            box_layout = QVBoxLayout(box)

            kind_label = QLabel(self._kind_description(conflict))
            kind_label.setWordWrap(True)
            box_layout.addWidget(kind_label)

            combo = QComboBox()
            combo.addItems(["Keep Remote", "Keep Local", "Keep Both"])
            self._combos[conflict.link_id] = combo
            box_layout.addWidget(combo)

            inner_layout.addWidget(box)

        scroll.setWidget(inner)
        layout.addWidget(scroll)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        ok_button = QPushButton("OK")
        ok_button.setDefault(True)
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

    @staticmethod
    def _kind_description(conflict: ConflictRecord) -> str:
        """Return a human-readable description of the conflict kind.

        Args:
            conflict: The conflict to describe.

        Returns:
            A descriptive sentence for the conflict type.
        """
        if conflict.kind == "edit_edit":
            return "This link was edited on both sides since the last sync."
        if conflict.kind == "delete_edit":
            return "You deleted this link, but it was edited remotely."
        if conflict.kind == "edit_delete":
            return "You edited this link, but it was deleted remotely."
        return "Conflict detected for this link."

    def _on_apply_all_changed(self, text: str) -> None:
        """Apply the "Apply to All" choice to every per-conflict combo.

        Args:
            text: The selected "Apply to All" option.
        """
        if text == "None":
            return
        mapping = {
            "Keep Local": "Keep Local",
            "Keep Remote": "Keep Remote",
            "Keep Both": "Keep Both",
        }
        target = mapping.get(text)
        if target is None:
            return
        for combo in self._combos.values():
            combo.setCurrentText(target)

    def get_choices(self) -> Dict[str, str]:
        """Return the resolved choices for every conflict.

        Returns:
            A dict mapping each conflict link id to "local", "remote", or
            "keep_both".
        """
        token_map = {
            "Keep Local": "local",
            "Keep Remote": "remote",
            "Keep Both": "keep_both",
        }
        return {
            link_id: token_map.get(combo.currentText(), "remote")
            for link_id, combo in self._combos.items()
        }
