"""Tests for the in-flight "Reverting…" busy state on the Revert page button.

Mirrors ``test_card_applying.py``: the Revert page's "Revert All Changes" button
gets the same shared ``set_apply_busy`` loading treatment the dashboard cards
use, driven by ``PipelineController.start_revert``'s worker lifecycle. The busy
cue is button-only (the status bar carries the textual progress). Offscreen Qt
(conftest.py) + qtbot.
"""
from __future__ import annotations

from src.gui.widgets.revert_view import RevertView

_IDLE_LABEL = "↩  Revert All Changes (R)"


def test_set_reverting_round_trips_button(qtbot):
    view = RevertView()
    qtbot.addWidget(view)
    assert view._revert_btn.text() == _IDLE_LABEL
    assert view._revert_btn.isEnabled()

    view.set_reverting(True)
    assert view._revert_btn.text() == "Reverting…"
    assert not view._revert_btn.isEnabled()

    view.set_reverting(False)
    assert view._revert_btn.text() == _IDLE_LABEL
    assert view._revert_btn.isEnabled()


def test_set_reverting_round_trips_from_already_disabled(qtbot):
    """``set_flow_controls(False)`` disables the button (via ``set_revert_enabled``)
    BEFORE ``set_reverting(True)`` runs. The idle label must still round-trip
    from that already-disabled state -- ``set_apply_busy`` captures the current
    text, which is still the idle label at that point."""
    view = RevertView()
    qtbot.addWidget(view)
    view.set_revert_enabled(False)  # mimic the set_flow_controls(False) ordering

    view.set_reverting(True)
    assert view._revert_btn.text() == "Reverting…"

    view.set_reverting(False)
    assert view._revert_btn.text() == _IDLE_LABEL
    assert view._revert_btn.isEnabled()


def test_set_reverting_only_touches_revert_button(qtbot):
    """The busy cue is scoped to the revert action button -- the System Restore
    button and the no-fixes placeholder must be untouched."""
    view = RevertView()
    qtbot.addWidget(view)
    restore_text = view._restore_btn.text()
    restore_enabled = view._restore_btn.isEnabled()
    placeholder_text = view._no_fixes_lbl.text()

    view.set_reverting(True)
    assert view._restore_btn.text() == restore_text
    assert view._restore_btn.isEnabled() == restore_enabled
    assert view._no_fixes_lbl.text() == placeholder_text
