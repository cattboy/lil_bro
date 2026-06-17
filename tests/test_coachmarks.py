"""Tests for the first-run coachmark tour (src/gui/widgets/coachmarks.py).

Offscreen Qt (conftest.py) + qtbot. Covers:
- the Settings seen-flag round-trip (isolated QSettings scope, real key untouched),
- the Dashboard coachmark target helpers + readiness signal,
- the controller beat sequence (advance → dismiss marks seen),
- the C-reuse determinism guard: exactly one default button while a bubble shows,
  and the prior default restored on EVERY dismiss path,
- Esc / click-outside dismissal via the event filter,
- the always-on hover tooltips, and the Help/FAQ replay ignoring the seen-flag.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QPushButton

from src.gui.settings import Settings
from src.gui.widgets.coachmarks import (
    BEATS,
    _MAX_FIRST_RUN_ATTEMPTS,
    tooltip_html,
)
from src.gui.widgets.dashboard import Dashboard
from src.gui.windows.main_window import MainWindow


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def settings():
    """A Settings instance scoped to a throwaway QSettings key (real key untouched)."""
    s = Settings(organization="lil_bro_test", application="coachmarks")
    s._qs.clear()
    s._qs.sync()
    yield s
    s._qs.clear()
    s._qs.sync()


@pytest.fixture

def main(qtbot, settings):
    # Not shown on purpose: showEvent would auto-arm schedule_first_run and leak a
    # pending timer into other tests. mapTo()/findChildren() work without a show,
    # so the controller tests drive start()/dismiss() explicitly.
    win = MainWindow(settings=settings)
    qtbot.addWidget(win)
    return win


def _default_buttons(widget) -> list[QPushButton]:
    return [b for b in widget.findChildren(QPushButton) if b.isDefault()]


# ── Settings seen-flag ───────────────────────────────────────────────────────


def test_seen_flag_defaults_false_then_marks_true(settings):
    assert settings.has_seen_coachmarks() is False
    settings.mark_coachmarks_seen()
    assert settings.has_seen_coachmarks() is True


# ── Dashboard target helpers + readiness ─────────────────────────────────────


def test_dashboard_fix_target_none_until_a_card_shows(qtbot):
    dash = Dashboard()
    qtbot.addWidget(dash)
    # No set_*_data called yet → every fix card hidden.
    assert dash.coachmark_fix_target() is None
    # Fallback anchor is always present (the always-visible Mouse Polling card).
    assert dash.coachmark_fix_fallback() is dash._mouse_poll_card
    assert dash.is_coachmark_ready() is False


def test_dashboard_ready_after_monitor_wiring(qtbot):
    dash = Dashboard()
    qtbot.addWidget(dash)
    dash.set_monitor_data([])  # shows the "no displays" slot
    assert dash.is_coachmark_ready() is True


# ── Controller beat sequence ─────────────────────────────────────────────────


def test_start_anchors_first_beat_to_run_button(main):
    ctrl = main._coachmark_controller
    ctrl.start()
    assert ctrl._bubble is not None
    assert ctrl._index == 0
    assert ctrl._overlay._active is main._run_button


def test_runs_all_beats_then_marks_seen(main, settings):
    ctrl = main._coachmark_controller
    ctrl.start()
    n = len(ctrl._ordered_beats())
    assert n >= 2  # optimize + revert always resolve; fix falls back to the mouse poll card
    for _ in range(n):
        ctrl.next()
    assert ctrl._bubble is None
    assert ctrl._index < 0
    assert settings.has_seen_coachmarks() is True


def test_fix_beat_anchors_to_mouse_poll_card_when_no_actionable_fix(main):
    """Edge case: a fully-optimal PC has no actionable fix card. The 'fix' beat
    must anchor to the always-present Mouse Polling card, never a stat tile."""
    ctrl = main._coachmark_controller
    dash = main._dashboard
    assert dash.coachmark_fix_target() is None  # no visible Fix button
    ctrl._resolve_targets()
    assert ctrl._targets.get("fix") is dash._mouse_poll_card
    # Regression: the old fallback wrongly anchored to the CPU-usage stat tile.
    assert ctrl._targets.get("fix") is not dash._cards.get("cpu_usage")


# ── C-reuse determinism guard (the ★★★ test) ─────────────────────────────────


def test_exactly_one_default_button_while_showing(main):
    ctrl = main._coachmark_controller
    ctrl.start()
    defaults = _default_buttons(main)
    assert defaults == [ctrl._bubble.next_btn]


def test_prior_default_restored_on_dismiss(main):
    ctrl = main._coachmark_controller
    # Seed a pre-existing default button to prove it's restored afterwards.
    seed = main._run_button
    seed.setDefault(True)
    before = set(_default_buttons(main))

    ctrl.start()
    # The bubble's button is now the sole default (seed was cleared).
    assert _default_buttons(main) == [ctrl._bubble.next_btn]

    ctrl.dismiss()
    after = set(_default_buttons(main))
    assert after == before  # seed restored, bubble button gone


def test_default_restored_on_view_change_dismiss(main):
    ctrl = main._coachmark_controller
    ctrl.start()
    assert ctrl._bubble is not None
    # Leaving the Dashboard view dismisses the tour and restores defaults.
    main.show_output()
    assert ctrl._bubble is None
    assert _default_buttons(main) == []


# ── Esc / click-outside dismissal ────────────────────────────────────────────


def test_escape_dismisses(main):
    ctrl = main._coachmark_controller
    ctrl.start()
    ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape,
                   Qt.KeyboardModifier.NoModifier)
    consumed = ctrl.eventFilter(main, ev)
    assert consumed is True          # Esc is swallowed so the window shortcut won't fire
    assert ctrl._bubble is None


def test_s_key_dismisses(main):
    ctrl = main._coachmark_controller
    ctrl.start()
    ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_S,
                   Qt.KeyboardModifier.NoModifier)
    consumed = ctrl.eventFilter(main, ev)
    assert consumed is True          # S is swallowed (= Skip) so it won't hit the WASD stop path
    assert ctrl._bubble is None


def test_click_outside_bubble_dismisses_without_consuming(main):
    ctrl = main._coachmark_controller
    ctrl.start()
    ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0),
                     Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier)
    # The run button is outside the bubble → dismiss, but the event still
    # propagates (return False) so the underlying control still works.
    consumed = ctrl.eventFilter(main._run_button, ev)
    assert consumed is False
    assert ctrl._bubble is None


def test_click_on_bubble_does_not_dismiss(main):
    ctrl = main._coachmark_controller
    ctrl.start()
    ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0),
                     Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier)
    ctrl.eventFilter(ctrl._bubble.next_btn, ev)  # a click on the bubble's own button
    assert ctrl._bubble is not None


# ── Hover tooltips (single COACHMARK_COPY source) ────────────────────────────


def test_hover_tooltips_use_coachmark_copy(main):
    optimize = next(b for b in BEATS if b["name"] == "optimize")
    revert = next(b for b in BEATS if b["name"] == "revert")
    assert main._run_button.toolTip() == tooltip_html(optimize["title"], optimize["body"])
    assert main._revert_button.toolTip() == tooltip_html(revert["title"], revert["body"])


# ── First-run gating + Help/FAQ replay ───────────────────────────────────────


def test_schedule_first_run_respects_seen_flag(main, settings):
    ctrl = main._coachmark_controller
    settings.mark_coachmarks_seen()
    ctrl.schedule_first_run()
    assert ctrl._scheduled is False  # already seen → never schedules


def test_schedule_first_run_arms_when_unseen(main):
    ctrl = main._coachmark_controller
    ctrl.schedule_first_run()
    assert ctrl._scheduled is True


def test_start_first_run_shows_when_ready_past_retry_budget(main):
    ctrl = main._coachmark_controller
    ctrl._first_run_attempts = _MAX_FIRST_RUN_ATTEMPTS  # exhaust the poll budget
    ctrl._start_first_run()
    assert ctrl._bubble is not None  # shows regardless so the tour never stalls


def test_help_replay_ignores_seen_flag(main, settings):
    settings.mark_coachmarks_seen()
    main._on_help_requested()  # H / sidebar Help
    ctrl = main._coachmark_controller
    assert ctrl._bubble is not None
    assert ctrl._index == 0
