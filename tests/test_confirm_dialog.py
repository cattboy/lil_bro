"""Verifies ConfirmDialog Yes/No accept/reject + Esc semantics."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

from src.gui.widgets.confirm_dialog import ConfirmDialog


def test_yes_returns_accepted(qtbot):
    dialog = ConfirmDialog("Download model?")
    qtbot.addWidget(dialog)
    dialog.show()
    QTest.qWait(10)
    dialog.yes_btn.click()
    QTest.qWait(10)
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_no_returns_rejected(qtbot):
    dialog = ConfirmDialog("Download model?")
    qtbot.addWidget(dialog)
    dialog.show()
    QTest.qWait(10)
    dialog.no_btn.click()
    QTest.qWait(10)
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_escape_returns_rejected(qtbot):
    dialog = ConfirmDialog("Download model?")
    qtbot.addWidget(dialog)
    dialog.show()
    QTest.qWait(10)
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    QTest.qWait(10)
    assert dialog.result() == QDialog.DialogCode.Rejected
