"""Application-wide WASD navigation layer.

A single ``QObject`` event filter installed once on the ``QApplication`` so the
whole app reads ``W`` / ``S`` as gamer-native aliases for keys it already
honors:

* ``W`` -> proceed / forward  -- clicks the active surface's default button.
* ``S`` -> back / escape       -- rejects the active dialog, or routes the main
  window to the same Stop/abort path ``Esc`` already triggers.

Design contract (office-hours design doc, 2026-06-02):

* **Reuse, never reinvent.** ``W``/``S`` drive the *actions* that already
  exist (``QPushButton.click`` on the default button, ``QDialog.reject``), not
  synthesized ``Enter``/``Esc`` key events. Synthesizing keys would re-enter
  the same handler stack and risk a double-fire against the existing
  ``Esc/Q/Enter/Return`` shortcuts.
* **Inert inside text input.** When the focus widget accepts typed text
  (``QLineEdit`` / ``QTextEdit`` / ``QPlainTextEdit`` / editable ``QComboBox``)
  the filter does nothing and lets the character through. This is the line that
  keeps the feature from breaking trust -- typing "wasd" into a field must
  never navigate the app.
* **Plain key only.** Any modifier (Ctrl/Alt/Shift/Meta) is ignored so chords
  like ``Ctrl+S`` are never swallowed.

The filter is global but resolves the active surface dynamically at each
keypress, so it does not matter which object owns it -- it is installed from
``MainWindow.__init__`` alongside the other keyboard wiring.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
)

# Widgets that consume typed characters. W/S stay inert while one of these
# holds focus.
_TEXT_INPUT_TYPES = (QLineEdit, QTextEdit, QPlainTextEdit)


class WASDInputFilter(QObject):
    """Global event filter mapping ``W`` -> proceed and ``S`` -> back/escape."""

    def eventFilter(self, obj, event):  # noqa: N802  Qt override
        if event.type() != QEvent.Type.KeyPress:
            return False

        key = event.key()
        if key not in (Qt.Key.Key_W, Qt.Key.Key_S):
            return False

        # Plain key only -- never swallow Ctrl+S, Alt+W, Shift+W, etc.
        if event.modifiers() != Qt.KeyboardModifier.NoModifier:
            return False

        # Focus guard: inert while a text-input widget has focus.
        if self._focus_accepts_text():
            return False

        surface = QApplication.activeModalWidget() or QApplication.activeWindow()
        if surface is None:
            return False

        if key == Qt.Key.Key_W:
            return self._proceed(surface)
        return self._back(surface)

    # ── helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _focus_accepts_text() -> bool:
        """True when the focused widget would consume a typed character."""
        widget = QApplication.focusWidget()
        if widget is None:
            return False
        if isinstance(widget, _TEXT_INPUT_TYPES):
            return True
        # Editable combo boxes embed a line edit that accepts text.
        if isinstance(widget, QComboBox) and widget.isEditable():
            return True
        return False

    @staticmethod
    def _proceed(surface) -> bool:
        """``W``: click the surface's default button, if it has an enabled one."""
        button = WASDInputFilter._default_button(surface)
        if button is not None and button.isEnabled():
            button.click()
            return True
        return False

    @staticmethod
    def _back(surface) -> bool:
        """``S``: reject a dialog, else route a window to its Stop/abort path."""
        if isinstance(surface, QDialog):
            surface.reject()
            return True
        # Non-dialog surface (the main window): mirror the Esc/Q hotkeys, which
        # call ``_on_stop_clicked`` -- itself a no-op while the Stop button is
        # hidden (pipeline idle). We invoke the same handler rather than
        # synthesizing an Esc keypress.
        handler = getattr(surface, "_on_stop_clicked", None)
        if callable(handler):
            handler()
            return True
        return False

    @staticmethod
    def _default_button(surface) -> QPushButton | None:
        """Return the surface's default ``QPushButton`` (the Enter target)."""
        for button in surface.findChildren(QPushButton):
            if button.isDefault():
                return button
        return None
