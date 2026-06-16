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


def test_long_list_clamps_height_and_keeps_footer_visible(qtbot):
    """Many fixes must not push the Apply footer off-screen.

    Future pipeline checks can grow the proposal list unboundedly. The dialog
    clamps its height to the available screen and scrolls the card body, so the
    footer (Apply/Skip) stays on-screen no matter how many cards appear.
    """
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QScrollArea

    dialog = BatchSelectionDialog(_proposals(40))
    qtbot.addWidget(dialog)
    dialog.show()
    QTest.qWait(10)

    avail = QGuiApplication.primaryScreen().availableGeometry().height()
    # The dialog never grows past the screen, so its footer stays reachable.
    assert dialog.height() <= avail
    assert dialog._apply_btn.isVisible()
    # The card body is wrapped in a scroll area that absorbs the overflow.
    assert dialog.findChild(QScrollArea) is not None


def test_short_list_fits_without_scrolling(qtbot):
    """A 1-2 card list must render in full -- no scrollbar, no compression.

    Word-wrapped descriptions made the dialog open shorter than the cards needed
    once laid out at the fixed two-column width, forcing a needless scrollbar and
    squashing the cards. The dialog now sizes to the cards' true wrapped height,
    so the body fits the viewport and the vertical scrollbar has no range.
    """
    proposals = [
        {"finding": f"c{i}", "title": f"Title {i}",
         "description": "A deliberately long explanation that wraps across "
                        "several lines so the card needs real vertical space. " * 2,
         "severity": "HIGH", "can_auto_fix": True}
        for i in range(2)
    ]
    dialog = BatchSelectionDialog(proposals)
    qtbot.addWidget(dialog)
    dialog.show()
    QTest.qWait(20)

    # Cards fit: the body never overflows the viewport, so there is no scroll
    # range (and the ScrollHintArrow stays hidden off the back of this).
    assert dialog._scroll.verticalScrollBar().maximum() == 0


def test_single_fix_never_scrolls(qtbot):
    """A lone fix must NEVER show a scrollbar, however long its description.

    Regression for the single-item dialog opening too short. The scroll area's
    ``sizeHint`` measured the body's wrapped height at ``viewport().width()``,
    which before show reports a wide default (~640px, not 0) instead of the
    dialog's fixed 540px content width. Measured too wide, the text wrapped to
    fewer lines and under-reported its height, so the dialog opened short and a
    needless scrollbar appeared once laid out at the real width. The single
    column (540px) is its own code path -- ``test_short_list_fits_without_scrolling``
    only exercises the two-column (820px) path -- so it needs its own guard.
    """
    proposals = [
        {"finding": "power_plan", "title": "Switch power plan to High Performance",
         "description": "Your power plan is throttling your CPU. High Performance "
                        "keeps it at peak clock speed instead of scaling down "
                        "between tasks. All changes revertable and backed up, "
                        "lil_bro can roll them back.",
         "severity": "HIGH", "tag": "power plan", "can_auto_fix": True}
    ]
    dialog = BatchSelectionDialog(proposals)
    qtbot.addWidget(dialog)
    dialog.show()
    QTest.qWait(20)

    # The lone card fits the viewport: no scroll range, and the attention
    # ScrollHintArrow stays hidden because there is nothing below the fold.
    assert dialog._scroll.verticalScrollBar().maximum() == 0
    assert dialog._scroll_hint.isVisible() is False


def test_multi_row_lists_never_scroll(qtbot):
    """3-4 fixes (the first two-column, multi-row cases) must not scroll either.

    ``QGridLayout.heightForWidth`` under-reports the height of a multi-row,
    two-column card grid, so the dialog opened ~28px too short and showed a
    needless scrollbar for 3-4 fixes even though the cards fit -- the case the
    user hit in a real optimization run. ``_fit_to_content`` grows the dialog to
    swallow the real measured overflow (clamped to the screen). n=1 (single row,
    one column) and n=2 (single row, two columns) were already fine; this guards
    the first and second *multi-row* counts, which exercise the broken grid path.
    """
    long_desc = ("Your power plan is throttling your CPU. High Performance keeps "
                 "it at peak clock speed instead of scaling down between tasks. "
                 "All changes are revertable and backed up.")
    for n in (3, 4):
        proposals = [
            {"finding": f"c{i}", "title": f"Switch fix {i} to optimal setting",
             "description": long_desc, "severity": "HIGH",
             "tag": "power plan", "can_auto_fix": True}
            for i in range(n)
        ]
        dialog = BatchSelectionDialog(proposals)
        qtbot.addWidget(dialog)
        dialog.show()
        QTest.qWait(20)

        vmax = dialog._scroll.verticalScrollBar().maximum()
        assert vmax == 0, f"{n} fixes must fit without a scrollbar, got max={vmax}"
        assert dialog._scroll_hint.isVisible() is False
