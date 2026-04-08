"""Shared test fixtures for Qt-based tests."""

import pytest


@pytest.fixture(scope="session", autouse=True)
def _qapp():
    """Create a QApplication instance for the entire test session."""
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return

    app = QApplication.instance()
    if app is None:
        QApplication([])
