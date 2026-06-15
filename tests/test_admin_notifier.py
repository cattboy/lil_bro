"""Tests for AdminNotifier — the styled non-modal not-elevated warning dialog.

Uses the offscreen Qt platform (set in conftest.py) + the qtbot fixture so a
QApplication exists. The dialog is a real CardDialog (no QMessageBox), so the
tests inspect the live widget tree.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton

from src.gui.admin_notifier import AdminNotifier, AdminWarningDialog


def test_admin_notifier_shows_once(qtbot):
    """show_warning builds and shows one dialog; the second call is a no-op."""
    notifier = AdminNotifier()
    notifier.show_warning()
    dialog = notifier._dialog
    assert isinstance(dialog, AdminWarningDialog)
    qtbot.addWidget(dialog)

    notifier.show_warning()  # once-guard: self._dialog is not None
    assert notifier._dialog is dialog  # same instance, not rebuilt


def test_admin_warning_dialog_follows_popout_rule(qtbot):
    """Styled card, non-modal, with exactly one default primary button (the W/Enter target)."""
    dialog = AdminWarningDialog()
    qtbot.addWidget(dialog)

    assert dialog.objectName() == "cardDialog"  # drives the DESIGN.md card QSS
    assert dialog.isModal() is False  # non-modal: never blocks startup

    # The popout rule (WASDInputFilter) clicks the surface's isDefault() button on W.
    default_buttons = [b for b in dialog.findChildren(QPushButton) if b.isDefault()]
    assert len(default_buttons) == 1
    assert default_buttons[0].objectName() == "primary"


def test_admin_warning_dialog_text(qtbot):
    """The dialog tells the user lil_bro isn't elevated and to restart as Admin."""
    dialog = AdminWarningDialog()
    qtbot.addWidget(dialog)

    text = " ".join(lbl.text() for lbl in dialog.findChildren(QLabel))
    assert "Administrator" in text
    assert "restart" in text.lower()
