"""Verifies ApprovalDialog accept/reject behavior.

Approve → DialogCode.Accepted (truthy); Deny / Esc / close → Rejected.
The dialog doesn't perform the system change itself — it just returns
the user's choice. The handler returns a bool from the exec result.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

from src.gui.widgets.approval_dialog import ApprovalDialog


def _exec_async(dialog, action):
    dialog.show()
    QTest.qWait(10)
    action()
    QTest.qWait(10)


def test_approve_returns_accepted(qtbot):
    dialog = ApprovalDialog("apply NVIDIA setting")
    qtbot.addWidget(dialog)
    _exec_async(dialog, dialog.approve_btn.click)
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_deny_returns_rejected(qtbot):
    dialog = ApprovalDialog("apply NVIDIA setting")
    qtbot.addWidget(dialog)
    _exec_async(dialog, dialog.deny_btn.click)
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_escape_returns_rejected(qtbot):
    dialog = ApprovalDialog("apply NVIDIA setting")
    qtbot.addWidget(dialog)
    dialog.show()
    QTest.qWait(10)
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    QTest.qWait(10)
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_action_text_in_accessible_description(qtbot):
    text = "Switch power plan to High Performance"
    dialog = ApprovalDialog(text)
    qtbot.addWidget(dialog)
    assert dialog.accessibleDescription() == text


def test_approve_button_is_default_focus(qtbot):
    dialog = ApprovalDialog("x")
    qtbot.addWidget(dialog)
    assert dialog.approve_btn.isDefault()
    assert dialog.approve_btn.objectName() == "primary"
