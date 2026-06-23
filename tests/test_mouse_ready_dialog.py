"""Tests for MouseReadyDialog — the pre-measurement modal (src/gui/widgets/mouse_ready_dialog.py).

A thin single-action ``CardDialog`` specialization (accent-bar variant, no icon).
Uses the offscreen Qt platform (conftest.py) + the qtbot fixture so a QApplication
exists and the live widget tree can be inspected.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QPushButton

from src.gui.widgets.dialogs import CardDialog
from src.gui.widgets.mouse_ready_dialog import MouseReadyDialog


def test_is_card_dialog_with_single_action(qtbot):
    dialog = MouseReadyDialog()
    qtbot.addWidget(dialog)
    assert isinstance(dialog, CardDialog)
    assert dialog.objectName() == "cardDialog"
    # Single-action dialog: a primary button and no secondary.
    assert isinstance(dialog.primary_btn, QPushButton)
    assert dialog.secondary_btn is None


def test_primary_label_and_title(qtbot):
    dialog = MouseReadyDialog()
    qtbot.addWidget(dialog)
    assert "Mouse" in dialog.primary_btn.text()
    titles = [w for w in dialog.findChildren(QLabel) if w.objectName() == "cardTitle"]
    assert len(titles) == 1
    assert titles[0].text() == "Mouse Polling Check"


def test_accent_bar_variant_has_bar_and_no_icon(qtbot):
    """accent_bar=True / icon=None means a tone bar and no glyph label."""
    dialog = MouseReadyDialog()
    qtbot.addWidget(dialog)
    bars = [w for w in dialog.findChildren(QFrame) if w.objectName() == "cardAccentBar"]
    assert len(bars) == 1
    icons = [w for w in dialog.findChildren(QLabel) if w.objectName() == "cardIcon"]
    assert icons == []


def test_modal_and_accent_tone(qtbot):
    dialog = MouseReadyDialog()
    qtbot.addWidget(dialog)
    assert dialog.isModal() is True
    assert dialog.property("cardTone") == "accent"
    assert dialog.accessibleName() == "Mouse ready dialog"


def test_accepts_on_click_and_esc(qtbot):
    """Esc accepts (there is no meaningful skip — measurement always runs)."""
    for trigger in ("click", "esc"):
        dialog = MouseReadyDialog()
        qtbot.addWidget(dialog)
        dialog.show()
        QTest.qWait(10)
        if trigger == "click":
            dialog.primary_btn.click()
        else:
            QTest.keyClick(dialog, Qt.Key.Key_Escape)
        QTest.qWait(10)
        assert dialog.result() == QDialog.DialogCode.Accepted
