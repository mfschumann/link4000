"""UI state persistence for search term, filters, and sort order."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from link4000.utils.config import get_links_file_path
from link4000.utils.enums import TagMatchMode
from link4000.models.link_model import LinkTableModel
from PySide6.QtCore import Qt

_logger = logging.getLogger(__name__)

_SORT_ORDER_ASC = "asc"
_SORT_ORDER_DESC = "desc"

_MATCH_MODE_STRINGS = {
    "OR": TagMatchMode.OR,
    "AND": TagMatchMode.AND,
    "NONE": TagMatchMode.NONE,
}

_SORT_COLUMN_STRINGS = {
    "Title": LinkTableModel.COL_TITLE,
    "Tags": LinkTableModel.COL_TAGS,
    "Last Accessed": LinkTableModel.COL_LAST_ACCESSED,
}

# Serialized representations of the Qt sort roles used by the sort combo and
# the table header. Persisting the role (and not just the column) keeps the
# "saved first" secondary criterion and the combo/header distinction lossless
# across restarts.
_SORT_ROLE_STRINGS = {
    "display": Qt.ItemDataRole.DisplayRole,
    "user1": Qt.ItemDataRole.UserRole + 1,
    "user2": Qt.ItemDataRole.UserRole + 2,
}

_SORT_ROLE_TO_STRING = {value: key for key, value in _SORT_ROLE_STRINGS.items()}


def sort_role_to_string(role: int) -> str | None:
    """Return the serialized name of a Qt sort role.

    Args:
        role: A Qt item role value used for sorting.

    Returns:
        The persisted string for the role, or None if it is not one of the
        known sort roles.
    """
    return _SORT_ROLE_TO_STRING.get(role)


def sort_role_from_string(value: object) -> int | None:
    """Resolve a persisted sort role name back to its Qt role value.

    Args:
        value: The persisted value (expected to be a known role string).

    Returns:
        The Qt role value, or None when the value is unknown or not a string.
    """
    if not isinstance(value, str):
        return None
    return _SORT_ROLE_STRINGS.get(value)



def get_ui_state_file_path() -> str:
    """Return the filesystem path for the UI state file.

    The state file lives next to the links database so that it follows
    any custom ``--config`` / ``--links-file`` setting automatically.

    Returns:
        Absolute path to ``ui_state.json`` in the same directory as
        ``get_links_file_path()``.
    """
    links_path = Path(get_links_file_path())
    return str(links_path.parent / "ui_state.json")


def load_ui_state() -> dict:
    """Load persisted UI state from ``ui_state.json``.

    Returns an empty dict when the file is missing, unreadable, or
    corrupt.  Unknown/extra top-level keys are ignored by callers.

    Returns:
        Dict with keys ``search_text``, ``selected_tags``, ``match_mode``,
        ``selected_types``, ``sorting_active``, ``sort_column``,
        ``sort_order``, ``saved_first``, ``sort_role``, or ``{}`` if nothing
        could be loaded.
    """
    path = get_ui_state_file_path()
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        _logger.warning("Failed to read UI state from %s", path)
        return {}

    if not isinstance(data, dict):
        _logger.warning("UI state file %s is not a JSON object", path)
        return {}

    return data


def save_ui_state(state: dict) -> None:
    """Persist UI state to ``ui_state.json``.

    Writes with indentation for readability.  On write failure logs a
    warning but does not raise, so quit/close is never blocked.

    Args:
        state: State dictionary as produced by ``MainWindow._collect_ui_state``.
    """
    path = get_ui_state_file_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except OSError:
        _logger.warning("Failed to write UI state to %s", path)
