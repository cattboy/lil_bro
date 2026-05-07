"""Verifies the QSettings wrapper round-trips values + geometry."""

from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMainWindow

from src.gui.settings import Settings


_TEST_ORG = "lil_bro_test"
_TEST_APP = "GUI_test"


def _clear_test_settings():
    QSettings(_TEST_ORG, _TEST_APP).clear()


def test_get_set_round_trip(qtbot):
    _clear_test_settings()
    s = Settings(_TEST_ORG, _TEST_APP)
    s.set("ui/theme", "dark")
    assert s.get("ui/theme") == "dark"


def test_get_returns_default_when_unset(qtbot):
    _clear_test_settings()
    s = Settings(_TEST_ORG, _TEST_APP)
    assert s.get("missing/key", "fallback") == "fallback"


def test_save_and_restore_geometry(qtbot):
    """The save/restore round-trip must persist geometry bytes that Qt accepts."""
    _clear_test_settings()
    s = Settings(_TEST_ORG, _TEST_APP)

    win_a = QMainWindow()
    qtbot.addWidget(win_a)
    win_a.show()
    win_a.resize(900, 640)
    s.save_geometry(win_a)

    # Confirm bytes were stored.
    saved = s.get("window/geometry")
    assert saved is not None
    assert len(bytes(saved)) > 0

    # Restore into a fresh window — Qt accepts the bytes (returns True).
    win_b = QMainWindow()
    qtbot.addWidget(win_b)
    assert s.restore_geometry(win_b) is True


def test_restore_geometry_returns_false_when_missing(qtbot):
    _clear_test_settings()
    s = Settings(_TEST_ORG, _TEST_APP)
    win = QMainWindow()
    qtbot.addWidget(win)
    assert s.restore_geometry(win) is False
