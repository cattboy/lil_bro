"""Tests for the WASD navigation event filter.

Contract under test (see src/gui/input/wasd_filter.py):
- ``W`` clicks the active surface's default button (proceed).
- ``S`` rejects the active dialog, or calls ``_on_stop_clicked`` on a window.
- ``W``/``S`` are inert while a text-input widget holds focus.
- Modifier chords (Ctrl/Alt/Shift) and other keys are ignored.

The ``eventFilter`` dispatch tests swap the module's ``QApplication`` symbol
for a fake so the active surface / focus widget are deterministic without a
real window manager (Shiboken extension types reject attribute monkeypatching).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QDialog, QLineEdit, QWidget

from src.gui.input import wasd_filter
from src.gui.input.wasd_filter import WASDInputFilter
from src.gui.widgets.approval_dialog import ApprovalDialog


def _key(key, modifier=Qt.KeyboardModifier.NoModifier):
    return QKeyEvent(QEvent.Type.KeyPress, key, modifier)


class _FakeApp:
    """Stand-in for QApplication with controllable active surface / focus."""

    def __init__(self, modal=None, window=None, focus=None):
        self._modal = modal
        self._window = window
        self._focus = focus

    def activeModalWidget(self):
        return self._modal

    def activeWindow(self):
        return self._window

    def focusWidget(self):
        return self._focus


# ── direct helper behavior ───────────────────────────────────────────────

def test_proceed_clicks_default_button(qtbot):
    dialog = ApprovalDialog("apply setting")
    qtbot.addWidget(dialog)
    assert WASDInputFilter()._proceed(dialog) is True
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_back_rejects_dialog(qtbot):
    dialog = ApprovalDialog("apply setting")
    qtbot.addWidget(dialog)
    assert WASDInputFilter()._back(dialog) is True
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_proceed_without_default_button_returns_false(qtbot):
    dialog = QDialog()
    qtbot.addWidget(dialog)
    assert WASDInputFilter()._proceed(dialog) is False


def test_default_button_finds_approve(qtbot):
    dialog = ApprovalDialog("x")
    qtbot.addWidget(dialog)
    assert WASDInputFilter._default_button(dialog) is dialog.approve_btn


def test_back_window_calls_stop_handler(qtbot):
    calls = []

    class _FakeWindow(QWidget):
        def _on_stop_clicked(self):
            calls.append(True)

    win = _FakeWindow()
    qtbot.addWidget(win)
    # A plain window is not a QDialog, so _back routes to the stop handler.
    assert WASDInputFilter()._back(win) is True
    assert calls == [True]


def test_back_plain_window_without_handler_returns_false(qtbot):
    win = QWidget()
    qtbot.addWidget(win)
    assert WASDInputFilter()._back(win) is False


# ── eventFilter dispatch ───────────────────────────────────────────────────

def test_eventfilter_ignores_non_ws_keys():
    assert WASDInputFilter().eventFilter(None, _key(Qt.Key.Key_A)) is False


def test_eventfilter_ignores_non_keypress():
    evt = QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_W,
                    Qt.KeyboardModifier.NoModifier)
    assert WASDInputFilter().eventFilter(None, evt) is False


def test_eventfilter_w_proceeds(qtbot, monkeypatch):
    dialog = ApprovalDialog("x")
    qtbot.addWidget(dialog)
    monkeypatch.setattr(wasd_filter, "QApplication", _FakeApp(modal=dialog))
    assert WASDInputFilter().eventFilter(None, _key(Qt.Key.Key_W)) is True
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_eventfilter_s_backs(qtbot, monkeypatch):
    dialog = ApprovalDialog("x")
    qtbot.addWidget(dialog)
    monkeypatch.setattr(wasd_filter, "QApplication", _FakeApp(modal=dialog))
    assert WASDInputFilter().eventFilter(None, _key(Qt.Key.Key_S)) is True
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_eventfilter_ignores_modifier_chord(qtbot, monkeypatch):
    dialog = ApprovalDialog("x")
    qtbot.addWidget(dialog)
    monkeypatch.setattr(wasd_filter, "QApplication", _FakeApp(modal=dialog))
    handled = WASDInputFilter().eventFilter(
        None, _key(Qt.Key.Key_W, Qt.KeyboardModifier.ControlModifier)
    )
    assert handled is False
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_eventfilter_inert_while_text_field_focused(qtbot, monkeypatch):
    line = QLineEdit()
    dialog = ApprovalDialog("x")
    qtbot.addWidget(line)
    qtbot.addWidget(dialog)
    # Focus is in a text input -> W must pass through untouched.
    monkeypatch.setattr(
        wasd_filter, "QApplication", _FakeApp(modal=dialog, focus=line)
    )
    assert WASDInputFilter().eventFilter(None, _key(Qt.Key.Key_W)) is False
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_eventfilter_editable_combo_is_text_input(qtbot, monkeypatch):
    from PySide6.QtWidgets import QComboBox

    combo = QComboBox()
    combo.setEditable(True)
    dialog = ApprovalDialog("x")
    qtbot.addWidget(combo)
    qtbot.addWidget(dialog)
    monkeypatch.setattr(
        wasd_filter, "QApplication", _FakeApp(modal=dialog, focus=combo)
    )
    # Use the W/proceed path: Accepted (1) is distinguishable from the
    # default result (0), unlike Rejected which collides with the default.
    assert WASDInputFilter().eventFilter(None, _key(Qt.Key.Key_W)) is False
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_eventfilter_falls_back_to_active_window(qtbot, monkeypatch):
    # No modal up -> the filter uses activeWindow() instead.
    calls = []

    class _FakeWindow(QWidget):
        def _on_stop_clicked(self):
            calls.append(True)

    win = _FakeWindow()
    qtbot.addWidget(win)
    monkeypatch.setattr(wasd_filter, "QApplication", _FakeApp(window=win))
    assert WASDInputFilter().eventFilter(None, _key(Qt.Key.Key_S)) is True
    assert calls == [True]


def test_eventfilter_no_surface_returns_false(monkeypatch):
    monkeypatch.setattr(wasd_filter, "QApplication", _FakeApp())
    assert WASDInputFilter().eventFilter(None, _key(Qt.Key.Key_W)) is False
