"""Tests for CardDialog — the shared card dialog template (src/gui/widgets/dialogs.py).

Uses the offscreen Qt platform (conftest.py) + the qtbot fixture so a QApplication
exists and the live widget tree can be inspected.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QPushButton,
)

from src.gui.widgets.dialogs import _TONE_GLYPH, CardDialog


def test_single_button_card_has_no_secondary(qtbot):
    dialog = CardDialog("Heads up", "something happened", primary_label="OK")
    qtbot.addWidget(dialog)
    assert dialog.objectName() == "cardDialog"
    assert isinstance(dialog.primary_btn, QPushButton)
    assert dialog.secondary_btn is None


def test_single_button_accepts_on_click_and_esc(qtbot):
    for trigger in ("click", "esc"):
        dialog = CardDialog("Heads up", primary_label="OK")
        qtbot.addWidget(dialog)
        dialog.show()
        QTest.qWait(10)
        if trigger == "click":
            dialog.primary_btn.click()
        else:
            QTest.keyClick(dialog, Qt.Key.Key_Escape)
        QTest.qWait(10)
        assert dialog.result() == QDialog.DialogCode.Accepted


def test_two_button_card_secondary_setup(qtbot):
    dialog = CardDialog("Proceed?", "are you sure", primary_label="Yes",
                        secondary_label="No")
    qtbot.addWidget(dialog)
    assert isinstance(dialog.secondary_btn, QPushButton)
    # Secondary must not auto-default (WASD popout rule).
    assert dialog.secondary_btn.autoDefault() is False
    assert dialog.primary_btn.isDefault() is True


def test_two_button_rejects_on_secondary_and_esc(qtbot):
    for trigger in ("click", "esc"):
        dialog = CardDialog("Proceed?", primary_label="Yes", secondary_label="No")
        qtbot.addWidget(dialog)
        dialog.show()
        QTest.qWait(10)
        if trigger == "click":
            dialog.secondary_btn.click()
        else:
            QTest.keyClick(dialog, Qt.Key.Key_Escape)
        QTest.qWait(10)
        assert dialog.result() == QDialog.DialogCode.Rejected


def test_card_tone_drives_icon_glyph(qtbot):
    dialog = CardDialog("Error", "boom", tone="error")
    qtbot.addWidget(dialog)
    assert dialog.property("cardTone") == "error"

    icons = [w for w in dialog.findChildren(QLabel) if w.objectName() == "cardIcon"]
    assert len(icons) == 1
    assert icons[0].property("cardTone") == "error"
    assert icons[0].text() == _TONE_GLYPH["error"]


def test_accent_bar_variant_has_bar_and_no_icon(qtbot):
    dialog = CardDialog("Move mouse", "wiggle", icon=None, accent_bar=True)
    qtbot.addWidget(dialog)

    bars = [w for w in dialog.findChildren(QFrame) if w.objectName() == "cardAccentBar"]
    assert len(bars) == 1
    icons = [w for w in dialog.findChildren(QLabel) if w.objectName() == "cardIcon"]
    assert icons == []


def test_glow_applies_drop_shadow_to_primary(qtbot):
    glowing = CardDialog("Glow", glow=True)
    qtbot.addWidget(glowing)
    assert isinstance(glowing.primary_btn.graphicsEffect(), QGraphicsDropShadowEffect)

    plain = CardDialog("No glow", glow=False)
    qtbot.addWidget(plain)
    assert plain.primary_btn.graphicsEffect() is None


def test_empty_description_is_hidden(qtbot):
    dialog = CardDialog("Title only")
    qtbot.addWidget(dialog)
    descs = [w for w in dialog.findChildren(QLabel) if w.objectName() == "cardDesc"]
    assert len(descs) == 1
    assert descs[0].isHidden() is True
