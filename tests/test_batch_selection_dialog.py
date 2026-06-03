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
    dialog._apply_btn.click()
    QTest.qWait(10)
    assert dialog.selected_indices() == [1, 2, 3]


def test_skip_returns_empty(qtbot):
    dialog = BatchSelectionDialog(_proposals(3))
    qtbot.addWidget(dialog)
    dialog.show()
    QTest.qWait(10)
    dialog._skip_btn.click()
    QTest.qWait(10)
    assert dialog.selected_indices() == []


def test_apply_selected_respects_uncheck(qtbot):
    dialog = BatchSelectionDialog(_proposals(3))
    qtbot.addWidget(dialog)
    dialog.show()
    QTest.qWait(10)
    dialog._fix_items[0].toggle()
    dialog._apply_btn.click()
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


def test_default_check_state_all_selected(qtbot):
    proposals = [
        {"finding": "auto", "title": "auto", "severity": "L", "can_auto_fix": True},
        {"finding": "manual", "title": "manual", "severity": "L", "can_auto_fix": False},
    ]
    dialog = BatchSelectionDialog(proposals)
    qtbot.addWidget(dialog)
    assert dialog._fix_items[0].is_selected
    assert dialog._fix_items[1].is_selected


def test_number_key_toggles_matching_fix(qtbot):
    dialog = BatchSelectionDialog(_proposals(3))
    qtbot.addWidget(dialog)
    dialog.show()
    QTest.qWait(10)
    # Pressing "2" deselects the second fix (default is all-selected).
    QTest.keyClick(dialog, Qt.Key.Key_2)
    assert dialog._fix_items[1].is_selected is False
    dialog._apply_btn.click()
    QTest.qWait(10)
    assert dialog.selected_indices() == [1, 3]


def test_number_key_out_of_range_is_ignored(qtbot):
    dialog = BatchSelectionDialog(_proposals(2))
    qtbot.addWidget(dialog)
    dialog.show()
    QTest.qWait(10)
    # Only two fixes -> "5" must not toggle anything or raise.
    QTest.keyClick(dialog, Qt.Key.Key_5)
    assert dialog._fix_items[0].is_selected
    assert dialog._fix_items[1].is_selected


def test_fix_item_shows_number_badge(qtbot):
    dialog = BatchSelectionDialog(_proposals(3))
    qtbot.addWidget(dialog)
    assert dialog._fix_items[0]._num_lbl.text() == "1"
    assert dialog._fix_items[2]._num_lbl.text() == "3"


def test_w_key_applies_not_cancels_through_wasd_filter(qtbot):
    """Regression: W (via the global WASD filter) must apply, not cancel.

    All three buttons are autoDefault by default. Once the dialog is shown,
    focus lands on the close button, which would steal default-ness and make
    the WASD filter's W/Enter click *it* (reject) instead of Apply. The two
    secondary buttons must disable autoDefault so the primary Apply button
    stays the sole default.
    """
    from src.gui.input.wasd_filter import WASDInputFilter

    dialog = BatchSelectionDialog(_proposals(3))
    qtbot.addWidget(dialog)
    dialog.show()
    QTest.qWait(10)

    # The secondary buttons must not be able to become the default button.
    assert dialog._skip_btn.autoDefault() is False
    # The WASD filter resolves W to this surface's default button; it must be
    # Apply, even though the close button holds focus after show().
    assert WASDInputFilter._default_button(dialog) is dialog._apply_btn
    # Pressing W therefore applies every selected fix instead of cancelling.
    assert WASDInputFilter()._proceed(dialog) is True
    assert dialog.selected_indices() == [1, 2, 3]
