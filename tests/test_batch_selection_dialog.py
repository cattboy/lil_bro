"""Verifies BatchSelectionDialog returns the right indices for each action."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from src.gui.widgets.batch_selection_dialog import BatchSelectionDialog


def _proposals(n: int = 3) -> list[dict]:
    return [
        {"finding": f"check_{i}", "title": f"Title {i}",
         "severity": "MEDIUM", "can_auto_fix": True}
        for i in range(1, n + 1)
    ]


def test_apply_all_returns_full_list(qtbot):
    dialog = BatchSelectionDialog(_proposals(3))
    qtbot.addWidget(dialog)
    dialog.show()
    QTest.qWait(10)
    dialog.apply_all_btn.click()
    QTest.qWait(10)
    assert dialog.selected_indices() == [1, 2, 3]


def test_skip_returns_empty(qtbot):
    dialog = BatchSelectionDialog(_proposals(3))
    qtbot.addWidget(dialog)
    dialog.show()
    QTest.qWait(10)
    dialog.skip_btn.click()
    QTest.qWait(10)
    assert dialog.selected_indices() == []


def test_apply_selected_respects_uncheck(qtbot):
    dialog = BatchSelectionDialog(_proposals(3))
    qtbot.addWidget(dialog)
    dialog.show()
    QTest.qWait(10)
    dialog._list.item(0).setCheckState(Qt.CheckState.Unchecked)
    dialog.apply_btn.click()
    QTest.qWait(10)
    assert dialog.selected_indices() == [2, 3]


def test_escape_acts_as_skip(qtbot):
    dialog = BatchSelectionDialog(_proposals(2))
    qtbot.addWidget(dialog)
    dialog.show()
    QTest.qWait(10)
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    QTest.qWait(10)
    assert dialog.selected_indices() == []


def test_default_check_state_respects_can_auto_fix(qtbot):
    proposals = [
        {"finding": "auto", "title": "auto", "severity": "L", "can_auto_fix": True},
        {"finding": "manual", "title": "manual", "severity": "L", "can_auto_fix": False},
    ]
    dialog = BatchSelectionDialog(proposals)
    qtbot.addWidget(dialog)
    assert dialog._list.item(0).checkState() == Qt.CheckState.Checked
    assert dialog._list.item(1).checkState() == Qt.CheckState.Unchecked
